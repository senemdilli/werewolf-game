"""Player agent configuration class."""

import json

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
    llm_model : str = Field("gpt-4o-mini", description="LLM model to use")
    llm_temperature : float = Field(0.7, description="Temperature for LLM responses")
    llm_max_tokens : int = Field(2048, description="Maximum tokens for LLM responses")

    # Tools
    tools : list[str] = Field(default_factory=list, description="List of tools available to the agent")

    @classmethod
    def from_json(cls, json_path: Path):
        """Load agent configuration from a JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

def generate_prompt(role: Role, tools: list[str]) -> str:
    """Generate the initial prompt for the agent based on its role and tools."""

    base_prompt = (PROMPTS_DIR / "base-prompt.md").read_text(encoding="utf-8").strip()
    role_prompt = (PROMPTS_DIR / f"{role.value}.md").read_text(encoding="utf-8").strip()
    tools_prompt = "\n".join(f"- {tool}" for tool in tools) if tools else "- None"

    return f"{base_prompt}\n\n---\n\n{role_prompt}\n\n## Available Tools\n{tools_prompt}"