import pandas as pd
import pytest

from data.dataset import build_dataset
from data.filters import FilterSpec
from tools.correlation_tool import CorrelationTool

from tests.conftest import FIXTURES


@pytest.fixture(scope="module")
def df():
    return build_dataset(FIXTURES, FIXTURES / "llm")


@pytest.fixture(scope="module")
def tool(df):
    return CorrelationTool(df)


class TestSliceDescription:
    """Real-fixture coverage: per-slice extremity + extremity/confidence
    correlation, independent of whether the two slices share any cells.
    """

    def test_human_slice_extremity(self, tool):
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.success
        # hand-computed: mean(|score_norm - 0.5| * 2) over the 8 human rows
        assert out.data["slice_a"]["n"] == 8
        assert out.data["slice_a"]["mean_extremity"] == pytest.approx(0.5)
        assert out.data["slice_a"]["frac_at_extreme"] == pytest.approx(0.125)  # only Carol->Alpha alignment=0

    def test_llm_slice_extremity(self, tool):
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.data["slice_b"]["n"] == 11

    def test_extremity_confidence_spearman_present_when_enough_rows(self, tool):
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.data["slice_a"]["extremity_confidence_spearman"] is not None
        assert out.data["slice_b"]["extremity_confidence_spearman"] is not None


class TestFailureModes:
    def test_filters_a_empty_fails_cleanly(self, tool):
        out = tool.run(filters_a=FilterSpec(game_ids=["does-not-exist"]), filters_b=FilterSpec(sources=["llm"]))
        assert not out.success
        assert "filters_a" in out.error

    def test_filters_b_empty_fails_cleanly(self, tool):
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(game_ids=["does-not-exist"]))
        assert not out.success
        assert "filters_b" in out.error

    def test_unknown_group_by_column_fails_cleanly(self, tool):
        out = tool.run(
            filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]),
            group_by=["not_a_column"],
        )
        assert not out.success
        assert "not_a_column" in out.error

    def test_no_matched_cells_is_a_warning_not_a_crash(self, tool):
        # this fixture's LLM rows label the opposite direction from the human
        # rows (Alpha labels Bravo/Carol; Bravo/Carol label Alpha), so there
        # is no real overlap — same situation as DeltaTool hits here.
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.success
        assert out.data["comparison"]["matched"]["n_cells"] == 0
        assert "no matched cells" in out.metadata["warnings"][0]


class TestMatchedComparisonOnSyntheticData:
    """Needs real observer/target/phase overlap between the two slices,
    which the shared fixtures don't have — same reasoning as DeltaTool's
    synthetic-data test.
    """

    @pytest.fixture
    def synthetic_df(self):
        return pd.DataFrame([
            # matched cell, phase 1: human near midpoint, llm at the endpoint
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 1,
             "source": "human", "trust_type": "alignment", "score_norm": 0.5, "confidence_norm": 0.5},
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 1,
             "source": "llm", "trust_type": "alignment", "score_norm": 1.0, "confidence_norm": 0.0},
            # matched cell, phase 2: both at the endpoint, no delta
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 2,
             "source": "human", "trust_type": "alignment", "score_norm": 0.0, "confidence_norm": 1.0},
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 2,
             "source": "llm", "trust_type": "alignment", "score_norm": 0.0, "confidence_norm": 1.0},
            # unmatched: llm-only cell (different observer), dropped from matching
            {"game_id": "g1", "room_code": "TEST01", "observer": "Carol", "target": "Alpha", "phase_idx": 1,
             "source": "llm", "trust_type": "alignment", "score_norm": 1.0, "confidence_norm": 0.2},
        ])

    def test_matches_only_shared_cells(self, synthetic_df):
        tool = CorrelationTool(synthetic_df)
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.success
        matched = out.data["comparison"]["matched"]
        assert matched["n_cells"] == 2
        assert matched["mean_signed_delta"] == pytest.approx(0.5)  # (1.0-0.5 + 0.0-0.0) / 2

    def test_slice_b_includes_unmatched_row(self, synthetic_df):
        tool = CorrelationTool(synthetic_df)
        out = tool.run(filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]))
        assert out.data["slice_b"]["n"] == 3  # Carol's row counts in the slice, just not the match

    def test_group_by_phase(self, synthetic_df):
        tool = CorrelationTool(synthetic_df)
        out = tool.run(
            filters_a=FilterSpec(sources=["human"]), filters_b=FilterSpec(sources=["llm"]),
            group_by=["phase_idx"],
        )
        assert out.success
        groups = out.data["groups"]
        assert groups["1"]["extremity_delta"] == pytest.approx(1.0)  # human 0.5->extremity 0, llm 1.0->extremity 1
        assert groups["2"]["extremity_delta"] == pytest.approx(0.0)
