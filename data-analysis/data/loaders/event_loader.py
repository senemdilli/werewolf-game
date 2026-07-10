"""Loader for game events exports (`game-<room>-<id>.json`)."""

import json
from pathlib import Path

from data.models.event import GameEventsFile


def load_events(path: Path | str) -> GameEventsFile:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return GameEventsFile(**payload)


def is_events_file(payload: dict) -> bool:
    return "events" in payload and "game_id" in payload
