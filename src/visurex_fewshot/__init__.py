"""Training-free k-shot patch nearest-neighbour anomaly detection harness.

Research code for the few-shot protocol in ``docs/FEWSHOT_PROTOCOL.md``.
It compares frozen DINOv2 patch features (AnomalyDINO-style scoring) with the
repository's WideResNet-50 PatchCore embedding under identical shots, splits,
thresholds and metrics. It contains no results; see the protocol document.
"""

__all__ = ["backbones", "data", "detector", "metrics", "report"]
