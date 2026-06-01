"""Agent configuration class."""

class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    system_prompt: str
    tools: list[str]