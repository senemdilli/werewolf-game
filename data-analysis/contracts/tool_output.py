"""Tool output contract."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T",)

class ToolOutput(BaseModel, Generic[T]):
    """
    Contract for the output of a tool.
    """

    success: bool
    data: T | None = None
    source: str = Field(..., description="The source of the output, e.g., the tool name.")
    error: str | None = Field(None, description="Error message if the tool failed.")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Additional metadata related to the output.")