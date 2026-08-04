"""plot — render a filtered slice of the trust table as a PNG.

Returns the file path AND the aggregated numbers behind the figure: the
orchestrator LLM never sees the image, so the returned table is what it
reasons and writes captions from.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar, Literal

import matplotlib
from pydantic import BaseModel

matplotlib.use("Agg")  # file output only, no display needed
import matplotlib.pyplot as plt
import pandas as pd

from pydantic import BaseModel

from contracts.tool_output import ToolOutput
from data.filters import FilterSpec
from tools.base_tool import BaseTool
from tools.slicing import explain_empty_slice, slice_df

PlotKind = Literal["line_per_phase", "line_per_game", "histogram", "box", "scatter", "heatmap"]

_ROLE_ABBREVIATIONS = {"WEREWOLF": "W", "VILLAGER": "V", "SEER": "S", "WITCH": "Wi"}


def _likert_y_axis(ax: plt.Axes) -> None:
    """Tick the normalized-trust y axis with the likert level names.

    Ticks sit at the 7 level positions; matplotlib hides the ones outside the
    data range, so a plot spanning 0.3-0.6 shows only the relevant levels.
    """
    ax.set_yticks([k / 6 for k in range(7)], labels=_TRUST_TICK_LABELS, fontsize=8)
    ax.set_ylabel("trust")


def _describe_filters(spec: FilterSpec) -> str:
    """Compact 'filters: sources=llm, room_codes=5NOHGS' line for the chart.

    Only non-default fields appear, so an unfiltered plot says so explicitly
    instead of listing 20 Nones.
    """
    active = spec.model_dump(exclude_defaults=True, exclude_none=True)
    if "trust_types" not in active:
        active_copy = dict(active)
        active_copy["trust_types"] = ["all (align+info+cons combined)"]
        parts = [
            f"{field}={','.join(map(str, value)) if isinstance(value, list) else value}"
            for field, value in active_copy.items()
        ]
        return "filters: " + ", ".join(parts)
    if not active:
        return "filters: none (all rows)"
    parts = [
        f"{field}={','.join(map(str, value)) if isinstance(value, list) else value}"
        for field, value in active.items()
    ]
    return "filters: " + ", ".join(parts)

# Colorbar anchors for normalized trust: the 7 likert levels sit at (k-1)/6.
_TRUST_TICK_LABELS = [
    "VERY_LOW_TRUST",
    "LOW_TRUST",
    "SLIGHTLY_LOW_TRUST",
    "NEUTRAL",
    "SLIGHTLY_HIGH_TRUST",
    "HIGH_TRUST",
    "VERY_HIGH_TRUST",
]

class PlotInput(BaseModel):
    filters: FilterSpec
    kind: PlotKind
    hue: str = "source"
    agg: Literal["mean", "median"] = "mean"
    use_raw: bool = False
    title: str | None = None
    filename: str | None = None
    full_y_scale: bool | None = None

class PlotTool(BaseTool):
    name: ClassVar[str] = "plot"
    description: ClassVar[str] = (
        "Generate a PNG visualization from a filtered subset of the trust table and return the file path and the aggregated data values used in the chart. "
        "Supported chart types:"
        "- line_per_phase: trust development across phases of a single game, with separate lines for each hue category."
        "- line_per_game: trust development across games in chronological order."
        "- histogram: distribution of raw trust scores (1-7) per hue category to show score extremity."
        "- box: trust score distribution and spread per hue category."
        "- scatter: relationship between trust score extremity and confidence."
        "- heatmap: observer-to-target trust matrix for a single game."
        ""
        "The hue dimension controls how values are grouped. It defaults to \"source\" (e.g., human vs LLM comparison). Use another table column (such as \"trust_type\") to define a different grouping."
    )

    def __init__(self, df: pd.DataFrame, plots_dir: str | Path = "../results/data-analysis/plots", default_full_y_scale: bool = False) -> None:
        super().__init__()
        self._df = df
        self._plots_dir = Path(plots_dir)
        self._default_full_y_scale = default_full_y_scale
        self.input_schema = PlotInput

    def run(
        self,
        filters: FilterSpec,
        kind: PlotKind,
        hue: str = "source",
        agg: Literal["mean", "median"] = "mean",
        use_raw: bool = False,
        title: str | None = None,
        filename: str | None = None,
        full_y_scale: bool | None = None,
    ) -> ToolOutput:
        self.logger.debug("Running PlotTool with filters=%s, kind=%s, hue=%s, agg=%s, use_raw=%s, title=%s, filename=%s, full_y_scale=%s",
            filters,
            kind,
            hue,
            agg,
            use_raw,
            title,
            filename,
            full_y_scale,
        )

        rows = slice_df(self._df, filters)
        if rows.empty:
            return self._fail(explain_empty_slice(self._df, filters))
        if hue not in rows.columns:
            return self._fail(f"unknown hue column: {hue!r}")

        value = "score_raw" if use_raw else "score_norm"
        if use_raw and rows["scale"].nunique() > 1:
            return self._fail(
                "use_raw=True but the slice mixes scales "
                f"({sorted(rows['scale'].dropna().unique())}); filter to one "
                "scale or use normalized scores"
            )
        if kind in ("histogram", "heatmap") and rows["scale"].nunique() > 1:
            return self._fail("this plot kind needs a single scale; filter the slice down")

        fig, ax = plt.subplots(figsize=(8, 5))
        try:
            table = self._render(kind, rows, ax, hue, value, agg)
        except ValueError as exc:
            plt.close(fig)
            return self._fail(str(exc))

        ax.set_title(title or self._default_title(kind, rows))
        
        # Enforce standard scales only if full_y_scale is enabled (or for scatter which always needs it)
        actual_full_y = self._default_full_y_scale if full_y_scale is None else full_y_scale
        if kind in ("line_per_phase", "line_per_game", "box"):
            if actual_full_y:
                if use_raw:
                    ax.set_ylim(0.5, 7.5)  # Padding for 1 to 7 scale
                else:
                    ax.set_ylim(-0.05, 1.05)  # Padding for 0 to 1 scale
        elif kind == "scatter":
            ax.set_xlim(-0.05, 1.05)
            ax.set_ylim(-0.05, 1.05)

        fig.tight_layout()
        filters_line = _describe_filters(filters)
        fig.text(0.99, 0.005, filters_line, ha="right", va="bottom", fontsize=7, color="dimgray")
        path = self._save(fig, kind, filters, filename)
        plt.close(fig)

        caption = f"{kind} of {value} ({agg}) over {len(rows)} rows, split by {hue} [{filters_line}]"
        return ToolOutput(
            success=True,
            source=self.name,
            data={"path": str(path), "caption": caption, "table": table},
            metadata={"n_rows": len(rows), "games": sorted(rows["room_code"].dropna().unique())},
        )

    # -- renderers ----------------------------------------------------------

    def _render(
        self, kind: PlotKind, rows: pd.DataFrame, ax: plt.Axes, hue: str, value: str, agg: str
    ) -> dict[str, Any]:
        if kind == "line_per_phase":
            if rows["room_code"].nunique() > 1:
                raise ValueError(
                    "line_per_phase needs a single game; add room_codes to the filters "
                    f"(slice has {sorted(rows['room_code'].dropna().unique())})"
                )
            pivoted = rows.pivot_table(index="phase_idx", columns=hue, values=value, aggfunc=agg)
            pivoted.plot(ax=ax, marker="o")
            ax.set_xlabel("phase")
            ax.set_ylabel(value)
            if value == "score_norm":
                _likert_y_axis(ax)
            return _table(pivoted)

        if kind == "line_per_game":
            order = rows.groupby("room_code")["exported_at"].min().sort_values().index
            pivoted = rows.pivot_table(index="room_code", columns=hue, values=value, aggfunc=agg)
            pivoted = pivoted.reindex(order)
            pivoted.plot(ax=ax, marker="o")
            ax.set_xlabel("game (chronological)")
            ax.set_ylabel(value)
            if value == "score_norm":
                _likert_y_axis(ax)
            ax.tick_params(axis="x", rotation=45)
            return _table(pivoted)

        if kind == "histogram":
            counts = rows.groupby([hue, "score_raw"]).size().unstack(hue, fill_value=0)
            counts.plot.bar(ax=ax)
            ax.set_xlabel("raw score")
            ax.set_ylabel("count")
            if rows["scale"].iloc[0] == "7pt":  # single scale guaranteed by guard above
                ax.set_xticklabels(
                    [_TRUST_TICK_LABELS[int(v) - 1] for v in counts.index],
                    rotation=30, ha="right", fontsize=8,
                )
                ax.set_xlabel("trust level")
            return _table(counts)

        if kind == "box":
            groups = [(str(k), g[value].dropna()) for k, g in rows.groupby(hue)]
            ax.boxplot([g for _, g in groups], tick_labels=[k for k, _ in groups])
            ax.set_ylabel(value)
            if value == "score_norm":
                _likert_y_axis(ax)
            summary = rows.groupby(hue)[value].describe()[["count", "mean", "50%", "std"]]
            return _table(summary)

        if kind == "scatter":
            have = rows.dropna(subset=["score_norm", "confidence_norm"])
            if have.empty:
                raise ValueError("no rows with both score and confidence")
            for key, group in have.groupby(hue):
                extremity = (group["score_norm"] - 0.5).abs() * 2
                # jitter so overlapping ordinal points stay visible
                ax.scatter(
                    extremity + _jitter(len(group)),
                    group["confidence_norm"] + _jitter(len(group)),
                    label=str(key), alpha=0.5, s=18,
                )
            ax.set_xlabel("score extremity (0=midpoint, 1=endpoint)")
            ax.set_ylabel("confidence (normalized)")
            ax.legend()
            summary = have.groupby(hue).apply(
                lambda g: pd.Series({
                    "n": len(g),
                    "extremity_mean": ((g["score_norm"] - 0.5).abs() * 2).mean(),
                    "confidence_mean": g["confidence_norm"].mean(),
                }),
                include_groups=False,
            )
            return _table(summary)

        if kind == "heatmap":
            if rows["room_code"].nunique() > 1:
                raise ValueError("heatmap needs a single game; add room_codes to the filters")
            pivoted = rows.pivot_table(index="observer", columns="target", values=value, aggfunc=agg)

            # name -> "name (W)" using whichever role column knows the player
            roles = dict(rows.groupby("target")["target_role"].first().dropna())
            roles |= dict(rows.groupby("observer")["observer_role"].first().dropna())

            def _with_role(name: str) -> str:
                role = roles.get(name)
                if role is None:
                    return str(name)
                return f"{name} ({_ROLE_ABBREVIATIONS.get(role, role[0])})"

            im = ax.imshow(pivoted.to_numpy(), cmap="RdYlGn", vmin=0, vmax=1 if value == "score_norm" else None)
            ax.set_xticks(range(len(pivoted.columns)), [_with_role(c) for c in pivoted.columns], rotation=45)
            ax.set_yticks(range(len(pivoted.index)), [_with_role(i) for i in pivoted.index])
            ax.set_xlabel("target")
            ax.set_ylabel("observer")
            cbar = ax.figure.colorbar(im, ax=ax, label=value)
            if value == "score_norm":
                cbar.set_ticks([k / 6 for k in range(7)], labels=_TRUST_TICK_LABELS)
            return _table(pivoted)

        raise ValueError(f"unknown plot kind: {kind!r}")

    # -- output -------------------------------------------------------------

    def _save(self, fig: plt.Figure, kind: str, filters: FilterSpec, filename: str | None) -> Path:
        self._plots_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            fingerprint = hashlib.sha256(
                json.dumps({"kind": kind, "filters": filters.model_dump()}, default=str).encode()
            ).hexdigest()[:10]
            filename = f"{kind}-{fingerprint}.png"
        if not filename.endswith(".png"):
            filename += ".png"
        path = self._plots_dir / filename
        fig.savefig(path, dpi=150)
        return path

    def _default_title(self, kind: str, rows: pd.DataFrame) -> str:
        games = rows["room_code"].dropna().unique()
        where = games[0] if len(games) == 1 else f"{len(games)} games"
        return f"{kind} — {where}"

    def _fail(self, error: str) -> ToolOutput:
        return ToolOutput(success=False, source=self.name, error=error)


def _table(frame: pd.DataFrame) -> dict[str, Any]:
    """Round and dict-ify the aggregate behind a figure for the orchestrator."""
    return json.loads(frame.round(4).to_json(orient="index"))


def _jitter(n: int) -> pd.Series:
    import numpy as np

    return pd.Series(np.random.default_rng(0).uniform(-0.015, 0.015, n)).values
