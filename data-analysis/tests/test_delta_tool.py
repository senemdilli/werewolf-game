import pandas as pd
import pytest

from data.dataset import build_dataset
from data.filters import FilterSpec
from tools.delta_tool import DeltaTool

from tests.conftest import FIXTURES


@pytest.fixture(scope="module")
def df():
    return build_dataset(FIXTURES, FIXTURES / "llm")


@pytest.fixture(scope="module")
def tool(df):
    return DeltaTool(df)


class TestTrustTypeDelta:
    """Real-fixture coverage: alignment vs consistency is populated on every
    row in tests/fixtures, unlike source (llm/human label disjoint players
    there), so it's the axis that exercises the matched-cell join end to end.
    """

    def test_no_group_by(self, tool):
        out = tool.run(filters=FilterSpec(), compare="trust_type", value_a="alignment", value_b="consistency")
        assert out.success
        assert out.metadata["n_matched_cells"] == 7
        assert out.data[0]["n"] == 7
        assert out.data[0]["mean_delta"] == pytest.approx(-0.0865800865800865)

    def test_group_by_source(self, tool):
        out = tool.run(
            filters=FilterSpec(), compare="trust_type", value_a="alignment", value_b="consistency",
            group_by=["source"],
        )
        assert out.success
        by_source = {row["source"]: row for row in out.data}
        assert by_source["human"]["n"] == 3
        assert by_source["human"]["mean_delta"] == pytest.approx(-1 / 6)
        assert by_source["llm"]["n"] == 4

    def test_unknown_group_by_column_fails(self, tool):
        out = tool.run(
            filters=FilterSpec(), compare="trust_type", value_a="alignment", value_b="consistency",
            group_by=["not_a_column"],
        )
        assert not out.success
        assert "not_a_column" in out.error

    def test_compare_is_case_insensitive(self, tool):
        out = tool.run(filters=FilterSpec(), compare="trust_type", value_a="ALIGNMENT", value_b="Consistency")
        assert out.success
        assert out.metadata["n_matched_cells"] == 7


class TestNoOverlapIsAFailureNotACrash:
    def test_source_delta_has_no_overlap_in_fixtures(self, tool):
        # LLM runs here label the opposite direction from the human rows
        # (Alpha labels Bravo/Carol; Bravo/Carol label Alpha) so no cell
        # matches on (game, observer, target, phase) across sources.
        out = tool.run(filters=FilterSpec(), compare="source", value_a="llm", value_b="human")
        assert not out.success
        assert "no matched cells" in out.error

    def test_filters_excluding_everything_fails_cleanly(self, tool):
        out = tool.run(
            filters=FilterSpec(game_ids=["does-not-exist"]),
            compare="trust_type", value_a="alignment", value_b="consistency",
        )
        assert not out.success
        assert "filters match no rows" in out.error
        assert "matches no game_id" in out.error  # names the offending value

    def test_unknown_compare_value_fails_cleanly(self, tool):
        out = tool.run(
            filters=FilterSpec(), compare="trust_type", value_a="alignment", value_b="does-not-exist",
        )
        assert not out.success
        assert "does-not-exist" in out.error


class TestSourceDeltaOnSyntheticData:
    """Source vs source (the human-vs-LLM comparison from compare_llm.py)
    needs a case with real overlap, which the shared fixtures don't have.
    """

    @pytest.fixture
    def synthetic_df(self):
        return pd.DataFrame([
            # matched cell, phase 1: llm rates 0.4 higher than human
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 1,
             "source": "human", "trust_type": "alignment", "score_norm": 0.5},
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 1,
             "source": "llm", "trust_type": "alignment", "score_norm": 0.9},
            # matched cell, phase 2: no delta
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 2,
             "source": "human", "trust_type": "alignment", "score_norm": 0.2},
            {"game_id": "g1", "room_code": "TEST01", "observer": "Bravo", "target": "Alpha", "phase_idx": 2,
             "source": "llm", "trust_type": "alignment", "score_norm": 0.2},
            # unmatched: llm-only cell, no human counterpart -> dropped
            {"game_id": "g1", "room_code": "TEST01", "observer": "Carol", "target": "Alpha", "phase_idx": 1,
             "source": "llm", "trust_type": "alignment", "score_norm": 0.7},
        ])

    def test_matches_only_shared_cells(self, synthetic_df):
        tool = DeltaTool(synthetic_df)
        out = tool.run(filters=FilterSpec(), compare="source", value_a="llm", value_b="human")
        assert out.success
        assert out.metadata["n_matched_cells"] == 2
        assert out.data[0]["mean_delta"] == pytest.approx(0.2)
        assert out.data[0]["mean_abs_delta"] == pytest.approx(0.2)

    def test_group_by_phase(self, synthetic_df):
        tool = DeltaTool(synthetic_df)
        out = tool.run(
            filters=FilterSpec(), compare="source", value_a="llm", value_b="human", group_by=["phase_idx"],
        )
        assert out.success
        by_phase = {row["phase_idx"]: row["mean_delta"] for row in out.data}
        assert by_phase[1] == pytest.approx(0.4)
        assert by_phase[2] == pytest.approx(0.0)
