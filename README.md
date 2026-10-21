# VisureX Edge AI

Trustworthy industrial visual inspection using anomaly detection, mobile edge inference, and smart-glasses-assisted image capture.

## Current status

The inherited VisureX prototype has completed technical intake. A leakage-free
MVTec AD `bottle` smoke test now runs end to end on CPU. The next milestone is a
matched 15-category PatchCore baseline before mobile or smart-glasses
integration begins. See
[`docs/results/MVTEC_BOTTLE_SMOKE_2026-10-16.md`](docs/results/MVTEC_BOTTLE_SMOKE_2026-10-16.md).

## Development sequence

1. Reproduce inference with the supplied model artifacts.
2. Make training and evaluation portable and configuration-driven.
3. Build capture-group-aware train, validation, and test splits.
4. Retrain and report trustworthy per-view metrics.
5. Add mobile-camera capture and edge inference.
6. Integrate the validated mobile pipeline with supported Meta glasses interfaces.

## Repository policy

Raw industrial datasets, inherited model binaries, credentials, and generated
model artifacts are not committed here. The authorized upstream implementation
is being made portable and independently maintained here together with its
configuration, validation scripts, evaluation code, and approved documentation.

