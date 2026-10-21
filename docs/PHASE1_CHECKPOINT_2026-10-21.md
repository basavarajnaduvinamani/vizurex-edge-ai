# Phase 1 checkpoint — 21 October 2026

## Scope and boundaries

- Work in `development`; preserve the existing uncommitted report edit.
- Leave `upstream/VisureX` unchanged. Do not push to DeepWCTE/VisureX.
- Current development commit: `4bb4b1631d1bc5c510415a89bbe92ad5f279a53c`.
- Intended feasibility gate: bottle plus two diverse categories, one backbone.
  The full 15-category benchmark and ablations are later research work.

## Evidence found

- Existing bottle runner: `scripts/run_bottle_smoke.ps1`.
- Saved evidence and models: `artifacts/smoke/mvtec-bottle-smoke/`.
- Saved `results.csv`: image AUROC 1.0; TP 63, FP 1, TN 19, FN 0.
- Saved summary: 42 validation images, defect bank disabled, 18 cases marked
  Needs_Review. Review flags need interpretation before deployment claims.
- These are historical artifacts inspected today, not a newly reproduced run.
- Only the bottle category is currently present in `data/raw/mvtec_ad`.

## First execution check

Command: `.venv/Scripts/python.exe scripts/validate_mvtec_category.py data/raw/mvtec_ad --category bottle`

Result: failed at import with `ModuleNotFoundError: No module named 'PIL'`.
The current local virtual environment lacks the smoke-test ML dependencies.
This is an environment blocker, not evidence of detector failure.

## Remaining work

1. Identify the original execution environment or restore a dedicated test environment.
2. Re-run integrity checks, independently recompute saved prediction metrics,
   and inspect active calibration and score-normalization code.
3. Reproduce training and separately verify saved-model inference, using a new
   output directory so the historical evidence is not overwritten.
4. Compare upstream and development source; record inherited code and repairs.
5. Obtain only two additional categories after agreeing the category choice.
6. Run matched tests and measure latency, memory and artifact sizes.
7. Update contradictory older status/protocol documents after verification.
8. Review Git exclusions, attribution and publication permission before pushing
   the verified baseline to the user's repository.

## Parallel work option

Antigravity can perform a read-only comparison of upstream and development
source, including active threshold selection, test-score normalization,
defect-bank use, and saved-model loading. It should return file/line evidence
and commands, make no edits, install nothing, run no training, and push nothing.
This avoids conflicting changes while the main task restores reproducibility.
