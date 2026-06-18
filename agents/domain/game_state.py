"""Internal representation of the game state, including player information, roles, and actions."""
# TODO: Adjust to actual shared information

from pydantic import BaseModel

class GameState(BaseModel):
    """Represents the current state of the game."""
    
    players: list[tuple[str, bool]] = [] # list of (player name, is_alive) tuples
    current_day: int = 0
    chat_history: list[str] = [] # TODO: Determine if we really want to store the entire chat history here or just a summary/log of actions
    