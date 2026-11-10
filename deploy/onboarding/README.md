# Eight-reference browser onboarding

AnomalyDINO-style baseline, benchmarked and studied, not a new method.
Paper: https://arxiv.org/abs/2405.14529 . Official implementation:
https://github.com/dammsi/AnomalyDINO . PatchCore:
https://arxiv.org/abs/2106.08265 . DINOv2 independently pretrained weights:
https://github.com/facebookresearch/dinov2 (Apache-2.0).

This separate static demo uses generated S5 washer drawings, not MVTec images,
WCTE samples, logos, industrial weights or memory banks. Visitor photos remain
in browser memory, and are discarded on refresh. No analytics or remote API.
Downloaded pretrained model is approximately 88 MB; exact bytes in model.json.

Eight verified-normal bank images PLUS separate normal calibration images are
required. For visitor uploads at least two calibration images are required;
their p99 threshold is not validated. Two is an interface minimum, not an
adequate sample size for a reliable 99th percentile or industrial qualification.
Test photos never update the bank or threshold. Exact byte duplicates between
reference/calibration photos are rejected; this cannot identify repeated views
of the same physical item. Avoid capture-session or physical-item leakage.

Scoring: 224x224 centre crop after resize to 256, last-layer ViT-S/14 tokens,
cosine nearest-reference distance, mean of three highest-distance patches
(top 1% of 256). No masking, rotation augmentation, or weight training.
This differs from the complete AnomalyDINO paper's preprocessing/resolution;
it is an adaptation, not an exact paper-result reproduction. Threshold is
p99 normal-only calibration, frozen before tests. Browser interpolation may
differ from PIL; parity evidence explicitly states its input scope.
Heatmap uses unsmoothed 16x16 patch distances, fixed scale 0–1 with a translucent
single-colour overlay; unlike the benchmark's smoothed maps it is an explanation
of this demo's score, not a pixel segmentation benchmark.

Capture check ports fixed v1 Laplacian/dark/saturated heuristics. It can miss
blur and reject legitimate images; no real captures have qualified it. The
earlier stress failure remains visible. Unknown file format/decode/model errors
are errors, never a simulated GOOD. No factory deployment or pilot claimed.

Build from development root: Python environment with torch/timm/onnx runs
`scripts/prepare_onboarding.py`; then `npm ci --ignore-scripts` and `npm run build`
in this folder. Model export stays ignored under artifacts; static build uses
an explicit file allowlist. No benchmark file paths are distributed. Research
numbers come from existing summary files, not the generated examples.

Deployment gate: no public hosting or production until owner says “deploy”.
Protected preview may be prepared only if access protection is verified first.
