"""Loader for human trust annotations (`game-<room>-<id>-labels.json`).

Produces unified annotation rows — see data/dataset.py for the row contract.
"""

import json
from pathlib import Path
from typing import Any

from data.models.event import GameEventsFile
from data.models.human_observation import HumanGameLabels
from data.models.player import team_for_role
from data.models.trust_metric import CANONICAL_TRUST_TYPE, HUMAN_TRUST_KEYS, ConfidenceScale, TrustScale
from data.normalization import confidence_ordinal, normalize_confidence, normalize_trust
from data.phase_alignment import PhaseAlignment, build_phase_alignment


def load_human_labels(path: Path | str) -> HumanGameLabels:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return HumanGameLabels(**payload)


def is_human_labels_file(payload: dict) -> bool:
    return "rounds" in payload and "game_id" in payload


def human_rows(labels: HumanGameLabels, events: GameEventsFile | None) -> list[dict[str, Any]]:
    """Flatten one human labels file into unified annotation rows."""
    alignment: PhaseAlignment | None = None
    if events is not None:
        alignment = build_phase_alignment(events.events, events.player_names() or None)

    rows: list[dict[str, Any]] = []
    for game_round in labels.rounds:
        for checkpoint in game_round.checkpoints:
            phase_idx = alignment.phase_idx(game_round.round, checkpoint.checkpoint) if alignment else None
            dead = alignment.dead_players(phase_idx) if alignment and phase_idx is not None else frozenset()
            for entry in checkpoint.labels:
                for target in entry.targets:
                    for key in HUMAN_TRUST_KEYS:
                        score = getattr(target, key)
                        if score is None:
                            continue
                        rows.append({
                            "game_id": labels.game_id,
                            "room_code": labels.room_code,
                            "game_mode": labels.game_mode,
                            "winner": labels.winner,
                            "exported_at": labels.exported_at,
                            "source": "human",
                            "run_id": "human",
                            "observer": entry.observer.name,
                            "observer_role": (entry.observer.role or "").upper() or None,
                            "observer_team": _team(entry.observer.role),
                            "observer_alive": entry.observer.name not in dead,
                            "target": target.player.name,
                            "target_role": (target.player.role or "").upper() or None,
                            "target_team": _team(target.player.role),
                            "target_alive": target.player.name not in dead,
                            "round": game_round.round,
                            "checkpoint": checkpoint.checkpoint,
                            "phase_idx": phase_idx,
                            "trust_type": CANONICAL_TRUST_TYPE[key].value,
                            "score_raw": score.score,
                            "scale": TrustScale.SEVEN_POINT.value,
                            "score_norm": normalize_trust(score.score, TrustScale.SEVEN_POINT),
                            "confidence_raw": confidence_ordinal(score.confidence),
                            "confidence_scale": ConfidenceScale.THREE_LEVEL.value,
                            "confidence_norm": normalize_confidence(score.confidence),
                            "reasoning": target.reasoning,
                            "created_at": entry.created_at,
                            # LLM-run metadata columns (empty for human rows)
                            "model": None,
                            "inner_voice_model": None,
                            "experiment": None,
                            "temperature": None,
                            "trust_scale_mode": None,
                            "formatter": None,
                            "experiment_args": None,
                            "max_phases": None,
                            "context_as_tool": None,
                        })
    return rows


def _team(role: str | None) -> str | None:
    team = team_for_role(role)
    return team.value if team else None
