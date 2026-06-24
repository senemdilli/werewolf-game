"""Base class for all agents. All agents should inherit from this class and implement the required methods."""
from abc import ABC, abstractmethod

from agents.configuration.agent_config import AgentConfig
from agents.infrastructure.llm_factory import LLMFactory

from langchain_core.language_models import BaseChatModel

class BaseAgent(ABC):

    def __init__(self, agent_config: AgentConfig) -> None:
        self.agent_config = agent_config
        self.client = None  # Placeholder for the client instance

    def get_state(self):
        """Retrieve the current state of the game."""
        # Placeholder implementation
        return {}
    
    def get_llm(self) -> BaseChatModel:
        """Return the language model instance for the agent."""
        
        llm = LLMFactory.create_ollama(self.agent_config.llm_config)

        return llm
    
    @abstractmethod
    def get_prompt(self) -> str:
        """Return the prompt for the agent. Based on its role."""
        pass
