"""Sub-cell features: compute on a fine grid, integrate the intensity over each model cell.

A 100 m model cell is too coarse to say "within 20 m of a trail": distances
measured between 100 m cell centres jump 0, 100, 141, ... and the near bins
stay empty. So features are computed on a fine window with the same extent
(e.g. 10 m cells, ``factor`` = 10) and binned there.

Each sub-cell has intensity exp(sum over features of theta[its bin]), so
exp(theta[bin]) is a point multiplier: how much more likely a find is at a
point in that bin, the quantity Jacobs (2015) reports. A model cell's score is
the log of the mean intensity over its sub-cells, which is the exact integral
of that point process over the cell:

    s(cell) = log( 1/n_sub * sum over sub-cells exp(sum_f theta[f, bin_f(sub)]) )

(Averaging the bins' log-weights instead would make the weights depend on the
cell size: a trail covering 29% of a cell would need theta ~ 1/0.29 times too
large.) With ``factor`` = 1 each cell is its own single sub-cell, so this is
plain binning of the cell.

``SubcellDesign`` stores, per cell, how many sub-cells show each distinct
combination of bins ("pattern"); scores and gradients are sparse products.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from spm.features.spec import FeatureSpec
from spm.geodata.grid import Window


def fine_window(window: Window, feature_res: float | None) -> tuple[Window, int]:
    """Window with the same extent at ``feature_res``, and the sub-cells per side."""
    if feature_res is None or feature_res >= window.res:
        return window, 1
    factor = int(round(window.res / feature_res))
    if abs(factor * feature_res - window.res) > 1e-6:
        raise ValueError(f"feature_res {feature_res} must divide model res {window.res}")
    return Window(window.epsg, window.x0, window.y0, window.res / factor, window.n * factor), factor


@dataclass(frozen=True)
class SubcellDesign:
    """counts[cell, u] sub-cells of each cell with bin pattern u; patterns[u] its 0/1 bins."""

    counts: sparse.csr_matrix  # (cells, patterns)
    patterns: np.ndarray  # (patterns, K)
    n_sub: int  # sub-cells per cell

    @property
    def n_cells(self) -> int:
        return self.counts.shape[0]

    @classmethod
    def from_features(
        cls, specs: list[FeatureSpec], feats: dict[str, np.ndarray], factor: int
    ) -> SubcellDesign:
        """Design for every model cell of a window from features on its fine grid."""
        n_fine = next(iter(feats.values())).shape[0] if feats else factor
        n = n_fine // factor
        code = np.zeros((n_fine, n_fine), dtype=np.int64)
        radix = 1
        digits = []  # (spec index, radix) of each feature present
        for i, s in enumerate(specs):
            if s.name in feats:
                code += radix * s.bin_index(feats[s.name]).astype(np.int64)
                digits.append((i, radix))
                radix *= s.n_bins
        coarse = np.arange(n_fine) // factor
        cell = (coarse[:, None] * n + coarse[None, :]).ravel()  # model cell of each sub-cell
        key, cnt = np.unique(cell * radix + code.ravel(), return_counts=True)
        cell_of, code_of = np.divmod(key, radix)
        uniq, col = np.unique(code_of, return_inverse=True)
        counts = sparse.csr_matrix((cnt, (cell_of, col)), shape=(n * n, len(uniq)))
        offsets = np.cumsum([0] + [s.n_bins for s in specs])
        patterns = np.zeros((len(uniq), int(offsets[-1])), dtype=np.float32)
        for i, r in digits:
            b = (uniq // r) % specs[i].n_bins
            patterns[np.arange(len(uniq)), offsets[i] + b] = 1.0
        return cls(counts, patterns, factor * factor)

    @classmethod
    def from_cell_bins(cls, x: np.ndarray) -> SubcellDesign:
        """One sub-cell per cell, given its 0/1 bin indicators (cells, K). For tests."""
        uniq, col = np.unique(x, axis=0, return_inverse=True)
        counts = sparse.csr_matrix(
            (np.ones(len(x)), (np.arange(len(x)), col.ravel())), shape=(len(x), len(uniq))
        )
        return cls(counts, uniq.astype(np.float32), 1)

    def take(self, cells: np.ndarray) -> SubcellDesign:
        """Rows ``cells`` only (patterns no longer used are kept; they cost nothing)."""
        return SubcellDesign(self.counts[cells], self.patterns, self.n_sub)

    def log_intensity(self, theta: np.ndarray, cap: float | None = None) -> np.ndarray:
        """(cells,) log mean sub-cell intensity under log-multipliers ``theta``.

        ``cap`` clips each sub-cell's log-multiplier before averaging, so a capped map
        is the same terrain at any output resolution (the cap is a sub-cell quantile).
        """
        z = self.patterns @ theta
        if cap is not None:
            z = np.minimum(z, cap)
        zmax = z.max() if z.size else 0.0
        return np.log(self.counts @ np.exp(z - zmax)) + zmax - np.log(self.n_sub)

    def any_pattern(self, mask: np.ndarray) -> np.ndarray:
        """(cells,) True where a cell contains any sub-cell whose pattern is in ``mask``."""
        return np.asarray(self.counts @ mask.astype(np.float32)).ravel() > 0

    def grad(self, theta: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """sum over cells of weights[cell] * d log_intensity[cell] / d theta."""
        z = self.patterns @ theta
        e = np.exp(z - z.max())
        rowsum = self.counts @ e
        v = self.counts.T @ (weights / rowsum)  # per pattern
        return (v * e) @ self.patterns


def point_pattern(
    specs: list[FeatureSpec], feats: dict[str, np.ndarray], rc: tuple[int, int]
) -> np.ndarray:
    """(K,) 0/1 bin indicators of the single fine cell ``rc`` (e.g. the find's own sub-cell)."""
    offsets = np.cumsum([0] + [s.n_bins for s in specs])
    out = np.zeros(int(offsets[-1]), dtype=np.float32)
    for i, s in enumerate(specs):
        if s.name in feats:
            out[offsets[i] + int(s.bin_index(feats[s.name][rc]))] = 1.0
    return out


def value_range(values: np.ndarray) -> tuple[float, float] | None:
    v = values[np.isfinite(values)]
    return (float(v.min()), float(v.max())) if v.size else None


def no_data(stack, factor: int) -> np.ndarray:
    """(n, n) True where a model cell has any fine cell without elevation (nothing to
    reason about there; the map hatches it)."""
    if not stack.has("dem"):
        return np.zeros((stack.window.n // factor,) * 2, bool)
    nan = ~np.isfinite(stack["dem"])
    n = nan.shape[0] // factor
    return nan.reshape(n, factor, n, factor).any(axis=(1, 3))


def out_of_range(
    specs: list[FeatureSpec],
    feats: dict[str, np.ndarray],
    ranges: dict[str, tuple[float, float]],
    factor: int,
) -> np.ndarray:
    """(n, n) True where any sub-cell has a feature value outside its training range,
    or no value at all (no elevation data there).

    Values are first clipped to the spec's outer edges: beyond the last edge every
    value lands in the same bin, so a cell 20 km from a trail is no more of an
    extrapolation than one 2 km away when the last edge is 40 m.
    """
    n_fine = next(iter(feats.values())).shape[0]
    n = n_fine // factor
    flags = np.zeros((n_fine, n_fine), bool)
    for s in specs:
        if s.name in feats:
            flags |= ~np.isfinite(feats[s.name])
        if s.name in feats and s.name in ranges:
            lo, hi = np.clip(ranges[s.name], s.edges[0], s.edges[-1])
            v = np.clip(feats[s.name], s.edges[0], s.edges[-1])
            flags |= np.isfinite(feats[s.name]) & ((v < lo) | (v > hi))
    return flags.reshape(n, factor, n, factor).any(axis=(1, 3))
