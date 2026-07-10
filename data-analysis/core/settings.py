from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings for the application.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Logging settings
    log_level: str = Field("INFO")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    date_format: str = Field("%Y-%m-%d %H:%M:%S")

    # Ollama (only required once the orchestrator is used)
    ollama_api_key: str = Field("")
    ollama_api_url: str = Field("https://gpu.snet.tu-berlin.de/echelon/ollama")
    agent_model: str = Field("gemma4:26b")
    agent_temperature: float = Field(0.0)

settings: Settings | None = None

def get_settings() -> Settings:
    """
    Get the settings for the application.
    This function will load the settings from the environment variables and return a Settings object.
    """
    global settings
    if settings is None:
        settings = Settings()
    return settings
