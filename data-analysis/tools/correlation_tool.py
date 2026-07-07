"""correlation_tool — extremity comparison and extremity/confidence correlation.

Answers two related spec questions about *how* two slices of the trust table
label, not just what they score on average:

- "Compare how extreme the labelling of the LLMs are compared to the humans"
  (humans cluster near the midpoint; LLMs often hit the endpoints).
- "Find correlation between likert value and confidence, human vs LLM"
  (humans are confident when they commit to an extreme score; LLM confidence
  may not track how extreme its own score is).

`extremity` is `|score_norm - 0.5| * 2`, in [0, 1]: 0 = scale midpoint,
1 = either endpoint. Using the fold-to-endpoint distance (rather than the raw
score) is what makes "1/7 and 7/7 are both extreme" comparable and
correlatable in one number, and keeps it meaningful across the 1-7 and
1-100 scales at once.

Built on `tools/slicing.py`'s matched-cell join (same `MATCH_KEYS`,
`matchable`/`differing_fields` soundness check as `compare_data`), just
matching on `extremity` instead of raw `score_norm`.
"""

from typing import Any, ClassVar

import pandas as pd
from scipy import stats

from contracts.tool_output import ToolOutput
from data.filters import FilterSpec
from tools.base_tool import BaseTool
from tools.slicing import MIN_TEST_N, differing_fields, matchable, matched_cells, slice_df


