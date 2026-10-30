"""Training-free k-shot patch nearest-neighbour detector.

The memory bank is the set of patch features from k normal reference images.
Each test patch is scored by its distance to the nearest reference patch; the
image score aggregates those patch distances. With ``metric='cosine'`` and
``aggregation='mean_top'`` this follows AnomalyDINO (Damm et al., 2025). With
``metric='l2'``, ``aggregation='max'`` and an optional greedy coreset it is the
PatchCore scoring rule used by this repository.

Nearest-neighbour search, coreset sampling and map upsampling reuse the
inherited ``patchcore`` package so both methods share one implementation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional, Tuple

import numpy as np
import torch


@dataclass(frozen=True)
class DetectorConfig:
    metric: str = "cosine"            # "cosine" or "l2" (squared, as FAISS returns)
    aggregation: str = "mean_top"     # "max" or "mean_top"
    top_fraction: float = 0.01        # used by mean_top: mean of the top 1% patches
    coreset_fraction: Optional[float] = None  # None keeps every reference patch
    masking: bool = False             # optional zero-shot foreground masking

    def __post_init__(self):
        if self.metric not in ("cosine", "l2"):
            raise ValueError(f"Unknown metric: {self.metric}")
        if self.aggregation not in ("max", "mean_top"):
            raise ValueError(f"Unknown aggregation: {self.aggregation}")
        if not 0 < self.top_fraction <= 1:
            raise ValueError("top_fraction must be in (0, 1]")
        if self.coreset_fraction is not None and not 0 < self.coreset_fraction <= 1:
            raise ValueError("coreset_fraction must be in (0, 1]")

    def to_dict(self):
        return asdict(self)


def _normalize(features: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(features, axis=-1, keepdims=True)
    return (features / np.maximum(norms, 1e-12)).astype(np.float32)


class ForegroundMask:
    """Zero-shot foreground estimate from the first principal component of
    reference patch features (the masking idea in AnomalyDINO, simplified).

    The sign is chosen so the central patches of the reference images are
    foreground. Masking is an optional ablation and is off by default; it is
    inappropriate for textures (grid, carpet) where every patch is foreground.
    """

    def __init__(self, reference: np.ndarray, grid: Tuple[int, int]):
        flat = reference.reshape(-1, reference.shape[-1]).astype(np.float64)
        self.mean = flat.mean(axis=0)
        # Principal direction via SVD of centred features.
        _, _, vt = np.linalg.svd(flat - self.mean, full_matrices=False)
        self.direction = vt[0]
        projection = self._project(reference)
        h, w = grid
        centre = np.zeros((h, w), dtype=bool)
        centre[h // 4: h - h // 4, w // 4: w - w // 4] = True
        if projection[:, centre.ravel()].mean() < projection[:, ~centre.ravel()].mean():
            self.direction = -self.direction

    def _project(self, features):
        return (features.astype(np.float64) - self.mean) @ self.direction

    def __call__(self, features: np.ndarray) -> np.ndarray:
        mask = self._project(features) > 0
        # Never leave an image with nothing to score.
        mask[~mask.any(axis=1)] = True
        return mask


class KShotPatchNN:
    def __init__(self, config: DetectorConfig, seed: int = 0, num_workers: int = 4):
        self.config = config
        self.seed = seed
        self.num_workers = num_workers
        self.grid = None
        self.memory_size = 0
        self.mask = None
        self._nn = None

    def _prepare(self, features: np.ndarray) -> np.ndarray:
        features = features.astype(np.float32)
        return _normalize(features) if self.config.metric == "cosine" else features

    def fit(self, reference: np.ndarray, grid: Tuple[int, int]) -> "KShotPatchNN":
        """reference: (k, h * w, D) patch features of k normal images."""
        import patchcore.common
        import patchcore.sampler

        if reference.ndim != 3 or reference.shape[0] < 1:
            raise ValueError("reference must have shape (k, patches, dim) with k >= 1")
        if reference.shape[1] != grid[0] * grid[1]:
            raise ValueError("reference patch count does not match grid")
        self.grid = tuple(grid)
        bank = self._prepare(reference).reshape(-1, reference.shape[-1])
        if self.config.coreset_fraction is not None and self.config.coreset_fraction < 1:
            np.random.seed(self.seed)
            torch.manual_seed(self.seed)
            sampler = patchcore.sampler.ApproximateGreedyCoresetSampler(
                self.config.coreset_fraction, torch.device("cpu"))
            bank = np.ascontiguousarray(sampler.run(bank), dtype=np.float32)
        self.memory_size = int(bank.shape[0])
        self._nn = patchcore.common.FaissNN(False, self.num_workers)
        self._nn.fit(np.ascontiguousarray(bank))
        self.mask = ForegroundMask(reference, grid) if self.config.masking else None
        return self

    def patch_scores(self, features: np.ndarray) -> np.ndarray:
        """Nearest-reference distance for every patch: (B, h * w)."""
        if self._nn is None:
            raise RuntimeError("fit() must be called before scoring")
        b, n, d = features.shape
        query = np.ascontiguousarray(self._prepare(features).reshape(-1, d))
        distances, _ = self._nn.run(1, query)
        distances = np.maximum(distances[:, 0], 0.0)
        if self.config.metric == "cosine":
            # Squared L2 between unit vectors is 2 * (1 - cos).
            distances = distances / 2.0
        return distances.reshape(b, n).astype(np.float32)

    def image_scores(self, patch_scores: np.ndarray, features: np.ndarray = None) -> np.ndarray:
        valid = np.ones_like(patch_scores, dtype=bool)
        if self.mask is not None:
            if features is None:
                raise ValueError("masking needs the patch features")
            valid = self.mask(features)
        scores = []
        for row, keep in zip(patch_scores, valid):
            values = row[keep]
            if self.config.aggregation == "max":
                scores.append(float(values.max()))
            else:
                top = max(1, int(np.ceil(self.config.top_fraction * values.size)))
                scores.append(float(np.sort(values)[-top:].mean()))
        return np.asarray(scores, dtype=np.float64)

    def anomaly_maps(self, patch_scores: np.ndarray, image_size: Tuple[int, int]) -> np.ndarray:
        """Bilinear upsampling plus Gaussian smoothing (sigma 4), via the
        inherited PatchCore segmentor."""
        import patchcore.common

        segmentor = patchcore.common.RescaleSegmentor(torch.device("cpu"), target_size=tuple(image_size))
        grids = patch_scores.reshape(-1, *self.grid).astype(np.float32)
        return np.stack(segmentor.convert_to_segmentation(grids))

    def predict(self, features: np.ndarray, image_size: Tuple[int, int] = None):
        patch = self.patch_scores(features)
        scores = self.image_scores(patch, features)
        maps = self.anomaly_maps(patch, image_size) if image_size is not None else None
        return scores, maps
