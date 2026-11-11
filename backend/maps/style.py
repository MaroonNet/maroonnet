"""The map style: the document that tells MapLibre what to draw and how.

Rebuilt from the POC's make_style.py. Every layer carries metadata.group, which the web app's
layer switches turn on and off as a unit. Layers are drawn in list order: the first at the bottom.
"""

PAPER = "#f4f1e8"

SRC = "basemap"
BASEMAP_MAX_ZOOM = 14  # the basemap is built to zoom 14 (D16); MapLibre enlarges its tiles beyond that


def build_style(origin: str) -> dict:
    """The style, with every address made absolute from origin, for example http://127.0.0.1:8000.

    MapLibre needs absolute addresses: it fetches tiles from background workers that have no
    page address to resolve a relative one against.
    """
    return {
        "version": 8,
        "name": "MaroonNet SAR",
        "sources": {
            SRC: {"type": "vector", "tiles": [f"{origin}/tiles/basemap/{{z}}/{{x}}/{{y}}"],
                  "minzoom": 0, "maxzoom": BASEMAP_MAX_ZOOM},
        },
        "layers": [
            {"id": "paper", "type": "background", "metadata": {"group": "base"},
             "paint": {"background-color": PAPER}},
        ],
    }
