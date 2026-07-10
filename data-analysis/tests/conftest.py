from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REAL_GAME_RECORDS = Path(__file__).parent.parent.parent / "results" / "game-records"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def events_file():
    from data.loaders.event_loader import load_events

    return load_events(FIXTURES / "game-TEST01.json")


@pytest.fixture
def human_labels():
    from data.loaders.human_loader import load_human_labels

    return load_human_labels(FIXTURES / "game-TEST01-labels.json")


@pytest.fixture
def llm_likert_run():
    from data.loaders.llm_loader import load_llm_run

    return load_llm_run(FIXTURES / "llm" / "Alpha-likert01.json")


@pytest.fixture
def llm_numeric_run():
    from data.loaders.llm_loader import load_llm_run

    return load_llm_run(FIXTURES / "llm" / "Carol-numeric01.json")
