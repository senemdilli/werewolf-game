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


def _bundled_prompt(filename: str) -> str:
    """Load a required prompt shipped with the quiz benchmark."""
    return (_DEFAULT_PROMPT_DIR / filename).read_text(encoding="utf-8")


# Keep the public constants for callers/tests, but source them from the actual
# prompt files so CLI defaults and documented prompts cannot silently diverge.
DEFAULT_ANSWERER_SYSTEM = _bundled_prompt("answerer_system.md")
DEFAULT_JUDGE_SYSTEM = _bundled_prompt("judge_system.md")
DEFAULT_RULES = _bundled_prompt("rules.md")


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


def build_chat_model(
    model_name: str,
    ollama_url: str,
    temperature: float = 0.0,
    request_timeout: float | None = 300.0,
) -> Any:
    """Construct a langchain chat model for Ollama or an OpenAI-compatible server.

    Mirrors the detection logic used by the trust-labeling runner: URLs that look
    like LM Studio (`/v1` or port 1234) use the OpenAI-compatible client.

    `request_timeout` (seconds) bounds a single request so a hung or queued call
    fails fast instead of blocking an entire batch indefinitely. Pass ``None`` to
    disable the timeout.
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
            timeout=request_timeout,
            max_retries=2,
        )

    try:
        from langchain_ollama import ChatOllama
    except ImportError:  # pragma: no cover - optional dependency
        from langchain_community.chat_models import ChatOllama  # type: ignore

    client_kwargs: dict[str, Any] = {}
    if token:
        client_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
    if request_timeout is not None:
        # Passed through to the underlying ollama.Client -> httpx.Client(timeout=...).
        client_kwargs["timeout"] = request_timeout

    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=ollama_url,
        client_kwargs=client_kwargs,
    )
