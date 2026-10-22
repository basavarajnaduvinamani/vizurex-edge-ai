# VisureX software handover

Updated 22 October 2026. This research prototype defaults to laptop inference
and includes an experimental Android-local mode. It is not factory-qualified.

Later update: an experimental Android on-device path has now been added. It is
not device-qualified. The original laptop-backed workflow below remains the
default. See `WIFI_AND_OFFLINE_TESTING.md` for both optional modes.

## Run locally

1. Create the isolated Python environment: `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_clean.ps1`.
2. Existing trusted Phase 1 models can be packaged with `.venv-clean\Scripts\python.exe scripts/package_models.py`.
   The current machine already has bundles under `artifacts/model-bundles`.
   Packaging refuses to replace a completed bundle; use a new output folder for a new version.
3. Start `powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1`.
4. Open `http://127.0.0.1:8000` and select the category that matches the benchmark image.

Raw datasets, model weights, APKs, local environments and inspection logs are
deliberately excluded from Git. A fresh clone needs these local prerequisites;
source code alone does not contain a trained detector.

## Processing path

Tablet camera or gallery → native Android companion → USB connection → local
FastAPI service → category-specific PatchCore model → result and fixed-scale
overlay → tablet display and optional speech.

The same service supports the browser dashboard. Neither path requires a cloud
AI API. The detector currently runs on the laptop CPU, not inside the glasses or
tablet. See `ANDROID_COMPANION.md` for building, installing and connecting the app.

## Capture policy

The default `benchmark` mode preserves the earlier detector behaviour.
`quality_gated` adds fixed checks for image size, insufficient detail and gross
under/overexposure. It returns `RETAKE` without running the detector when a check
fails. No anomaly score or defect heatmap is invented for a rejected capture.

These checks are engineering heuristics. A plain good surface can be rejected,
and a blurred or wrong-product image may pass. They are not calibrated confidence,
industrial safety assurance or a general out-of-distribution detector. Keep this
mode experimental until a separate real-capture validation study is complete.

## Verification

- API/quality/integrity checks: `python -m pytest backend/test_api.py backend/test_quality.py backend/test_bundles.py -q`.
- Dataset checks: `python -m pytest scripts/test_capture_manifest.py scripts/test_dataset_validator.py -q`.
- Frontend checks: `node scripts/test_frontend.mjs`.
- Offline prediction parity: `python scripts/verify_offline_bundles.py`.
- Synthetic capture study: `python scripts/evaluate_capture_stress.py`.

Run Python commands from the isolated environment. Real-model scripts need the
local bundles and MVTec files. Generated evidence is under `artifacts/phase3`.
The CI workflow runs source-level checks without distributing private data or models.

## Privacy and operating limits

The server binds only to the laptop loopback address. Use USB `adb reverse` for
the tablet instead of exposing an unauthenticated service on Wi-Fi. There is no
production authentication, rate-limiting service, HTTPS deployment or multi-user
isolation. Do not deploy it publicly as it stands.

Uploads are processed in memory. Metadata is recorded locally; raw images and
original filenames are not retained by the API. The Android app uses temporary
capture files; uninstall/backup and device security policies still need review.
TTS must use an available offline voice to keep spoken feedback local.

Bundles contain trusted locally generated pickle/NumPy artifacts. File hashes
detect accidental alteration; they do not authenticate an unknown publisher.
Never load bundles from an untrusted source. Retain upstream attribution and
check MVTec/backbone/software licences before any commercial distribution.

## What remains dependent on access or new evidence

- Install and test on the actual Xiaomi tablet: camera permissions, USB, rotation,
  response times, speech and interrupted requests.
- Validate official Meta SDK access and capture/audio routing with real glasses.
- Collect consented WCT captures with part/session identifiers and defect labels.
- Train a model for each intended product and freeze thresholds before final tests.
- Measure recall, false alarms, retake burden and latency on untouched real captures.
- Qualify the experimental portable Android detector on the actual device before
  claiming mobile speed, image-score parity or operational reliability.
- Validate NCR/DataPy/MANGO connectors against their actual APIs and access rules.

Do not claim these integrations, factory deployment or a publication as complete.
