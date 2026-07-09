"""LangGraph orchestrator for natural-language analysis queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain.agents import create_agent

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


def build_tool_registry(df, plots_dir: str | Path = "analysis/plots") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_tool(CompareDataTool(df))
    registry.register_tool(PlotTool(df, plots_dir=plots_dir))
    registry.register_tool(DeltaTool(df))
    registry.register_tool(CorrelationTool(df))
    return registry


def build_Ollama_model() -> ChatOllama:
    settings = get_settings()
    name = settings.agent_model
    temperature = settings.agent_temperature
    base_url = settings.ollama_api_url
    api_key = settings.ollama_api_key
    client_kwargs = {"headers": {"Authorization": f"Bearer {api_key}"}}
    model = ChatOllama(model=name, temperature=temperature, base_url=base_url, client_kwargs=client_kwargs)

    return model


def build_agent(config: OrchestratorConfig):
    df = load_dataset(config.game_records, config.llm_results, cache_dir=config.cache_dir)
    registry = build_tool_registry(df, config.plots_dir)
    tools = [registry.get_tool(name).as_langchain_tool() for name in registry.list_tools()]
    model = build_Ollama_model()
    return create_agent(model, tools, system_prompt=SYSTEM_PROMPT)


def ask(question: str, config: OrchestratorConfig) -> str:
    agent = build_agent(config)
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    messages = result.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            answer = _message_text(message).strip()
            if answer:
                return answer
    raise RuntimeError("orchestrator returned no assistant response")


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
