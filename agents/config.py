"""Player agent configuration class."""

import importlib
import json
import os

from pathlib import Path

from roles import Role
from pydantic import BaseModel, Field

from agents.prompts import *

PROMPTS_DIR = Path(__file__).parent / "prompts"

class AgentConfig(BaseModel):
    """Configuration schema for a player."""

    # Basic Information
    name : str = Field(..., description="Name of the agent")
    role : Role = Field(..., description="Role of the agent")
    prompt : str = Field("", description="Initial prompt for the agent")

    # LLM Configuration
    model_name : str = Field("gemma4:26b", description="Ollama model name")
    temperature : float = Field(0, description="Sampling temperature")
    base_url : str = Field(
        default_factory=lambda: os.getenv("SNET_OLLAMA_ENDPOINT"),
        description="Ollama base URL",
    )
    api_key_env : str = Field(
        "SNET_TOKEN", description="Environment variable containing the bearer token"
    )

    # Tools
    tools : list[str] = Field(default_factory=list, description="List of tools available to the agent")

    @classmethod
    def from_json(cls, json_path: Path):
        """Load agent configuration from a JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def build_chat_model(self):
        """Create the configured Ollama chat model."""
        chat_ollama_module = importlib.import_module("langchain_ollama")
        ChatOllama = chat_ollama_module.ChatOllama

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ValueError(f"Missing required environment variable: {self.api_key_env}")

        return ChatOllama(
            model=self.model_name,
            temperature=self.temperature,
            base_url=self.base_url,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {api_key}"
                }
            },
        )

def generate_prompt(role: Role, tools: list[str]) -> str:
    """Generate the initial prompt for the agent based on its role and tools."""

    base_prompt = (PROMPTS_DIR / "base-prompt.md").read_text(encoding="utf-8").strip()
    role_prompt = (PROMPTS_DIR / f"{role.value}.md").read_text(encoding="utf-8").strip()
    tools_prompt = "\n".join(f"- {tool}" for tool in tools) if tools else "- None"

    return f"{base_prompt}\n\n---\n\n{role_prompt}\n\n## Available Tools\n{tools_prompt}"