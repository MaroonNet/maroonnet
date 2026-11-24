"""Test helpers shared by every backend folder. pytest applies this file to all tests below it."""

import pytest

from maps.folders import DATA_DIR_VARIABLE
from mission.folders import MISSIONS_DIR_VARIABLE
from mission.open_mission import close_mission


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Every test gets its own app data folder, so no test touches the real one."""
    folder = tmp_path / "app-data"
    monkeypatch.setenv(DATA_DIR_VARIABLE, str(folder))
    return folder


@pytest.fixture(autouse=True)
def missions_dir(tmp_path, monkeypatch):
    """Every test gets its own missions folder, so no test touches a real mission. A mission
    the test opened is closed when the test ends."""
    folder = tmp_path / "missions"
    monkeypatch.setenv(MISSIONS_DIR_VARIABLE, str(folder))
    yield folder
    close_mission(forget=False)
