"""The settings' web routes."""

from fastapi import APIRouter
from pydantic import ConfigDict

from .settings_file import Settings, change_settings, read_settings

router = APIRouter(prefix="/api/settings")


class SettingsChange(Settings):
    """What a request may change: any of the settings. A name that is not a setting is
    refused, so a misspelled one is not silently ignored."""

    model_config = ConfigDict(extra="forbid")


@router.get("")
def get_settings() -> Settings:
    return read_settings()


# The request names only the settings to change. exclude_unset keeps just those, leaving
# out the starting values the model fills in for the settings the request did not name.
@router.patch("")
def patch_settings(changes: SettingsChange) -> Settings:
    return change_settings(changes.model_dump(exclude_unset=True))
