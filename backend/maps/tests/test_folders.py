"""The app data folder is where D22 says, on each system."""

from pathlib import Path

from platformdirs.macos import MacOS
from platformdirs.windows import Windows

from maps import folders


def test_mac_app_data_folder(monkeypatch):
    monkeypatch.setattr(folders, "PlatformDirs", MacOS)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)  # would move it on a Mac if set
    assert folders.app_data_folder() == Path.home() / "Library" / "Application Support" / "MaroonNet"


def test_windows_app_data_folder_names_maroonnet_once(monkeypatch):
    # Windows' rules, checked on any computer: platformdirs reads the Local AppData folder
    # from this variable instead of asking Windows.
    monkeypatch.setattr(folders, "PlatformDirs", Windows)
    monkeypatch.setenv("WIN_PD_OVERRIDE_LOCAL_APPDATA", r"C:\Users\sar\AppData\Local")
    path = str(folders.app_data_folder()).replace("\\", "/")
    assert path == "C:/Users/sar/AppData/Local/MaroonNet"
