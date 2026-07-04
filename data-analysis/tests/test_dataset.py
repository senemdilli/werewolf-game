import pytest

from data.dataset import COLUMNS, build_dataset, load_dataset

from tests.conftest import FIXTURES, REAL_GAME_RECORDS


@pytest.fixture(scope="module")
def df():
    return build_dataset(FIXTURES, FIXTURES / "llm")


class TestBuildDataset:

    def test_all_sources_loaded(self, df):
        assert len(df) == 19  # 8 human + 8 likert llm + 3 numeric llm
        assert df["source"].value_counts().to_dict() == {"llm": 11, "human": 8}

    def test_column_contract(self, df):
        assert list(df.columns) == COLUMNS

    def test_game_metadata_joined_to_llm_rows(self, df):
        llm = df[df["source"] == "llm"]
        assert set(llm["room_code"]) == {"TEST01"}
        assert set(llm["winner"]) == {"VILLAGERS"}

    def test_human_only_when_no_llm_dir(self):
        df = build_dataset(FIXTURES)
        assert set(df["source"]) == {"human"}


class TestParquetCache:
    def test_cache_roundtrip(self, tmp_path):
        first = load_dataset(FIXTURES, FIXTURES / "llm", cache_dir=tmp_path)
        assert (tmp_path / "dataset.parquet").exists()
        second = load_dataset(FIXTURES, FIXTURES / "llm", cache_dir=tmp_path)
        assert first.shape == second.shape
        assert first["score_raw"].sum() == second["score_raw"].sum()

    def test_cache_invalidated_on_change(self, tmp_path):
        import shutil

        data_dir = tmp_path / "records"
        shutil.copytree(FIXTURES, data_dir)
        cache_dir = tmp_path / "cache"

        load_dataset(data_dir, cache_dir=cache_dir)
        fingerprint = (cache_dir / "dataset.fingerprint").read_text()

        labels = data_dir / "game-TEST01-labels.json"
        labels.write_text(labels.read_text())  # touch: new mtime
        load_dataset(data_dir, cache_dir=cache_dir)
        assert (cache_dir / "dataset.fingerprint").read_text() != fingerprint


@pytest.mark.skipif(not REAL_GAME_RECORDS.exists(), reason="real game records not available")
class TestRealGameRecords:
    def test_loads_all_human_games(self):
        df = build_dataset(REAL_GAME_RECORDS)
        assert len(df) > 0
        assert set(df["source"]) == {"human"}
        # every human row must be phase-aligned when its events export exists
        aligned = df[df["phase_idx"].notna()]
        assert len(aligned) / len(df) > 0.9
        assert set(df["scale"]) == {"7pt"}
        assert df["score_raw"].between(1, 7).all()
