"""The app data folder is where D22 says, on each system."""

from pathlib import Path

from fastapi.testclient import TestClient
from platformdirs.macos import MacOS
from platformdirs.windows import Windows

from maps import folders
from server.main import app


def test_mac_app_data_folder(monkeypatch):
    monkeypatch.delenv(folders.DATA_DIR_VARIABLE)  # set for every test by conftest.py
    monkeypatch.setattr(folders, "PlatformDirs", MacOS)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)  # would move it on a Mac if set
    assert folders.app_data_folder() == Path.home() / "Library" / "Application Support" / "MaroonNet"


def test_windows_app_data_folder_names_maroonnet_once(monkeypatch):
    monkeypatch.delenv(folders.DATA_DIR_VARIABLE)
    # Windows' rules, checked on any computer: platformdirs reads the Local AppData folder
    # from this variable instead of asking Windows.
    monkeypatch.setattr(folders, "PlatformDirs", Windows)
    monkeypatch.setenv("WIN_PD_OVERRIDE_LOCAL_APPDATA", r"C:\Users\sar\AppData\Local")
    path = str(folders.app_data_folder()).replace("\\", "/")
    assert path == "C:/Users/sar/AppData/Local/MaroonNet"


def test_variable_replaces_app_data_folder(data_dir):
    assert folders.app_data_folder() == data_dir
    assert folders.maps_folder() == data_dir / "maps"


def test_starting_the_app_creates_the_maps_folder(data_dir, capsys):
    assert not (data_dir / "maps").exists()
    with TestClient(app):  # a with block runs the start-up code, as the real server does
        assert (data_dir / "maps").is_dir()
    assert f"Maps folder: {data_dir / 'maps'}" in capsys.readouterr().out
