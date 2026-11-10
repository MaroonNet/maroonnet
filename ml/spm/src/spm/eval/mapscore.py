"""MapScore, re-implemented in numpy.

Source: Sava, Twardy, Koester & Sonwalkar (2016), "Evaluating lost person
behavior models", Transactions in GIS 20(1):38-53, doi:10.1111/tgis.12143,
and the reference code in github.com/ctwardy/mapscore (framework/models.py,
``Test.rate``).

The metric (Rossmo's, rescaled by Koester so random maps score 0):

    n = number of cells with probability greater than the find cell
    m = number of cells with probability equal to the find cell
    N = total number of cells
    r = (n + m/2) / N          fraction of the map searched before the find, in priority order
    score = (0.5 - r) / 0.5    in [-1, 1]; uniform map = 0, perfect map ~ 1

Find outside the window: the original assumes the window is searched before
"rest of world" (ROW), so r = 1 - P(ROW). This version reads P(ROW) from
``Prediction.p_outside``. The original fell back to P(ROW) = 0.05 for images
that did not model ROW; that fallback is not reproduced because every SPM
prediction states its own p_outside.

Protocol constants in the original: 25 km square window centred on the IPP,
5 m cells (5001 x 5001). Scores for smooth maps barely depend on cell size,
so SPM defaults to 25 m cells (1001 x 1001) and keeps 5 m available.

Note on the original code: it reads the find cell as ``values[x, y]`` on an
array indexed [row, col], which transposes row and column. Ring maps are
symmetric about the IPP so their scores are unaffected, but asymmetric maps
would be scored at the wrong cell. SPM indexes [row, col].
"""

from __future__ import annotations

import numpy as np

from spm.schema import Case, Prediction


def score_raster(
    prob: np.ndarray, find_rc: tuple[int, int] | None, p_outside: float = 0.0
) -> float:
    """MapScore for a probability raster and a find cell (None = outside the window)."""
    if find_rc is None:
        r = 1.0 - p_outside
    else:
        p = prob[find_rc]
        n = np.count_nonzero(prob > p)
        m = np.count_nonzero(prob == p)
        r = (n + m / 2.0) / prob.size
    return (0.5 - r) / 0.5


def score(pred: Prediction, case: Case) -> float:
    """MapScore of ``pred`` against the case's true find location."""
    if case.find is None:
        raise ValueError(f"{case.case_id} has no find location to score against")
    find_rc = pred.window.rowcol(case.find.lon, case.find.lat)
    return score_raster(pred.prob, find_rc, pred.p_outside)
