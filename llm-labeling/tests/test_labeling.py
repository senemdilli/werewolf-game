from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import pytest

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import Label, Score, TrustScores, ReportLabelsArgs, SinglePlayerLabel, LabelSchema, TrustScoresSchema, ScoreSchema
from wolf_llm_labeling.contexts import ContextProvider, Ctx
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.labeling import label_once


# Simple Mock Context Provider
class DummyContextProvider:
    player_name = "Villager"
    
    def get_context(self, game_record: GameRecord, phase_idx: int) -> Ctx:
        return Ctx(header="Game Information", content="Mock context content")
        
    @staticmethod
    def get_topness() -> float:
        return 100.0


# Mock LLM provider
class MockChatModel:
    def __init__(self, responses: list[Any]):
        self.responses = responses
        self.invocations = []
        self.tools_bound = None

    def bind_tools(self, tools: list[Any], *args: Any, **kwargs: Any) -> MockChatModel:
        self.tools_bound = tools
        return self

    def invoke(self, messages: list[Any]) -> Any:
        self.invocations.append(messages)
        if self.responses:
            return self.responses.pop(0)
        
        from langchain_core.messages import AIMessage
        return AIMessage(content="")

    def with_structured_output(self, schema: Any) -> Any:
        structured_mock = MagicMock()
        # Mocking the response for the fallback structured invoke call
        structured_mock.invoke.return_value = ReportLabelsArgs(
            labels=[
                SinglePlayerLabel(
                    player_name="Wolf",
                    label=LabelSchema(
                        trust_scores=TrustScoresSchema(
                            alignment=ScoreSchema(trust=5, confidence=3),
                            strategic=None,
                            consistency=None,
                        ),
                        reasoning="fallback logic reasoning",
                    )
                )
            ]
        )
        return structured_mock


def test_label_once_via_tool_call(tmp_path: Path) -> None:
    # Setup a dummy game records export
    from game_record.conftest import write_export
    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    # Mock response from LLM calling
    from langchain_core.messages import AIMessage
    tool_call_response = AIMessage(
        content="",
        tool_calls=[{
            "name": "report_labels",
            "args": {
                "labels": [
                    {
                        "player_name": "Wolf",
                        "label": {
                            "trust_scores": {
                                "alignment": {"trust": 6, "confidence": 3},
                                "strategic": None,
                                "consistency": None,
                            },
                            "reasoning": "we caught him",
                        }
                    }
                ]
            },
            "id": "call_123"
        }]
    )
    
    llm = MockChatModel([tool_call_response])
    context = DummyContextProvider()
    
    labels, call_info = label_once(
        llm_provider=llm,
        system_prompt="You are a villager",
        context=context,
        inner_voice=None,
        game_data=record,
        phase_idx=0,
    )
    
    assert "Wolf" in labels
    assert labels["Wolf"].trust_scores.alignment.trust == 6
    assert labels["Wolf"].reasoning == "we caught him"
    assert call_info.provider_name == "MockChatModel"
    assert call_info.context == "# Game Information\n\nMock context content"
    assert len(call_info.tool_calls) == 1
    assert call_info.tool_calls[0]["name"] == "report_labels"


def test_label_once_structured_fallback(tmp_path: Path) -> None:
    # Setup a dummy game records export
    from game_record.conftest import write_export
    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    # Mock response that doesn't call any tools
    from langchain_core.messages import AIMessage
    conversational_response = AIMessage(
        content="I think Wolf is suspicious but I am not ready to report yet."
    )
    
    llm = MockChatModel([conversational_response])
    context = DummyContextProvider()
    
    labels, call_info = label_once(
        llm_provider=llm,
        system_prompt="You are a villager",
        context=context,
        inner_voice=None,
        game_data=record,
        phase_idx=0,
    )
    
    # Assert fallback logic successfully triggered and parsed values
    assert "Wolf" in labels
    assert labels["Wolf"].trust_scores.alignment.trust == 5
    assert labels["Wolf"].reasoning == "fallback logic reasoning"
