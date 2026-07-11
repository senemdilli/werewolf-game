import pytest

from data.dataset import build_dataset
from data.filters import FilterSpec, apply_filters

from tests.conftest import FIXTURES


@pytest.fixture(scope="module")
def df():
    return build_dataset(FIXTURES, FIXTURES / "llm")


class TestApplyFilters:
    def test_no_constraints_keeps_everything(self, df):
        assert len(apply_filters(df, FilterSpec())) == len(df)

    def test_source(self, df):
        human = apply_filters(df, FilterSpec(sources=["human"]))
        llm = apply_filters(df, FilterSpec(sources=["llm"]))
        assert len(human) == 8
        assert len(llm) == 11
        assert len(human) + len(llm) == len(df)

    def test_trust_given_by_team(self, df):
        given = apply_filters(df, FilterSpec(observer_teams=["WEREWOLVES"]))
        assert set(given["observer"]) == {"Alpha"}

    def test_trust_received_by_team(self, df):
        received = apply_filters(df, FilterSpec(target_teams=["WEREWOLVES"]))
        assert set(received["target"]) == {"Alpha"}

    def test_team_filter_is_case_insensitive(self, df):
        received = apply_filters(df, FilterSpec(target_teams=["werewolves"]))
        assert set(received["target"]) == {"Alpha"}

    def test_trust_types(self, df):
        info = apply_filters(df, FilterSpec(trust_types=["information"]))
        assert set(info["trust_type"]) == {"information"}

    def test_round_range(self, df):
        round1 = apply_filters(df, FilterSpec(round_max=1))
        assert set(round1["round"]) == {1}

    def test_alive_only(self, df):
        alive = apply_filters(df, FilterSpec(alive_only=True))
        assert "Delta" not in set(alive["target"])
        assert len(alive) == len(df) - 3  # only the Delta target rows drop

    def test_llm_config_filters(self, df):
        exp_a = apply_filters(df, FilterSpec(experiments=["a"]))
        assert set(exp_a["run_id"]) == {"Alpha-likert01"}
        cool = apply_filters(df, FilterSpec(temperature_max=0.5))
        assert set(cool["run_id"]) == {"Alpha-likert01"}  # numeric run has no temperature

    def test_combined(self, df):
        rows = apply_filters(df, FilterSpec(sources=["llm"], targets=["Carol"], trust_types=["alignment"]))
        assert len(rows) == 2  # Carol labeled in phases 1 and 3
        assert sorted(rows["score_raw"]) == [2, 7]


class TestSpecLeniency:
    """The orchestrator LLM writes sloppy specs; unambiguous ones must work."""

    def test_singular_alias(self):
        spec = FilterSpec.model_validate({"room_code": ["G1"], "source": ["human"]})
        assert spec.room_codes == ["G1"]
        assert spec.sources == ["human"]

    def test_bare_string_becomes_list(self):
        spec = FilterSpec.model_validate({"room_codes": "G1", "trust_type": "alignment"})
        assert spec.room_codes == ["G1"]
        assert spec.trust_types == ["alignment"]

    def test_unknown_field_fails_loudly(self):
        with pytest.raises(Exception, match="game"):
            FilterSpec.model_validate({"game": "5NOHGS"})

    def test_plural_wins_over_singular(self):
        spec = FilterSpec.model_validate({"room_codes": ["G1"], "room_code": "G2"})
        assert spec.room_codes == ["G1"]
