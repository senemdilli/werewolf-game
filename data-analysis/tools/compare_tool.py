"""compare_data — the Data Comparison / Evaluation tool.

Answers "how do two slices of the dataset differ, and how strongly do they
agree?" for any pair of FilterSpecs; with a single spec it evaluates that
slice alone. All numeric analysis questions from the spec are calls to this
tool with different filters.
"""

from typing import Any, ClassVar, Literal

import numpy as np
import pandas as pd
from scipy import stats

from contracts.tool_output import ToolOutput
from data.filters import FilterSpec
from tools.base_tool import BaseTool
from tools.slicing import (
    MIN_TEST_N,
    describe_slice,
    differing_fields,
    explain_empty_slice,
    match_keys_for,
    matchable,
    matched_cells,
    slice_df,
)


class CompareDataTool(BaseTool):
    name: ClassVar[str] = "compare_data"
    description: ClassVar[str] = (
        "Compare two slices of the trust-annotation table (filters_a vs "
        "filters_b) or evaluate a single slice (filters_a only). Reports "
        "per-slice stats (n, mean, distribution, extremeness index), the "
        "delta between slices, agreement (Spearman, weighted kappa) on "
        "matched cells, and significance tests. delta is always slice B "
        "minus slice A on normalized [0,1] scores. Use group_by to break "
        "the comparison down by a column, e.g. ['trust_type'] or "
        "['phase_idx'] or ['room_code']."
    )

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__()
        self._df = df

    def run(
        self,
        filters_a: FilterSpec,
        filters_b: FilterSpec | None = None,
        mode: Literal["auto", "matched", "independent"] = "auto",
        group_by: list[str] | None = None,
        metric: Literal["score", "confidence"] = "score",
        correlate: bool = False,
    ) -> ToolOutput:
        
        self.logger.debug("Running CompareDataTool with filters_a=%s, filters_b=%s, mode=%s, group_by=%s, metric=%s, correlate=%s",
            filters_a,
            filters_b,
            mode,
            group_by,
            metric,
            correlate,
        )

        value = "score_norm" if metric == "score" else "confidence_norm"

        rows_a = slice_df(self._df, filters_a)
        if rows_a.empty:
            return self._fail("filters_a: " + explain_empty_slice(self._df, filters_a))

        data: dict[str, Any] = {"slice_a": describe_slice(rows_a)}
        warnings: list[str] = []

        rows_b = None
        if filters_b is not None:
            rows_b = slice_df(self._df, filters_b)
            if rows_b.empty:
                return self._fail("filters_b: " + explain_empty_slice(self._df, filters_b))
            data["slice_b"] = describe_slice(rows_b)
            data["comparison"] = self._compare(
                rows_a, rows_b, filters_a, filters_b, mode, value, warnings
            )

        if group_by:
            missing = [c for c in group_by if c not in self._df.columns]
            if missing:
                return self._fail(f"unknown group_by column(s): {missing}")
            data["groups"] = self._grouped(
                rows_a, rows_b, filters_a, filters_b, mode, group_by, value, warnings
            )

        if correlate:
            data["extremity_confidence_correlation"] = {
                "slice_a": _extremity_confidence(rows_a),
                **({"slice_b": _extremity_confidence(rows_b)} if rows_b is not None else {}),
            }

        metadata: dict[str, Any] = {"n_rows_a": len(rows_a)}
        if rows_b is not None:
            metadata["n_rows_b"] = len(rows_b)
        if warnings:
            metadata["warnings"] = warnings
        return ToolOutput(success=True, source=self.name, data=data, metadata=metadata)

    # -- comparison ---------------------------------------------------------

    def _compare(
        self,
        rows_a: pd.DataFrame,
        rows_b: pd.DataFrame,
        spec_a: FilterSpec,
        spec_b: FilterSpec,
        mode: str,
        value: str,
        warnings: list[str],
    ) -> dict[str, Any]:
        if mode == "auto":
            mode = "matched" if matchable(spec_a, spec_b) else "independent"
        elif mode == "matched" and not matchable(spec_a, spec_b):
            warnings.append(
                "matched mode requested but the specs differ on row-identity "
                f"fields {differing_fields(spec_a, spec_b)}; results pair cells "
                "on the remaining keys"
            )

        out: dict[str, Any] = {
            "mode": mode,
            "differing_filter_fields": differing_fields(spec_a, spec_b),
            "delta_of_means": round(
                float(rows_b[value].mean() - rows_a[value].mean()), 4
            ),
        }

        if mode == "matched":
            keys = match_keys_for(spec_a, spec_b)
            cells = matched_cells(rows_a, rows_b, keys, value)
            out["matched"] = self._matched_stats(cells, rows_a, rows_b, warnings)
        else:
            out["independent"] = self._independent_stats(rows_a, rows_b, value, warnings)
        return out

    def _matched_stats(
        self,
        cells: pd.DataFrame,
        rows_a: pd.DataFrame,
        rows_b: pd.DataFrame,
        warnings: list[str],
    ) -> dict[str, Any]:
        n = len(cells)
        if n == 0:
            warnings.append("no matched cells — the two slices never rate the same thing")
            return {"n_cells": 0}
        delta = cells["b"] - cells["a"]
        out: dict[str, Any] = {
            "n_cells": n,
            "mean_signed_delta": round(float(delta.mean()), 4),
            "mean_abs_delta": round(float(delta.abs().mean()), 4),
        }
        if n >= MIN_TEST_N:
            out["spearman"] = round(float(cells["a"].corr(cells["b"], method="spearman")), 4)
            if not np.allclose(delta, 0):
                out["wilcoxon_p"] = round(float(stats.wilcoxon(cells["a"], cells["b"]).pvalue), 4)
            kappa = _weighted_kappa(rows_a, rows_b, cells)
            if kappa is not None:
                out["weighted_kappa"] = kappa
        else:
            warnings.append(f"only {n} matched cells — agreement/significance skipped")
        return out

    def _independent_stats(
        self,
        rows_a: pd.DataFrame,
        rows_b: pd.DataFrame,
        value: str,
        warnings: list[str],
    ) -> dict[str, Any]:
        a, b = rows_a[value].dropna(), rows_b[value].dropna()
        if len(a) < MIN_TEST_N or len(b) < MIN_TEST_N:
            warnings.append("slice too small for significance tests")
            return {}
        return {
            "mann_whitney_p": round(float(stats.mannwhitneyu(a, b).pvalue), 4),
            "ks_p": round(float(stats.ks_2samp(a, b).pvalue), 4),
        }

    def _grouped(
        self,
        rows_a: pd.DataFrame,
        rows_b: pd.DataFrame | None,
        spec_a: FilterSpec,
        spec_b: FilterSpec | None,
        mode: str,
        group_by: list[str],
        value: str,
        warnings: list[str],
    ) -> dict[str, Any]:
        """Compact per-group breakdown: n, mean, and (with two slices) delta."""
        groups: dict[str, Any] = {}
        keys_b = rows_b if rows_b is not None else pd.DataFrame(columns=group_by)
        group_values = (
            pd.concat([rows_a[group_by], keys_b[group_by]])
            .drop_duplicates()
            .itertuples(index=False)
        )
        for key in group_values:
            label = "|".join(str(v) for v in key)
            in_a = rows_a[(rows_a[group_by] == key).all(axis=1)]
            entry: dict[str, Any] = {
                "n_a": int(len(in_a)),
                "mean_a": round(float(in_a[value].mean()), 4) if len(in_a) else None,
            }
            if rows_b is not None:
                in_b = rows_b[(rows_b[group_by] == key).all(axis=1)]
                entry["n_b"] = int(len(in_b))
                entry["mean_b"] = round(float(in_b[value].mean()), 4) if len(in_b) else None
                if len(in_a) and len(in_b):
                    entry["delta"] = round(entry["mean_b"] - entry["mean_a"], 4)
                    if matchable(spec_a, spec_b):
                        cells = matched_cells(in_a, in_b, match_keys_for(spec_a, spec_b), value)
                        if len(cells):
                            d = cells["b"] - cells["a"]
                            entry["matched_n"] = int(len(cells))
                            entry["matched_delta"] = round(float(d.mean()), 4)
            groups[label] = entry
        return dict(sorted(groups.items()))

    def _fail(self, error: str) -> ToolOutput:
        return ToolOutput(success=False, source=self.name, error=error)


