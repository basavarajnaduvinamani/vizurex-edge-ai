# VisureX Android companion

Native Kotlin phone/tablet prototype. Uses the real local inspection API; no
Meta SDK and no mock inference. See [setup, safety and acceptance checklist](../docs/ANDROID_COMPANION.md).

Build on Windows: `./build-local.ps1` with JDK17+ and SDK34 configured.
The script downloads verified Gradle8.9 into project-local ignored `.tools/`.
Default tasks compile the debug APK and execute JVM contract tests.

The debug APK permits cleartext HTTP strictly for local prototype use. Release
configuration rejects cleartext. Use USB `adb reverse` and loopback backend;
do not publish the unauthenticated inspection service to the internet.

Device installation, camera and audio behaviour must be validated on hardware.
# Glasses development bridge (4 November 2026)

DAT core/camera/mockdevice are pinned to 1.0.1 from Maven Central. Open the
**Glasses bridge · In progress** button. It reuses the portable local ONNX engine,
with local face masking and S1 JSON drafts. Real glasses, phone speech and audio
routing are not yet validated. See [first-light checklist](../GLASSES_FIRST_LIGHT.md)
and [decision record](../docs/adr/0003-glasses-development-bridge.md).
The bridge requires Android 12+, compile SDK 36, Kotlin 2.2.21, AGP 8.11.1 and
Gradle 8.13. Earlier phone-only build notes below are historical.

