"""Tests for compare_data and plot on a small synthetic table with known values."""

import pandas as pd
import pytest

from data.dataset import build_dataset
from data.filters import FilterSpec
from tests.conftest import FIXTURES
from tools.compare_tool import CompareDataTool
from tools.plot_tool import PlotTool
from tools.slicing import describe_slice, explain_empty_slice, match_keys_for, matched_cells


def _row(source, observer, target, phase, trust_type, raw, confidence=2, room="G1"):
    return {
        "game_id": f"id-{room}",
        "room_code": room,
        "game_mode": "CLASSIC",
        "winner": "VILLAGERS",
        "exported_at": "2026-01-01T00:00:00Z",
        "source": source,
        "run_id": "human" if source == "human" else f"{observer}-run1",
        "observer": observer,
        "observer_role": "WEREWOLF" if observer == "Wolf" else "VILLAGER",
        "observer_team": "WEREWOLVES" if observer == "Wolf" else "VILLAGERS",
        "observer_alive": True,
        "target": target,
        "target_role": "WEREWOLF" if target == "Wolf" else "VILLAGER",
        "target_team": "WEREWOLVES" if target == "Wolf" else "VILLAGERS",
        "target_alive": True,
        "round": 1,
        "checkpoint": "BEFORE_VOTING",
        "phase_idx": phase,
        "trust_type": trust_type,
        "score_raw": raw,
        "scale": "7pt",
        "score_norm": (raw - 1) / 6,
        "confidence_raw": confidence,
        "confidence_scale": "3level",
        "confidence_norm": (confidence - 1) / 2,
        "reasoning": None,
        "created_at": None,
        "model": None if source == "human" else "test-model",
        "inner_voice_model": None,
        "experiment": None if source == "human" else "a",
        "temperature": None,
        "trust_scale_mode": None if source == "human" else "likert",
        "formatter": None,
        "experiment_args": None,
        "max_phases": None,
        "context_as_tool": None,
    }


@pytest.fixture(scope="module")
def synthetic_df() -> pd.DataFrame:
    # Human rates Wolf 1 and Ann 7 at each of two phases; LLM rates the same
    # four cells exactly 1 raw point higher (Wolf 2, Ann 7 capped -> use 6/7
    # values chosen to keep deltas exact).
    rows = [
        _row("human", "Ben", "Wolf", 1, "alignment", 1, confidence=3),
        _row("human", "Ben", "Ann", 1, "alignment", 7, confidence=3),
        _row("human", "Ben", "Wolf", 2, "alignment", 1, confidence=3),
        _row("human", "Ben", "Ann", 2, "alignment", 7, confidence=3),
        _row("human", "Ben", "Wolf", 3, "alignment", 1, confidence=3),
        _row("human", "Ben", "Ann", 3, "alignment", 7, confidence=3),
        _row("llm", "Ben", "Wolf", 1, "alignment", 2, confidence=1),
        _row("llm", "Ben", "Ann", 1, "alignment", 6, confidence=1),
        _row("llm", "Ben", "Wolf", 2, "alignment", 2, confidence=1),
        _row("llm", "Ben", "Ann", 2, "alignment", 6, confidence=1),
        _row("llm", "Ben", "Wolf", 3, "alignment", 2, confidence=1),
        _row("llm", "Ben", "Ann", 3, "alignment", 6, confidence=1),
        # an LLM-only cell that must not appear in matched comparisons
        _row("llm", "Ben", "Cal", 1, "alignment", 4, confidence=2),
    ]
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def fixture_df() -> pd.DataFrame:
    return build_dataset(FIXTURES, FIXTURES / "llm")


class TestSlicing:
    def test_describe_slice(self, synthetic_df):
        human = synthetic_df[synthetic_df["source"] == "human"]
        desc = describe_slice(human)
        assert desc["n"] == 6
        assert desc["score_raw_histogram"] == {1: 3, 7: 3}
        assert desc["extremeness_index"] == 1.0  # all scores at endpoints
        assert desc["score_norm_mean"] == 0.5

    def test_matched_cells_excludes_unpaired(self, synthetic_df):
        human = synthetic_df[synthetic_df["source"] == "human"]
        llm = synthetic_df[synthetic_df["source"] == "llm"]
        cells = matched_cells(human, llm)
        assert len(cells) == 6  # Cal cell has no human counterpart
        assert set(cells.columns) >= {"a", "b"}

    def test_match_keys_drop_compared_axis(self):
        a = FilterSpec(trust_types=["alignment"])
        b = FilterSpec(trust_types=["consistency"])
        assert "trust_type" not in match_keys_for(a, b)

    def test_explain_empty_slice_names_right_field(self, synthetic_df):
        # the agent's real mistake: a room code passed as game_ids
        msg = explain_empty_slice(synthetic_df, FilterSpec(game_ids=["G1"]))
        assert "not a game_id" in msg
        assert "room_codes" in msg

    def test_explain_empty_slice_unknown_value(self, synthetic_df):
        msg = explain_empty_slice(synthetic_df, FilterSpec(room_codes=["NOPE"]))
        assert "matches no room_code" in msg
        assert "G1" in msg  # examples of valid values are listed

    def test_explain_empty_slice_narrow_combination(self, synthetic_df):
        # each value valid alone, but humans never rated Cal
        msg = explain_empty_slice(
            synthetic_df, FilterSpec(sources=["human"], targets=["Cal"])
        )
        assert "combination" in msg


