"""Re-weight a prediction with what the search already knows.

Two updates, both plain probability arithmetic on a ``Prediction``:

``apply_time_cap``   The subject cannot be where they could not yet have
                     walked. Cells whose travel time from the IPP
                     (geodata.travel) exceeds the hours elapsed get zero
                     mass; the rest is renormalized. If no cell on the
                     window edge is reachable, the mass beyond the window
                     is zero too. The travel speeds are a purposeful
                     walker's, so the cap is generous: it never claims
                     more than "not physically reachable yet".

``apply_search``     Bayes' rule after a search that did not find the
                     subject. With POD_c the probability a search of cell
                     c would have found them if they were there:

                         P(c | not found) = P(c) (1 - POD_c) / (1 - sum_k P(k) POD_k)

                     Unsearched cells and the mass beyond the window keep
                     their numerator and grow by the same factor. This is
                     the standard search-theory update the (P)MP segment
                     probabilities assume; the POD per segment comes from
                     the teams' coverage, not from this model.

Both keep the model's out-of-range flags and record the step in the
prediction's ``model`` name, so an exported raster says what was done to it.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from spm.schema import Prediction


def apply_time_cap(pred: Prediction, hours: np.ndarray, elapsed_h: float) -> Prediction:
    """Zero the cells not reachable within ``elapsed_h`` hours and renormalize."""
    if hours.shape != pred.prob.shape:
        raise ValueError(f"hours shape {hours.shape} != prediction {pred.prob.shape}")
    reachable = hours <= elapsed_h
    edge = np.zeros(pred.prob.shape, bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    p_outside = pred.p_outside if reachable[edge].any() else 0.0
    prob = np.where(reachable, pred.prob, 0.0)
    inside = float(prob.sum())
    if inside <= 0.0:  # nothing reachable, not even the start: keep the single nearest cell
        prob = np.zeros_like(prob)
        prob[np.unravel_index(np.argmin(hours), hours.shape)] = 1.0 - p_outside
    else:
        prob *= (1.0 - p_outside) / inside
    return dataclasses.replace(
        pred, prob=prob, p_outside=p_outside, model=f"{pred.model}+cap{elapsed_h:g}h"
    )


def combine_pod(layers: list[np.ndarray]) -> np.ndarray:
    """POD of several independent searches of the same cells: 1 - prod(1 - POD_i)."""
    miss = np.ones_like(layers[0], dtype=float)
    for pod in layers:
        miss *= 1.0 - np.clip(pod, 0.0, 1.0)
    return 1.0 - miss


def apply_search(pred: Prediction, pod: np.ndarray) -> Prediction:
    """Posterior after searching with per-cell ``pod`` (0 where unsearched) and not finding."""
    if pod.shape != pred.prob.shape:
        raise ValueError(f"pod shape {pod.shape} != prediction {pred.prob.shape}")
    pod = np.clip(np.nan_to_num(pod, nan=0.0), 0.0, 1.0)
    found = float((pred.prob * pod).sum())
    miss = 1.0 - found
    if miss <= 1e-9:
        raise ValueError("the search covered all the probability; nothing left to update")
    return dataclasses.replace(
        pred,
        prob=pred.prob * (1.0 - pod) / miss,
        p_outside=pred.p_outside / miss,
        model=f"{pred.model}+search",
    )
