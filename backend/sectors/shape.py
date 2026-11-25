"""The rules a sector's shape follows, apart from its number of corners.

A corner is (latitude, longitude). A sector is small next to the earth, so its sides are
treated as straight lines on a flat grid of degrees. The search area is a rectangle on that
same grid, so "inside" is exact.
"""

from collections.abc import Sequence
from typing import Protocol

Corner = tuple[float, float]  # latitude, longitude


class Bounds(Protocol):
    """A rectangle by its corners, as the search area is kept."""
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


def inside(corners: Sequence[Corner], area: Bounds) -> bool:
    """Whether every corner is inside the search area. A corner on its line counts as inside."""
    return all(area.min_lat <= lat <= area.max_lat and area.min_lon <= lon <= area.max_lon
               for lat, lon in corners)


def sides_cross(corners: Sequence[Corner]) -> bool:
    """Whether any two sides of the shape cross or touch. The last corner joins back to the
    first, so a shape needs no repeated corner to close it; one that repeats it is refused."""
    count = len(corners)
    sides = [(corners[i], corners[(i + 1) % count]) for i in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1:                    # neighbours: side i ends where side j starts
                if _doubles_back(sides[i][0], sides[i][1], sides[j][1]):
                    return True
            elif i == 0 and j == count - 1:   # the last side ends where the first starts
                if _doubles_back(sides[j][0], sides[i][0], sides[i][1]):
                    return True
            elif _meet(*sides[i], *sides[j]):
                return True
    return False


def _doubles_back(before: Corner, shared: Corner, after: Corner) -> bool:
    """Whether two neighbouring sides lie on top of each other: the path goes out to the
    shared corner and comes straight back along the same line. A side of no length counts."""
    if before == shared or after == shared:
        return True
    out = (before[0] - shared[0], before[1] - shared[1])
    back = (after[0] - shared[0], after[1] - shared[1])
    in_line = out[0] * back[1] - out[1] * back[0] == 0
    same_way = out[0] * back[0] + out[1] * back[1] > 0
    return in_line and same_way


def _meet(a: Corner, b: Corner, c: Corner, d: Corner) -> bool:
    """Whether the side a-b and the side c-d cross or touch."""
    ab_c, ab_d = _turn(a, b, c), _turn(a, b, d)
    cd_a, cd_b = _turn(c, d, a), _turn(c, d, b)
    if ab_c * ab_d < 0 and cd_a * cd_b < 0:
        return True  # each side has the other's ends on opposite sides of it
    # A corner lying on the other side.
    return ((ab_c == 0 and _within(a, b, c)) or (ab_d == 0 and _within(a, b, d))
            or (cd_a == 0 and _within(c, d, a)) or (cd_b == 0 and _within(c, d, b)))


def _turn(a: Corner, b: Corner, c: Corner) -> float:
    """Which way the path a to b to c turns: one sign for left, the other for right, zero
    when the three are in a line."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _within(a: Corner, b: Corner, c: Corner) -> bool:
    """Whether c, already known to be in line with a and b, lies between them."""
    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
