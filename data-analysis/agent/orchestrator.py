"""LangGraph orchestrator for natural-language analysis queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain.agents import create_agent
from pydantic import BaseModel, Field

from core.logging import get_logger
from core.settings import get_settings
from data.dataset import load_dataset
from tools import (
    CompareDataTool,
    CorrelationTool,
    DeltaTool,
    PlotTool,
    ToolRegistry,
)

logger = get_logger("agents.orchestrator")

SYSTEM_PROMPT = """\
You are the orchestrator of a data analysis agent.
You answer questions about the unified werewolf trust dataset by using the
available analysis tools.

Rules:
1. Prefer tools over guessing.
2. Ask a clarifying question only if the request is ambiguous.
3. When you use a tool, explain the result in plain language.
4. If a tool returns an error, adjust the filters or explain the limitation.
5. Keep the final answer concise and grounded in the returned data.
"""


@dataclass(frozen=True)
class OrchestratorConfig:
    game_records: str | Path
    llm_results: str | Path | None = None
    cache_dir: str | Path | None = "analysis/cache"
    plots_dir: str | Path = "analysis/plots"
    model: str | None = None
    temperature: float | None = None


class OrchestratorResponse(BaseModel):
    answer: str
    conversation: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

class Orchestrator:
    """Orchestrator for the data analysis agent."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.logger = get_logger("agents.orchestrator")
        self.logger.debug("Initializing orchestrator with config: %s", config)

        self.config = config
        self.conversation: list[BaseMessage] = []
        self.df = load_dataset(
            config.game_records, config.llm_results, cache_dir=config.cache_dir
        )
        self.registry = build_tool_registry(self.df, config.plots_dir)
        self.tools = [
            self.registry.get_tool(name).as_langchain_tool()
            for name in self.registry.list_tools()
        ]
        self.model = build_model(config)
        self.agent = create_agent(self.model, self.tools, system_prompt=SYSTEM_PROMPT)

    def ask(self, question: str) -> OrchestratorResponse:
        self.logger.info("Orchestrator received question: %s", question)
        self.conversation.append(HumanMessage(content=question))

        result = self.agent.invoke({"messages": self.conversation})
        self.logger.debug("Orchestrator generated response: %s", result)
        messages = result.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                answer = _message_text(message).strip()
                if answer:
                    self.conversation.append(AIMessage(content=answer))
                    return OrchestratorResponse(
                        answer=answer,
                        conversation=_conversation_to_dicts(self.conversation),
                        metadata={
                            "model": self.config.model,
                            "n_messages": len(self.conversation),
                            "n_tools": len(self.tools),
                        },
                    )
        raise RuntimeError("orchestrator returned no assistant response")


def ask(question: str, config: OrchestratorConfig) -> OrchestratorResponse:
    return Orchestrator(config).ask(question)


def build_tool_registry(df, plots_dir: str | Path = "analysis/plots") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_tool(CompareDataTool(df))
    registry.register_tool(PlotTool(df, plots_dir=plots_dir))
    registry.register_tool(DeltaTool(df))
    registry.register_tool(CorrelationTool(df))
    return registry


def build_model(config: OrchestratorConfig) -> ChatOllama:
    settings = get_settings()
    name = config.model or settings.agent_model
    temperature = settings.agent_temperature if config.temperature is None else config.temperature
    base_url = settings.ollama_api_url
    api_key = settings.ollama_api_key
    client_kwargs = {"headers": {"Authorization": f"Bearer {api_key}"}}
    model = ChatOllama(model=name, temperature=temperature, base_url=base_url, client_kwargs=client_kwargs)

    return model

def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _conversation_to_dicts(messages: list[BaseMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.type, "content": _message_text(message)}
        for message in messages
    ]
