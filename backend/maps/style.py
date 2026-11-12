"""The map style: the document that tells MapLibre what to draw and how.

Rebuilt from the POC's make_style.py. Every layer carries metadata.group, which the web app's
layer switches turn on and off as a unit. Layers are drawn in list order: the first at the bottom.
"""

# colours
PAPER = "#f4f1e8"
WATER, WATER_LINE, WATER_TEXT = "#a9cfe6", "#3f8fc4", "#2a6a99"
TRAIL, TRAIL_PAVED = "#b3261e", "#8c8c8c"
TRACK, FOUR_WD, DIRT = "#8a5a2b", "#2f2418", "#b08850"
CONTOUR, CONTOUR_INDEX = "#a0703f", "#7d4f22"
PEAK_TEXT = "#4a3426"
HALO = "rgba(255,255,255,0.85)"  # the pale rim around label text that keeps it readable over lines

# The layer groups the user can hide, with each checkbox's label, in the order the web app lists
# them. Every layer's group is one of these, or "base" (the background, which is never hidden).
GROUPS = {
    "trails": "Trails",
    "backroads": "4WD & dirt roads",
    "roads": "Paved roads",
    "water": "Rivers, streams & lakes",
    "peaks": "Peaks & passes",
    "contours": "Contours",
    "hillshade": "Hillshade",
    "public_land": "Public land (forest, wilderness, BLM)",
    "landcover": "Vegetation",
    "sar_points": "Trailheads, huts, camps, helipads",
    "places": "Towns & named places",
}

# Uses the user can narrow the trails to: each has a label and a filter, a rule that reads the
# trail's OpenStreetMap tags. The web app adds the rule to each trail layer's own filter.
# OpenStreetMap tag values that mean a use is allowed. "literal" marks the list as plain data, not a rule.
ALLOWED = ["literal", ["yes", "designated", "permissive", "open"]]
TRAIL_USES = {
    # foot is not "no" or "private". A trail with no foot tag counts as allowed.
    "hiking": ("Hiking allowed", ["!", ["in", ["coalesce", ["get", "foot"], "yes"], ["literal", ["no", "private"]]]]),
    # The uses below need their tag set to an allowed value. A trail without the tag is not drawn.
    "horse": ("Horse allowed", ["in", ["get", "horse"], ALLOWED]),
    # A bicycle tag that allows bikes, or an mtb_scale tag (OpenStreetMap's mountain-bike difficulty rating).
    "bike":("Bike allowed", ["any", ["in", ["get", "bicycle"], ALLOWED], ["has", "mtb_scale"]]),
    "motorized": ("Motorcycle / ATV allowed", ["any", ["in", ["get", "motorcycle"], ALLOWED],
                                               ["in", ["get", "atv"], ALLOWED],
                                               ["in", ["get", "motor_vehicle"], ALLOWED]]),
}

# Credits the data's licences require on the map, set on each source. Plain text, not links: the map
# works offline, and the style names no internet addresses. The terrain credit is the wording the
# Copernicus licence requires; the US terrain (USGS) is public domain and needs none.
OSM_CREDIT = "© OpenStreetMap contributors"
TERRAIN_CREDIT = ("Terrain: DLR e.V. 2010-2014, Airbus Defence and Space GmbH 2014-2018, "
                  "provided under COPERNICUS by the European Union and ESA. All rights reserved.")

SRC = "basemap"
BASEMAP_MAX_ZOOM = 14  # the basemap is built to zoom 14 (D16); MapLibre enlarges its tiles beyond that

# Contour lines are traced in the browser: dem-contour:// asks the contour plug-in to trace them
# from the shared height tiles. Heights are in feet (multiplier). thresholds lists, per zoom, the
# spacing of the thin lines and of the thicker index lines: at zoom 12, every 100 ft and every 500 ft.
CONTOUR_URL = ("dem-contour://{z}/{x}/{y}?contourLayer=contours&elevationKey=ele&levelKey=level"
               "&multiplier=3.28084&thresholds=10*500*2500~11*200*1000~12*100*500~14*40*200~15*20*100")
