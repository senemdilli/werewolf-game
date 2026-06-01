"""Role definitions for player agents."""
from enum import Enum

class Role(str, Enum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    WITCH = "witch"
    SEER = "seer"