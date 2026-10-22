# Android companion — phone/tablet prototype

## Latest software expansion: 22 October

The app now has two processing choices: the original laptop backend and an
experimental on-device ONNX CPU path. Optional Wi-Fi session-key support has
also been added. See `WIFI_AND_OFFLINE_TESTING.md` for installation and model
import instructions. Earlier verification details below are historical.

Current checks: 18 JVM tests passed and APK assembly/lint succeeded. Lint has
no errors; remaining warnings are dependency updates and untranslated English
UI strings. No device/emulator run is claimed. Offline mode has been compiled
but not executed on Android hardware. Android image resizing may differ from
the reference Pillow transform, even though all 261 laptop tensor comparisons
passed. ONNX Runtime telemetry is explicitly disabled in the offline path.

The app-private backup/transfer exclusions and launcher icon are now explicit.
The Wi-Fi access key is not persisted or restored through view state/autofill.
The latest debug APK SHA256 is
`b2f425f74bece095c4fbf3dfdb2a5bba83720d85eb1b89c38910f0c7abef29da`.
The earlier SHA256 below belongs to the superseded laptop-only build.

Native Kotlin app in `android-companion/`. This is **not a Meta SDK integration**.
Camera, installation, TTS and tablet behaviour require testing on the actual device.
The exact user tablet model and Android version remain unconfirmed; Android 8/API26+
is the app's minimum, not a claim of wearable SDK compatibility.

## Scope

- External camera app through Activity Result `TakePicture` + restricted cache-only
  FileProvider; image picker without broad storage permission.
- Category selection, configurable backend, JPEG/PNG checks (10 MiB,16MP).
- Multipart `category`, `quality_mode` and `image` sent to `/api/inspect`.
- Benchmark mode default; quality-gated mode is an experimental capture screen,
  not a validated confidence or factory-suitability measure.
- GOOD/ANOMALY result metadata, processed crop and overlay. RETAKE does not need
  anomaly outputs. HTTP failures produce UNAVAILABLE, never GOOD or mock results.
- Offline English TextToSpeech voice if installed. Visual fallback otherwise.
- Inputs disabled during imports/requests, no automatic HTTP retries, explicit
  connection errors, cancelled request on activity teardown.
- Original copies held in app-private cache, removed when replaced or activity
  ends; external camera/gallery originals are not removed. Android/OS crash can
  leave cache files until OS cleanup; no permanent image archive is created.
- Base URL stored in private app preferences. No secrets or production auth.

## Build

Open `android-companion` in Android Studio, choose JDK17+ and SDK34. The pinned
AGP8.7.3/Gradle8.9 pairing uses Java17 bytecode. Kotlin1.9.25, AndroidX Activity1.9.3,
Core1.13.1, OkHttp4.12.0 are pinned.

Windows bootstrap (downloads Gradle to ignored `.tools/`, verifies official
distribution SHA256, caches dependencies under the project):

```powershell
cd android-companion
# Set JAVA_HOME to your JDK17+ and ANDROID_HOME to your existing Android SDK.
.\build-local.ps1
```

Tasks: `testDebugUnitTest`, `assembleDebug`. No Gradle wrapper binary is checked
in; use this bootstrap or generate a wrapper from the pinned Gradle distribution.
APK output: `app/build/outputs/apk/debug/app-debug.apk` (ignored; not a device test).

## Safest local connection: USB

Start the backend bound to loopback as documented in API_CONTRACT.md. Connect
your unlocked device with USB debugging deliberately enabled; authorize only
your own computer. Then run these yourself:

```powershell
adb devices
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb reverse tcp:8000 tcp:8000
```

Use `http://127.0.0.1:8000` in the app, including on an emulator with adb reverse.
The emulator's alternate host address is intentionally not recommended because
the backend validates host headers. No public hosting, firewall changes or LAN exposure needed.
ADB reverse must be restored after reconnecting. Installation is not performed
automatically by this project.

Debug manifest permits HTTP for local testing; the main/release manifest rejects
cleartext. This is not certificate bypass. Do not use debug HTTP for sensitive
industrial data or expose the unauthenticated API publicly. Release HTTPS alone
does not make this production-ready: authentication, consent, retention review
and server access controls remain necessary.

## Physical-device acceptance checklist

1. Confirm exact Android device/model, API level and camera availability.
2. Install APK yourself, connect via USB; inspect a held-out normal then defective
   image from the correct benchmark category. Compare score/decision with web.
3. Confirm spoken feedback with a downloaded offline English voice.
4. Verify capture cancellation, wrong format, oversize image and backend outage.
5. Change category/image after a request; ensure old result is cleared. Rotate
   during request; verify cancellation and explicit new-selection instruction.
6. Verify portrait/landscape and text scaling on the actual phone/tablet.
7. Verify quality-gated RETAKE displays reasons with no good/anomaly verdict.

Physical phone photos of arbitrary bottles are **not** equivalent to MVTec test
images. Their detection performance must be evaluated separately.

## Verification evidence — 22 October 2026

- Final cached offline `testDebugUnitTest assembleDebug`: **BUILD SUCCESSFUL**,
  40 seconds; 13 JVM contract tests, zero failures/errors/skips.
- APK: `android-companion/app/build/outputs/apk/debug/app-debug.apk`.
- APK SHA256: `58c09484791777efcb2f24e4ad4c795c43b16c8713416a530d541f5fc25a9dfc`.
- XML test evidence under `app/build/test-results/testDebugUnitTest/` (ignored).
- Android lint was not completed: the separate requested invocation was
  interrupted before execution. No lint-clean claim is made.
- No emulator/device installation or camera/TTS execution was performed.

## Official API references

- https://developer.android.com/reference/androidx/activity/result/contract/ActivityResultContracts.TakePicture
- https://developer.android.com/reference/androidx/core/content/FileProvider
- https://developer.android.com/reference/android/speech/tts/TextToSpeech
- https://developer.android.com/privacy-and-security/security-config
- https://developer.android.com/build/releases/agp-8-7-0-release-notes
