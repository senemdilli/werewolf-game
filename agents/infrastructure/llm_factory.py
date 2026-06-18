"""This module contains the factory for creating LangChain LLM instances."""

from agents.configuration.llm_config import LLMConfig
from langchain_ollama import ChatOllama

class LLMFactory:
    """Factory for creating LLM instances based on configuration."""

    @staticmethod
    def create_ollama(config: LLMConfig) -> ChatOllama:
        """Create a ChatOllama instance based on the provided configuration."""
        return ChatOllama(
            model=config.model_name,
            temperature=config.temperature,
            base_url=config.base_url,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {config.api_key}"
                }
            },
        )