"""Loader for LLM labeling engine outputs (`<player>-<uuid>.json`).

Produces unified annotation rows — see data/dataset.py for the row contract.
"""

import json
from pathlib import Path
from typing import Any

from data.models.event import GameEventsFile
from data.models.experiment import LLMRun
from data.models.game import GameMeta
from data.models.player import team_for_role
from data.models.trust_metric import CANONICAL_TRUST_TYPE, LLM_TRUST_KEYS, ConfidenceScale
from data.normalization import infer_trust_scale, normalize_confidence, normalize_trust
from data.phase_alignment import PhaseAlignment, build_phase_alignment


def load_llm_run(path: Path | str) -> LLMRun:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    run = LLMRun(**payload)
    run.run_id = path.stem  # e.g. "Blue-99c55270"
    return run


def is_llm_run_file(payload: dict) -> bool:
    return "phases" in payload and "player_name" in payload and "game_id" in payload


def llm_rows(
    run: LLMRun,
    events: GameEventsFile | None,
    game_meta: GameMeta | None = None,
) -> list[dict[str, Any]]:
    """Flatten one LLM run output into unified annotation rows."""
    roles = events.roles_by_player() if events else {}
    alignment: PhaseAlignment | None = None
    if events is not None:
        alignment = build_phase_alignment(events.events, events.player_names() or None)

    trust_values = [
        score.trust
        for phase in run.phases
        for label in phase.labels.values()
        for key in LLM_TRUST_KEYS
        if (score := getattr(label, key)) is not None and score.trust is not None
    ]
    scale = infer_trust_scale(run.trust_scale_mode, trust_values)

    meta = game_meta or (events if events else None)
    observer_role = roles.get(run.player_name)

    rows: list[dict[str, Any]] = []
    for phase in run.phases:
        round_checkpoint = alignment.round_checkpoint(phase.phase_idx) if alignment else None
        dead = alignment.dead_players(phase.phase_idx) if alignment else frozenset()
        for target_name, label in phase.labels.items():
            target_role = roles.get(target_name)
            for key in LLM_TRUST_KEYS:
                score = getattr(label, key)
                if score is None or score.trust is None:
                    continue
                rows.append({
                    "game_id": run.game_id,
                    "room_code": meta.room_code if meta else None,
                    "game_mode": meta.game_mode if meta else None,
                    "winner": meta.winner if meta else None,
                    "exported_at": meta.exported_at if meta else None,
                    "source": "llm",
                    "run_id": run.run_id,
                    "observer": run.player_name,
                    "observer_role": observer_role,
                    "observer_team": _team(observer_role),
                    "observer_alive": run.player_name not in dead,
                    "target": target_name,
                    "target_role": target_role,
                    "target_team": _team(target_role),
                    "target_alive": target_name not in dead,
                    "round": round_checkpoint[0] if round_checkpoint else None,
                    "checkpoint": round_checkpoint[1] if round_checkpoint else None,
                    "phase_idx": phase.phase_idx,
                    "trust_type": CANONICAL_TRUST_TYPE[key].value,
                    "score_raw": score.trust,
                    "scale": scale.value,
                    "score_norm": normalize_trust(score.trust, scale),
                    "confidence_raw": score.confidence,
                    "confidence_scale": ConfidenceScale.THREE_LEVEL.value,
                    "confidence_norm": normalize_confidence(score.confidence),
                    "reasoning": label.reasoning,
                    "created_at": run.time,
                    "model": run.primary_model,
                    "inner_voice_model": run.inner_voice_model,
                    "experiment": run.experiment,
                    "temperature": run.temperature,
                    "trust_scale_mode": run.trust_scale_mode,
                    "formatter": run.formatter,
                    "experiment_args": run.experiment_args,
                    "max_phases": run.max_phases,
                    "context_as_tool": run.context_as_tool,
                })
    return rows


def _team(role: str | None) -> str | None:
    team = team_for_role(role)
    return team.value if team else None
