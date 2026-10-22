# Project status

Latest follow-up on 22 October: optional authenticated private-Wi-Fi support
and experimental Android-local ONNX inference are implemented. Three portable
graphs match all 261 reference decisions on the laptop. Android hardware
qualification, capture reliability and industrial validation remain pending.
See `WIFI_AND_OFFLINE_TESTING.md` and `SOFTWARE_CHECKPOINT_2026-10-22.md`.

## Software expansion — 22 October 2026

- Offline bundles reproduced all 261 held-out Phase 1 scores and decisions
  across bottle, grid and transistor (score tolerance 0.0002 against rounded CSV).
- Capture checks can return RETAKE without claiming a defect verdict. This
  optional policy is heuristic and remains experimental.
- Android companion source supports camera/gallery, USB-backed inspection,
  result overlays and offline speech. Physical tablet validation is pending.
- Dataset intake checks reject exact repeats and physical-part/session leakage.
- CI source checks, a clean-environment bootstrap, synthetic capture experiment
  and handover/research protocols are provided.

See `SOFTWARE_HANDOVER.md` for use and limitations. This does not close the
real-device, factory-evaluation, mobile-inference or publication gates.

## Latest milestone — Phase 2 complete

The local web inspection prototype is verified against the real Phase 1
models, with 13 backend tests, 17 frontend checks and browser upload/result
verification. See `results/PHASE2_COMPLETE_2026-10-21.md`.
Next: Android companion application using the laptop inspection backend.

## Current update — 21 October 2026

The three-category feasibility gate is complete. Fresh training, evaluation
and saved-model score/decision checks passed on bottle, grid and transistor.
See `results/PHASE1_RESULTS_2026-10-21.md` for measured results and limitations.
Next: laptop-backed inspection service and Android integration prototype.
The earlier intake notes below are historical, not the current integration gate.

## Historical intake and full-benchmark plan

The upstream implementation and datasets have been inventoried and audited. The inherited prototype is technically substantive, but its current performance figures are not yet suitable as a trustworthy baseline.

Verified intake findings:

- Top view: all 50 test-good images are exact copies of training images.
- Bottom view: no exact train-good/test-good overlap was found.
- Side view: no exact train-good/test-good overlap was found, but one image has contradictory normal and known-defect roles.
- The existing validation loader reads from `test/good`.
- Existing execution scripts contain machine-specific paths.

The immediate milestone is now a controlled MVTec AD benchmark of standard PatchCore versus the inherited VisureX pipeline and its individual additions. See `docs/MVTEC_BENCHMARK_PROTOCOL.md`. Smart-glasses work begins only after that decision gate passes.

Upstream snapshot audited: `87721a681dcbee6cf1786f571b40c2906ec5ef18`.
