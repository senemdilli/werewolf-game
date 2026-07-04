"""The shared FilterSpec every analysis tool accepts.

The orchestrator LLM fills this in from the user's question; tools apply it
with `apply_filters` before doing any computation. List fields mean "keep rows
matching any of these values"; None means "no constraint".

Trust given vs received is expressed through the observer/target axes: filter
`observer_team` for trust *given by* a team, `target_team` for trust
*received by* a team.
"""

import pandas as pd
from pydantic import BaseModel


class FilterSpec(BaseModel):
    # game-level
    game_ids: list[str] | None = None
    room_codes: list[str] | None = None
    game_modes: list[str] | None = None
    winners: list[str] | None = None

    # source / run
    sources: list[str] | None = None  # "human" | "llm"
    run_ids: list[str] | None = None

    # observer / target perspective (trust given vs received)
    observers: list[str] | None = None
    targets: list[str] | None = None
    observer_teams: list[str] | None = None
    target_teams: list[str] | None = None
    observer_roles: list[str] | None = None
    target_roles: list[str] | None = None
    exclude_self: bool = False  # drop rows where observer == target
    alive_only: bool = False  # keep rows where observer and target are alive

    # time within the game
    trust_types: list[str] | None = None  # alignment | information | consistency
    checkpoints: list[str] | None = None
    round_min: int | None = None
    round_max: int | None = None
    phase_idx_min: int | None = None
    phase_idx_max: int | None = None

    # LLM experiment configuration (no effect on human rows unless combined
    # with sources=["llm"])
    models: list[str] | None = None
    experiments: list[str] | None = None
    trust_scale_modes: list[str] | None = None
    temperature_min: float | None = None
    temperature_max: float | None = None
    context_as_tool: bool | None = None


_CASEFOLD_COLUMNS = {
    "sources": "source",
    "observer_teams": "observer_team",
    "target_teams": "target_team",
    "observer_roles": "observer_role",
    "target_roles": "target_role",
    "trust_types": "trust_type",
    "checkpoints": "checkpoint",
    "winners": "winner",
    "game_modes": "game_mode",
    "trust_scale_modes": "trust_scale_mode",
}

_EXACT_COLUMNS = {
    "game_ids": "game_id",
    "room_codes": "room_code",
    "run_ids": "run_id",
    "observers": "observer",
    "targets": "target",
    "models": "model",
    "experiments": "experiment",
}


def apply_filters(df: pd.DataFrame, spec: FilterSpec) -> pd.DataFrame:
    """Return the rows of the unified table matching the spec."""
    mask = pd.Series(True, index=df.index)

    for field, column in _EXACT_COLUMNS.items():
        values = getattr(spec, field)
        if values:
            mask &= df[column].isin(values)

    for field, column in _CASEFOLD_COLUMNS.items():
        values = getattr(spec, field)
        if values:
            wanted = {str(v).strip().casefold() for v in values}
            mask &= df[column].astype("string").str.casefold().isin(wanted)

    if spec.exclude_self:
        mask &= df["observer"] != df["target"]
    if spec.alive_only:
        mask &= df["observer_alive"].fillna(False) & df["target_alive"].fillna(False)

    if spec.round_min is not None:
        mask &= df["round"] >= spec.round_min
    if spec.round_max is not None:
        mask &= df["round"] <= spec.round_max
    if spec.phase_idx_min is not None:
        mask &= df["phase_idx"] >= spec.phase_idx_min
    if spec.phase_idx_max is not None:
        mask &= df["phase_idx"] <= spec.phase_idx_max
    if spec.temperature_min is not None:
        mask &= df["temperature"] >= spec.temperature_min
    if spec.temperature_max is not None:
        mask &= df["temperature"] <= spec.temperature_max
    if spec.context_as_tool is not None:
        mask &= df["context_as_tool"] == spec.context_as_tool

    return df[mask]