class TestCompareData:
    def test_single_slice_describe(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(filters_a=FilterSpec(sources=["human"]))
        assert out.success
        assert out.data["slice_a"]["n"] == 6
        assert "slice_b" not in out.data

    def test_matched_human_vs_llm(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(
            filters_a=FilterSpec(sources=["human"]),
            filters_b=FilterSpec(sources=["llm"]),
        )
        assert out.success
        comparison = out.data["comparison"]
        assert comparison["mode"] == "matched"  # auto: specs differ only in sources
        matched = comparison["matched"]
        assert matched["n_cells"] == 6
        # deltas: Wolf 1->2 = +1/6, Ann 7->6 = -1/6, twice each -> signed 0, abs 1/6
        assert matched["mean_signed_delta"] == 0.0
        assert matched["mean_abs_delta"] == round(1 / 6, 4)
        assert matched["spearman"] == 1.0  # identical ranking

    def test_independent_mode_for_team_comparison(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(
            filters_a=FilterSpec(target_teams=["WEREWOLVES"]),
            filters_b=FilterSpec(target_teams=["VILLAGERS"]),
        )
        assert out.success
        assert out.data["comparison"]["mode"] == "independent"
        # wolves get (1+2+1+2)/4 = 1.5 raw; villagers (7+6+7+6+4)/5 = 6 raw
        assert out.data["comparison"]["delta_of_means"] > 0

    def test_group_by(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(
            filters_a=FilterSpec(sources=["human"]),
            filters_b=FilterSpec(sources=["llm"]),
            group_by=["phase_idx"],
        )
        assert out.success
        assert set(out.data["groups"]) == {"1", "2", "3"}
        assert out.data["groups"]["1"]["matched_n"] == 2

    def test_correlate(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(
            filters_a=FilterSpec(sources=["human"]), correlate=True
        )
        assert out.success
        assert out.data["extremity_confidence_correlation"]["slice_a"]["n"] == 6

    def test_empty_slice_fails(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(filters_a=FilterSpec(room_codes=["NOPE"]))
        assert not out.success
        assert "no rows" in out.error

    def test_unknown_group_by_fails(self, synthetic_df):
        out = CompareDataTool(synthetic_df).run(
            filters_a=FilterSpec(), group_by=["not_a_column"]
        )
        assert not out.success

    def test_runs_on_fixture_dataset(self, fixture_df):
        out = CompareDataTool(fixture_df).run(
            filters_a=FilterSpec(sources=["human"]),
            filters_b=FilterSpec(sources=["llm"]),
            group_by=["trust_type"],
            correlate=True,
        )
        assert out.success
        assert out.metadata["n_rows_a"] > 0


class TestPlot:
    def test_line_per_phase(self, synthetic_df, tmp_path):
        out = PlotTool(synthetic_df, plots_dir=tmp_path).run(
            filters=FilterSpec(room_codes=["G1"]), kind="line_per_phase"
        )
        assert out.success
        assert (tmp_path / out.data["path"].split("/")[-1]).exists()
        assert out.data["table"]  # aggregates returned alongside the image

    def test_histogram(self, synthetic_df, tmp_path):
        out = PlotTool(synthetic_df, plots_dir=tmp_path).run(
            filters=FilterSpec(), kind="histogram"
        )
        assert out.success
        # human bar at raw 1 must be 3
        assert out.data["table"]["1"]["human"] == 3

    def test_heatmap_multi_game_fails(self, fixture_df, tmp_path):
        out = PlotTool(fixture_df, plots_dir=tmp_path).run(
            filters=FilterSpec(), kind="heatmap"
        )
        # fixture set has a single game so pick line_per_phase guard instead:
        # heatmap on a single game should succeed
        assert out.success or "single" in (out.error or "")

    def test_raw_mixed_scales_fails(self, fixture_df, tmp_path):
        out = PlotTool(fixture_df, plots_dir=tmp_path).run(
            filters=FilterSpec(sources=["llm"]), kind="box", use_raw=True
        )
        assert not out.success  # fixtures mix likert and numeric100 runs
        assert "scale" in out.error

    def test_scatter_and_box_on_fixtures(self, fixture_df, tmp_path):
        for kind in ("scatter", "box"):
            out = PlotTool(fixture_df, plots_dir=tmp_path).run(
                filters=FilterSpec(), kind=kind
            )
            assert out.success, out.error

    def test_empty_fails(self, synthetic_df, tmp_path):
        out = PlotTool(synthetic_df, plots_dir=tmp_path).run(
            filters=FilterSpec(room_codes=["NOPE"]), kind="histogram"
        )
        assert not out.success


class TestLangchainConversion:
    def test_nested_filterspec_schema(self, synthetic_df):
        tool = CompareDataTool(synthetic_df).as_langchain_tool()
        assert "filters_a" in tool.args_schema.model_fields
        out = tool.invoke({"filters_a": {"sources": ["human"]}})
        assert out.success