def _extremity_confidence(rows: pd.DataFrame) -> dict[str, Any]:
    """Spearman between score extremity (|norm - 0.5|) and confidence.

    The hypothesis: humans are more confident when they give extreme scores;
    LLM confidence may not track extremity at all.
    """
    have = rows.dropna(subset=["score_norm", "confidence_norm"])
    if len(have) < MIN_TEST_N:
        return {"n": int(len(have)), "note": "too few rows with both score and confidence"}
    extremity = (have["score_norm"] - 0.5).abs()
    res = stats.spearmanr(extremity, have["confidence_norm"])
    return {
        "n": int(len(have)),
        "spearman": round(float(res.statistic), 4),
        "p": round(float(res.pvalue), 4),
    }


def _weighted_kappa(
    rows_a: pd.DataFrame, rows_b: pd.DataFrame, cells: pd.DataFrame
) -> float | None:
    """Quadratic-weighted Cohen's kappa on raw scores; needs one shared scale.

    Standard agreement metric for ordinal annotations: 1 = perfect agreement,
    0 = chance-level, < 0 = worse than chance.
    """
    scales = set(rows_a["scale"].dropna().unique()) | set(rows_b["scale"].dropna().unique())
    if scales != {"7pt"}:
        return None
    # cells hold normalized means; map back to the 1-7 grid and round to ints
    a = (cells["a"] * 6 + 1).round().astype(int).to_numpy()
    b = (cells["b"] * 6 + 1).round().astype(int).to_numpy()
    categories = np.arange(1, 8)
    n_cat = len(categories)
    observed = np.zeros((n_cat, n_cat))
    for ai, bi in zip(a, b):
        observed[ai - 1, bi - 1] += 1
    observed /= observed.sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0))
    weights = np.square(categories[:, None] - categories[None, :]) / (n_cat - 1) ** 2
    denom = (weights * expected).sum()
    if denom == 0:
        return None
    return round(float(1 - (weights * observed).sum() / denom), 4)
