# MVTec AD bottle smoke test — 2026-10-16

## Decision

**PASS for pipeline execution; not yet a full benchmark result.**

The inherited VisureX PatchCore path now runs end to end on a clean external
category: dataset validation, normal-only training, validation-based threshold
calibration, anomaly scoring, metric generation, CSV/Excel export, and model
serialization all completed successfully on the laptop CPU.

## Scope

| Setting | Value |
|---|---|
| Dataset | MVTec AD, `bottle` category |
| Training images | 167 normal images |
| Validation images | 42 normal images |
| Test images | 83 total: 20 normal + 63 anomalous |
| Test defect groups | 20 broken-large, 22 broken-small, 21 contamination |
| Exact train/test overlap | 0 |
| Backbone | WideResNet-50 |
| Feature layers | `layer2`, `layer3` |
| Coreset | 1% approximate greedy |
| Image size | 224 px |
| Seed | 0 |
| Execution | CPU-only laptop run |

The category was obtained from a public MVTec AD mirror to avoid downloading
the complete multi-gigabyte dataset for this limited smoke test. Raw images and
model artifacts remain outside Git.

## Image-level result

| AUROC | F1 | Precision | Recall | TP | FP | TN | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.9921 | 0.9844 | 1.0000 | 63 | 1 | 19 | 0 |

The operating threshold was derived only from the 42 normal validation images.
One normal test image was incorrectly flagged; all 63 anomalous test images
were detected. The perfect AUROC on this one easy category is encouraging, but
it is not evidence that VisureX is perfect or that it outperforms standard
PatchCore.

## Repairs required to obtain the run

1. The MVTec loader previously expected a physical `val` directory that the
   official layout does not contain. It now creates a deterministic holdout
   from `train/good`.
2. The custom defect-bank stage assumed fields available only in the WCTE
   dataset. It is now disabled for the standard unsupervised MVTec run.
3. CPU execution is supported by making the GPU argument optional.
4. Prediction evidence now records paths such as
   `broken_large/000.png` rather than repeating only `000.png`.
5. The Excel exporter now uses the correct `Needs_Review` field.

## What this establishes

- The core implementation is runnable rather than a hollow placeholder.
- It can learn a PatchCore memory bank from normal samples and separate the
  MVTec bottle anomalies in this limited test.
- The earlier custom Top-view score cannot be used as proof because of its
  train/test leakage; this clean smoke test is the first trustworthy execution
  checkpoint.

## What remains unproven

- Results across all 15 MVTec categories
- Pixel-level AUROC and AUPRO from the segmentation masks
- Reproducibility across multiple seeds
- Whether VisureX additions improve on a matched standard PatchCore baseline
- Multi-backbone benefit, GPU latency, memory use, edge deployment, and
  smart-glasses robustness

## Next decision gate

Run the matched single-backbone baseline across all 15 categories on a GPU.
Only after that passes should compute be spent on multi-backbone ablations or
mobile/smart-glasses integration.

## Reproduction

From the repository root on Windows:

```powershell
.\scripts\run_bottle_smoke.ps1
```

Local evidence is generated under
`artifacts/smoke/mvtec-bottle-smoke/` and intentionally ignored by Git.
