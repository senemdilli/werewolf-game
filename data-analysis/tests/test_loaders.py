import pytest

from data.loaders.human_loader import human_rows
from data.loaders.llm_loader import llm_rows


class TestHumanRows:
    @pytest.fixture
    def rows(self, human_labels, events_file):
        return human_rows(human_labels, events_file)

    def test_row_count_skips_null_trust_dicts(self, rows):
        # label-1: Alpha has 2 non-null dims, Delta has 3; label-2: Alpha has 3
        assert len(rows) == 8

    def test_phase_alignment(self, rows):
        by_key = {(r["round"], r["checkpoint"]) for r in rows}
        assert by_key == {(1, "BEFORE_VOTING"), (2, "BEFORE_DISCUSSION")}
        assert all(
            r["phase_idx"] == (1 if r["round"] == 1 else 3) for r in rows
        )

    def test_teams_and_roles(self, rows):
        row = next(r for r in rows if r["observer"] == "Bravo" and r["target"] == "Alpha" and r["trust_type"] == "alignment")
        assert row["observer_team"] == "VILLAGERS"
        assert row["target_team"] == "WEREWOLVES"
        assert row["target_role"] == "WEREWOLF"

    def test_normalization(self, rows):
        row = next(r for r in rows if r["observer"] == "Carol" and r["trust_type"] == "alignment")
        assert row["score_raw"] == 1
        assert row["score_norm"] == 0.0
        assert row["confidence_raw"] == 3
        assert row["confidence_norm"] == 1.0
        assert row["scale"] == "7pt"

    def test_alive_tracking(self, rows):
        delta_row = next(r for r in rows if r["target"] == "Delta")
        assert delta_row["target_alive"] is False  # died night 1
        assert delta_row["observer_alive"] is True

    def test_source_and_run(self, rows):
        assert {r["source"] for r in rows} == {"human"}
        assert {r["run_id"] for r in rows} == {"human"}
        assert all(r["model"] is None for r in rows)

    def test_without_events_phase_idx_is_none(self, human_labels):
        rows = human_rows(human_labels, None)
        assert len(rows) == 8
        assert all(r["phase_idx"] is None for r in rows)


class TestLLMRows:
    @pytest.fixture
    def rows(self, llm_likert_run, events_file):
        return llm_rows(llm_likert_run, events_file, events_file)

    def test_row_count_skips_null_dimensions(self, rows):
        # phase 1: Bravo 3 dims + Carol 2 (strategic null); phase 3: Carol 3
        assert len(rows) == 8

    def test_strategic_maps_to_information(self, rows):
        types = {r["trust_type"] for r in rows}
        assert types == {"alignment", "information", "consistency"}
        info = next(r for r in rows if r["target"] == "Bravo" and r["trust_type"] == "information")
        assert info["score_raw"] == 6  # was the "strategic" dimension

    def test_phase_to_round_checkpoint(self, rows):
        phase1 = next(r for r in rows if r["phase_idx"] == 1)
        assert (phase1["round"], phase1["checkpoint"]) == (1, "BEFORE_VOTING")
        phase3 = next(r for r in rows if r["phase_idx"] == 3)
        assert (phase3["round"], phase3["checkpoint"]) == (2, "BEFORE_DISCUSSION")

    def test_observer_metadata(self, rows):
        assert all(r["observer"] == "Alpha" for r in rows)
        assert all(r["observer_role"] == "WEREWOLF" for r in rows)
        assert all(r["observer_team"] == "WEREWOLVES" for r in rows)
        assert all(r["source"] == "llm" for r in rows)
        assert all(r["run_id"] == "Alpha-likert01" for r in rows)
        assert all(r["model"] == "test-model:1b" for r in rows)
        assert all(r["experiment"] == "a" for r in rows)

    def test_alive_tracking(self, rows):
        bravo_ph3 = [r for r in rows if r["phase_idx"] == 3]
        assert all(r["target"] == "Carol" for r in bravo_ph3)
        carol_row = bravo_ph3[0]
        assert carol_row["target_alive"] is True
        assert carol_row["observer_alive"] is True  # Alpha dies at phase 5

    def test_likert_scale(self, rows):
        assert {r["scale"] for r in rows} == {"7pt"}
        top = next(r for r in rows if r["target"] == "Carol" and r["phase_idx"] == 1 and r["trust_type"] == "alignment")
        assert top["score_raw"] == 7
        assert top["score_norm"] == 1.0


class TestLLMNumericRun:
    def test_scale_inferred_from_values(self, llm_numeric_run, events_file):
        rows = llm_rows(llm_numeric_run, events_file, events_file)
        assert len(rows) == 3
        assert {r["scale"] for r in rows} == {"numeric100"}
        alignment = next(r for r in rows if r["trust_type"] == "alignment")
        assert alignment["score_raw"] == 20
        assert alignment["score_norm"] == pytest.approx(19 / 99)

    def test_missing_metadata_tolerated(self, llm_numeric_run):
        assert llm_numeric_run.trust_scale_mode is None
        assert llm_numeric_run.temperature is None
