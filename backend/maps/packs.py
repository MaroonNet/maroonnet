"""Reading tiles out of a pack: one PMTiles file holding every tile of one area."""

from functools import cache

from pmtiles.reader import MmapSource, Reader
from pmtiles.tile import Compression, TileType

# What the pack's header says about its tiles, as the HTTP headers a browser understands.
MEDIA_TYPES = {
    TileType.MVT: "application/vnd.mapbox-vector-tile",
    TileType.PNG: "image/png",
    TileType.JPEG: "image/jpeg",
    TileType.WEBP: "image/webp",
    TileType.AVIF: "image/avif",
}
ENCODINGS = {Compression.GZIP: "gzip", Compression.BROTLI: "br", Compression.ZSTD: "zstd"}


class Pack:
    def __init__(self, path: str):
        self._file = open(path, "rb")
        self._reader = Reader(MmapSource(self._file))
        header = self._reader.header()
        self.media_type = MEDIA_TYPES[header["tile_type"]]
        # None when tiles are stored uncompressed, as terrain WebP tiles are.
        self.encoding = ENCODINGS.get(header["tile_compression"])
        self.min_zoom = header["min_zoom"]
        self.max_zoom = header["max_zoom"]

    def tile(self, z: int, x: int, y: int) -> bytes | None:
        """The stored bytes of one tile, still compressed, or None if the pack has no such tile."""
        if x >= 2**z or y >= 2**z:
            return None
        return self._reader.get(z, x, y)


@cache
def open_pack(path: str) -> Pack:
    """Open each pack once and reuse it for every request."""
    return Pack(path)
