from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """
    Settings for the application.
    """

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    # Logging settings
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    date_format: str = Field("%Y-%m-%d %H:%M:%S", env="DATE_FORMAT")

    # Ollama
    ollama_api_key: str = Field(..., env="OLLAMA_API_KEY")

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
