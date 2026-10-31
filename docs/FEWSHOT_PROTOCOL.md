# Few-shot protocol for new parts

Status: **pre-registered protocol and harness only. No few-shot result exists yet.**
Nothing in this document is a measurement. Results will appear only in run folders
written by `scripts/run_fewshot.py` and, once reviewed, in a dated file under
`docs/results/` that cites those files.

## Motivation

The Phase 1 detector is the inherited PatchCore pipeline (WideResNet-50-2,
ImageNet weights) trained on 167–211 normal images per MVTec AD category
(`docs/results/PHASE1_RESULTS_2026-10-21.md`). An MSME introducing a new part
usually cannot collect hundreds of verified-normal captures before inspection
starts. The practical question is how much detection quality is lost when only
k = 1–16 normal images of the new part are available, and whether a stronger
frozen backbone (DINOv2) reduces that loss without any training.

## Hypothesis

H1. At k ≤ 8, a training-free nearest-neighbour detector on frozen DINOv2 ViT-S/14
patch features (AnomalyDINO-style scoring) has higher mean image AUROC than the
same detector on the repository's WideResNet-50 PatchCore features, under the
same reference images, splits, thresholds and metrics.

H2. At k = full, DINOv2 k-NN is not materially worse than full-shot PatchCore
(difference in mean image AUROC within the seed-to-seed spread).

H0 for both: no difference beyond seed variation. Either outcome is reportable.

## Methods compared

All methods share `src/visurex_fewshot/detector.py`: patch features from k normal
reference images form the memory bank; each test patch is scored by its distance to
the nearest reference patch (exact search through the inherited `patchcore.common.FaissNN`);
maps are upsampled and smoothed with the inherited `RescaleSegmentor` (sigma 4).

| Method id | Features | Distance | Image score | Memory bank |
|---|---|---|---|---|
| `patchcore_wrn50` at k = full | Phase 1 PatchCore embedding: WRN-50-2 layer2+layer3, 3x3 aggregation, 1024 → 384 dim | squared L2 | max patch | 1% approximate greedy coreset (Phase 1 setting) |
| `patchcore_wrn50` at k < full | same | squared L2 | max patch | all patches of the k images |
| `dinov2_vits14` | DINOv2 ViT-S/14 last-layer patch tokens (`vit_small_patch14_dinov2.lvd142m`, timm) | cosine | mean of top 1% patches | all patches |
| `dinov2_vits14_masked` (optional ablation) | same, plus zero-shot PCA foreground mask | cosine | mean of top 1% foreground patches | all patches |

Baselines named in the brief map to: **PatchCore full-shot** = `patchcore_wrn50`, k = full;
**PatchCore k-shot** = `patchcore_wrn50`, k < full; **DINOv2 k-shot** = `dinov2_vits14`.

The full-shot PatchCore here reuses the Phase 1 embedding code but runs through the
harness's own scoring loop, so its numbers are expected to be close to, but are not
guaranteed identical to, the Phase 1 table. Any difference will be reported, not
reconciled by editing either result.

Deviations from AnomalyDINO, stated in advance: default resolution is 224 px
(16 x 16 patches) for parity with Phase 1 preprocessing, while AnomalyDINO
reports 448–672 px; no rotation augmentation of references; the masking rule is a
simplified first-principal-component threshold. Higher resolution is a planned
ablation via `--resize 512 --imagesize 448`, reported separately.

## Data, splits and shots

- MVTec AD categories found under `--data-root`. Primary set: bottle, grid,
  transistor (the Phase 1 categories). Secondary: all 15 when compute allows.
- Each category must pass `scripts/validate_mvtec_category.py` (readability,
  exact train/test overlap, one-to-one masks). A failing category is skipped and
  the failure is recorded in `results.json`.
- Splits reuse the repository rule (`MVTecDataset`, `train_val_split=0.8`):
  first 80% of sorted `train/good` = reference pool, last 20% = normal validation
  holdout, official `test` = evaluation only.
- k ∈ {1, 2, 4, 8, 16, full}; seeds {0, 1, 2}. The seed selects k pool images
  without replacement (`numpy.random.default_rng(seed)`); the chosen filenames are
  saved with every run. k = full uses the whole pool and is run once (seed 0).
