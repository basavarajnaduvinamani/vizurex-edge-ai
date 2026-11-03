# Step 1 export and browser parity protocol

Registered 2026-11-04, before execution. Not a robustness study.

Export the existing independently pretrained timm DINOv2 ViT-S/14 at 224x224,
opset 17, batch one, last-layer 256 patch tokens x 384 dimensions. No inherited
WCTE checkpoint or bank. Record weight/graph hashes, size, runtime versions.
Preprocess by a shared deterministic resize-256/centre-crop-224 pixel tensor
saved by the browser; compare Python and browser on those identical tensors
to separate runtime parity from image decoder/interpolation differences.
Also compare the browser-preprocessed tensor to Python decoding and report
differences; never present shared-tensor parity as decoder parity.

Use S5 generated drawings only: bank seeds 0..7, calibration 100..107;
evaluation seeds 200..209 normal and 200..209 scratch. These are synthetic
functional examples, not a new accuracy estimate. Freeze splits and p99
normal-calibration threshold before testing. Save every sample score/map and
decision, including misses/false alarms. Parity acceptance: all decisions same
and max absolute score difference <=0.001. Report actual n and uncertainty for
decision agreement; generated examples cannot validate real inspection.

Browser WASM CPU one thread (works without cross-origin isolation), no GPU.
Measure cold loading separately. Warm two calls, then 20 sequential checks
on the frozen sample set; save every duration. Report p50/p95 and bootstrap
95% intervals over requests (10,000 replicates, seed 20261104); these describe
this laptop/session, not device population. Full request timing includes
decode/preprocess/feature extraction/patch scoring/capture check, excludes
initial model download/onboarding. Also record feature-extraction time.
Cache reference features once. Rejected captures have no anomaly score.

Capture heuristic cutoffs remain v1; port its grayscale/Laplacian and crop
behaviour, document numerical tolerances and known synthetic blur failures.
Report RETAKE and any generated blur passing the gate; do not tune it here.

Final gates once on final code: inherited Python/frontend suites plus new
freeze/RETAKE/parity/build-exclusion tests; actual Playwright desktop and
390px light/dark flows/screenshots; measured Lighthouse mobile scores.
Preview only if access protection can be verified; otherwise BLOCKED.
