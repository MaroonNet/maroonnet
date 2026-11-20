"""Fetching elevation for a pack's area, with spm itself replaced: nothing is downloaded."""

import subprocess

import pytest
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

from mapdb import dem, spm


def make_pack(path, bounds=None):
    """A one-tile pack. bounds (lon_min, lat_min, lon_max, lat_max) go in its header."""
    header = {"tile_type": TileType.WEBP, "tile_compression": Compression.NONE}
    if bounds:
        keys = ("min_lon_e7", "min_lat_e7", "max_lon_e7", "max_lat_e7")
        header.update({key: round(value * 1e7) for key, value in zip(keys, bounds)})
    with write(path) as writer:
        writer.write_tile(zxy_to_tileid(0, 0, 0), b"tile")
        writer.finalize(header, {})
    return str(path)


@pytest.fixture
def spm_root(tmp_path, monkeypatch):
    root = tmp_path / "spm"
    python = spm.spm_python(root)
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setenv(spm.SPM_DIR_SETTING, str(root))
    return root


def test_bounds_come_from_the_pack_header(tmp_path):
    pack = make_pack(tmp_path / "t.pmtiles", (-110.86, 31.34, -110.49, 31.67))
    assert dem.pack_bounds(pack) == pytest.approx((-110.86, 31.34, -110.49, 31.67))


def test_tile_count():
    assert dem.tile_count((-110.86, 31.34, -110.49, 31.67)) == 1  # inside one degree square
    assert dem.tile_count((-111.2, 31.8, -110.9, 32.1)) == 4      # crosses both degree lines
    assert dem.tile_count((-180, -90, 180, 90)) == 360 * 180


def test_fetch_runs_spm_for_the_pack_bounds(tmp_path, spm_root, monkeypatch):
    calls = []

    def run(root, args, timeout=spm.TIMEOUT_S, capture=True):
        calls.append((args, timeout, capture))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(spm, "run", run)
    dem.main([make_pack(tmp_path / "t.pmtiles", (-110.86, 31.34, -110.49, 31.67))])
    args, timeout, capture = calls[0]
    assert args == ["fetch-dem", "-110.860000", "31.340000", "-110.490000", "31.670000"]
    assert timeout is None and capture is False  # a long download, printed as it goes


def test_a_pack_without_bounds_is_refused(tmp_path, spm_root, monkeypatch):
    monkeypatch.setattr(spm, "run", lambda *a, **k: pytest.fail("spm must not run"))
    with pytest.raises(SystemExit, match="more than --max-tiles"):
        dem.main([make_pack(tmp_path / "world.pmtiles")])


def test_dry_run_fetches_nothing(tmp_path, spm_root, monkeypatch, capsys):
    monkeypatch.setattr(spm, "run", lambda *a, **k: pytest.fail("spm must not run"))
    dem.main([make_pack(tmp_path / "t.pmtiles", (-110.86, 31.34, -110.49, 31.67)), "--dry-run"])
    assert "1 tiles" in capsys.readouterr().out


def test_a_failed_fetch_is_an_error(tmp_path, spm_root, monkeypatch):
    monkeypatch.setattr(spm, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1))
    with pytest.raises(SystemExit, match="fetch-dem failed"):
        dem.main([make_pack(tmp_path / "t.pmtiles", (-110.86, 31.34, -110.49, 31.67))])
