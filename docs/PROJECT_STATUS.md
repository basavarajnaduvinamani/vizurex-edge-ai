# Project status

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
