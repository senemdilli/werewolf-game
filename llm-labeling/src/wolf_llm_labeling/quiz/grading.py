"""Answering and grading logic for the quiz (model-agnostic).

Everything here operates on an injected `model` object that only needs to expose
`.invoke(messages)` (and optionally `.with_structured_output(schema)`), exactly
like the langchain chat models and the test `MockChatModel`. Messages are passed
as ``(role, content)`` tuples, which langchain chat models accept natively, so
this module never imports langchain.
"""

from __future__ import annotations

import re
import time
from typing import Any

from wolf_llm_labeling.quiz.models import JudgeVerdict, QuizQuestion


def _content(response: Any) -> str:
    """Best-effort extraction of text from a model response."""
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Some providers return a list of content blocks.
        parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ]
        return " ".join(p for p in parts if p)
    return str(response)


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, and collapse whitespace for matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def exact_match(candidate: str, acceptable: list[str]) -> bool:
    """Deterministic match: candidate equals or contains a reference answer.

    We only test "reference inside candidate" (not the reverse) so that a short
    stray token in the candidate cannot spuriously match a long reference.
    """
    normalized_candidate = normalize(candidate)
    if not normalized_candidate:
        return False
    for answer in acceptable:
        normalized_answer = normalize(answer)
        if not normalized_answer:
            continue
        if normalized_answer == normalized_candidate:
            return True
        if normalized_answer in normalized_candidate:
            return True
    return False


_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5.0


def _invoke_with_retry(
    invoke: Any,
    messages: Any,
    attempts: int = _RETRY_ATTEMPTS,
    backoff: float = _RETRY_BACKOFF_SECONDS,
) -> Any:
    """Call `invoke(messages)` with retries on transient errors (timeouts, etc.).

    Retries with linear backoff; re-raises the last exception if all attempts
    fail so the caller can decide how to record the failure.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return invoke(messages)
        except Exception as exc:  # noqa: BLE001 - transient server/network errors
            last_exc = exc
            if attempt < attempts:
                time.sleep(backoff * attempt)
    assert last_exc is not None
    raise last_exc


def answer_question(model: Any, system_prompt: str, context: str, question: str) -> str:
    """Ask the candidate model a single question about the given context."""
    human = (
        f"Game context:\n{context}\n\n"
        f"Question:\n{question}\n\n"
        "Answer:"
    )
    response = _invoke_with_retry(
        model.invoke, [("system", system_prompt), ("human", human)]
    )
    return _content(response).strip()


def _judge_human_message(
    question: str,
    acceptable: list[str],
    candidate: str,
    judge_context: str | None = None,
) -> str:
    references = "\n".join(f"- {answer}" for answer in acceptable)
    context = (
        f"Complete game context:\n{judge_context}\n\n" if judge_context else ""
    )
    return (
        context
        + f"Question:\n{question}\n\n"
        f"Reference answer(s) (any one is correct):\n{references}\n\n"
        f"Candidate answer:\n{candidate}\n\n"
        "Is the candidate answer correct?"
    )


def _parse_bool_from_text(text: str) -> bool:
    lowered = text.lower()
    # "incorrect"/"not correct"/"false"/"no" -> False takes precedence.
    if "incorrect" in lowered or "not correct" in lowered:
        return False
    if re.search(r"\bfalse\b", lowered):
        return False
    if re.search(r"\b(correct|true|yes)\b", lowered):
        return True
    if re.match(r"\s*no\b", lowered):
        return False
    return False


def judge(
    model: Any,
    system_prompt: str,
    question: str,
    acceptable: list[str],
    candidate: str,
    judge_context: str | None = None,
) -> tuple[bool, str]:
    """Grade candidate vs. reference answers using an LLM judge.

    Prefers structured output (a `JudgeVerdict`); falls back to parsing the
    model's free text if structured output is unavailable or fails.
    """
    human = _judge_human_message(
        question,
        acceptable,
        candidate,
        judge_context=judge_context,
    )
    messages = [("system", system_prompt), ("human", human)]

    structured = getattr(model, "with_structured_output", None)
    if callable(structured):
        try:
            verdict = _invoke_with_retry(structured(JudgeVerdict).invoke, messages)
            if verdict is not None:
                correct = bool(getattr(verdict, "correct"))
                reason = getattr(verdict, "reason", "") or ""
                return correct, reason
        except Exception:
            pass

    response = _invoke_with_retry(model.invoke, messages)
    text = _content(response)
    return _parse_bool_from_text(text), text.strip()


def grade_answer(
    question: QuizQuestion,
    candidate: str,
    judge_model: Any,
    judge_system_prompt: str,
    judge_context: str | None = None,
) -> tuple[bool, str, str]:
    """Grade one answer, returning (correct, graded_by, judge_reason).

    Respects the question's grading mode:
      - "exact_only": deterministic match only.
      - "judge_only": always ask the judge.
      - "auto": deterministic match first, judge as fallback.
    """
    if question.grading != "judge_only":
        if exact_match(candidate, question.acceptable_answers):
            return True, "exact", ""
        if question.grading == "exact_only":
            return False, "exact", ""

    correct, reason = judge(
        judge_model,
        judge_system_prompt,
        question.question,
        question.acceptable_answers,
        candidate,
        judge_context=judge_context,
    )
    return correct, "judge", reason
