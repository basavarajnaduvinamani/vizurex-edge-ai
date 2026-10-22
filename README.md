# VisureX Edge AI

Trustworthy industrial visual inspection using anomaly detection, mobile edge inference, and smart-glasses-assisted image capture.

## Current status

Private Wi-Fi support and an experimental on-device Android ONNX mode are now
implemented. The portable graphs match all 261 reference decisions on the laptop;
physical Android inference, memory use and image-level preprocessing agreement
still need testing. See [phone testing](docs/WIFI_AND_OFFLINE_TESTING.md).

The 22 October software expansion adds verified offline model bundles,
experimental capture checks with a separate RETAKE outcome, an Android
phone/tablet companion, dataset-group validation and CI checks. See
[software handover](docs/SOFTWARE_HANDOVER.md) and the
[research/field protocol](docs/RESEARCH_AND_FIELD_PROTOCOL.md).
The companion defaults to laptop inference through USB; experimental local CPU
inference is a separate option. Physical-device testing and Meta integration
remain separate gates.

Phase 2 is complete as a local web inspection prototype: real model inference,
fixed-scale heatmaps, upload validation, metadata logs and explicit Live/Demo
modes. See [Phase 2 verification](docs/results/PHASE2_COMPLETE_2026-10-21.md).
Start with `backend/README.md`. Next is the Android companion prototype;
phone-local inference and real glasses capture are not yet validated.

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

