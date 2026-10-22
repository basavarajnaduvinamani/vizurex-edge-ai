# Wi-Fi and portable inference checkpoint

## Implemented

- Optional private-Wi-Fi configuration with a per-session access key. Unknown
  hosts/origins and missing/incorrect API keys are rejected. The default remains
  laptop-only. No non-loopback server or firewall change was made during testing.
- Password-style session-key input in the browser and Android app, without URL
  parameters, audit-log retention or persistent key storage.
- A fixed-shape ONNX detector candidate, verified for bottle, grid and transistor.
- Trusted model-ZIP import and experimental CPU inference in the Android APK.
  The laptop-backed path remains the default and retains capture checks/heatmaps.
- Explicit Android backup/transfer exclusions and disabled offline-runtime telemetry.

## Verification

| Check | Result |
|---|---|
| Python API, dataset, integrity and portable-pooling suite | 29 passed |
| Frontend regression suite | 23 passed |
| Android JVM contract and portable-manifest tests | 18 passed |
| APK assembly | Successful |
| Android lint | Successful, zero errors; 3 dependency-update and 25 English-string warnings |
| ONNX/reference decisions | All 261 matched |
| Maximum ONNX score difference from rounded reference | 0.00006817 |
| Model import ZIP archive checks | All three passed |
| Browser key control and phone-width layout | Verified; no horizontal overflow |

Final APK SHA256:
`b2f425f74bece095c4fbf3dfdb2a5bba83720d85eb1b89c38910f0c7abef29da`.
The APK is approximately 80 MB and each optional model ZIP approximately 81 MB
in decimal units. Models are not embedded in the APK.

Artifacts remain local under `artifacts/portable-candidate/v2/` and the Android
build output folder. They are excluded from Git. The first transistor export
failed parity for one normal image because zero-floor normalisation was missing;
that candidate was not packaged. Version 2 corrected the conversion and passed
all comparisons without changing the trained model or decision thresholds.

The current Chrome profile blocked automated file upload because its extension
does not allow local-file access. No permission was changed or bypassed. The
new UI's complete upload-to-result browser flow was therefore not reverified;
real-image backend integration tests passed. Earlier Phase 2 browser evidence
remains separate from this latest UI check.

## Not established by these checks

- Actual Android camera, model import, native inference, speech, memory use or
  latency. No tablet/phone/emulator was installed or exercised.
- Pixel/score parity between Android bitmap preprocessing and reference Pillow
  preprocessing. Tensor parity on the laptop does not establish this.
- Wi-Fi reachability through the user's campus/router/firewall configuration.
- Industrial reliability. The previously measured blur/lighting weakness remains.
- NCR/DataPy/MANGO product integration without their actual APIs and access.
- Thesis completion, paper submission or publication.

See `WIFI_AND_OFFLINE_TESTING.md` for use. These are research prototypes, not a
production release. The weekly progress sheet was not changed in this work.
