# Project status

## Current gate: clean baseline

The upstream implementation and datasets have been inventoried and audited. The inherited prototype is technically substantive, but its current performance figures are not yet suitable as a trustworthy baseline.

Verified intake findings:

- Top view: all 50 test-good images are exact copies of training images.
- Bottom view: no exact train-good/test-good overlap was found.
- Side view: no exact train-good/test-good overlap was found, but one image has contradictory normal and known-defect roles.
- The existing validation loader reads from `test/good`.
- Existing execution scripts contain machine-specific paths.

The development repository will first reproduce inference, repair data splitting and calibration, and regenerate per-view metrics. Smart-glasses work begins only after that decision gate passes.

Upstream snapshot audited: `87721a681dcbee6cf1786f571b40c2906ec5ef18`.
