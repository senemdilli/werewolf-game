"""Agent configuration class."""

import json
import os

from pathlib import Path

from pydantic import BaseModel, Field

from agents.domain.roles import Role

class AgentConfig(BaseModel):
    """Configuration schema for an agent."""

    # Basic Information
    name: str = Field(..., description="Name of the agent")
    role: Role = Field(..., description="Role of the agent")
    prompt: str = Field("", description="Initial prompt for the agent")

    # LLM Configuration
    model_name: str = Field("gemma4:26b", description="Ollama model name")
    temperature: float = Field(0, description="Sampling temperature")
    base_url: str = Field(
        default_factory=lambda: os.getenv("SNET_OLLAMA_ENDPOINT"),
        description="Ollama base URL",
    )
    api_key_env: str = Field(
        "SNET_TOKEN", description="Environment variable containing the bearer token"
    )

    # Tools
    tools: list[str] = Field(default_factory=list, description="List of tools available to the agent")

    @classmethod
    def from_json(cls, json_path: Path):
        """Load agent configuration from a JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
