# Research and field protocol

## Question

Can capture checks reduce unreliable decisions in a wearable-assisted inspection
workflow while keeping the retake burden acceptable? The current benchmark
model is a starting point for this study, not evidence that this claim holds.

## Existing evidence

The Phase 1 study covers bottle, grid and transistor, three MVTec AD categories,
using one WideResNet50_2 backbone and separate normal validation data. Historical
image-level AUROC values were 1.0000, 0.9883 and 0.9983 respectively. Full
threshold-specific counts and protocol are in the Phase 1 results documents.
These are not a full 15-category result or a wearable-camera result.

The inherited PatchCore pipeline and earlier work must be credited. The new work
is baseline repair, independent validation, offline packaging, capture-aware
inspection and the application workflow. Using an established method is not a
claim of a novel anomaly-detection algorithm.

## Controlled synthetic study

The capture stress script applies the same predefined conditions to every
held-out image: unchanged capture, Gaussian blur radius 5, brightness multiplier
0.08 and multiplier 4. These simulate only a few capture problems. They do not
represent real optical glare, camera motion distributions or glasses optics.

Use the original frozen anomaly threshold and the fixed capture-check policy.
Compare baseline decisions with accepted decisions. Report coverage, accepted
defect recall, false positives, rejected defects and the end-to-end detected
defect fraction. A rejected defect is a request for another capture, not a
successful detection. Include zero-coverage cases rather than hiding them.

If thresholds are changed after inspecting these results, this becomes development
data. A fresh untouched evaluation set is then required. Do not use this study to
claim an independently validated operating threshold.

## Real capture collection

Start with one product family and a fixed view. Agree with the team which defects
matter, what a visible defect looks like, and what error rates are acceptable.
Collect both good and defective physical parts where available. Record:

- product ID, physical part ID, capture session and operator;
- device/camera, view, distance and lighting condition;
- normal/defect label, defect type and reviewer;
- permission for storage and any customer-data restrictions.

Use different physical parts and capture sessions for train, validation and test.
Keep all views or repeated frames of the same part together. Do not manufacture
ground truth from the model's own predictions. Independent human review is needed
for disputed labels. Avoid giving a phone model trained only on benchmark bottles
an unrelated industrial part and interpreting its score as defect evidence.

The validator accepts a local CSV with columns
`path,product_id,part_id,session_id,split,label`. Run
`python scripts/validate_capture_manifest.py manifest.csv path/to/images`.
It checks exact duplicates, split/group leakage, paths and normal-only training.
It cannot establish label correctness or detect every near-duplicate.

## Acceptance gates

1. Confirm clean splits and freeze the training/configuration record.
2. Validate operating thresholds without touching the final test set.
3. Evaluate baseline and capture-gated workflow on identical held-out captures.
4. Report per-product and per-condition outcomes, uncertainty intervals, coverage
   and failure examples, not just an average accuracy.
5. Measure cold/warm latency, upload size and laptop/tablet resource use.
6. Review errors with WCT before a supervised pilot. Do not automate safety-critical
   release or reject decisions from this prototype.

## Thesis and paper preparation

The thesis can describe the reproducible benchmark, engineering implementation,
capture stress study and limitations. A paper needs a defensible contribution,
relevant comparisons, ablations and adequate real evidence. A submission deadline
does not imply acceptance or publication. Keep the planned November 23 thesis
and December 18 paper-submission dates separate from measured deliverables.

Potential access to more than 50 MSMEs is a future evaluation/deployment pathway,
not completed deployment or a count of organisations already benefiting.
