"""
This is the brain of the data analysis agent.
It takes in a user query and orchestrates the execution of various tools to provide a comprehensive answer.
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from core.logging import get_logger

logger = get_logger("agents.orchestrator")

SYSTEM_PROMPT = """\
You are the orchestrator of a data analysis agent.
You receive a user query and a list of available tools.

Your job:
1. Analyze the user query to understand what the user is asking for.
2. Determine which tools are necessary to answer the query.
3. Execute the tools in a logical sequence to gather the required information.
4. Combine the results from the tools to formulate a comprehensive answer to the user query.
"""

class Orchestrator(BaseModel):
    """
    The Orchestrator class is responsible for managing the execution of various tools to answer user queries.
    It takes in a user query and orchestrates the execution of tools in a logical sequence.
    """

    system_prompt: str = Field(default=SYSTEM_PROMPT, description="The system prompt for the orchestrator.")

