"""The shape rules: sides that cross, and corners inside the search area."""

import pytest

from sectors.shape import inside, sides_cross

from sectors.tests.conftest import BEAR_CREEK_AREA, SQUARE


class Area:
    """A search area with the four fields the rule reads."""
    min_lat, min_lon = BEAR_CREEK_AREA["min_lat"], BEAR_CREEK_AREA["min_lon"]
    max_lat, max_lon = BEAR_CREEK_AREA["max_lat"], BEAR_CREEK_AREA["max_lon"]


@pytest.mark.parametrize("shape", [
    SQUARE,
    [(40.0, -105.6), (40.05, -105.6), (40.0, -105.55)],                                # a triangle
    [(40.0, -105.6), (40.05, -105.6), (40.02, -105.58), (40.05, -105.55), (40.0, -105.55)],  # a notch: one corner bent in
])
def test_a_shape_whose_sides_do_not_cross_is_allowed(shape):
    assert not sides_cross(shape)


@pytest.mark.parametrize("shape", [
    [(40.0, -105.6), (40.05, -105.55), (40.05, -105.6), (40.0, -105.55)],              # a bow-tie
    [(40.0, -105.6), (40.02, -105.6), (40.05, -105.6)],                               # three corners in a line
    [(40.0, -105.6), (40.05, -105.6), (40.05, -105.55), (40.05, -105.6)],             # a side that doubles back
    [(40.0, -105.6), (40.05, -105.6), (40.05, -105.55), (40.0, -105.55), (40.0, -105.6)],  # the first corner again at the end
    [(40.0, -105.6), (40.04, -105.6), (40.04, -105.56), (40.0, -105.56), (40.04, -105.58)],  # a corner on another side
])
def test_a_shape_whose_sides_cross_or_touch_is_refused(shape):
    assert sides_cross(shape)


def test_a_shape_inside_the_search_area_is_inside():
    assert inside(SQUARE, Area)


def test_a_corner_on_the_search_area_line_counts_as_inside():
    on_the_line = [(39.9, -105.7), (40.1, -105.7), (40.1, -105.5), (39.9, -105.5)]  # the area itself
    assert inside(on_the_line, Area)


@pytest.mark.parametrize("corner", [(40.1001, -105.6), (39.8999, -105.6), (40.0, -105.7001), (40.0, -105.4999)])
def test_one_corner_past_the_line_is_outside(corner):
    assert not inside([*SQUARE[:3], corner], Area)
