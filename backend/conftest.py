"""Test helpers shared by every backend folder. pytest applies this file to all tests below it."""

import pytest

from maps.folders import DATA_DIR_VARIABLE


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Every test gets its own app data folder, so no test touches the real one."""
    folder = tmp_path / "app-data"
    monkeypatch.setenv(DATA_DIR_VARIABLE, str(folder))
    return folder
