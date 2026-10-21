# Phase 2 backend checkpoint — 21 October 2026

Historical intermediate checkpoint. Frontend integration and browser checks
subsequently completed; see `PHASE2_COMPLETE_2026-10-21.md`.

## Completed

- Local FastAPI service: health, model availability and multipart image inspection.
- Three actual Phase 1 CPU models, loaded lazily once per category.
- Benchmark-matched resize, centre crop and normalization; no reused industrial
  background removal or brightness-normalization path.
- Fixed per-model heatmap display scales calibrated using normal validation
  images only: bottle n=42, grid n=53, transistor n=43. Repeated-image overlays
  are independent of other requests. Colours are not probabilities or a
  validated pixel decision threshold.
- PNG/JPEG content validation, upload/pixel caps, loopback host checks,
  explicit local origins and metadata-only local inspection logging.
- Backend and frontend contract: `docs/API_CONTRACT.md`.

## Verification

- Twelve API boundary tests passed outside the sandbox; sandbox thread/socket
  restrictions caused earlier test-client hangs, not a model failure.
- The real-model integration test passed: six normal/anomaly requests across
  the three models matched Phase 1 scores within 0.0002 and all decisions.
  Three repeated normal requests returned identical image/heatmap payloads
  with model caching active.
- A real HTTP multipart request to `127.0.0.1:8000/api/inspect` for
  bottle/test/broken_large/000.png returned ANOMALY, score 5.770784854888916,
  model `phase1-bottle-879319acd415` and an actual PNG overlay. Observed model
  time was about 206 ms for this request, not a general latency benchmark.
- New Python modules compile and Git whitespace checks pass.
- Test evidence is local under `artifacts/phase2/api_real_model_tests.json`.

## Not complete yet

The frontend is a parallel agent's work and was not modified here. Its existing
draft uses mock thresholds and a guessed `/api/v1/inspect` adapter, while the
verified backend uses `/api/inspect`. It needs the documented field mapping,
upload limits and centre-crop-aligned overlay handling before calling Phase 2
complete. `docs/ANTIGRAVITY_PHASE2_CONNECT.md` is the bounded integration task.

No new detector accuracy is claimed. No phone or glasses integration, public
hosting, authentication or factory-domain validation has been performed.
The pre-existing report edit remains preserved. Deep's clone remains unchanged.
