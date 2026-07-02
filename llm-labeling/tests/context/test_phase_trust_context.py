from __future__ import annotations

import pytest

from wolf_llm_labeling.contexts import PhaseTrustContext
from wolf_llm_labeling.models import Label, Score, TrustScores


PhaseLabels = dict[str, dict[str, list[Label]]]


class FakeGameRecord:
    def __init__(self, phases: list[PhaseLabels]) -> None:
        self.phases = phases

    def get_phase_count(self) -> int:
        return len(self.phases)

    def get_labels(self, phase_idx: int) -> PhaseLabels:
        return self.phases[phase_idx]


def make_label(
    *,
    alignment: Score | None = None,
    information: Score | None = None,
    consistency: Score | None = None,
    reasoning: str = "",
) -> Label:
    return Label(
        trust_scores=TrustScores(
            alignment=alignment,
            information=information,
            consistency=consistency,
        ),
        reasoning=reasoning,
    )


def full_label(reasoning: str = "fixture reason") -> Label:
    return make_label(
        alignment=Score(2, 3),
        information=Score(3, 2),
        consistency=Score(4, 1),
        reasoning=reasoning,
    )


def render(context) -> str:
    assert context is not None
    return context.to_string()


def test_explicit_observer_renders_only_that_observer() -> None:
    record = FakeGameRecord(
        [
            {
                "Alice": {"Wolf": [full_label("alice reason")]},
                "Bob": {"Seer": [full_label("bob secret")]},
            }
        ]
    )

    output = render(PhaseTrustContext(player_name="Alice").get_context(record, 0))

    assert output == (
        "# Trust Labels\n\n"
        "## Wolf\n\n"
        "Alignment: trust 2/7, confidence 3/3\n"
        "Information: trust 3/7, confidence 2/3\n"
        "Consistency: trust 4/7, confidence 1/3\n"
        "Reasoning: alice reason"
    )
    assert "Bob" not in output
    assert "bob secret" not in output


def test_missing_explicit_observer_unknown_observer_and_empty_observer_return_none() -> None:
    record = FakeGameRecord([{"Alice": {"Wolf": [full_label()]}, "Empty": {}}])

    assert PhaseTrustContext().get_context(record, 0) is None
    assert PhaseTrustContext(player_name="Missing").get_context(record, 0) is None
    assert PhaseTrustContext(player_name="Empty").get_context(record, 0) is None


def test_offset_selects_requested_or_previous_phase_and_rejects_out_of_range_phase() -> None:
    record = FakeGameRecord(
        [
            {"Alice": {"Wolf": [full_label("phase zero")]}},
            {"Alice": {"Wolf": [full_label("phase one")]}},
        ]
    )

    assert "phase one" in render(PhaseTrustContext(offset=0, player_name="Alice").get_context(record, 1))
    assert "phase zero" in render(PhaseTrustContext(offset=1, player_name="Alice").get_context(record, 1))
    assert PhaseTrustContext(offset=1, player_name="Alice").get_context(record, 0) is None
    assert PhaseTrustContext(player_name="Alice").get_context(record, 2) is None


@pytest.mark.parametrize("offset", [True, False, "1", 1.5])
def test_offset_must_be_integer_not_bool(offset: object) -> None:
    with pytest.raises(TypeError):
        PhaseTrustContext(offset=offset)  # type: ignore[arg-type]


def test_negative_offset_raises_value_error() -> None:
    with pytest.raises(ValueError):
        PhaseTrustContext(offset=-1)


def test_injected_trust_overrides_game_record_and_needs_no_observer() -> None:
    record = FakeGameRecord([{"Alice": {"Wolf": [full_label("record reason")]}}])
    context = PhaseTrustContext(
        injected_trust=[{"Wolf": full_label("injected reason")}],
    ).get_context(record, 0)

    output = render(context)

    assert "injected reason" in output
    assert "record reason" not in output


@pytest.mark.parametrize("injected_trust", [[], [{}]])
def test_empty_injected_trust_returns_none_without_fallback(injected_trust: list[dict[str, Label]]) -> None:
    record = FakeGameRecord([{"Alice": {"Wolf": [full_label("record reason")]}}])

    assert PhaseTrustContext(injected_trust=injected_trust, player_name="Alice").get_context(record, 0) is None


