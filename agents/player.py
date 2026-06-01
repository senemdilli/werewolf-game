"""This is the Player agent, playing the game of werewolf."""
# TODO - Determine if we need different agents for differnt roles

from .config import AgentConfig

class PlayerAgent:
    name = ""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.name = config.name