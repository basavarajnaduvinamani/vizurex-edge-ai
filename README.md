# VisureX Edge AI

Trustworthy industrial visual inspection using anomaly detection, mobile edge inference, and smart-glasses-assisted image capture.

## Current status

The inherited VisureX prototype has completed technical intake. The next milestone is a reproducible, leakage-free PatchCore baseline for the Top, Bottom, and Side views before mobile or smart-glasses integration begins.

## Development sequence

1. Reproduce inference with the supplied model artifacts.
2. Make training and evaluation portable and configuration-driven.
3. Build capture-group-aware train, validation, and test splits.
4. Retrain and report trustworthy per-view metrics.
5. Add mobile-camera capture and edge inference.
6. Integrate the validated mobile pipeline with supported Meta glasses interfaces.

## Repository policy

Raw industrial datasets, inherited model binaries, credentials, and private upstream material are not committed here. This repository will contain the independently maintained implementation, configuration, dataset manifests, evaluation code, and approved documentation.

