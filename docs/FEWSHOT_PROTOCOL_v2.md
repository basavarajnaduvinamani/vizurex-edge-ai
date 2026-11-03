# Few-shot breadth protocol v2

Registered extension, 31 October 2026. This file must be committed before new
model runs. V1's primary bottle/grid/transistor results have already been seen;
this is a disclosed extension, not a fresh pre-registration of those results.
All fifteen categories' separate full-data PatchCore baseline results have also
been inspected. The remaining few-shot comparisons are new evaluations.

## Frozen methods and data

Inherit `docs/FEWSHOT_PROTOCOL.md` unchanged for image transforms (resize 256,
centre crop 224), pretrained weights, detector implementations, distance and
aggregation, 80/20 sorted normal-reference/validation split, p99 normal-only
validation threshold, pixel metrics, CPU execution and four torch threads.
No retuning based on observed test performance. No raw data or weights in Git.

Categories: bottle, cable, capsule, carpet, grid, hazelnut, leather, metal_nut,
pill, screw, tile, toothbrush, transistor, wood, zipper. Methods:
`patchcore_wrn50` and `dinov2_vits14`. Budgets: 1, 2, 4, 8, 16, full.
Seeds: 0, 1, 2 at EVERY budget, including full. Full reference membership is
identical across seeds: only stochastic PatchCore coreset selection changes.
DINOv2's deterministic full runs are repeats, not independent reference samples.

Reuse only complete v1 few-shot records with matching method, category, budget,
seed, transforms, reference filenames, detector settings and hashed private
prediction/calibration sidecars. Validate current dataset content using the
existing pinned dataset audit. Full-data step2 runs use a different scoring
harness and MUST NOT substitute for missing few-shot records. List all reuse and
exclusions in `docs/sprint/S2_INVENTORY.md` and its generated JSON.

Checkpoint each record and use a fresh output folder per category/attempt.
Recover a failed attempt by importing its validated completed records into a new
attempt, never overwriting old evidence. Freeze a work plan before execution.

## Analysis registered before new execution

- Publish every category/method/k/seed, mean and population SD (v1 convention).
- Macro AUROC: unweighted mean of category means, not pooled-image AUROC.
- Bootstrap percentile 95% intervals: resample categories with replacement,
  10,000 replicates, NumPy default_rng(20261101). Resample the same category
  indices for paired model differences. These describe category variation in
  this benchmark, not industrial deployment performance or extra independent
  seeds. Publish per-seed numbers separately.
- Texture split fixed by MVTec taxonomy: carpet, grid, leather, tile, wood.
  Remaining categories are objects. No regrouping after results.
- H1 retain v1's criterion for its ORIGINAL three primary categories; report
  breadth descriptively. Do not replace the original negative finding.
- H2 per category: absolute difference of full-shot method means is at most the
  larger population seed SD, or 0.01 if both SDs are zero. Overall H2 requires
  all categories. Also publish signed differences; a large positive difference
  can fail this equivalence-style rule and is not evidence of inferiority.
- Practical criterion: a shared k <= 8 gives mean AUROC >= .95 and false-alarm
  rate <= .10 in every category. Extra normal calibration images are still
  required beyond k. No onboarding-time or factory impact claim.

S3's router is not selected or tuned here; it requires its own committed
normal-validation-only protocol before any router analysis. No new dataset,
resolution, mask rule, threshold or baseline is introduced in this sprint item.

## Planned output and stopping

Two methods x six budgets x three seeds x fifteen categories = 540 planned
configurations (design count, not a completed result). Existing matching records
are included once with provenance; only missing configurations are executed.
Incomplete coverage produces an INCOMPLETE report, never a full-breadth claim.
