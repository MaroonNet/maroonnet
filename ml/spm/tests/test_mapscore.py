import numpy as np
import pytest

from spm.eval.mapscore import score_raster


def test_uniform_map_scores_zero():
    assert score_raster(np.ones((11, 11)), (3, 7)) == pytest.approx(0.0)


def test_find_at_unique_peak_scores_near_one():
    prob = np.zeros((101, 101))
    prob[50, 50] = 1.0
    # r = (0 + 1/2) / N, so score = 1 - 1/N
    assert score_raster(prob, (50, 50)) == pytest.approx(1 - 1 / prob.size)


def test_find_in_lowest_cell_scores_near_minus_one():
    prob = np.arange(100.0).reshape(10, 10)
    assert score_raster(prob, (0, 0)) == pytest.approx(-1 + 1 / prob.size)


def test_find_outside_uses_p_outside():
    prob = np.full((5, 5), 0.9 / 25)
    # window searched first: r = 1 - P(outside) = 0.9 -> score -0.8
    assert score_raster(prob, None, p_outside=0.1) == pytest.approx(-0.8)


def test_rows_and_columns_are_not_transposed():
    prob = np.zeros((5, 5))
    prob[1, 3] = 1.0  # row 1, col 3
    assert score_raster(prob, (1, 3)) > 0.9
    assert score_raster(prob, (3, 1)) < 0.2
