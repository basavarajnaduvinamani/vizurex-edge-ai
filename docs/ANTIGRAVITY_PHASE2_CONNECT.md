# Frontend integration handoff

The real backend is ready. Read `docs/API_CONTRACT.md` completely, then edit
only `frontend-prototype/`. Preserve other agents' work; do not change backend,
datasets, requirements, reports, or Git state. Do not deploy or install packages.

1. Use POST `/api/inspect`, not the guessed `/api/v1/inspect`. Send FormData
   fields `category` and `image`, with no manually set Content-Type header.
2. Strictly map the actual response: `decision`, `inspection_id`, `model_version`,
   `anomaly_score`, `threshold`, `timing.model_inference_ms`, and `images`.
   Never default a missing real decision to GOOD or a missing score to zero;
   treat malformed responses as errors. Never substitute mock results on failure.
3. Use `images.processed` as the 224-pixel image aligned with `images.heatmap`
   and `images.overlay`. Do not stretch the heatmap over the full uploaded image.
   Keep the full original upload preview separately and explain the centre crop.
4. Real operating thresholds are approximately 1.0, not 0.850/0.790/0.820.
   Remove claims that synthetic demo thresholds/ranges came from Phase 1.
   Keep fabricated demo values explicitly described as UI-only fixtures.
   Show real model version/threshold only from the response.
5. Enforce PNG/JPEG only, 10 MiB upload limit. Read `/api/models` capabilities
   if useful. The backend enforces a further 16-megapixel cap.
6. Client round-trip timing must include reading/parsing the response body.
   Keep it distinct from model time and backend processing time.
7. Use same-origin API calls when served from port 8000. A separate frontend
   server on localhost:8080 is also allowed. Keep an explicit Demo/Live switch,
   and make the active mode unmistakable.
8. Verify error handling, model switching, repeat requests and stale-result
   clearing. Do not label score/heatmap intensity as confidence or probability.

The main agent starts the backend separately. Return changed files, exact
preview steps and remaining issues. Do not claim visual QA unless performed.
