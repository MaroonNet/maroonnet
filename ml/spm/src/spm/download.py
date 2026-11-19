"""Download a file atomically: write to ``<name>.part``, rename when complete.

A download interrupted half-way (3DEP tiles are ~400 MB) must not leave a file
that later code mistakes for a complete one.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def fetch(url: str, path: Path, force: bool = False) -> Path:
    """Download ``url`` to ``path`` unless it already exists (or ``force``)."""
    path = Path(path)
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    try:
        log.info("downloading %s", url)
        urllib.request.urlretrieve(url, part)
        part.replace(path)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return path
