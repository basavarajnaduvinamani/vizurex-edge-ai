"""Splits, k-shot reference selection and one-pass feature extraction.

Split rules are the repository's: ``patchcore.datasets.mvtec.MVTecDataset``
with ``train_val_split=0.8``. The first 80% of sorted ``train/good`` files are
the reference pool, the last 20% are the normal validation holdout used only
for the operating threshold, and the official ``test`` folder is evaluation
only. k references are drawn from the pool without replacement by seed, so a
reference image can never also be a validation or test image.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np
import torch

TRAIN_VAL_SPLIT = 0.8


def find_categories(data_root: str, requested: Optional[Sequence[str]] = None) -> List[str]:
    """MVTec AD categories present under data_root (folders with train/good)."""
    from patchcore.datasets.mvtec import _CLASSNAMES

    names = list(requested) if requested else _CLASSNAMES
    return [name for name in names if os.path.isdir(os.path.join(data_root, name, "train", "good"))]


def load_splits(data_root: str, category: str, resize: int = 256, imagesize: int = 224):
    from patchcore.datasets.mvtec import DatasetSplit, MVTecDataset

    common = dict(source=data_root, classname=category, resize=resize, imagesize=imagesize)
    return {
        "train": MVTecDataset(split=DatasetSplit.TRAIN, train_val_split=TRAIN_VAL_SPLIT, **common),
        "val": MVTecDataset(split=DatasetSplit.VAL, train_val_split=TRAIN_VAL_SPLIT, **common),
        "test": MVTecDataset(split=DatasetSplit.TEST, **common),
    }


def select_shots(pool_size: int, k, seed: int) -> np.ndarray:
    """Indices of k reference images from the pool; ``k='full'`` keeps all."""
    if k == "full":
        return np.arange(pool_size)
    k = int(k)
    if k < 1:
        raise ValueError("k must be at least 1")
    if k > pool_size:
        raise ValueError(f"k={k} exceeds the {pool_size} available reference images")
    return np.sort(np.random.default_rng(seed).choice(pool_size, size=k, replace=False))


@dataclass
class EmbeddedSplit:
    features: np.ndarray            # (n, h * w, D)
    grid: tuple
    labels: np.ndarray              # (n,) 1 = anomaly
    masks: Optional[np.ndarray]     # (n, H, W) bool or None
    names: List[str]
    seconds_per_image: List[float]


def embed_split(backbone, dataset, batch_size: int = 1, keep_masks: bool = False) -> EmbeddedSplit:
    """Embed every image once; k-shot runs then reuse these cached features.

    Timing is wall-clock per batch divided by batch size, CPU only. With the
    default batch size 1 it matches the Phase 1 per-image model-call timing
    convention (model call only, decoding/preprocessing excluded).
    """
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    features, labels, masks, names, seconds = [], [], [], [], []
    grid = None
    for batch in loader:
        begin = time.perf_counter()
        batch_features, grid = backbone.embed(batch["image"])
        elapsed = time.perf_counter() - begin
        features.append(batch_features)
        labels.extend(int(x) for x in batch["is_anomaly"])
        names.extend(batch["image_name"])
        seconds.extend([elapsed / len(batch["image"])] * len(batch["image"]))
        if keep_masks:
            masks.append((batch["mask"][:, 0].numpy() > 0.5))
    return EmbeddedSplit(
        features=np.concatenate(features, axis=0), grid=grid, labels=np.asarray(labels),
        masks=np.concatenate(masks, axis=0) if keep_masks else None, names=names,
        seconds_per_image=seconds)
