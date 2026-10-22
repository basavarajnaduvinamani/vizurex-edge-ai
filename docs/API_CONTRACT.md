# VisureX local API contract — version 0.1.0

Optional private Wi-Fi update: `VISUREX_LAN_IP` must be a specific RFC1918 IPv4
address and `VISUREX_ACCESS_KEY` a strong per-session key. In this mode API
requests other than health/preflight require header `X-Visurex-Key`; missing or
wrong keys return HTTP 401 before upload parsing. Host/origin restrictions
remain explicit. Keys in query strings are not accepted. The default remains
loopback-only. This is an HTTP trusted-network demo, not public deployment or
encrypted transport. No firewall configuration is automated.

For the frontend agent: do not modify backend files. Use the real endpoints
below only when the backend is running; otherwise keep mock mode explicit.

## Local service

Start from `development`:

```powershell
.\.venv-phase1\Scripts\python.exe scripts\calibrate_heatmaps.py
.\.venv-phase1\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Calibration only needs repeating when model files change. The locally generated
Phase 1 model artifacts and cached ImageNet V1 backbone weights must exist.
Install `requirements-api.txt` in a suitable environment if dependencies are
missing. Do not expose this unauthenticated prototype to the internet.

`http://127.0.0.1:8000/api/docs` provides the interactive API documentation.
When `frontend-prototype/index.html` exists at startup, the same service serves
the frontend at `/`, eliminating the need for a separate frontend server.
For separate development servers, localhost/127.0.0.1 ports 5500, 5173 and 8080 are
allowed origins. Opening HTML with a `file://` URL is not supported in live mode.

## Routes

- `GET /api/health`: service status, not a claim that all model artifacts loaded.
- `GET /api/models`: category artifact/calibration presence and cache state.
- `POST /api/inspect`: multipart form fields `category` and `image`.

Categories: `bottle`, `grid`, `transistor`. One PNG/JPEG, at most 10 MiB and
16 megapixels. Send a browser `FormData`; do not manually set its Content-Type
header. The server checks actual image contents, not just filename/MIME type.

## Successful response

```json
{
  "inspection_id": "uuid",
  "timestamp": "UTC ISO-8601",
  "category": "bottle",
  "decision": "GOOD",
  "anomaly_score": 0.3,
  "threshold": 1.0,
  "model_version": "phase1-bottle-modelhash",
  "cold_start": false,
  "timing": {"model_inference_ms": 165.0, "server_processing_ms": 190.0},
  "images": {
    "processed": "data:image/png;base64,...",
    "heatmap": "data:image/png;base64,...",
    "overlay": "data:image/png;base64,..."
  },
  "heatmap_scale": {
    "lower": 0.0, "upper": 10.0,
    "method": "normal-validation-pixel-p99", "is_probability": false
  },
  "preprocessing": {
    "resize_short_edge": 256, "center_crop": 224,
    "display_region": "processed image and overlays show only the centre crop"
  },
  "warnings": ["Research prototype; not validated for safety-critical inspection."]
}
```

Numbers above illustrate the schema, not new performance measurements.
Always display the processed centre crop alongside the overlay, not an overlay
stretched across the full original image. Preserve an original upload preview
separately. EXIF orientation is applied before processing JPEGs.

Scores and heatmaps are not confidence percentages. Red means a higher local
distance on a fixed display scale, not a validated pixel-level defect verdict.
The display upper bound comes from only normal validation maps; it is never
recomputed from uploaded or test images. Bounds are model-specific and should
not be compared as if identical between categories.

`server_processing_ms` starts after multipart parsing and excludes JSON
serialization, log completion, network transfer and browser rendering. Measure
client request round-trip separately if displaying total request time. The
first request includes model loading outside `model_inference_ms` and can be
slower. Models are cached; CPU inference is serialized with a lock.

## Errors

Read `detail` from a non-2xx JSON response; handle validation lists gracefully.
400 invalid category/empty/corrupt image; 403 disallowed Origin;
413 upload/pixel limit; 415 unsupported image format; 422 missing form fields;
503 missing/incompatible local artifacts or unavailable local logging.
Never fall back silently to a mock result when a real request fails.

## Retention

Only inspection metadata is appended under ignored `artifacts/inspections/`.
Uploaded images, filenames and overlays are not retained by the backend.
Image retention is currently disabled; enabling it requires a separate explicit
implementation decision. Nothing is sent to an external AI service.
# Additive software update: 22 October 2026

`POST /api/inspect` accepts optional multipart `quality_mode`: `benchmark`
(default, previous behaviour) or `quality_gated` (experimental capture heuristics).
An invalid mode returns HTTP 400. Rejected captures return HTTP 200 with
`decision: "RETAKE"`, `quality.passed: false`, nonempty `quality.reasons`, capture
metrics, inspection metadata and timing. They deliberately omit anomaly score,
threshold and images because the detector did not run. Clients must not render a
GOOD result or stale overlay for RETAKE. Accepted quality-gated images retain the
normal inspection response and include `quality.passed: true`.

Set `VISUREX_BUNDLE_ROOT` to a trusted local offline bundle directory to avoid
runtime backbone downloads. Integrity is checked on first model load. Never
accept arbitrary model paths or bundles through the request interface.

Physical Android devices should connect through `adb reverse tcp:8000 tcp:8000`
and use `http://127.0.0.1:8000`. The service remains loopback-only and does not
accept arbitrary hostnames or public browser origins. See SOFTWARE_HANDOVER.md.
