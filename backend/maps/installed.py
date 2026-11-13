"""The packs installed in the maps folder, found once when the server starts (spec 8.3)."""

from pathlib import Path

# Where packs may sit inside the maps folder. A folder anywhere else is ignored.
PACK_FOLDER_PATTERNS = ("state/*/basemap", "state/*/terrain", "mission/*")


def pack_folders(maps: Path) -> dict[str, Path]:
    """The pack folders that exist in the agreed layout, by id, in id order.

    A pack's id is its folder's place in the maps folder, such as "state/CO/terrain".
    """
    folders = {}
    for pattern in PACK_FOLDER_PATTERNS:
        for folder in maps.glob(pattern):
            if folder.is_dir():
                # as_posix writes "/" between folder names on Windows too, so ids look the same everywhere.
                folders[folder.relative_to(maps).as_posix()] = folder
    return dict(sorted(folders.items()))
