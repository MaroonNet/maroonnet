"""Fetch the elevation spm needs for the ground a map pack covers.

The map draws terrain from a pack (PMTiles). spm reads USGS 3DEP elevation tiles, the data its
models were trained on. Run this once, with internet, after a terrain pack is built or
downloaded, so both cover the same ground:

    cd backend
    uv run python -m mapdb.dem path/to/terrain.pmtiles
    uv run python -m mapdb.dem path/to/terrain.pmtiles --dry-run

It reads the pack's bounds from its header and runs `spm fetch-dem` for them. The tiles land in
spm's own data folder, where `spm predict` looks for them.
"""

import argparse
import math

from pmtiles.reader import MmapSource, Reader

from . import spm

# A 3DEP tile covers 1 x 1 degree and is a few hundred megabytes. A mission pack touches one to
# four. More than this is most likely a pack with no bounds in its header (the whole world) or
# a state-wide pack, so the command stops and says so. DRAFT VALUE: the team sets it.
MAX_TILES = 4

Bounds = tuple[float, float, float, float]  # lon_min, lat_min, lon_max, lat_max


def pack_bounds(path: str) -> Bounds:
    """The area a pack covers, from its header."""
    with open(path, "rb") as file:
        header = Reader(MmapSource(file)).header()
    return tuple(
        header[key] / 1e7 for key in ("min_lon_e7", "min_lat_e7", "max_lon_e7", "max_lat_e7")
    )


def tile_count(bounds: Bounds) -> int:
    """How many 1 x 1 degree 3DEP tiles touch the bounds (as spm.geodata.dem counts them)."""
    lon_min, lat_min, lon_max, lat_max = bounds
    columns = math.ceil(lon_max) - math.floor(lon_min)
    rows = math.ceil(lat_max) - math.floor(lat_min)
    return max(columns, 0) * max(rows, 0)


def fetch_args(bounds: Bounds) -> list[str]:
    return ["fetch-dem", *(f"{value:.6f}" for value in bounds)]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="fetch 3DEP elevation for a map pack's area")
    parser.add_argument("pack", help="a .pmtiles file, usually the terrain pack")
    parser.add_argument("--max-tiles", type=int, default=MAX_TILES)
    parser.add_argument("--dry-run", action="store_true", help="say what would be fetched")
    args = parser.parse_args(argv)

    bounds = pack_bounds(args.pack)
    count = tile_count(bounds)
    west, south, east, north = bounds
    print(f"{args.pack} covers {west:.4f},{south:.4f} to {east:.4f},{north:.4f}: {count} tiles")
    if count > args.max_tiles:
        raise SystemExit(
            f"{count} tiles is more than --max-tiles {args.max_tiles}. A pack with no bounds "
            "in its header reads as the whole world. Pass a smaller pack, or raise --max-tiles."
        )
    if args.dry_run:
        return
    root = spm.spm_dir()
    if not spm.spm_python(root).is_file():
        raise SystemExit(f"spm cannot run: no Python at {spm.spm_python(root)}")
    # No time limit and no capture: a tile is a long download, and spm prints its progress.
    result = spm.run(root, fetch_args(bounds), timeout=None, capture=False)
    if result.returncode != 0:
        raise SystemExit(f"spm fetch-dem failed (exit {result.returncode})")


if __name__ == "__main__":
    main()
