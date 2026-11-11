"""The map style: the document that tells MapLibre what to draw and how.

Rebuilt from the POC's make_style.py. Every layer carries metadata.group, which the web app's
layer switches turn on and off as a unit. Layers are drawn in list order: the first at the bottom.
"""

# colours
PAPER = "#f4f1e8"
WATER, WATER_LINE = "#a9cfe6", "#3f8fc4"

SRC = "basemap"
BASEMAP_MAX_ZOOM = 14  # the basemap is built to zoom 14 (D16); MapLibre enlarges its tiles beyond that


def layer(id, group, type, source_layer=None, **spec):
    """One style layer. source_layer names the layer inside the basemap tiles that it draws."""
    out = {"id": id, "type": type, "metadata": {"group": group}}
    if source_layer:
        out |= {"source": SRC, "source-layer": source_layer}
    return out | spec


LAYERS = [
    layer("paper", "base", "background", paint={"background-color": PAPER}),

    # ---- water
    layer("water", "water", "fill", "water",
          paint={"fill-color": ["match", ["get", "kind"], "glacier", "#eef6fb", WATER],
                 "fill-outline-color": ["match", ["get", "kind"], "glacier", "#9fc4dc", WATER_LINE]}),
]


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
        "layers": LAYERS,
    }
