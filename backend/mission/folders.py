"""Where mission files are kept on this computer.

The missions folder holds one folder for each mission. Inside it is one file for each
session of that mission:

    missions/bear-creek-952592f8/session-01.sqlite3
    missions/bear-creek-952592f8/session-02.sqlite3
"""

import os
from pathlib import Path

from maps.folders import app_data_folder

# Development sets this to use another folder, such as backend/missions, where the sample
# missions are built. Tests set it too. The packaged app never sets it.
MISSIONS_DIR_VARIABLE = "MAROONNET_MISSIONS_DIR"


def missions_folder() -> Path:
    if override := os.environ.get(MISSIONS_DIR_VARIABLE):
        return Path(override)
    return app_data_folder() / "missions"
