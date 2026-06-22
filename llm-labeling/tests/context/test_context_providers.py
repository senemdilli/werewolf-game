from __future__ import annotations

from wolf_llm_labeling.contexts import (
    ContextProvider,
    Ctx,
    GameNowContext,
    JoinedContext,
    StaticContext,
)
from wolf_llm_labeling.game_records import GameRecord


class FakeProvider:
    def get_context(self, game_record: GameRecord, phase_idx: int) -> Ctx | None:
        return Ctx(content="example")

    def get_topness(self) -> float:
        return 10.0


def materialize_provider(
    provider: ContextProvider,
    game_record: GameRecord,
    phase_idx: int,
) -> tuple[Ctx | None, float]:
    return provider.get_context(game_record, phase_idx), provider.get_topness()


def test_structural_provider_works_without_inheriting_from_protocol() -> None:
    provider = FakeProvider()

    ctx, topness = materialize_provider(provider, GameRecord(), 0)

    assert ctx is not None
    assert ctx.to_string() == "example"
    assert topness == 10.0
    assert FakeProvider.__bases__ == (object,)


def test_implemented_provider_topness_is_instance_method() -> None:
    assert StaticContext("Brown").get_topness() == 100.0
    assert GameNowContext("Brown").get_topness() == 50.0


def test_joined_context_accepts_structural_provider_constructor_argument() -> None:
    JoinedContext(None, None, 0.0, FakeProvider())
