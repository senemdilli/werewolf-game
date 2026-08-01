"""Tests for the implemented inner-voice variants."""

from types import SimpleNamespace

import pytest

from wolf_llm_labeling.inner_voice import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    TRUST_MAX,
    TRUST_MIN,
    ConstantInnerVoice,
    HumanHistoricInnerVoice,
    RandomInnerVoice,
)
from wolf_llm_labeling.models import Score, TrustScores


class FakeGameRecord:
    """Minimal stand-in exposing only get_labels, which is all the voices use."""

    def __init__(self, labels):
        self._labels = labels

    def get_labels(self, phase_idx):
        return self._labels


def _label(trust_scores):
    return SimpleNamespace(trust_scores=trust_scores)


def _categories(scores):
    return [scores.alignment, scores.information, scores.consistency]


class TestRandomInnerVoice:
    def test_scores_within_valid_ranges(self):
        voice = RandomInnerVoice()
        for _ in range(200):
            scores = voice.ask("bob", None, None, 0)
            for category in _categories(scores):
                assert TRUST_MIN <= category.trust <= TRUST_MAX
                assert CONFIDENCE_MIN <= category.confidence <= CONFIDENCE_MAX

    def test_tool_description_is_nonempty(self):
        assert RandomInnerVoice().tool_description().strip()


class TestConstantInnerVoice:
    def test_returns_configured_trust_scores_for_every_player(self):
        scores = TrustScores(
            alignment=Score(2, 1),
            information=Score(3, 2),
            consistency=Score(4, 3),
        )
        voice = ConstantInnerVoice(scores)

        assert voice.ask("alice", None, None, 0) == scores
        assert voice.ask("bob", None, None, 0) == scores

    def test_single_score_is_used_for_all_dimensions(self):
        score = Score(5, 2)
        scores = ConstantInnerVoice(score).ask("alice", None, None, 0)

        assert scores.alignment == score
        assert scores.information == score
        assert scores.consistency == score

    def test_tool_description_is_nonempty(self):
        assert ConstantInnerVoice(Score(4, 1)).tool_description().strip()


class TestHumanHistoricInnerVoice:
    def test_returns_latest_label_for_observer_and_target(self):
        latest = object()
        records = FakeGameRecord({"alice": {"bob": [_label(object()), _label(latest)]}})
        voice = HumanHistoricInnerVoice("alice")

        assert voice.ask("bob", None, records, 0) is latest

    def test_neutral_fallback_when_no_labels_at_all(self):
        voice = HumanHistoricInnerVoice("alice")
        scores = voice.ask("bob", None, FakeGameRecord({}), 0)
        self._assert_neutral(scores)

    def test_neutral_fallback_when_observer_missing(self):
        records = FakeGameRecord({"someone_else": {"bob": [_label(object())]}})
        scores = HumanHistoricInnerVoice("alice").ask("bob", None, records, 0)
        self._assert_neutral(scores)

    def test_neutral_fallback_when_target_missing(self):
        records = FakeGameRecord({"alice": {"charlie": [_label(object())]}})
        scores = HumanHistoricInnerVoice("alice").ask("bob", None, records, 0)
        self._assert_neutral(scores)

    def test_neutral_fallback_when_get_labels_returns_none(self):
        records = FakeGameRecord(None)
        scores = HumanHistoricInnerVoice("alice").ask("bob", None, records, 0)
        self._assert_neutral(scores)

    def test_tool_description_mentions_observer(self):
        assert "alice" in HumanHistoricInnerVoice("alice").tool_description()

    @staticmethod
    def _assert_neutral(scores):
        midpoint = (TRUST_MIN + TRUST_MAX) // 2
        for category in _categories(scores):
            assert category.trust == midpoint
            assert category.confidence == 2
