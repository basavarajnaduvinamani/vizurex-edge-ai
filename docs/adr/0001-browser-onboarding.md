# Browser-only onboarding demo

Date: 2026-11-04. Scope: Step 1 only.

PANEL: demonstration runtime and calibration
Options: A) static browser WASM; B) hosted Python container.
Key views: Platform/privacy: A keeps visitor images local and avoids a serving bill.
Research/data: retain pretrained ViT-S/14, cosine nearest patches, top 1%, disjoint calibration.
Product: eight bank photos are not eight total photos; request separate normal calibration.
Call: A first; measure before considering B. Reversible: yes. No public release before “deploy”.
Resume impact: SDE browser inference; pre-doc reproducibility; APM onboarding flow.

Existing inspection app remains unchanged. New demo uses generated S5 drawings;
no MVTec images, WCTE data, industrial memory banks, or logos enter its build.
Only independently pretrained DINOv2 weights (Apache-2.0) may enter the export.
No new anomaly-detection method is claimed. Cite AnomalyDINO and PatchCore.

Eight bank images plus at least two disjoint normal calibration images are
required for visitor onboarding. This is intentionally explicit additional
data, as in the benchmark. Threshold is p99 (linear quantile) of normal-only
calibration scores and frozen before any test. No retuning from test results.
Generated samples use eight bank and eight held-out calibration drawings.

Protected preview only after verifying protection; no publicly accessible
deployment or production promotion without explicit owner “deploy”. If that
cannot be assured, report preview BLOCKED and keep the tested artifact local.

Missing referenced files: prompts/finish/_COMMON_RULES.txt and
prompts/polish/_common/design_brief.txt were absent from this workspace and
development checkout on inspection. Use supplied AGENTS.md rules; report the
missing R9 template rather than invent its contents.
