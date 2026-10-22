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
