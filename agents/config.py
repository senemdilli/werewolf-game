"""Player agent configuration class."""

from pathlib import Path

from roles import Role
from pydantic import BaseModel, Field

from agents.prompts import *

PROMPTS_DIR = Path(__file__).parent / "prompts"

class PlayerAgentConfig(BaseModel):
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

    def __init__(
        self,
        # Basic Information
        name: str,
        role: Role,

        # LLM Configuration
        llm_model: str = "gpt-4o-mini",
        llm_temperature: float = 0.7,
        llm_max_tokens: int = 2048,

        # Tools
        tools: list[str] = [],
    )-> None:
        
        self.name = name
        self.role = role
        self.prompt = generate_prompt(role, tools)
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.llm_max_tokens = llm_max_tokens
        self.tools = tools

def generate_prompt(role: Role, tools: list[str]) -> str:
    """Generate the initial prompt for the agent based on its role and tools."""

    base_prompt = (PROMPTS_DIR / "base-prompt.md").read_text(encoding="utf-8").strip()
    role_prompt = (PROMPTS_DIR / f"{role.value}.md").read_text(encoding="utf-8").strip()
    tools_prompt = "\n".join(f"- {tool}" for tool in tools) if tools else "- None"

    return f"{base_prompt}\n\n---\n\n{role_prompt}\n\n## Available Tools\n{tools_prompt}"