class CorrelationTool(BaseTool):
    name: ClassVar[str] = "correlation_tool"
    description: ClassVar[str] = (
        "Compare labelling extremity between two slices (filters_a vs "
        "filters_b) of the trust table, and correlate score extremity with "
        "confidence within each slice. extremity = |score_norm - 0.5| * 2 "
        "(0 = midpoint, 1 = either endpoint), so it captures 'humans avoid "
        "1/7 and 7/7, LLMs go there often' as one number, and lets 7/7-low-"
        "confidence vs 7/7-high-confidence show up as a real correlation. "
        "Reports per-slice extremity stats + extremity/confidence Spearman, "
        "the delta in extremity between slices (independent Mann-Whitney U "
        "and, on matched game/observer/target/phase/trust_type cells, a "
        "paired Wilcoxon), and an optional group_by breakdown."
    )

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__()
        self._df = df

    def run(
        self,
        filters_a: FilterSpec,
        filters_b: FilterSpec,
        group_by: list[str] | None = None,
    ) -> ToolOutput:
        a = slice_df(self._df, filters_a)
        if a.empty:
            return self._fail("filters_a matches no rows")
        b = slice_df(self._df, filters_b)
        if b.empty:
            return self._fail("filters_b matches no rows")

        group_by = group_by or []
        unknown = [c for c in group_by if c not in self._df.columns]
        if unknown:
            return self._fail(f"unknown group_by column(s): {unknown}")

        warnings: list[str] = []
        data: dict[str, Any] = {
            "slice_a": self._describe(a),
            "slice_b": self._describe(b),
            "comparison": self._compare(a, b, filters_a, filters_b, warnings),
        }
        if group_by:
            data["groups"] = self._grouped(a, b, group_by)

        metadata: dict[str, Any] = {"n_rows_a": len(a), "n_rows_b": len(b)}
        if warnings:
            metadata["warnings"] = warnings
        return ToolOutput(success=True, source=self.name, data=data, metadata=metadata)

    # -- per-slice description ----------------------------------------------

    def _describe(self, rows: pd.DataFrame) -> dict[str, Any]:
        extremity = _extremity(rows)
        out: dict[str, Any] = {
            "n": int(len(rows)),
            "mean_extremity": round(float(extremity.mean()), 4),
            # score_norm hits exactly 0 or 1 only at the scale's endpoints,
            # regardless of whether the row is on the 7pt or 1-100 scale.
            "frac_at_extreme": round(float(rows["score_norm"].isin([0.0, 1.0]).mean()), 4),
        }
        have = rows.dropna(subset=["score_norm", "confidence_norm"])
        if len(have) >= MIN_TEST_N:
            res = stats.spearmanr(_extremity(have), have["confidence_norm"])
            out["extremity_confidence_spearman"] = round(float(res.statistic), 4)
            out["extremity_confidence_p"] = round(float(res.pvalue), 4)
            out["extremity_confidence_n"] = int(len(have))
        else:
            out["extremity_confidence_spearman"] = None
        return out

    # -- two-slice comparison -------------------------------------------------

    def _compare(
        self,
        a: pd.DataFrame,
        b: pd.DataFrame,
        filters_a: FilterSpec,
        filters_b: FilterSpec,
        warnings: list[str],
    ) -> dict[str, Any]:
        ext_a, ext_b = _extremity(a), _extremity(b)
        out: dict[str, Any] = {
            "extremity_delta_of_means": round(float(ext_b.mean() - ext_a.mean()), 4),
        }

        if len(ext_a) >= MIN_TEST_N and len(ext_b) >= MIN_TEST_N:
            out["independent"] = {
                "mann_whitney_p": round(float(stats.mannwhitneyu(ext_a, ext_b).pvalue), 4),
            }
        else:
            warnings.append("too few rows for the independent extremity test")

        if not matchable(filters_a, filters_b):
            warnings.append(
                "matched mode may not be meaningful — filters_a/filters_b differ on "
                f"{differing_fields(filters_a, filters_b)}; results pair cells on the "
                "remaining identity columns"
            )

        cells = self._matched_cells(a, b)
        if cells.empty:
            warnings.append("no matched cells — the two slices never rate the same thing")
            out["matched"] = {"n_cells": 0}
        else:
            out["matched"] = self._matched_stats(cells)
        return out

    def _matched_stats(self, cells: pd.DataFrame) -> dict[str, Any]:
        delta = cells["b"] - cells["a"]
        out: dict[str, Any] = {
            "n_cells": len(cells),
            "mean_signed_delta": round(float(delta.mean()), 4),
            "mean_abs_delta": round(float(delta.abs().mean()), 4),
        }
        if len(cells) >= MIN_TEST_N and not (delta == 0).all():
            out["wilcoxon_p"] = round(float(stats.wilcoxon(cells["a"], cells["b"]).pvalue), 4)
        return out

    def _matched_cells(self, a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
        return matched_cells(a.assign(extremity=_extremity(a)), b.assign(extremity=_extremity(b)), value="extremity")

    # -- group_by breakdown ---------------------------------------------------

    def _grouped(self, a: pd.DataFrame, b: pd.DataFrame, group_by: list[str]) -> dict[str, Any]:
        groups: dict[str, Any] = {}
        keys = pd.concat([a[group_by], b[group_by]]).drop_duplicates().itertuples(index=False)
        for key in keys:
            label = "|".join(str(v) for v in key)
            in_a = a[(a[group_by] == key).all(axis=1)]
            in_b = b[(b[group_by] == key).all(axis=1)]
            entry: dict[str, Any] = {"n_a": int(len(in_a)), "n_b": int(len(in_b))}
            if len(in_a):
                entry["mean_extremity_a"] = round(float(_extremity(in_a).mean()), 4)
            if len(in_b):
                entry["mean_extremity_b"] = round(float(_extremity(in_b).mean()), 4)
            if len(in_a) and len(in_b):
                entry["extremity_delta"] = round(entry["mean_extremity_b"] - entry["mean_extremity_a"], 4)
                cells = self._matched_cells(in_a, in_b)
                if len(cells):
                    d = cells["b"] - cells["a"]
                    entry["matched_n"] = int(len(cells))
                    entry["matched_delta"] = round(float(d.mean()), 4)
            groups[label] = entry
        return dict(sorted(groups.items()))

    def _fail(self, error: str) -> ToolOutput:
        return ToolOutput(success=False, source=self.name, error=error)


def _extremity(rows: pd.DataFrame) -> pd.Series:
    return (rows["score_norm"] - 0.5).abs() * 2
