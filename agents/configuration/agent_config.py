"""This class is used to describe specific agent configurations"""

from pydantic import BaseModel

from agents.domain.roles import Role

class AgentConfig(BaseModel):
    """Configuration schema for an agent."""

    name: str
    role: Role
    prompt: str
    
    # TODO: Add tools once implemented