import inspect

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from agents.config import AgentConfig
from agents.client import Client

class BaseAgent(ABC):

    def __init__(self, config: Any) -> None:
        self.config = config
        self.client = Client()

    @classmethod
    def load_default_config(cls) -> AgentConfig:
        """Load the default configuration for the agent."""
        config_path = Path(inspect.getfile(cls)).resolve().with_name("config.json")
        return AgentConfig.from_json(config_path)
    
    @classmethod
    def vote(cls, player_name: str) -> None:
        """Vote for a player based on the current game state."""
        pass

    @classmethod
    def send_message(cls, message: str) -> None:
        """Send a message to the game server."""
        cls.client.send_message(message)