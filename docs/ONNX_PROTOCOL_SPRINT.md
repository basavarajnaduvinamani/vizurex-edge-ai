# S4: shipped-model ONNX parity and paired CPU timing

Commit before execution. Export the shipped bottle, grid and transistor bundles
using the existing `backend.portable_model.PortablePatchCore` graph. These are
the inherited WCTE PatchCore detector with the project's portable graph wrapper,
not new trained models. Keep thresholds, weights, memory banks and preprocessing
fixed. Private model binaries and benchmark images never enter Git.

Use the existing `.venv-phase1` export environment (actual versions recorded by
the run), CPU, four Torch and ORT threads, fixed batch shape 1x3x224x224, legacy
ONNX exporter, opset 17. No quantisation or DINOv2 export is required in this
bounded item; both remain later work unless time permits.

Use every official test image of each shipped category, sorted by relative path.
Compare freshly executed shipped Torch scores against ONNX scores and preserve
all per-image outcomes privately. Acceptance: maximum absolute normalised score
delta <= 0.001 and every threshold decision agrees. A normalised anomaly score
is not a probability. Report any failures without changing thresholds/tolerance.

For like-for-like timing, compare the portable Torch graph and ONNX graph, both
returning the score and unsmoothed patch-distance map. Warm each graph twice on
the first image, time one call per test image, alternate execution order, report
p50/p95. Exclude image decoding/preprocessing, startup, network, UI and heatmap
rendering. Also measure the shipped Torch call (which returns the final smoothed
map) separately; its output scope differs, so do not claim a speedup by comparing
that column to the raw-output graph. No phone, tablet, glasses or end-to-end
latency claim. Export and parity scripts must not update the serving model.
