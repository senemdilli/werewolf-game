import pytest

from data.phase_alignment import build_phase_alignment

from tests.conftest import REAL_GAME_RECORDS


class TestFixtureGame:
    @pytest.fixture
    def alignment(self, events_file):
        return build_phase_alignment(events_file.events, events_file.player_names())

    def test_phase_defs_order(self, alignment):
        assert alignment.phase_defs == [
            (1, "BEFORE_DISCUSSION"),
            (1, "BEFORE_VOTING"),
            (1, "AFTER_VOTING"),
            (2, "BEFORE_DISCUSSION"),
            (2, "BEFORE_VOTING"),
            (2, "AFTER_VOTING"),
            (3, "BEFORE_DISCUSSION"),
        ]

    def test_post_vote_message_counts_toward_next_round(self, alignment):
        # the last "Dawn breaks." event is tagged round 2 in the export but
        # occurs after round 2's vote result -> effective round 3
        assert (3, "BEFORE_DISCUSSION") in alignment.phase_defs

    def test_bidirectional_mapping(self, alignment):
        assert alignment.phase_idx(1, "BEFORE_VOTING") == 1
        assert alignment.phase_idx(2, "BEFORE_DISCUSSION") == 3
        assert alignment.round_checkpoint(5) == (2, "AFTER_VOTING")
        assert alignment.phase_idx(9, "BEFORE_VOTING") is None
        assert alignment.round_checkpoint(99) is None

    def test_phase_names(self, alignment):
        assert alignment.phase_name(0) == "MORNING"
        assert alignment.phase_name(1) == "DAY"
        assert alignment.phase_name(2) == "EVENING"

    def test_death_tracking(self, alignment):
        assert alignment.dead_players(0) == {"Delta"}
        assert alignment.dead_players(2) == {"Delta"}
        assert alignment.dead_players(3) == {"Delta", "Bravo"}
        assert alignment.dead_players(5) == {"Delta", "Bravo", "Alpha"}


@pytest.mark.skipif(not REAL_GAME_RECORDS.exists(), reason="real game records not available")
class TestRealGame:
    """Guard against divergence from the labeling engine's phase construction."""

    @pytest.fixture
    def alignment(self):
        from data.loaders.event_loader import load_events

        events = load_events(REAL_GAME_RECORDS / "game-44UT6Y-d59e923e.json")
        return build_phase_alignment(events.events, events.player_names())

    def test_total_phases_matches_llm_run_output(self, alignment):
        # the labeling engine reported total_phases=9 for this game
        assert len(alignment.phase_defs) == 9

    def test_alive_phases_matches_llm_run_output(self, alignment):
        # the engine reported alive_phases=5 for player Blue
        blue_alive = [i for i in range(9) if "Blue" not in alignment.dead_players(i)]
        assert len(blue_alive) == 5
