"""Delta calculation: compare trust scores across sources or trust dimensions.

Covers two of the spec's BI questions directly:
- `compare="source", value_a="llm", value_b="human"`: how far off is the LLM
  labeling from the human labeling on the same cells?
- `compare="trust_type", value_a="alignment", value_b="information"`: how
  does one trust dimension diverge from another for the same observer/target?

"""

from typing import Literal

import pandas as pd

from contracts.tool_output import ToolOutput
from data.filters import FilterSpec
from tools.base_tool import BaseTool
from tools.slicing import MATCH_KEYS as _SLICING_MATCH_KEYS
from tools.slicing import matched_cells, slice_df

_BASE_KEYS = [k for k in _SLICING_MATCH_KEYS if k != "trust_type"]  # game_id, room_code, observer, target, phase_idx
_OTHER_AXIS = {"source": "trust_type", "trust_type": "source"}
_DESCRIPTIVE_COLUMNS = [
    "round", "checkpoint", "target_team", "observer_team", "target_role", "observer_role", "exported_at",
]


class DeltaTool(BaseTool):
    """Compute the delta between two sources or two trust types on matched cells."""

    name = "delta_tool"
    description = (
        "Calculate the difference between two trust scores (score_a - score_b) "
        "for matched observations in the trust table. Compare values along one "
        "dimension: use compare='source' with value_a/value_b as 'human' and "
        "'llm', or compare='trust_type' with value_a/value_b as "
        "'alignment', 'information', or 'consistency'. "
        "Scores are matched on the same game, observer, target, phase, and the "
        "remaining relevant axis. Optionally aggregate results by round, "
        "phase_idx, checkpoint, or team/role columns."
    )

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__()
        self._df = df

    def run(
        self,
        filters: FilterSpec,
        compare: Literal["source", "trust_type"],
        value_a: str,
        value_b: str,
        group_by: list[str] | None = None,
    ) -> ToolOutput:
        self.logger.debug("Running DeltaTool with filters=%s, compare=%s, value_a=%s, value_b=%s, group_by=%s",
            filters,
            compare,
            value_a,
            value_b,
            group_by,
        )

        df = slice_df(self._df, filters)
        if df.empty:
            return ToolOutput(success=False, source=self.name, error="no rows match the filters")

        group_by = group_by or []
        match_keys = _BASE_KEYS + [_OTHER_AXIS[compare]]

        a = df[df[compare].astype(str).str.casefold() == value_a.strip().casefold()]
        b = df[df[compare].astype(str).str.casefold() == value_b.strip().casefold()]
        if a.empty or b.empty:
            return ToolOutput(
                success=False, source=self.name,
                error=f"no rows with {compare}={value_a!r} or {compare}={value_b!r} after filtering",
            )

        descriptive = [c for c in _DESCRIPTIVE_COLUMNS if c in df.columns]
        matched = matched_cells(a, b, keys=match_keys, value="score_norm", extra_columns=descriptive)
        matched = matched.rename(columns={"a": "score_a", "b": "score_b"})
        if matched.empty:
            return ToolOutput(
                success=False, source=self.name,
                error=(
                    f"no matched cells between {compare}={value_a!r} and {compare}={value_b!r} "
                    "(same game/observer/target/phase required on both sides)"
                ),
            )
        matched["delta"] = matched["score_a"] - matched["score_b"]

        unknown_group_cols = [c for c in group_by if c not in matched.columns]
        if unknown_group_cols:
            return ToolOutput(
                success=False, source=self.name,
                error=f"unknown group_by column(s): {unknown_group_cols}",
            )

        if group_by:
            carry = {c: (c, "first") for c in descriptive if c not in group_by}
            summary = matched.groupby(group_by).agg(
                mean_delta=("delta", "mean"),
                mean_abs_delta=("delta", lambda s: s.abs().mean()),
                n=("delta", "size"),
                **carry,
            ).reset_index()
        else:
            summary = pd.DataFrame([{
                "mean_delta": matched["delta"].mean(),
                "mean_abs_delta": matched["delta"].abs().mean(),
                "n": len(matched),
            }])

        return ToolOutput(
            success=True,
            source=self.name,
            data=summary.to_dict(orient="records"),
            metadata={
                "n_matched_cells": len(matched),
                "compare": compare,
                "value_a": value_a,
                "value_b": value_b,
                "group_by": group_by,
            },
        )