# Contour lines are traced for zooms up to 15. At zoom 15 there is a line for every 20 ft of
# height, the most detail we draw. At zooms 16 and 17 the map shows zoom 15's lines, drawn larger.
CONTOUR_MAX_ZOOM = 15

# Noto Sans, from @fontsource/noto-sans 5.3.0 (SIL Open Font License 1.1: assets/fonts/LICENSE).
# The style's font-faces hand MapLibre the font files, and it draws the letters itself.
FONT = {"regular": ["Noto Sans Regular"], "bold": ["Noto Sans Bold"], "italic": ["Noto Sans Italic"]}


def font_faces(origin: str) -> dict:
    def files(weight):
        return [{"url": f"{origin}/maps/fonts/noto-sans-{subset}-{weight}.woff2"} for subset in ("latin", "latin-ext")]

    return {"Noto Sans Regular": files("400-normal"), "Noto Sans Bold": files("700-normal"),
            "Noto Sans Italic": files("400-italic")}


def layer(id, group, type, source_layer=None, source=None, **spec):
    """One style layer. source names the data it draws from: the basemap unless given.
    source_layer names the part of that source's tiles it reads."""
    out = {"id": id, "type": type, "metadata": {"group": group}}
    if source or source_layer:
        out["source"] = source or SRC
    if source_layer:
        out["source-layer"] = source_layer
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


