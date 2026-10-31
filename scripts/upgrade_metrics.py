"""Explicit image and exact-threshold pixel metrics; no test-set fitting."""
import numpy as np
from scipy.ndimage import label
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score


def image_metrics(labels, scores, threshold):
    labels, scores = np.asarray(labels), np.asarray(scores)
    predictions = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return dict(image_auroc=float(roc_auc_score(labels, scores)),
                f1=float(f1_score(labels, predictions, zero_division=0)),
                missed_defects=int(fn), false_alarms=int(fp), tp=int(tp), tn=int(tn),
                threshold=float(threshold), test_images=int(len(labels)))


def pixel_metrics(masks, maps, fpr_limit=0.3):
    """Macro per-connected-region overlap integrated up to normal-pixel FPR=.3.

    All distinct score thresholds are used, ties are processed together, and the
    endpoint is linearly interpolated. Masks must be nearest-neighbour resized
    binary masks in exactly the input crop. Connectivity is eight-neighbour.
    """
    masks = np.asarray(masks, dtype=bool)
    maps = np.asarray(maps, dtype=np.float32)
    if masks.shape != maps.shape or not np.isfinite(maps).all():
        raise ValueError('finite equal-shaped masks and maps required')
    weights = np.zeros(masks.shape, dtype=np.float64)
    regions = 0
    for i, mask in enumerate(masks):
        components, count = label(mask, structure=np.ones((3, 3)))
        sizes = np.bincount(components.ravel())
        for component in range(1, count + 1):
            weights[i][components == component] = 1.0 / sizes[component]
        regions += count
    if not regions or masks.all():
        raise ValueError('positive regions and background pixels required')
    weights /= regions
    flat = maps.ravel()
    order = np.argsort(-flat, kind='stable')
    sorted_scores = flat[order]
    ends = np.r_[np.flatnonzero(sorted_scores[1:] != sorted_scores[:-1]), len(order)-1]
    negatives = ~masks.ravel()
    fp = np.cumsum(negatives[order], dtype=np.int64)[ends] / negatives.sum()
    pro = np.cumsum(weights.ravel()[order])[ends]
    fp, pro = np.r_[0.0, fp], np.r_[0.0, pro]
    below = fp < fpr_limit
    x = np.r_[fp[below], fpr_limit]
    y = np.r_[pro[below], np.interp(fpr_limit, fp, pro)]
    # Duplicate FPR coordinates represent vertical segments and have zero area.
    area = np.trapezoid(y, x) / fpr_limit
    return dict(pixel_auroc=float(roc_auc_score(masks.ravel(), flat)),
                aupro_fpr_0_3=float(area), connected_regions=int(regions),
                foreground_pixels=int(masks.sum()), background_pixels=int(negatives.sum()),
                mask_shape=list(masks.shape), connectivity=8,
                method='exact distinct thresholds; tie groups; linear FPR endpoint; crop-aligned nearest masks')
