import pytest

from data.dataset import COLUMNS, build_dataset, load_dataset

from tests.conftest import FIXTURES, REAL_GAME_RECORDS


@pytest.fixture(scope="module")
def df():
    return build_dataset(FIXTURES, FIXTURES / "llm")


class TestBuildDataset:

    def test_all_sources_loaded(self, df):
        assert len(df) == 35  # 24 human + 8 likert llm + 3 numeric llm
        assert df["source"].value_counts().to_dict() == {"human": 24, "llm": 11}

    def test_column_contract(self, df):
        assert list(df.columns) == COLUMNS

    def test_game_metadata_joined_to_llm_rows(self, df):
        llm = df[df["source"] == "llm"]
        assert set(llm["room_code"]) == {"TEST01"}
        assert set(llm["winner"]) == {"VILLAGERS"}

    def test_human_only_when_no_llm_dir(self):
        df = build_dataset(FIXTURES)
        assert set(df["source"]) == {"human"}

    def test_self_labels_dropped(self, tmp_path):
        # The engine sometimes labels the observer themselves; the game never
        # allows that, so such rows must not reach the unified table.
        import json
        import shutil

        shutil.copy(FIXTURES / "game-TEST01-labels.json", tmp_path)
        shutil.copy(FIXTURES / "game-TEST01.json", tmp_path)
        llm_dir = tmp_path / "llm"
        llm_dir.mkdir()
        run = json.loads((FIXTURES / "llm" / "Alpha-likert01.json").read_text())
        phase = run["phases"][0]
        phase["labels"]["Alpha"] = phase["labels"]["Bravo"]  # self-label
        (llm_dir / "Alpha-likert01.json").write_text(json.dumps(run))

        df = build_dataset(tmp_path, llm_dir)
        assert not (df["observer"] == df["target"]).any()
        # only the likert run was copied: its usual 8 rows, self-labels gone
        assert len(df[df["source"] == "llm"]) == 8


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