def test_too_short_injected_trust_returns_none_without_fallback() -> None:
    record = FakeGameRecord(
        [
            {"Alice": {"Wolf": [full_label("phase zero")]}},
            {"Alice": {"Wolf": [full_label("phase one")]}},
        ]
    )

    assert PhaseTrustContext(injected_trust=[{"Wolf": full_label("injected")}], player_name="Alice").get_context(record, 1) is None


def test_injected_trust_order_is_preserved_and_outer_containers_are_detached() -> None:
    phase = {
        "Wolf": full_label("first"),
        "Seer": full_label("second"),
    }
    injected = [phase]
    context_provider = PhaseTrustContext(injected_trust=injected)
    injected.append({"Late": full_label("late list")})
    phase["Late"] = full_label("late dict")

    output = render(context_provider.get_context(FakeGameRecord([{}]), 0))

    assert output == (
        "# Trust Labels\n\n"
        "## Wolf\n\n"
        "Alignment: trust 2/7, confidence 3/3\n"
        "Information: trust 3/7, confidence 2/3\n"
        "Consistency: trust 4/7, confidence 1/3\n"
        "Reasoning: first\n\n"
        "## Seer\n\n"
        "Alignment: trust 2/7, confidence 3/3\n"
        "Information: trust 3/7, confidence 2/3\n"
        "Consistency: trust 4/7, confidence 1/3\n"
        "Reasoning: second"
    )


def test_missing_dimensions_and_reasoning_are_omitted_or_trimmed() -> None:
    record = FakeGameRecord(
        [
            {
                "Alice": {
                    "NoAlignment": [make_label(information=Score(5, 2), consistency=Score(6, 1), reasoning="  trimmed  ")],
                    "NoInformation": [make_label(alignment=Score(1, 3), consistency=Score(2, 2), reasoning="")],
                    "NoConsistency": [make_label(alignment=Score(3, 1), information=Score(4, 2), reasoning="   ")],
                }
            }
        ]
    )

    output = render(PhaseTrustContext(player_name="Alice").get_context(record, 0))

    assert "## NoAlignment\n\nInformation: trust 5/7, confidence 2/3\nConsistency: trust 6/7, confidence 1/3\nReasoning: trimmed" in output
    assert "## NoInformation\n\nAlignment: trust 1/7, confidence 3/3\nConsistency: trust 2/7, confidence 2/3" in output
    assert "## NoConsistency\n\nAlignment: trust 3/7, confidence 1/3\nInformation: trust 4/7, confidence 2/3" in output
    assert "Reasoning:\n" not in output


def test_multiple_labels_are_numbered_after_empty_labels_are_omitted() -> None:
    empty = make_label()
    first = make_label(alignment=Score(2, 3), reasoning="first reason")
    second = make_label(information=Score(5, 2), reasoning="second reason")
    record = FakeGameRecord([{"Alice": {"Wolf": [empty, first, second]}}])

    output = render(PhaseTrustContext(player_name="Alice").get_context(record, 0))

    assert output == (
        "# Trust Labels\n\n"
        "## Wolf\n\n"
        "Label 1:\n"
        "Alignment: trust 2/7, confidence 3/3\n"
        "Reasoning: first reason\n\n"
        "Label 2:\n"
        "Information: trust 5/7, confidence 2/3\n"
        "Reasoning: second reason"
    )


def test_empty_targets_are_omitted_and_all_empty_returns_none() -> None:
    empty = make_label(reasoning="   ")
    mixed_record = FakeGameRecord(
        [
            {
                "Alice": {
                    "EmptyTarget": [empty],
                    "RenderableTarget": [make_label(alignment=Score(7, 3))],
                }
            }
        ]
    )
    empty_record = FakeGameRecord([{"Alice": {"EmptyTarget": [empty]}}])

    output = render(PhaseTrustContext(player_name="Alice").get_context(mixed_record, 0))

    assert "EmptyTarget" not in output
    assert "RenderableTarget" in output
    assert PhaseTrustContext(player_name="Alice").get_context(empty_record, 0) is None


def test_phase_trust_context_topness_is_zero() -> None:
    assert PhaseTrustContext().get_topness() == 0.0
