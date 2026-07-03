"""Runtime helpers: build chat models and load prompt files.

This is the only quiz module that touches langchain, and it imports it lazily
inside `build_chat_model` so the rest of the package (and its tests) stay free
of heavy dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Prompt files live under <llm-labeling>/prompts/quiz by default. This file is at
# src/wolf_llm_labeling/quiz/llm_setup.py, so the project root is parents[3].
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROMPT_DIR = _PROJECT_ROOT / "prompts" / "quiz"

DEFAULT_ANSWERER_SYSTEM = (
    "You are answering factual questions about a single game of Werewolf.\n"
    "Answer ONLY using the provided rules and game context. Be concise and "
    "direct. If the information needed is not present in the context, answer "
    'exactly: "Not stated in the context". Do not invent votes, deaths, roles, '
    "or events that are not shown.\n\nRules of the game:\n${rules}"
)
DEFAULT_JUDGE_SYSTEM = (
    "You are a strict grader comparing a candidate answer to reference answers "
    "for a question about a Werewolf game. Mark the candidate correct if it "
    "matches the meaning of ANY reference answer, ignoring wording, "
    "capitalization, and punctuation. A different player name, number, or fact "
    "is incorrect."
)
DEFAULT_RULES = (
    "8 players: 2 werewolves, 1 seer, 1 witch, 4 villagers. Werewolves kill one "
    "player each night and win when they equal or outnumber the villagers. The "
    "village wins when all werewolves are exiled. Each day the village may elect "
    "a mayor (double vote), discusses, then votes to exile one player (whose role "
    "is revealed). At night the seer learns one player's faction, the werewolves "
    "vote a victim, then the witch may heal or poison. Individual mayor votes are "
    "secret; only the result is public."
)


def load_prompt(path: str | Path | None, default: str) -> str:
    """Read a prompt file, falling back to a built-in default."""
    if path is None:
        return default
    candidate = Path(path)
    if not candidate.is_absolute() and not candidate.exists():
        candidate = _DEFAULT_PROMPT_DIR / candidate
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return default


def default_prompt_dir() -> Path:
    return _DEFAULT_PROMPT_DIR


def build_chat_model(model_name: str, ollama_url: str, temperature: float = 0.0) -> Any:
    """Construct a langchain chat model for Ollama or an OpenAI-compatible server.

    Mirrors the detection logic used by the trust-labeling runner: URLs that look
    like LM Studio (`/v1` or port 1234) use the OpenAI-compatible client.
    """
    token = os.getenv("OLLAMA_API_KEY")
    is_openai = "1234" in ollama_url or "/v1" in ollama_url

    if is_openai:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:  # pragma: no cover - optional dependency
            from langchain_community.chat_models import ChatOpenAI  # type: ignore

        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            base_url=ollama_url,
            api_key=token or "lm-studio",
        )

    try:
        from langchain_ollama import ChatOllama
    except ImportError:  # pragma: no cover - optional dependency
        from langchain_community.chat_models import ChatOllama  # type: ignore

    client_kwargs = {"headers": {"Authorization": f"Bearer {token}"}} if token else {}
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=ollama_url,
        client_kwargs=client_kwargs,
    )
