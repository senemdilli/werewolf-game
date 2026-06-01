"""Agent configuration class."""

class AgentConfig:
    """Configuration for an agent."""

    # Basic Information
    name: str
    role: str

    # LLM Configuration
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int

    # Tools
    tools: list[str]