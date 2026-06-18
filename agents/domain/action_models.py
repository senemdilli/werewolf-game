"""Actions for the agents to perform during the game."""

from pydantic import BaseModel

class Action(BaseModel):
    """Represents an action taken by an agent."""
    
    name: str
    description: str
    parameters: dict[str, str] = {} # TODO: Adjust to actual parameters needed for actions

class VoteAction(Action):
    """Represents a voting action taken by an agent."""
    
    target_player: str

class InspectAction(Action):
    """Represents an inspection action taken by an agent."""
    
    target_player: str

class KillAction(Action):
    """Represents a killing action taken by an agent."""
    
    target_player: str

class TalkAction(Action):
    """Represents a talking action taken by an agent."""
    
    message: str

class HealAction(Action):
    """Represents a healing action taken by an agent."""
    
    target_player: str