"""Shared slice/describe/match helpers used by the analysis tools.

A "slice" is the subset of the unified table selected by one FilterSpec.
`compare_data` and `plot` (and the standalone scripts) all build on these three
operations so the statistics are computed in exactly one place.
"""

import pandas as pd

from data.filters import FilterSpec, apply_filters

# Columns that identify one annotation cell. Two rows from different sources
# with equal values here are ratings of the same thing by the same observer at
# the same moment — the apples-to-apples unit for matched comparison.
MATCH_KEYS = ["game_id", "room_code", "observer", "target", "phase_idx", "trust_type"]

# FilterSpec field -> unified-table column, for spec fields whose values map
# 1:1 onto a match key column.
_SPEC_FIELD_TO_COLUMN = {
    "game_ids": "game_id",
    "room_codes": "room_code",
    "observers": "observer",
    "targets": "target",
    "trust_types": "trust_type",
}

# If two specs differ only in these fields, their slices still describe the
# same cells (or the same cells along one axis), so matched mode is meaningful.
_MATCHABLE_FIELDS = {
    "sources", "run_ids", "models", "experiments", "trust_scale_modes",
    "temperature_min", "temperature_max", "context_as_tool", "trust_types",
}

MIN_TEST_N = 5  # below this, significance tests are noise; report n and skip


def slice_df(df: pd.DataFrame, spec: FilterSpec) -> pd.DataFrame:
    return apply_filters(df, spec)


def describe_slice(rows: pd.DataFrame) -> dict:
    """Descriptive stats for one slice, JSON-serializable.

    Raw-scale numbers (histogram) are only reported when the slice sits on a
    single scale; normalized numbers and the extremeness index are always
    comparable across scales.
    """
    if rows.empty:
        return {"n": 0}

    scales = sorted(rows["scale"].dropna().unique())
    out: dict = {
        "n": int(len(rows)),
        "games": sorted(rows["room_code"].dropna().unique()),
        "sources": sorted(rows["source"].dropna().unique()),
        "runs": int(rows["run_id"].nunique()),
        "scales": scales,
        "score_norm_mean": round(float(rows["score_norm"].mean()), 4),
        "score_norm_std": round(float(rows["score_norm"].std()), 4),
        "score_norm_median": round(float(rows["score_norm"].median()), 4),
        # mean distance from the scale midpoint, 0 (all midpoint) .. 1 (all
        # endpoints); identical to |raw - mid| / half-range on any one scale
        "extremeness_index": round(float(((rows["score_norm"] - 0.5).abs() * 2).mean()), 4),
    }
    if len(scales) == 1:
        hist = rows["score_raw"].value_counts().sort_index()
        out["score_raw_mean"] = round(float(rows["score_raw"].mean()), 4)
        out["score_raw_histogram"] = {int(k): int(v) for k, v in hist.items()}
    if rows["confidence_norm"].notna().any():
        out["confidence_norm_mean"] = round(float(rows["confidence_norm"].mean()), 4)
    return out


def differing_fields(spec_a: FilterSpec, spec_b: FilterSpec) -> list[str]:
    """FilterSpec field names on which the two specs disagree."""
    a, b = spec_a.model_dump(), spec_b.model_dump()
    return sorted(field for field in a if a[field] != b[field])


def matchable(spec_a: FilterSpec, spec_b: FilterSpec) -> bool:
    """True when a matched (cell-paired) comparison of the two specs is sound."""
    return set(differing_fields(spec_a, spec_b)) <= _MATCHABLE_FIELDS


def match_keys_for(spec_a: FilterSpec, spec_b: FilterSpec) -> list[str]:
    """MATCH_KEYS minus the columns the two specs deliberately differ on.

    E.g. comparing trust_types=["alignment"] vs ["consistency"] must not
    require equal trust_type — that is the axis under comparison.
    """
    differing = set(differing_fields(spec_a, spec_b))
    dropped = {col for field, col in _SPEC_FIELD_TO_COLUMN.items() if field in differing}
    return [k for k in MATCH_KEYS if k not in dropped]


def matched_cells(
    rows_a: pd.DataFrame,
    rows_b: pd.DataFrame,
    keys: list[str] | None = None,
    value: str = "score_norm",
) -> pd.DataFrame:
    """Inner-join the two slices on cell keys, averaging duplicates per cell.

    Averaging first means repeated LLM runs of the same cell count once.
    Returns columns: *keys, "a", "b".
    """
    keys = keys or MATCH_KEYS
    a = rows_a.groupby(keys)[value].mean().rename("a")
    b = rows_b.groupby(keys)[value].mean().rename("b")
    return pd.concat([a, b], axis=1, join="inner").reset_index()