- All methods see exactly the same reference images for a given (category, k, seed).

## Fixed threshold policy

- Operating threshold = 99th percentile of the method's scores on the normal
  validation holdout, computed after fitting on the k references and before any
  test image is scored. Same rule as Phase 1.
- No threshold, k, seed, resolution or aggregation is changed after looking at
  test results. If anything is changed, the affected runs become development runs
  and are labelled as such.
- Limitation stated in advance: the validation holdout (≈ 20% of `train/good`)
  is extra normal data beyond the k references. Threshold-dependent numbers
  (recall, false-alarm rate) therefore describe "k references + a small normal
  calibration set", not a pure k-image deployment. Image AUROC and AUPRO are
  threshold-free and do not depend on it.

## Metrics

- Image AUROC (primary), average precision.
- Defect recall and normal false-alarm rate at the fixed threshold, with TP/FP/TN/FN
  counts (inherited `compute_imagewise_retrieval_metrics`).
- Pixel AUPRO up to 30% FPR and pixel AUROC on the 224 px centre-crop masks.
  Masks follow the same resize/crop as images, so defects outside the crop are
  not visible to any method, as in Phase 1.
- Mean ± standard deviation across seeds. With three seeds the spread is a rough
  indication, not a confidence interval; per-seed values are kept in `results.json`.

## What would count as success

Decided before running:

1. **Supports H1**: for at least 2 of the 3 primary categories, mean image AUROC of
   `dinov2_vits14` exceeds `patchcore_wrn50` at k = 1, 2, 4 and 8, each by more than
   the larger of the two seed standard deviations.
2. **Practically useful few-shot** (separate claim): some k ≤ 8 reaches mean image
   AUROC ≥ 0.95 *and* false-alarm rate ≤ 10% at the fixed threshold on every primary
   category. Benchmark success is still not factory validation.
3. **Supports H2**: at k = full the DINOv2 mean is within one seed standard deviation
   (or within 0.01 AUROC if the deviation is zero) of full-shot PatchCore.

Anything else is reported as a negative or mixed result with the full table.

## Compute budget (CPU)

The harness embeds every image once per backbone and category (batch 1, 4 threads,
timed), then reuses cached features across all k and seeds. `results.md` reports
per-category embedding median/p95 ms, total embedding seconds and per-image scoring
time; nothing is estimated in advance here. Phase 1 recorded 144–174 ms median
WRN-50 model calls on CPU, so the budget planning assumption is that one category
needs one embedding pass per backbone over about 250–330 images, plus nearest-
neighbour scoring for 16 (k, seed) runs per method. Record the machine with
`environment.json`. Colab CPU or GPU runs are allowed; timings from a GPU run are
reported separately and never mixed with the CPU column.

## How to run

```bash
pip install -r requirements-fewshot.txt
python scripts/run_fewshot.py --data-root data/raw/mvtec_ad --categories bottle grid transistor \
    --output artifacts/fewshot-run1
# optional ablation (separate output folder):
python scripts/run_fewshot.py --data-root data/raw/mvtec_ad --categories bottle transistor \
    --methods dinov2_vits14_masked --output artifacts/fewshot-masked-run1
```

`notebooks/fewshot_colab.ipynb` runs the same commands on Colab. The script refuses
to overwrite an existing `results.json`. `--report-only` regenerates `results.md`
and `fewshot_auroc.png` from saved records.

Offline tests (`python -m pytest scripts/test_fewshot.py -q`) use random-weight stubs
and synthetic images; their numbers test the code path only and are never results.

## Scope and honesty

This is an external benchmark study on MVTec AD, not the WCTE factory dataset, a
wearable-camera evaluation or a device measurement. A few-shot result would not
remove the need for real-capture validation, consented part/session-grouped data,
and the capture-quality work described in `RESEARCH_AND_FIELD_PROTOCOL.md`.
AnomalyDINO is an established published method; reproducing it on this repository's
splits is a baseline comparison, not a new algorithm.

Reference: S. Damm, M. Laszkiewicz, J. Lederer, A. Fischer, "AnomalyDINO: Boosting
Patch-based Few-shot Anomaly Detection with DINOv2", WACV 2025.
