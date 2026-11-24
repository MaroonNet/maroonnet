"""The packs installed in the maps folder, found once when the server starts (spec 8.3)."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .pack_info import PackInfo, read_pack_info
from .packs import Pack

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


@dataclass
class InstalledPack:
    info: PackInfo
    pack: Pack | None  # the open map file; None while the pack is partial


# The installed packs, by id. Filled once when the server starts: packs are not copied in by hand
# for now (spec section 2). Deleting (plan 2.6) and downloading (5.6) will change it.
installed: dict[str, InstalledPack] = {}


def packs_to_ask(contents: str) -> list[Pack]:
    """The open packs that hold basemap or terrain tiles, in the order to ask them for a tile
    (spec 8.4): mission packs before state packs, and newer map data before older. The first
    pack that has the tile answers."""
    entries = [entry for entry in installed.values() if entry.info.contents == contents]

    def order(entry: InstalledPack):
        age = -(entry.info.data_date or date.min).toordinal()  # an unknown date counts as oldest
        return (entry.info.kind != "mission", age)

    # A partial pack has no open map file, so it is never asked.
    return [entry.pack for entry in sorted(entries, key=order) if entry.pack is not None]


def scan(maps: Path) -> None:
    """Finds the installed packs and keeps them in `installed`. Complete packs are opened, ready
    to serve; partial ones are listed but not opened. A complete pack whose map file is missing or
    is not a pack is skipped with a message."""
    installed.clear()
    for pack_id, info in read_pack_infos(maps).items():
        pack = None
        if info.status == "complete":
            path = maps / pack_id / info.file
            try:
                pack = Pack(str(path))
            except Exception as error:  # missing, unreadable, or not a pack at all
                print(f"Skipped {path.parent}: its map file {info.file} could not be opened "
                      f"({error!r})", flush=True)
                continue
        installed[pack_id] = InstalledPack(info, pack)
