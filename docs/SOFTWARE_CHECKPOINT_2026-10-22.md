# Software checkpoint: 22 October 2026

## Later software expansion on 22 October

- Added opt-in private-Wi-Fi mode with a per-session access key and explicit host
  and origin restrictions. It has not been enabled on the laptop's network and
  no firewall rules have been changed.
- Added an experimental Android on-device ONNX CPU path with trusted model-ZIP
  import. All three portable models matched the 261 reference decisions on the
  laptop, with maximum score difference below 0.00007.
- The updated APK compiled and passed 18 JVM tests. Android lint completed with
  no errors; remaining warnings concern pinned older libraries and English-only
  UI strings, not a claim of a warning-free production app.
- Current Python suite: 29 passing tests. Current frontend: 23 passing checks.
- Physical Android inference and image preprocessing parity remain unverified.
  See `WIFI_AND_OFFLINE_TESTING.md` for the new modes and their limits.

The earlier milestone below is retained as history and superseded where noted.

## Completed locally

- Isolated Windows Python 3.11 environment with a full version lock and no broken
  dependency requirements.
- Portable trusted model bundles with shared backbone weights, preprocessing
  recipe, checksums and offline loading. Verified against every one of the 261
  Phase 1 test predictions in the isolated environment.
- An offline-loader BatchNorm restoration fix and a saved-neighbour-count fix,
  with regression coverage.
- Optional capture checks and explicit RETAKE handling in the API and browser.
- 25 Python backend, real-model integration and dataset tests passed; 21 frontend
  regression checks passed.
- A reproducible 1,044-inspection synthetic capture study, including the failure
  cases documented in `results/SOFTWARE_AND_STRESS_2026-10-22.md`.
- Group-aware real-capture manifest validation, a CI workflow and operating,
  privacy and research protocols. CI is configured; a hosted run is not claimed.
- Native Android companion compiled successfully as a debug APK; all 13 JVM
  contract tests passed. Android lint was not completed. No emulator or physical
  device installation, camera or speech test is claimed. Its separate build/test
  record is in `ANDROID_COMPANION.md`.

## Phase status

| Area | Status |
|---|---|
| Software reproducibility and offline bundles | Verified locally |
| Laptop-backed browser inspection | Implemented; automated regressions passed |
| Android capture/client software | Implemented; actual-device acceptance pending |
| Capture reliability | Initial controlled study complete; blur limitation found |
| Meta SDK and glasses capture/audio | Deferred as requested |
| Phone/tablet-local detector | Experimental Android CPU path implemented; laptop tensor parity passed, physical-device qualification pending |
| Factory product models and real-camera generalisation | Awaiting suitable WCT data and validation |
| NCR/DataPy/MANGO integrations | Awaiting actual APIs, approved scope and access |
| Thesis/paper | Research protocol and evidence prepared; writing, review and submission are not complete |

The source changes and generated evidence are saved locally. This checkpoint
does not claim that all research phases are finished. Software can prepare and
measure the workflow, but it cannot replace missing real captures or device
tests. The inherited upstream checkout has not been modified by this work.

The pre-existing edits in `docs/VISUREX_META_GO_NO_GO_2026-10-16.md` were left alone.
