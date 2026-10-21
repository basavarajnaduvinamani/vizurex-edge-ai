# Local inspection backend

This is the Phase 2 backend, not a production service or a universal detector.
The UI is being built separately in `frontend-prototype/`.

## Run

From the development repository root, using the Phase 1 environment:

```powershell
.\.venv-phase1\Scripts\python.exe scripts\calibrate_heatmaps.py
.\.venv-phase1\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

The calibration command uses only the normal validation holdout and binds the
fixed display scale to each model's artifact hash. Run it after changing models.
For a new environment, install `requirements-api.txt` and reproduce/download
the required local artifacts first. Cached pretrained backbone weights are
required for offline model loading.

Open `http://127.0.0.1:8000/api/docs`. If the frontend exists when the server
starts, it is served at `/`. Its live adapter must follow
`docs/API_CONTRACT.md`; a working static page does not establish real inference.

## Verify

```powershell
.\.venv-phase1\Scripts\python.exe -m pytest backend/test_api.py backend/test_real_models.py -v
```

The boundary suite uses an explicitly fake test registry. The separate real
suite checks normal/anomalous inputs across all three actual models against
saved Phase 1 scores, repeats requests to confirm caching and stable overlays,
and exports local evidence under `artifacts/phase2/`.

## Boundaries

- CPU model calls are serialized; models are lazily cached by category.
- PNG/JPEG only; 10 MiB upload and 16-megapixel decoded-image limits.
- Only inspection metadata is retained, without filenames or uploaded images.
- Raw scores and heatmap colours are not probabilities. The centre crop may
  exclude peripheral defects; the processed region is explicit in the response.
- Bind only to loopback. Authentication, network/TLS deployment, batching,
  mobile inference and safety-critical acceptance are outside this prototype.
- No changes to Deep's upstream clone or the inherited industrial pipeline.
