# VisureX Edge AI

Trustworthy industrial visual inspection using anomaly detection, mobile edge inference, and smart-glasses-assisted image capture.

## Current status

Phase 1 now has fresh CPU results on MVTec AD bottle, grid and transistor,
including dataset checks and saved-model inference verification. The decision
is a controlled go-ahead for a laptop-backed integration prototype, not an
industrial reliability claim. See
[`docs/results/PHASE1_RESULTS_2026-10-21.md`](docs/results/PHASE1_RESULTS_2026-10-21.md).
The full 15-category benchmark remains later research work.

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

