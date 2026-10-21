# MVTec AD benchmark protocol

## Objective

Determine whether the inherited VisureX pipeline is correct, reproducible, and materially better than its standard PatchCore foundation when evaluated on the official MVTec AD protocol.

This benchmark validates the anomaly-detection core. It does not by itself validate mobile deployment, smart-glasses capture, or performance under factory-domain shift.

## Dataset protocol

- Use all 15 MVTec AD categories.
- Train only on each category's official `train/good` images.
- Never train, calibrate, select thresholds, or choose hyperparameters using official test images.
- Create a deterministic normal-only validation subset from `train/good` when calibration is required.
- Preserve the official test folders and pixel-level ground-truth masks.
- Keep the raw dataset outside Git. Commit only its manifest, checksums, split metadata, and evaluation outputs.

## Experiment matrix

| ID | System | Purpose |
|---|---|---|
| E0 | Reproduced standard PatchCore | Reference implementation and sanity check |
| E1 | VisureX core with matched PatchCore settings | Test whether implementation changes preserve performance |
| E2 | E1 + multi-backbone ensemble | Isolate ensemble contribution |
| E3 | E2 + brightness normalization | Isolate preprocessing contribution |
| E4 | E3 + geometric judge | Isolate geometric contribution where applicable |
| E5 | E3/E4 + defect bank | Separate labelled/few-shot setting; not directly comparable to unsupervised E0–E4 |

All comparable experiments must use the same image resolution, category split, seeds, preprocessing policy, and metric implementation.

## Required metrics

- Image-level AUROC and Average Precision
- Pixel-level AUROC and AUPRO
- Precision, recall and F1 at a validation-derived operating threshold
- False-positive rate on normal test images
- Per-category results plus macro average across 15 categories
- Inference latency, peak memory and artifact size
- Mean and standard deviation across at least three seeds for the final comparison

## Execution stages

### Stage A — dataset intake

1. Download the supplied Kaggle mirror without committing it.
2. Verify the 15-category directory structure and image/mask counts.
3. Create checksums and a local dataset manifest.
4. Confirm there is no train/test overlap.

### Stage B — environment and smoke test

1. Create a locked Python environment.
2. Port the inherited scripts away from machine-specific paths.
3. Run one lightweight category, such as `bottle`, end to end.
4. Confirm training, saved model loading, inference, masks and metrics.

### Stage C — baseline benchmark

1. Run E0 on all categories.
2. Compare reproduced scores with the published PatchCore range.
3. Stop and repair the runner if results diverge materially before testing VisureX.

### Stage D — VisureX benchmark and ablations

1. Run E1–E4 under matched conditions.
2. Report category-level gains and regressions, not only one average.
3. Run E5 only as a clearly labelled few-shot experiment.

### Stage E — decision gate

Proceed to edge/mobile integration only if the pipeline is reproducible and at least one VisureX addition provides a measurable benefit in accuracy, robustness, efficiency, or interpretability without test leakage.

## Compute plan

The local NVIDIA GTX 1650 has 4 GB VRAM. Use it for dataset validation, unit tests and a single-category smoke test with conservative settings. Use a lab or cloud GPU for the full multi-backbone, 15-category and multi-seed benchmark.

