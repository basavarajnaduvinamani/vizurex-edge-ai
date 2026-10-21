# Phase 2 complete — local web inspection prototype

Completed on 21 October 2026. This is a local research prototype, not a
production, phone-local or glasses-integrated deployment.

## Working path

Browser image upload -> local inspection API -> selected cached PatchCore
model -> category-specific decision, fixed-scale heatmap and metadata log.
Supported models are bottle, grid and transistor from the Phase 1 runs.

## Completion evidence

- All 13 backend boundary/real-model tests passed on the final rerun.
- All 17 Node frontend regression checks passed, including malformed response
  rejection, no mock fallback, upload blocking during inspection and ignored
  stale image-decode callbacks.
- Chrome Live mode: bottle/test/broken_large/000.png returned ANOMALY with
  displayed score 5.7708, matching the Phase 1 evidence.
- Chrome Live mode: bottle/test/good/000.png returned GOOD with displayed
  score 0.4032, matching the Phase 1 evidence.
- Real score, model version, decision threshold, inspection ID, centre-crop
  overlay and separate model/server/client timings were visible in the UI.
- While processing, image changes, category changes and mode changes are
  blocked; the result is also guarded against stale request/selection state.
- Switching Live -> Demo cleared the real result. Live mode hides the
  simulation controls; Demo mode is explicitly marked as simulated.
- At 390 x 844 viewport, the dashboard stacked into a readable single column
  without horizontal document overflow. Viewport override was reset afterwards.
- Screenshots: local ignored artifacts/phase2/desktop-final.png and
  artifacts/phase2/mobile-result.png. Browser file upload was verified after
  the user enabled extension file access.

Browser timing observations were approximately 1.1–1.3 seconds client round
trip in this session, not the isolated Phase 1 model-only timings. Performance
varies with load and startup; no end-to-end latency guarantee is claimed.

## Repairs made during final verification

- Tightened required metadata, category, timing and PNG-payload validation.
- Added input locks and stale decode/request safeguards.
- Added a universal hidden-state CSS rule; otherwise some elements carrying
  `is-hidden` were still visible, including Demo controls in Live mode.
- Removed an unverified WCAG compliance badge, cleaned up fieldset layout,
  corrected displayed score/heatmap labels and included JSON parsing in
  client round-trip timing.
- Versioned frontend asset URLs to avoid stale cached JavaScript/CSS.

## Run and test

From development, with local model artifacts and calibration files present:

```powershell
.\.venv-phase1\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
.\.venv-phase1\Scripts\python.exe -m pytest backend/test_api.py backend/test_real_models.py -q
node scripts/test_frontend.mjs
```

Open http://127.0.0.1:8000/. For fresh model artifacts, first run
`scripts/calibrate_heatmaps.py`. See backend/README.md and docs/API_CONTRACT.md.
Images are not retained by default; metadata logs stay under ignored artifacts/.

## Next phase

Build the Android companion prototype, beginning with phone-camera capture,
API communication and spoken feedback. Actual glasses SDK access and audio
routing require separate hardware verification. The laptop API stays the
initial inference backend; neither browser success nor MVTec performance
establishes factory-domain or mobile-inference reliability.

Deep's upstream copy remains disconnected and unchanged. The pre-existing
unverified report edit is not included in this phase's changes.
