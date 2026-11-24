"""The settings file: settings.json in the app data folder."""

import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from maps.folders import app_data_folder

FILE_NAME = "settings.json"


class Settings(BaseModel):
    """Every setting, with its starting value."""

    units: Literal["imperial", "metric"] = "imperial"  # miles and feet, or kilometers and meters


def settings_path() -> Path:
    return app_data_folder() / FILE_NAME


def read_settings() -> Settings:
    """The saved settings. A setting the file does not name has its starting value, and with
    no file they all do. A damaged file is treated as no file, with a line printed to say so:
    the app never refuses to start over its settings."""
    path = settings_path()
    if not path.exists():
        return Settings()
    try:
        return Settings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # unreadable, cut off, or a value no setting offers
        print(f"SETTINGS {FILE_NAME} could not be read, so the starting values are used: {error!r}", flush=True)
        return Settings()


# Held while a change is read, altered and written, so two changes arriving together are
# made one after the other and neither undoes the other.
_one_change_at_a_time = threading.Lock()


def change_settings(changes: dict) -> Settings:
    """Saves the settings with the named ones changed, and returns them all. The settings
    not named keep their values."""
    with _one_change_at_a_time:
        settings = read_settings().model_copy(update=changes)
        write_settings(settings)
        return settings


def write_settings(settings: Settings) -> None:
    """Writes settings.json, making the app data folder if it is not there yet. The text goes
    to a temporary file first, which is then renamed over settings.json in one step, so the
    program stopping part way never leaves half a file."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{FILE_NAME}.tmp")
    temporary.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, path)
