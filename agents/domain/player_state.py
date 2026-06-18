""""Represents the state of a player in the game."""
# TODO: The game logic is not handled here so do we even need this?

from pydantic import BaseModel

class PlayerState(BaseModel):
    """Represents the state of a player in the game."""
    
    name: str
    role: str # TODO: Change to Role once we have it implemented
    is_alive: bool = True