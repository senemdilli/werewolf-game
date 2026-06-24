"""This module contains the factory for creating LangChain LLM instances."""

from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from agents.configuration.llm_config import LLMConfig
from agents.configuration.settings import Settings

class LLMFactory:
    """Factory for creating LLM instances based on configuration."""

    @staticmethod
    def create(config: LLMConfig, settings: Settings) -> BaseChatModel:
        """Create an LLM instance based on the provided configuration."""

        if config.model_name.startswith("ollama"):
            return LLMFactory._create_ollama(config, settings)
        else:
            raise ValueError(f"Unsupported model name: {config.model_name}")

    @staticmethod
    def _create_ollama(config: LLMConfig, settings: Settings) -> ChatOllama:
        """Create a ChatOllama instance based on the provided configuration."""
        return ChatOllama(
            model=config.model_name,
            temperature=config.temperature,
            base_url=settings.OLLAMA_URL,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {config.api_key}"
                }
            },
        )