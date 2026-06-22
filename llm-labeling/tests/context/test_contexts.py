from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wolf_llm_labeling.contexts import Ctx


@pytest.mark.parametrize(
    ("ctx", "expected"),
    [
        (Ctx(), ""),
        (Ctx(header="Title"), "# Title"),
        (Ctx(content="Text"), "Text"),
        (Ctx(header="Title", content="Text"), "# Title\n\nText"),
        (Ctx(header="   ", content="Text"), "Text"),
        (Ctx(header="Title", content="\n\t"), "# Title"),
        (Ctx(header="  Header  ", content="\nLine one\nLine two\n"), "# Header\n\nLine one\nLine two"),
        (Ctx(content="**bold**\n\n- item"), "**bold**\n\n- item"),
    ],
)
def test_basic_rendering(ctx: Ctx, expected: str) -> None:
    assert ctx.to_string() == expected


def test_hierarchy_rendering() -> None:
    ctx = Ctx(
        header="Game State",
        content="Current information.",
        subsections=[
            Ctx(header="Last night", content="Charles died."),
            Ctx(header="Current day", content="The village is discussing."),
        ],
    )

    assert (
        ctx.to_string()
        == "# Game State\n\n"
        "Current information.\n\n"
        "## Last night\n\n"
        "Charles died.\n\n"
        "## Current day\n\n"
        "The village is discussing."
    )


def test_headerless_wrappers_do_not_increase_heading_depth() -> None:
    assert Ctx(subsections=[Ctx(header="A")]).to_string() == "# A"
    assert Ctx(content="Introduction", subsections=[Ctx(header="Section")]).to_string() == "Introduction\n\n# Section"
    assert Ctx(header="Root", subsections=[Ctx(subsections=[Ctx(header="Leaf")])]).to_string() == "# Root\n\n## Leaf"


def test_empty_children_are_omitted() -> None:
    ctx = Ctx(
        header="Parent",
        subsections=[
            Ctx(),
            Ctx(header="Child"),
            Ctx(content="   "),
            Ctx(subsections=[Ctx(header=" "), Ctx(content="\n")]),
        ],
    )

    assert ctx.to_string() == "# Parent\n\n## Child"


def test_nested_visible_headings_and_depth_cap() -> None:
    ctx = Ctx(header="Level 8")
    for level in range(7, 0, -1):
        ctx = Ctx(header=f"Level {level}", subsections=[ctx])

    assert ctx.to_string() == "\n\n".join(
        [
            "# Level 1",
            "## Level 2",
            "### Level 3",
            "#### Level 4",
            "##### Level 5",
            "###### Level 6",
            "###### Level 7",
            "###### Level 8",
        ]
    )


@pytest.mark.parametrize(
    "ctx",
    [
        Ctx(),
        Ctx(header=""),
        Ctx(header="   "),
        Ctx(content=""),
        Ctx(content="\n\t"),
        Ctx(subsections=[Ctx()]),
        Ctx(subsections=[Ctx(header=" "), Ctx(content="\n")]),
    ],
)
def test_is_empty_true(ctx: Ctx) -> None:
    assert ctx.is_empty()


@pytest.mark.parametrize(
    "ctx",
    [
        Ctx(header="Title"),
        Ctx(content="Text"),
        Ctx(subsections=[Ctx(header="Child")]),
        Ctx(subsections=[Ctx(content="Child content")]),
    ],
)
def test_is_empty_false(ctx: Ctx) -> None:
    assert not ctx.is_empty()


def test_subsection_storage_is_immutable_and_detached() -> None:
    child = Ctx(header="Child")
    original = [child]
    ctx = Ctx(subsections=original)
    original.append(Ctx(header="Late"))

    assert ctx.subsections == (child,)
    assert isinstance(ctx.subsections, tuple)
    with pytest.raises(AttributeError):
        ctx.subsections.append(Ctx())  # type: ignore[attr-defined]


def test_subsections_accept_tuple_and_generator_and_keep_order() -> None:
    first = Ctx(header="First")
    second = Ctx(header="Second")

    assert Ctx(subsections=(first, second)).to_string() == "# First\n\n# Second"
    assert Ctx(subsections=(child for child in [first, second])).to_string() == "# First\n\n# Second"


@pytest.mark.parametrize("bad_value", [None, "not a context"])
def test_invalid_subsections_raise_type_error(bad_value: object) -> None:
    with pytest.raises(TypeError, match="Ctx subsections must be Ctx instances"):
        Ctx(subsections=[bad_value])  # type: ignore[list-item]


def test_ctx_attributes_are_mutable() -> None:
    ctx = Ctx(header="Old", content="Before")

    ctx.header = "New"
    ctx.content = "After"

    assert ctx.to_string() == "# New\n\nAfter"


def test_rendering_is_idempotent_and_does_not_mutate_fields() -> None:
    child = Ctx(header="Child")
    ctx = Ctx(header="Parent", content="Body", subsections=[child])
    before = (ctx.header, ctx.content, ctx.subsections)

    assert ctx.to_string() == ctx.to_string()
    assert str(ctx) == ctx.to_string()
    assert (ctx.header, ctx.content, ctx.subsections) == before


def test_contexts_module_imports() -> None:
    import wolf_llm_labeling.contexts

    assert wolf_llm_labeling.contexts.Ctx is Ctx


def test_contexts_module_imports_in_fresh_interpreter() -> None:
    src = Path(__file__).parents[2] / "src"
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(src) if not existing_pythonpath else f"{src}{os.pathsep}{existing_pythonpath}"

    subprocess.run(
        [sys.executable, "-c", "import wolf_llm_labeling.contexts"],
        check=True,
        env=env,
    )
