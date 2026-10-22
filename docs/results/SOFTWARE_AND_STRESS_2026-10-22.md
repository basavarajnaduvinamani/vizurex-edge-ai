# Software verification and capture stress results

## Offline model verification

All 261 held-out images reproduced the Phase 1 predictions when loaded from
the offline bundles: bottle 83, grid 78 and transistor 100. Scores matched the
rounded historical CSV within 0.0002 and all decisions matched. Backbone download
was prohibited in the verification process.

The initial offline check failed because restoring an already initialized
backbone let the feature-shape probe update BatchNorm buffers again. Loading the
bundled backbone in evaluation mode prevented that second update. The complete
comparison then passed. Historical Phase 1 files were not changed.

## Synthetic capture study

The study used all 261 test images in four fixed conditions: 1,044 inspections.
No detector thresholds or capture-policy cutoffs were tuned after this run.
These conditions are synthetic, not a measurement of factory-camera behaviour.

| Category | Original: detected defects / total | Original: false alarms / good images | Blur: false alarms / good images | Darkened: requested retakes / all images |
|---|---:|---:|---:|---:|
| Bottle | 63/63 | 1/20 | 20/20 | 83/83 |
| Grid | 53/57 | 1/21 | 21/21 | 78/78 |
| Transistor | 39/40 | 3/60 | 60/60 | 100/100 |

Blur used Gaussian radius 5 on the source image; darkening used brightness 0.08.
The current heuristic rejected no original or blurred images. Under blur the
detector classified every test image as anomalous. Its resulting 100% defect
recall is therefore not useful on its own: the normal-image false-alarm rate was
also 100%. This is a capture-sensitivity failure, not improved defect detection.

At brightness multiplier 4, the capture policy accepted 81/83 bottle images,
2/78 grid images and 100/100 transistor images. All accepted normal images in
these conditions were false alarms. The darkened condition had zero accepted
images, so accepted-set recall is undefined; rejected defects are not counted
as successful detections.

## Decision

Continue building and testing the capture/application workflow, but do not
promote the heuristic policy to a reliable quality gate or claim readiness for
uncontrolled phone/glasses images. Keep benchmark mode as the default.

The next reliability study needs separate normal development captures, realistic
camera variation and untouched test captures. Thresholds should be selected on
development/validation data and frozen before final evaluation. The current
stress images have now been inspected and cannot be reused as an unseen test
set if the policy is adjusted using these results.

## Evidence and scope

The isolated Windows Python environment passed its dependency consistency check
and the complete backend/dataset integration suite. Frontend regression checks
include the new RETAKE path. Exact test counts are recorded in the final
software checkpoint after the Android build checks.

Local generated records:

- `artifacts/phase3/offline_parity.json`
- `artifacts/phase3/capture-stress/per_image.csv`
- `artifacts/phase3/capture-stress/summary.json`

The offline results establish loading parity, not a new benchmark improvement.
The synthetic study establishes a failure mode, not industrial deployment
performance. No actual tablet, glasses, factory pilot or publication is claimed.
