"""The map style: the document that tells MapLibre what to draw and how.

Rebuilt from the POC's make_style.py. Every layer carries metadata.group, which the web app's
layer switches turn on and off as a unit. Layers are drawn in list order: the first at the bottom.
"""

PAPER = "#f4f1e8"


def build_style() -> dict:
    return {
        "version": 8,  # the style format's version, not ours; MapLibre accepts only 8
        "name": "MaroonNet SAR",
        "sources": {},
        "layers": [
            {"id": "paper", "type": "background", "metadata": {"group": "base"},
             "paint": {"background-color": PAPER}},
        ],
    }
