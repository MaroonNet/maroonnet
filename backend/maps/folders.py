"""Where the CPA keeps its files on this computer (spec 8.3, D17 and D22)."""

from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "MaroonNet"


def app_data_folder() -> Path:
    """The system's per-user app data folder: ~/Library/Application Support/MaroonNet on Mac,
    %LOCALAPPDATA%\\MaroonNet on Windows. appauthor=False stops Windows nesting it as
    MaroonNet\\MaroonNet."""
    return PlatformDirs(APP_NAME, appauthor=False).user_data_path


def maps_folder() -> Path:
    """Where the packs live. It is fixed: the user cannot change it (D17)."""
    return app_data_folder() / "maps"