def kind(*kinds):
    """A filter: the feature's kind is one of these."""
    return ["in", ["get", "kind"], ["literal", list(kinds)]]


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

    # ---- terrain: shading drawn from heights, lit from the north-west
    layer("hillshade", "hillshade", "hillshade", source="terrain",
          paint={"hillshade-exaggeration": 0.45, "hillshade-shadow-color": "rgba(60,50,40,0.55)",
                 "hillshade-highlight-color": "rgba(255,255,255,0.25)"}),

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

    # ---- contours: a thin line at every interval, a thicker index line every fifth
    layer("contours-minor", "contours", "line", "contours", source="contours",
          filter=["==", ["get", "level"], 0],
          paint={"line-color": CONTOUR, "line-opacity": 0.55, "line-width": 0.7}),
    layer("contours-index", "contours", "line", "contours", source="contours",
          filter=[">", ["get", "level"], 0],
          paint={"line-color": CONTOUR_INDEX, "line-opacity": 0.9, "line-width": 1.4}),

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

    # ---- labels: water, public land, roads, trails. symbol-placement "line" runs text along a line.
    layer("water-labels", "water", "symbol", "water_labels",
          layout={"text-field": ["get", "name"], "text-font": FONT["italic"], "text-size": 11},
          paint={"text-color": WATER_TEXT, "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("waterway-labels", "water", "symbol", "waterways", minzoom=12,
          filter=["has", "name"],
          layout={"symbol-placement": "line", "text-field": ["get", "name"], "text-font": FONT["italic"],
                  "text-size": 10.5, "text-max-angle": 60, "symbol-spacing": 350},
          paint={"text-color": WATER_TEXT, "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("public-land-labels", "public_land", "symbol", "public_land_labels",
          layout={"text-field": ["get", "name"], "text-font": FONT["italic"], "text-size": zoom(7, 10, 12, 12.5),
                  "text-max-width": 9, "text-letter-spacing": 0.05},
          paint={"text-color": ["match", ["get", "designation"], "blm", "#8a6a12", "#3d6e2f"],
                 "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("contour-labels", "contours", "symbol", "contours", source="contour_labels",
          filter=[">", ["get", "level"], 0],
          layout={"symbol-placement": "line", "text-field": ["to-string", ["get", "ele"]], "text-font": FONT["regular"],
                  "text-size": 10, "text-max-angle": 120, "symbol-spacing": 400},
          paint={"text-color": CONTOUR_INDEX, "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("road-labels", "roads", "symbol", "roads", minzoom=11,
          filter=["any", ["has", "name"], ["has", "ref"]],
          layout={"symbol-placement": "line", "text-field": ["coalesce", ["get", "ref"], ["get", "name"]],
                  "text-font": FONT["regular"], "text-size": 10.5, "symbol-spacing": 400},
          paint={"text-color": "#444", "text-halo-color": HALO, "text-halo-width": 1.4}),
    layer("backroad-labels", "backroads", "symbol", "backroads", minzoom=12,
          filter=["any", ["has", "name"], ["has", "ref"]],
          layout={"symbol-placement": "line", "text-field": ["coalesce", ["get", "ref"], ["get", "name"]],
                  "text-font": FONT["regular"], "text-size": 10, "symbol-spacing": 350},
          paint={"text-color": TRACK, "text-halo-color": HALO, "text-halo-width": 1.4}),
    layer("trail-labels", "trails", "symbol", "trails", minzoom=13,
          filter=["all", ["has", "name"], ["!", ["get", "paved"]]],
          layout={"symbol-placement": "line", "text-field": ["get", "name"], "text-font": FONT["italic"],
                  "text-size": 10.5, "symbol-spacing": 300, "text-max-angle": 60},
          paint={"text-color": TRAIL, "text-halo-color": HALO, "text-halo-width": 1.4}),

    # ---- points: water features, SAR points, peaks, places (later layers win label collisions)
    layer("water-points", "water", "symbol", "water_points",
          layout={"icon-image": ["match", ["get", "kind"], "spring", "water", ""], "icon-size": 0.8,
                  "text-field": ["match", ["get", "kind"], "ford", "ford", ["coalesce", ["get", "name"], ""]],
                  "text-font": FONT["italic"], "text-size": 9.5, "text-offset": [0, 0.9], "text-anchor": "top"},
          paint={"text-color": WATER_TEXT, "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("sar-points-dot", "sar_points", "circle", "sar_points",
          filter=kind("trailhead", "gate", "cave"),
          paint={"circle-radius": ["match", ["get", "kind"], "trailhead", 5, 3],
                 "circle-color": ["match", ["get", "kind"], "trailhead", "#2e7d32", "gate", "#6b6b6b", "#5a3d2b"],
                 "circle-stroke-color": "#fff", "circle-stroke-width": 1.2}),
    layer("sar-points", "sar_points", "symbol", "sar_points",
          filter=["any", ["!=", ["get", "kind"], "mine"], [">=", ["zoom"], 13]],
          layout={"icon-size": ["match", ["get", "kind"], "mine", 0.65, 0.9],
                  "icon-image": ["match", ["get", "kind"],
                                 "hut", "lodging", "shelter", "shelter", "campsite", "campsite",
                                 "ranger_station", "ranger_station", "helipad", "heliport", "mine", "danger", ""],
                  "text-field": ["match", ["get", "kind"],
                                 "trailhead", ["coalesce", ["get", "name"], "Trailhead"],
                                 "helipad", ["coalesce", ["get", "name"], "Helipad"],
                                 "mine", ["coalesce", ["get", "name"], "Mine"],
                                 "gate", "",
                                 ["coalesce", ["get", "name"], ""]],
                  "text-font": FONT["regular"], "text-size": 10, "text-offset": [0, 1], "text-anchor": "top",
                  "text-optional": True},
          paint={"text-color": "#333", "text-halo-color": HALO, "text-halo-width": 1.2}),
    layer("peaks", "peaks", "symbol", "peaks",
          layout={"icon-image": ["match", ["get", "kind"], "peak", "triangle", ""], "icon-size": 0.9,
                  "text-field": ["format",
                                 ["case", ["==", ["get", "kind"], "peak"], ["coalesce", ["get", "name"], ""],
                                  ["concat", ["coalesce", ["get", "name"], ""], ["case", ["has", "name"], " ", ""], "(pass)"]], {},
                                 "\n", {},
                                 ["case", ["has", "ele_ft"],
                                  ["concat", ["number-format", ["get", "ele_ft"], {"locale": "en-US"}], " ft"], ""],
                                 {"font-scale": 0.85}],
                  "text-font": FONT["regular"], "text-size": 11, "text-anchor": "top", "text-offset": [0, 0.6],
                  # higher peaks win when labels collide
                  "symbol-sort-key": ["-", ["coalesce", ["get", "ele_ft"], 0]]},
          paint={"text-color": PEAK_TEXT, "text-halo-color": HALO, "text-halo-width": 1.4}),
    layer("places", "places", "symbol", "places",
          layout={"text-field": ["get", "name"],
                  "text-font": ["match", ["get", "kind"], "city", ["literal", FONT["bold"]],
                                "locality", ["literal", FONT["italic"]], ["literal", FONT["regular"]]],
                  "text-size": ["match", ["get", "kind"], "city", 14, "town", 12.5, "village", 11.5, "locality", 10, 10.5],
                  "text-transform": ["match", ["get", "kind"], "locality", "none", "uppercase"],
                  "text-letter-spacing": 0.04, "text-max-width": 8,
                  "symbol-sort-key": ["match", ["get", "kind"], "city", 0, "town", 1, "village", 2, "hamlet", 3, 4]},
          paint={"text-color": ["match", ["get", "kind"], "locality", "#5a4a3a", "#222"],
                 "text-halo-color": HALO, "text-halo-width": 1.6}),
]


def build_style(origin: str, terrain_max_zoom: int) -> dict:
    """The style, with every address made absolute from origin, for example http://127.0.0.1:8000.

    MapLibre needs absolute addresses: it fetches tiles from background workers that have no
    page address to resolve a relative one against.
    """
    return {
        "version": 8,
        "name": "MaroonNet SAR",
        # Notes MapLibre ignores. The web app builds its layer and trail-use checkboxes from them.
        "metadata": {
            "groups": [{"id": group, "label": label} for group, label in GROUPS.items()],
            "trail_uses": [{"id": use, "label": label, "filter": rule} for use, (label, rule) in TRAIL_USES.items()],
        },
        "font-faces": font_faces(origin),
        # OpenFreeMap's icon sheet (MIT; its icons are Maki, CC0: assets/sprites/LICENSE.md).
        # MapLibre adds .json, .png and @2x to this address; to swap sheets, change this line (D12).
        "sprite": f"{origin}/maps/sprites/ofm",
        "sources": {
            SRC: {"type": "vector", "tiles": [f"{origin}/tiles/basemap/{{z}}/{{x}}/{{y}}"],
                  "minzoom": 0, "maxzoom": BASEMAP_MAX_ZOOM, "attribution": OSM_CREDIT},
            # Heights stored as colours (Terrarium encoding) in 512-pixel tiles, as Mapterhorn makes them.
            # dem-shared:// is answered by the contour plug-in, not the network. It downloads each tile once
            # and shares it between the hillshade and the contour lines.
            "terrain": {"type": "raster-dem", "tiles": ["dem-shared://{z}/{x}/{y}"],
                        "encoding": "terrarium", "tileSize": 512, "maxzoom": terrain_max_zoom,
                        "attribution": TERRAIN_CREDIT},
            # The contour sources carry the terrain credit too: MapLibre shows a source's credit only
            # while a visible layer uses it, and contours can be shown with the hillshade hidden.
            "contours": {"type": "vector", "tiles": [CONTOUR_URL], "maxzoom": CONTOUR_MAX_ZOOM,
                         "attribution": TERRAIN_CREDIT},
            # A copy of the contour lines traced one zoom coarser (overzoom=1), used only to place labels.
            # Text cannot follow the full-detail lines' sharp bends, so most labels would be dropped.
            "contour_labels": {"type": "vector", "tiles": [CONTOUR_URL + "&overzoom=1"],
                               "maxzoom": CONTOUR_MAX_ZOOM, "attribution": TERRAIN_CREDIT},
        },
        "layers": LAYERS,
    }
