"""Game events export (`game-<room>-<id>.json`) — the ground-truth record."""

from pydantic import BaseModel

from data.models.game import GameMeta


class GameEvent(BaseModel):
    type: str  # "chat" | "day_vote" | "night_action"
    round: int
    phase: str  # "NIGHT" | "DAY"
    player_name: str
    player_role: str | None = None
    target_name: str | None = None
    content: str
    is_system: bool = False
    timestamp: str | None = None


class GameEventsFile(GameMeta):
    events: list[GameEvent]

    def roles_by_player(self) -> dict[str, str]:
        """Player name -> role, from all non-system events that carry a role."""
        roles: dict[str, str] = {}
        for event in self.events:
            if not event.is_system and event.player_role:
                roles.setdefault(event.player_name, event.player_role.upper())
        return roles

    def player_names(self) -> set[str]:
        """All player names, including silent players only seen as targets."""
        names = set()
        for event in self.events:
            if not event.is_system:
                names.add(event.player_name)
            if event.target_name:
                names.add(event.target_name)
        return names
