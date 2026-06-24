"""This class loads environment variables and other application settings."""

from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Ollama API configuration
    OLLAMA_URL: str = Field("SNET_OLLAMA_ENDPOINT", description="Base URL for the Ollama API")
    OLLAMA_API_KEY: str = Field("SNET_OLLAMA_API_KEY", description="API key for the Ollama API")