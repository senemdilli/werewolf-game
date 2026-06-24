"""This class is used to describe specific agent configurations"""

from pydantic import BaseModel

from agents.domain.roles import Role
from agents.configuration.llm_config import LLMConfig

class AgentConfig(BaseModel):
    """Configuration schema for an agent."""

    name: str
    role: Role
    prompt: str

    llm_config: LLMConfig
    
    # TODO: Add tools once implemented