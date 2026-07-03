"""Game-comprehension quiz benchmark for the Werewolf LLM engine.

This subpackage evaluates how well an LLM *understands* a Werewolf game when it
is given the rules and a single game situation. It is a small, objectively
gradable benchmark that complements the (subjective) trust-labeling engine:

- Stage A (`generate`): turn a game record into a quiz of question/answer pairs
  with known ground truth, derived deterministically from the same context the
  labeler sees.
- Stage B (`run_quiz`): ask a candidate LLM each question, then grade the answer
  against the ground truth (deterministic string match first, LLM-as-judge as a
  fallback for paraphrases).

The core modules are intentionally free of any langchain import so they can be
unit-tested without heavy dependencies. Only `llm_setup` imports langchain, and
it does so lazily at call time.
"""

from wolf_llm_labeling.quiz.models import (
    JudgeVerdict,
    QuestionResult,
    Quiz,
    QuizQuestion,
    QuizSet,
)

__all__ = [
    "JudgeVerdict",
    "QuestionResult",
    "Quiz",
    "QuizQuestion",
    "QuizSet",
]
