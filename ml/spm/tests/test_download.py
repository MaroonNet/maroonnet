import pytest

from spm.download import fetch


def test_fetch_writes_whole_file_and_skips_existing(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 1000)
    dst = tmp_path / "out" / "tile.tif"
    assert fetch(src.as_uri(), dst) == dst
    assert dst.read_bytes() == b"x" * 1000
    assert not list(dst.parent.glob("*.part"))
    src.write_bytes(b"changed")
    fetch(src.as_uri(), dst)  # exists: not re-downloaded
    assert dst.read_bytes() == b"x" * 1000


def test_fetch_leaves_nothing_behind_on_failure(tmp_path):
    dst = tmp_path / "missing.tif"
    with pytest.raises(OSError):
        fetch((tmp_path / "does-not-exist").as_uri(), dst)
    assert not dst.exists() and not list(tmp_path.glob("*.part"))
