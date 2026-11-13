"""The packs installed in the maps folder, found once when the server starts (spec 8.3)."""

from pathlib import Path

from .pack_info import PackInfo, read_pack_info

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


def folder_holds(pack_id: str) -> tuple[str, str]:
    """The kind and contents a pack's folder says it holds: state/CO/terrain holds a state
    terrain pack, and every mission/<name> folder a mission terrain pack."""
    place, *_, last = pack_id.split("/")
    return ("state", last) if place == "state" else ("mission", "terrain")


def read_pack_infos(maps: Path) -> dict[str, PackInfo]:
    """Each pack folder's pack.json, by id. One that is missing, damaged, or disagrees with its
    folder is skipped with a message."""
    infos = {}
    for pack_id, folder in pack_folders(maps).items():
        info = read_pack_info(folder)
        if info is None:
            continue  # read_pack_info has printed why
        kind, contents = folder_holds(pack_id)
        if (info.kind, info.contents) != (kind, contents):
            print(f"Skipped {folder}: its pack.json says {info.kind} {info.contents}, "
                  f"but its folder holds {kind} {contents}", flush=True)
            continue
        infos[pack_id] = info
    return infos
