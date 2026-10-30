"""Metrics for the few-shot harness.

Image-level counts reuse ``patchcore.metrics.compute_imagewise_retrieval_metrics``
with a manual threshold, the same rule as Phase 1: the operating threshold is
the 99th percentile of normal validation scores, fixed before test scoring.
Pixel AUPRO is added here because the inherited package has no
implementation; it follows the MVTec AD definition (mean per-region overlap,
integrated up to a 30% pixel false-positive rate and normalized).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

VALIDATION_QUANTILE = 99.0


def validation_threshold(validation_scores, quantile: float = VALIDATION_QUANTILE) -> float:
    scores = np.asarray(validation_scores, dtype=np.float64)
    if scores.size == 0:
        raise ValueError("A normal validation set is required to fix the threshold")
    return float(np.percentile(scores, quantile))


def image_metrics(scores, labels, threshold: float) -> dict:
    from sklearn.metrics import average_precision_score
    from patchcore.metrics import compute_imagewise_retrieval_metrics

    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=int)
    both = len(np.unique(labels)) > 1
    counts = compute_imagewise_retrieval_metrics(scores, labels, manual_threshold=threshold)
    tp, fp, tn, fn = (int(counts[key]) for key in ("tp", "fp", "tn", "fn"))
    return {
        # The inherited helper returns 0.0 for a one-class set; report None.
        "image_auroc": float(counts["auroc"]) if both else None,
        "average_precision": float(average_precision_score(labels, scores)) if both else None,
        "threshold": float(threshold), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "defect_recall": tp / (tp + fn) if tp + fn else None,
        "false_alarm_rate": fp / (fp + tn) if fp + tn else None,
    }


def pixel_auroc(gt_masks: np.ndarray, maps: np.ndarray) -> Optional[float]:
    from sklearn.metrics import roc_auc_score

    gt = np.asarray(gt_masks, dtype=bool).ravel()
    if gt.all() or not gt.any():
        return None
    return float(roc_auc_score(gt, np.asarray(maps, dtype=np.float32).ravel()))


def compute_aupro(gt_masks: np.ndarray, maps: np.ndarray, fpr_limit: float = 0.3,
                  num_thresholds: int = 200) -> Optional[float]:
    """Normalized area under the per-region-overlap curve up to ``fpr_limit``.

    gt_masks: (n, H, W) bool; maps: (n, H, W) float. Returns None when there
    are no anomalous pixels (for example a category without masks).
    """
    from scipy import ndimage

    gt = np.asarray(gt_masks, dtype=bool)
    maps = np.asarray(maps, dtype=np.float64)
    if gt.shape != maps.shape:
        raise ValueError(f"mask shape {gt.shape} != map shape {maps.shape}")
    if not gt.any() or gt.all():
        return None
    normal = np.sort(maps[~gt])
    regions = []
    for image_mask, image_map in zip(gt, maps):
        labelled, count = ndimage.label(image_mask)
        for region in range(1, count + 1):
            regions.append(np.sort(image_map[labelled == region]))
    # Thresholds placed at normal-pixel quantiles give even resolution in FPR.
    targets = np.linspace(0.0, fpr_limit, num_thresholds)
    thresholds = np.quantile(normal, 1.0 - targets)
    thresholds = np.concatenate([[np.inf], thresholds])

    def fraction_above(sorted_values, t):
        # Strictly above t, so a threshold at a normal-pixel value excludes it.
        return (sorted_values.size - np.searchsorted(sorted_values, t, side="right")) / sorted_values.size

    fprs = np.array([fraction_above(normal, t) for t in thresholds])
    pros = np.array([np.mean([fraction_above(r, t) for r in regions]) for t in thresholds])
    order = np.lexsort((pros, fprs))
    fprs, pros = fprs[order], pros[order]
    keep = fprs <= fpr_limit
    fprs, pros = fprs[keep], pros[keep]
    if fprs[-1] < fpr_limit:
        # Extend the last observed overlap to the limit (conservative step).
        fprs = np.append(fprs, fpr_limit)
        pros = np.append(pros, pros[-1])
    return float(np.trapezoid(pros, fprs) / fpr_limit) if hasattr(np, "trapezoid") \
        else float(np.trapz(pros, fprs) / fpr_limit)
