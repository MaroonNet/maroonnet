import pytest

from spm.geodata.grid import Window, utm_epsg

LON, LAT = -105.6156, 40.2549  # Longs Peak area, Rocky Mountain NP


def test_colorado_is_utm_13n():
    assert utm_epsg(LON, LAT) == 32613


def test_window_is_odd_and_centred_on_ipp():
    w = Window.around(LON, LAT, side_m=25_000, res=25)
    assert w.n % 2 == 1
    row, col = w.rowcol(LON, LAT)
    assert abs(row - w.n // 2) <= 1 and abs(col - w.n // 2) <= 1


def test_origin_snapped_so_windows_share_cell_edges():
    a = Window.around(LON, LAT, res=30)
    b = Window.around(LON + 0.03, LAT - 0.02, res=30)
    assert a.x0 % 30 == 0 and a.y0 % 30 == 0
    assert (a.x0 - b.x0) % 30 == 0 and (a.y0 - b.y0) % 30 == 0


def test_point_outside_window_returns_none():
    w = Window.around(LON, LAT, side_m=5_000, res=25)
    assert w.rowcol(LON + 0.5, LAT) is None


def test_distance_grid_is_zero_near_ipp_and_metric():
    w = Window.around(LON, LAT, side_m=5_000, res=10)
    d = w.distance_from(LON, LAT)
    assert d.min() < 10
    # 0.01 deg latitude is about 1,112 m
    r, c = w.rowcol(LON, LAT + 0.01)
    assert d[r, c] == pytest.approx(1112, abs=15)
