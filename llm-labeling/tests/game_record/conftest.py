from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

CSV_FIELDS = [
    "type",
    "game_id",
    "room_code",
    "game_mode",
    "winner",
    "round",
    "phase",
    "player_name",
    "player_role",
    "target_name",
    "content",
    "is_system",
    "timestamp",
]


def row(
    row_type: str,
    phase: str,
    player_name: str,
    player_role: str,
    content: str,
    *,
    target_name: str = "",
    is_system: str = "false",
    game_id: str = "game-a",
    round_number: str = "1",
) -> dict[str, str]:
    return {
        "type": row_type,
        "game_id": game_id,
        "room_code": "ROOM",
        "game_mode": "CLASSIC",
        "winner": "",
        "round": round_number,
        "phase": phase,
        "player_name": player_name,
        "player_role": player_role,
        "target_name": target_name,
        "content": content,
        "is_system": is_system,
        "timestamp": "2026-01-01T00:00:00.000Z",
    }


def base_rows() -> list[dict[str, str]]:
    return [
        row("chat", "NIGHT", "System", "", "Night 1 begins.", is_system="true"),
        row("chat", "NIGHT", "Wolf", "WEREWOLF", "wolf whisper"),
        row("night_action", "NIGHT", "Wolf", "WEREWOLF", "KILL", target_name="Seer"),
        row("night_action", "NIGHT", "Seer", "SEER", "INVESTIGATE", target_name="Wolf"),
        row("night_action", "NIGHT", "Witch", "WITCH", "HEAL", target_name="Seer"),
        row("chat", "DAY", "System", "", "Dawn breaks. Seer (seer) was found dead.", is_system="true"),
        row("chat", "DAY", "System", "", "A strange bell rings.", is_system="true"),
        row("chat", "DAY", "System", "", "The village must elect a Mayor.", is_system="true"),
        row(
            "chat",
            "DAY",
            "System",
            "",
            "Villager has been elected Mayor. Their vote counts double.",
            is_system="true",
        ),
        row("chat", "DAY", "Villager", "VILLAGER", "hello village"),
        row("chat", "DAY", "System", "", "Voting begins.", is_system="true"),
        row("chat", "DAY", "System", "", "The village voted. Wolf (werewolf) has been eliminated.", is_system="true"),
    ]


def player(name: str, role: str) -> dict[str, str]:
    return {"name": name, "role": role}


def label(observer: str = "Villager", target: str = "Wolf") -> dict[str, Any]:
    return {
        "observer": player(observer, "VILLAGER"),
        "targets": [
            {
                "player": player(target, "WEREWOLF"),
                "alignment": {"score": 2, "confidence": "HIGH"},
                "information": {"score": 3, "confidence": "MEDIUM"},
                "consistency": {"score": 4, "confidence": "LOW"},
                "reasoning": "fixture reason",
            }
        ],
    }


def base_labels(game_id: str = "game-a") -> dict[str, Any]:
    return {
        "game_id": game_id,
        "room_code": "ROOM",
        "game_mode": "CLASSIC",
        "winner": "",
        "exported_at": "2026-01-01T00:00:00.000Z",
        "rounds": [
            {
                "round": 1,
                "checkpoints": [
                    {"checkpoint": "BEFORE_DISCUSSION", "labels": [label()]},
                    {"checkpoint": "BEFORE_VOTING", "labels": [label()]},
                    {"checkpoint": "AFTER_VOTING", "labels": [label()]},
                ],
            }
        ],
    }


def write_export(
    tmp_path: Path,
    name: str = "game-test",
    rows: list[dict[str, str]] | None = None,
    labels: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    csv_path = tmp_path / f"{name}.csv"
    labels_path = tmp_path / f"{name}-labels.json"
    rows = rows if rows is not None else base_rows()
    labels = labels if labels is not None else base_labels()
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    labels_path.write_text(json.dumps(labels), encoding="utf-8")
    return csv_path, labels_path
