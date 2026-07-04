"""Player identity, roles and teams."""

from enum import Enum

from pydantic import BaseModel


class Team(str, Enum):
    VILLAGERS = "VILLAGERS"
    WEREWOLVES = "WEREWOLVES"


def team_for_role(role: str | None) -> Team | None:
    """Map a role string to its team. Unknown/empty roles return None."""
    if not role:
        return None
    if role.strip().upper() == "WEREWOLF":
        return Team.WEREWOLVES
    return Team.VILLAGERS


class Player(BaseModel):
    """A player as referenced in game exports (id may be absent in event logs)."""

    id: str | None = None
    name: str
    role: str | None = None

    @property
    def team(self) -> Team | None:
        return team_for_role(self.role)
