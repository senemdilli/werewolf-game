"""Shared game-level metadata (present in both export files)."""

from pydantic import BaseModel


class GameMeta(BaseModel):
    game_id: str
    room_code: str | None = None
    game_mode: str | None = None
    winner: str | None = None
    exported_at: str | None = None
