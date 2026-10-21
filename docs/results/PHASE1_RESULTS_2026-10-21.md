# Phase 1 validation — 21 October 2026

## Decision

**Controlled go-ahead for a laptop-backed integration prototype.** The inherited
PatchCore path was freshly trained, evaluated, saved and reloaded on three
MVTec AD categories. This establishes baseline functionality, not industrial
deployment readiness or superiority over standard PatchCore.

## Fresh results

| Category | Train / validation | Test normal / anomaly | Image AUROC | TP / FP / TN / FN | Defect recall | Normal false-alarm rate | Median / p95 inference |
|---|---:|---:|---:|---|---:|---:|---|
| Bottle | 167 / 42 | 20 / 63 | 1.0000 | 63 / 1 / 19 / 0 | 100% | 5.00% | 165 / 198 ms |
| Grid | 211 / 53 | 21 / 57 | 0.9883 | 53 / 1 / 20 / 4 | 92.98% | 4.76% | 174 / 226 ms |
| Transistor | 170 / 43 | 60 / 40 | 0.9983 | 39 / 3 / 57 / 1 | 97.50% | 5.00% | 144 / 188 ms |

These are CPU model-call timings, batch size 1, four PyTorch threads, after
loading the model. They exclude startup, image decoding/preprocessing,
camera transfer, API transport and speech. They are not glasses-to-answer
latency. Training plus initial evaluation took approximately 99, 124 and
121 seconds respectively; saved-model verification was additional work.

Across 261 test images, five defects were missed and five normal images were
flagged. No threshold was adjusted after looking at these test results.

## Protocol and integrity

- One WideResNet-50-2 backbone using ImageNet V1 weights, layer2/layer3 features,
  1024-dimensional preprocessing and 384-dimensional target embedding.
- 224-pixel centre crop after resize 256; seed 0; 1% approximate greedy coreset;
  one nearest neighbour; normal-only 80/20 training/validation holdout.
- The holdout is deterministic by sorted filename, not a random or
  capture-group-aware split. Official test folders remain untouched.
- Score normalization uses normal validation scores; the operating threshold
  is their 99th percentile. Test labels are used for evaluation, not fitting.
- All three datasets passed image readability, exact SHA-256 train/test
  overlap checks and one-to-one anomaly-mask filename checks.
- Zero exact overlap does not establish physical-object or near-duplicate
  independence. This is an external benchmark, not the WCTE factory dataset.
- Every saved model was reloaded and tested on the entire category test set.
  Scores matched fresh-run CSV values within 0.0002, and every binary decision
  matched. Validation thresholds reproduced within 0.0001.
- Geometric judgement and defect-bank stages were disabled for these runs.
  This is the PatchCore core, not evidence that the extra VisureX judges help.
- Test-wide normalization exists for visualization maps in the inherited
  runner, but is not used for the image scores/decisions reported here.
  Pixel-level metrics and production heatmap calibration remain unvalidated.

## Source and environment review

The local upstream snapshot is `87721a681dcbee6cf1786f571b40c2906ec5ef18`.
Before this phase, only `bin/run_patchcore1.py` and
`src/patchcore/datasets/mvtec.py` differed from matching upstream Python files.
The development repairs support normal-only holdout validation, CPU execution,
standard MVTec runs without a defect bank and unambiguous evidence filenames.
Deep's local clone was read but not modified or reconnected.

The original `.venv` lacked ML dependencies. A new ignored `.venv-phase1`
environment reuses existing system CPU PyTorch 2.7.0/torchvision 0.22.0 and
installs FAISS/timm locally. Core versions are recorded in
`requirements-phase1-locked.txt`; this is a core-version snapshot, not a
fully isolated transitive lock. Existing unrelated system Streamlit/pandas
and TensorFlow/NumPy conflicts remain visible in `pip check`; neither package
is used by this evaluation. A clean isolated environment is recommended for
deployment/CI. No global packages were changed.

## Resource observations and limitations

- Saved category-specific index/parameter artifacts are approximately
  2.01 MB (bottle), 2.54 MB (grid) and 2.05 MB (transistor), decimal MB.
  These exclude the much larger pretrained backbone weights in the Torch cache.
  They are not total deployable model sizes.
- Standalone bottle inference observed about 707 MB process RSS and 712 MB
  peak working set. This is one example process, not a mobile estimate.
- The first training memory monitor sampled the Windows launcher instead of
  the true worker. Those tiny RSS readings are invalid and excluded from the
  published results; training peak memory remains unestablished.
- Scores and the inherited `Needs_Review` flag are not calibrated confidence
  probabilities. Do not present a high score as a probability of a defect.
- The inherited multi-view inference entry point applies industrial cropping,
  brightness normalization and a different resize recipe. It must not be used
  unchanged with the MVTec-trained models. `infer_mvtec_image.py` provides a
  matching benchmark inference path; it is not a general factory detector.

## Changes and verification in this phase

- Added reproducible three-category runner, source/data inventory, bounded
  dataset downloader, saved-model round-trip checks and single-image inference.
- Hardened the dataset validator against empty groups and wrongly named masks.
- Four validator regression tests pass. New scripts compile, and Git whitespace
  checks pass. Fixed `setup.py` referring to a nonexistent requirements file.
- Raw datasets, model artifacts and local environments remain ignored by Git.
- The pre-existing edit to `docs/VISUREX_META_GO_NO_GO_2026-10-16.md` is preserved
  separately and is not part of this phase's verified report.

## Reproduction and evidence

From the `development` repository root, with dependencies installed:

```powershell
.\.venv-phase1\Scripts\python.exe scripts\test_dataset_validator.py
.\.venv-phase1\Scripts\python.exe scripts\phase1_inventory.py --output artifacts\phase1-20261021\inventory.json
.\.venv-phase1\Scripts\python.exe scripts\run_phase1.py --output artifacts\phase1-new-run
```

The runner refuses to overwrite an existing evaluation. Downloading only grid
and transistor is available through `scripts/download_phase1_categories.py`.
The mirror is `foersben/mvtec-ad`, pinned for this run to
`c75b39616f84db43677bcc8228caaafaf5096d7f`; its recorded intake was 756 files,
564.6 MB. Preserve the dataset's non-commercial licence restrictions.

Local logs, commands, model files and full prediction records are under
`artifacts/phase1-20261021/runs/<category>/`. Hash manifests are in
`artifacts/phase1-20261021/inventory.json`. Compact verified evidence is in
`docs/results/PHASE1_RESULTS_2026-10-21.json`.

## Next step

Begin a laptop-backed image-upload service and Android bridge using the
matching preprocessing path. In parallel, inspect the five missed defects
and select a controlled physical-part task. Phone-local inference, actual
glasses capture and robustness to motion/glare require separate measurements.
All-15-category, multi-seed, pixel-metric and matched ablation work belongs to
the later research benchmark, not this feasibility gate.
