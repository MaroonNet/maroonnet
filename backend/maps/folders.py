"""Where the CPA keeps its files on this computer (spec 8.3, D17 and D22)."""

import os
from pathlib import Path

from platformdirs import PlatformDirs

APP_NAME = "MaroonNet"

# Tests and development set this to use another folder. The packaged app never sets it.
DATA_DIR_VARIABLE = "MAROONNET_DATA_DIR"


def app_data_folder() -> Path:
    """The system's per-user app data folder: ~/Library/Application Support/MaroonNet on Mac,
    %LOCALAPPDATA%\\MaroonNet on Windows. appauthor=False stops Windows nesting it as
    MaroonNet\\MaroonNet."""
    if override := os.environ.get(DATA_DIR_VARIABLE):
        return Path(override)
    return PlatformDirs(APP_NAME, appauthor=False).user_data_path


def maps_folder() -> Path:
    """Where the packs live. It is fixed: the user cannot change it (D17)."""
    return app_data_folder() / "maps"
