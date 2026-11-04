# Glasses first light — 15-minute checklist

Status: **In progress. No real-glasses test is claimed.**
Use only your own objects, no people, private documents or factory footage.
This development APK is not a published app. Prepare a trusted portable model
ZIP for the exact part/category first. The Android model is the existing portable
PatchCore path, not the browser DINOv2 demo.

1. **0–3 min — prepare.** Android 12+ phone, charged Ray-Ban Meta glasses paired
   in the current Meta AI app. Enable Meta AI Developer Mode. This debug build
   uses documented development attestation IDs `0`/`0`; no production credentials
   are included. Connect USB and deliberately approve debugging on your phone.
   From `development`, run:
   ```powershell
   adb install -r android-companion/.tools/app-s9/outputs/apk/debug/app-debug.apk
   adb logcat -c
   ```
2. **3–5 min — connect.** Open **VisureX Companion → Glasses bridge · In progress**.
   Enter your plant ID and station. Tap **Connect via Meta AI**, grant Bluetooth,
   finish registration in Meta AI, return and verify `REGISTERED`. Tap **Start
   glasses stream**, grant DAT camera permission, and wait for `STREAMING`.
   Record the exact phone/Android/glasses/firmware versions and state/error text.
3. **5–7 min — note.** Point at your own object; enter a short note; tap **Note**.
   Expect a local draft, not an inspection verdict. Tap **Export latest Finding +
   CaptureEvent JSON** and choose a local file. Verify `origin=glasses`, exact S1
   schema versions, no fabricated score, and suggested fields unconfirmed.
4. **7–10 min — check.** Import the trusted portable model ZIP; select its matching
   category. Tap **Check** on the same object. Expect GOOD or ANOMALY, or an honest
   unavailable/RETAKE error. Record score/model SHA/ONNX milliseconds if shown;
   this is a functional check, not a latency benchmark or accuracy estimate.
   Verify spoken output. If it comes from the phone, select glasses as Android's
   media output and repeat; record failure if routing still does not work.
5. **10–12 min — voice.** Tap **Listen once · phone microphone** and allow the
   microphone. Say “note washer at station one”, then arm again and say “check
   washer”. Recognition must be on-device; unsupported recognition shows the
   button fallback. There is no always-on wake word or tested glasses-mic route.
   Record exact recognized note and whether capture started once.
6. **12–14 min — errors.** Tap the glasses once to pause: Note/Check must reject
   capture while paused, not use that tap as a trigger. Resume, then test Stop
   and restarting. Deny permissions and test missing/wrong-category model; no
   fabricated verdict should appear. Redaction failure must save no raw image.
   Check redacted output visually; do not test faces of real people.
7. **14–15 min — evidence.** Export the latest JSON, take screenshots of states,
   result and any failure. Stop the session. Send the exported JSON, screenshots,
   device versions and this checklist with each item PASS/FAIL/NOT RUN. No video
   recording is required. Do not mark the site Done until real results are reviewed.

## Mock Device Kit (developer check, not real glasses)

The pinned Mock Device Kit is included and `GlassesMockTest` exercises simulated
registration/pairing and denied camera permission. An emulator or physical Android
target is required; compiling this test is not execution:

```powershell
cd android-companion
.\build-local.ps1 -Tasks connectedDebugAndroidTest
```

This test passed on an Android 14 emulator (registration, pairing and denied
camera permission only); see `docs/glasses/build.json` and `mock-result.txt`.
Full mock video/photo/inference coverage and all real-device tests remain pending.

The sprint APK above uses a fresh ignored output directory because the old
OneDrive build output was locked. To reproduce it with the existing SDK/JDK set:

```powershell
# From development/android-companion; JAVA_HOME and ANDROID_HOME must be set.
$env:GRADLE_USER_HOME="$pwd/.gradle/user-home"
.tools/gradle-8.13/bin/gradle.bat --no-daemon --project-cache-dir .gradle/s9 -PvisurexBuildDir=../.tools/app-s9 testDebugUnitTest assembleDebug assembleDebugAndroidTest
```
