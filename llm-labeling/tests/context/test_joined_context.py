from __future__ import annotations

from wolf_llm_labeling.contexts import Ctx, JoinedContext
from wolf_llm_labeling.game_records import GameRecord


class FakeProvider:
    def __init__(
        self,
        context: Ctx | None,
        topness: float,
        name: str = "",
        call_log: list[str] | None = None,
    ) -> None:
        self.context = context
        self.topness = topness
        self.name = name
        self.call_log = call_log
        self.context_calls = 0
        self.topness_calls = 0

    def get_context(self, game_record: GameRecord, phase_idx: int) -> Ctx | None:
        self.context_calls += 1
        if self.call_log is not None:
            self.call_log.append(self.name)
        return self.context

    def get_topness(self) -> float:
        self.topness_calls += 1
        return self.topness


class FailingProvider:
    def get_context(self, game_record: GameRecord, phase_idx: int) -> Ctx | None:
        raise RuntimeError("child failed")

    def get_topness(self) -> float:
        return 1.0


def test_joined_context_topness_comes_from_instance() -> None:
    assert JoinedContext(None, "body", 12.5).get_topness() == 12.5


def test_joined_context_returns_none_for_header_only_whitespace_or_empty_children() -> None:
    record = GameRecord()
    empty_child = FakeProvider(Ctx(header=" "), 100.0)
    none_child = FakeProvider(None, 50.0)

    assert JoinedContext("Header", None, 0.0).get_context(record, 0) is None
    assert JoinedContext("Header", "   ", 0.0).get_context(record, 0) is None
    assert JoinedContext(None, None, 0.0, empty_child, none_child).get_context(record, 0) is None


def test_joined_context_keeps_own_content_without_children() -> None:
    context = JoinedContext("Header", "body", 0.0).get_context(GameRecord(), 0)

    assert context is not None
    assert context.to_string() == "# Header\n\nbody"


def test_joined_context_drops_empty_children_and_sorts_by_topness_stably() -> None:
    record = GameRecord()
    none_child = FakeProvider(None, 500.0)
    empty_child = FakeProvider(Ctx(), 999.0)
    joined = JoinedContext(
        "Combined",
        "intro",
        0.0,
        FakeProvider(Ctx(header="Low", content="low"), 10.0),
        none_child,
        FakeProvider(Ctx(header="Equal A", content="a"), 20.0),
        empty_child,
        FakeProvider(Ctx(header="High", content="high"), 100.0),
        FakeProvider(Ctx(header="Equal B", content="b"), 20.0),
    )

    context = joined.get_context(record, 0)

    assert context is not None
    assert (
        context.to_string()
        == "# Combined\n\n"
        "intro\n\n"
        "## High\n\n"
        "high\n\n"
        "## Equal A\n\n"
        "a\n\n"
        "## Equal B\n\n"
        "b\n\n"
        "## Low\n\n"
        "low"
    )
    assert none_child.topness_calls == 0
    assert empty_child.topness_calls == 0


def test_joined_context_materializes_children_once_in_constructor_order() -> None:
    call_log: list[str] = []
    low = FakeProvider(Ctx(content="low"), 1.0, "low", call_log)
    high = FakeProvider(Ctx(content="high"), 10.0, "high", call_log)
    empty = FakeProvider(Ctx(), 100.0, "empty", call_log)
    none = FakeProvider(None, 1000.0, "none", call_log)

    context = JoinedContext(None, None, 0.0, low, high, empty, none).get_context(GameRecord(), 0)

    assert context is not None
    assert context.to_string() == "high\n\nlow"
    assert call_log == ["low", "high", "empty", "none"]
    assert [low.context_calls, high.context_calls, empty.context_calls, none.context_calls] == [1, 1, 1, 1]
    assert [low.topness_calls, high.topness_calls, empty.topness_calls, none.topness_calls] == [1, 1, 0, 0]


def test_joined_context_child_exceptions_propagate() -> None:
    try:
        JoinedContext(None, None, 0.0, FailingProvider()).get_context(GameRecord(), 0)
    except RuntimeError as exc:
        assert str(exc) == "child failed"
    else:
        raise AssertionError("expected child exception to propagate")


def test_nested_joined_context_keeps_inner_grouping_and_ordering() -> None:
    inner = JoinedContext(
        "Inner",
        None,
        50.0,
        FakeProvider(Ctx(header="Inner Low", content="low"), 1.0),
        FakeProvider(Ctx(header="Inner High", content="high"), 10.0),
    )
    outer = JoinedContext(
        "Outer",
        None,
        0.0,
        FakeProvider(Ctx(header="Outer High", content="outer"), 100.0),
        inner,
        JoinedContext("Empty Inner", None, 999.0),
    )

    context = outer.get_context(GameRecord(), 0)

    assert context is not None
    assert (
        context.to_string()
        == "# Outer\n\n"
        "## Outer High\n\n"
        "outer\n\n"
        "## Inner\n\n"
        "### Inner High\n\n"
        "high\n\n"
        "### Inner Low\n\n"
        "low"
    )


def test_joined_context_child_storage_is_tuple_and_detached_from_source_list() -> None:
    providers = [FakeProvider(Ctx(content="first"), 1.0)]
    joined = JoinedContext(None, None, 0.0, *providers)
    providers.append(FakeProvider(Ctx(content="late"), 100.0))

    assert isinstance(joined.sub_contexts, tuple)
    assert len(joined.sub_contexts) == 1
    assert joined.get_context(GameRecord(), 0).to_string() == "first"  # type: ignore[union-attr]


def test_joined_context_is_repeatable() -> None:
    joined = JoinedContext(None, "intro", 0.0, FakeProvider(Ctx(content="child"), 1.0))
    record = GameRecord()

    first = joined.get_context(record, 0)
    second = joined.get_context(record, 0)

    assert first is not None
    assert second is not None
    assert first.to_string() == second.to_string() == "intro\n\nchild"
