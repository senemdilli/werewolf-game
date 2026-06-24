"""Base class for all agents. All agents should inherit from this class and implement the required methods."""
from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel

from agents.configuration.agent_config import AgentConfig
from agents.infrastructure.llm_factory import LLMFactory
from agents.configuration.settings import Settings

class BaseAgent(ABC):

    def __init__(self, agent_config: AgentConfig, settings: Settings) -> None:
        self.agent_config = agent_config
        self.settings = settings
        self.client = None  # Placeholder for the client instance

    def get_state(self):
        """Retrieve the current state of the game."""
        # Placeholder implementation
        return {}
    
    def get_llm(self) -> BaseChatModel:
        """Return the language model instance for the agent."""
        
        llm = LLMFactory.create(self.agent_config.llm_config, self.agent_config.settings)

        return llm
    
    @abstractmethod
    def get_prompt(self) -> str:
        """Return the prompt for the agent. Based on its role."""
        pass
