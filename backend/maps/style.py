"""The map style: the document that tells MapLibre what to draw and how.

Rebuilt from the POC's make_style.py. Every layer carries metadata.group, which the web app's
layer switches turn on and off as a unit. Layers are drawn in list order: the first at the bottom.
"""

# colours
PAPER = "#f4f1e8"
WATER, WATER_LINE = "#a9cfe6", "#3f8fc4"
TRAIL, TRAIL_PAVED = "#b3261e", "#8c8c8c"
TRACK, FOUR_WD, DIRT = "#8a5a2b", "#2f2418", "#b08850"

SRC = "basemap"
BASEMAP_MAX_ZOOM = 14  # the basemap is built to zoom 14 (D16); MapLibre enlarges its tiles beyond that


def layer(id, group, type, source_layer=None, **spec):
    """One style layer. source_layer names the layer inside the basemap tiles that it draws."""
    out = {"id": id, "type": type, "metadata": {"group": group}}
    if source_layer:
        out |= {"source": SRC, "source-layer": source_layer}
    return out | spec


def zoom(*stops):
    """A value that changes with zoom: zoom(10, 1, 16, 4) is 1 at zoom 10 and 4 at zoom 16."""
    return ["interpolate", ["linear"], ["zoom"], *stops]


def zoom_match(prop, stops, default):
    """One zoom ramp whose value at each stop depends on a field.

    MapLibre allows only one zoom ramp per value, and it must be the outermost expression, so a
    width that depends on both zoom and a field is written as a field match inside each zoom stop:
    zoom_match("kind", {7: {"river": 0.8}, 16: {"river": 4}}, {7: 0.3, 16: 1.2})
    """
    out = ["interpolate", ["linear"], ["zoom"]]
    for z, by_value in stops.items():
        m = ["match", ["get", prop]]
        for value, width in by_value.items():
            m += [value, width]
        out += [z, m + [default[z]]]
    return out


LAYERS = [
    layer("paper", "base", "background", paint={"background-color": PAPER}),

    # ---- vegetation and ground cover
    layer("landcover", "landcover", "fill", "landcover",
          paint={"fill-color": ["match", ["get", "kind"],
                                "forest", "#d3e3bf", "scrub", "#e1e5c3", "meadow", "#edf0d4",
                                "rock", "#e0dbd2", "wetland", "#d5e6e6", PAPER],
                 "fill-opacity": 0.85}),

    # ---- public land: fills, then outlines (BLM in yellow, as on agency maps)
    layer("public-land-fill", "public_land", "fill", "public_land",
          paint={"fill-color": ["match", ["get", "designation"],
                                "wilderness", "#5f9a4c", "national_forest", "#8fbf73", "national_park", "#6aa35a",
                                "blm", "#e8c66a", "park", "#9cc58b", "#b9cfa9"],
                 "fill-opacity": ["match", ["get", "designation"], "blm", 0.22, 0.18]}),
    layer("public-land-outline", "public_land", "line", "public_land",
          paint={"line-color": ["match", ["get", "designation"],
                                "wilderness", "#3d6e2f", "blm", "#b58a1c", "#5d8f47"],
                 "line-width": zoom(6, 0.6, 12, 1.6),
                 "line-opacity": ["match", ["get", "designation"], "blm", 0.35, 0.9],
                 "line-dasharray": ["match", ["get", "designation"],
                                    "wilderness", ["literal", [4, 2]], ["literal", [1, 0]]]}),

    # ---- water
    layer("water", "water", "fill", "water",
          paint={"fill-color": ["match", ["get", "kind"], "glacier", "#eef6fb", WATER],
                 "fill-outline-color": ["match", ["get", "kind"], "glacier", "#9fc4dc", WATER_LINE]}),
    layer("waterways", "water", "line", "waterways",
          layout={"line-cap": "round", "line-join": "round"},
          paint={"line-color": WATER_LINE,
                 "line-width": zoom_match("kind", {7: {"river": 0.8, "stream": 0.2}, 10: {"river": 1.4, "stream": 0.3},
                                                   12: {"river": 2, "stream": 0.7}, 16: {"river": 4, "stream": 1.6}},
                                          {7: 0.3, 10: 0.4, 12: 0.7, 16: 1.2}),
                 "line-dasharray": ["case", ["get", "intermittent"], ["literal", [3, 2]], ["literal", [1, 0]]]}),

    # ---- paved roads (casing under fill)
    layer("roads-casing", "roads", "line", "roads", minzoom=10,
          layout={"line-cap": "round", "line-join": "round"},
          paint={"line-color": "#9a8f80",
                 "line-width": zoom_match("kind", {10: {"highway": 3, "major": 2.4}, 16: {"highway": 9, "major": 7}},
                                          {10: 1.4, 16: 5})}),
    layer("roads", "roads", "line", "roads",
          layout={"line-cap": "round", "line-join": "round"},
          paint={"line-color": ["match", ["get", "kind"], "highway", "#e3843c", "major", "#f3c35a", "#ffffff"],
                 "line-width": zoom_match("kind", {5: {"highway": 0.8, "major": 0.4}, 10: {"highway": 2, "major": 1.4},
                                                   16: {"highway": 7, "major": 5.4}}, {5: 0.2, 10: 0.5, 16: 3.6})}),

    # ---- 4WD tracks and dirt roads
    layer("backroads", "backroads", "line", "backroads",
          layout={"line-join": "round"},
          paint={"line-color": ["case", ["get", "four_wd"], FOUR_WD, ["==", ["get", "kind"], "track"], TRACK, DIRT],
                 "line-width": zoom(9, ["case", ["get", "four_wd"], 0.8, 0.7], 16, ["case", ["get", "four_wd"], 2.6, 2.2]),
                 "line-dasharray": ["case", ["get", "four_wd"], ["literal", [4, 1.5]],
                                    ["==", ["get", "kind"], "dirt_road"], ["literal", [1, 0]], ["literal", [3, 1.5]]]}),

    # ---- trails: dashed; alpine routes dotted; paved paths (towns) thin grey
    layer("trails-paved", "trails", "line", "trails", filter=["get", "paved"],
          paint={"line-color": TRAIL_PAVED, "line-width": zoom(12, 0.6, 16, 1.6)}),
    layer("trails", "trails", "line", "trails", filter=["!", ["get", "paved"]],
          layout={"line-join": "round"},
          paint={"line-color": TRAIL,
                 "line-width": zoom(10, 0.8, 16, 2.4),
                 "line-dasharray": ["case",
                                    ["in", "alpine", ["coalesce", ["get", "sac_scale"], ""]], ["literal", [0.6, 1.8]],
                                    ["literal", [2.5, 1.5]]]}),
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
