# 0003 — Android glasses development bridge

Date: 4 November 2026. Status: implemented skeleton, physical validation pending.

Use Meta DAT core/camera/mockdevice **1.0.1** from Maven Central and reuse
`OfflineInspector`, rather than write a second inspection engine. The official
sample uses Kotlin 2.2.21 / AGP 8.11.1 / compile SDK 36; the build is updated to
that combination with Gradle 8.13. Minimum Android 12 is a deliberate prototype
default for platform on-device speech recognition, not a Meta hardware claim.

Development attestation uses the documented `0`/`0` identifiers and Meta AI
Developer Mode. No credentials or production project are fabricated. Both DAT
analytics and crash capture are opted out. Recognition is explicitly armed on
the phone, once per utterance, with no cloud fallback. Audio output uses Android's
media route; actual glasses speaker playback requires device verification.

Capture only while STREAMING, one request at a time. A cap-touch pause is a pause,
not a trigger. A bundled ML Kit detector masks expanded face boxes before JPEG
encoding, local inference, or persistence. Detection failure rejects the capture;
zero detected faces does not guarantee a face-free image. No raw photo is saved.

The imported portable PatchCore ONNX model is reused without retraining or new
accuracy claims. It is distinct from the browser DINOv2 demo. Suggested JSON
business fields remain unconfirmed. Export is manual; there is no browser sync
or deployed NCR import endpoint.

S8 already consumed the requested single PR/merge/deploy. S9 stays on a separate
branch without another production deployment. The deployed glasses status stays
In progress until the owner's real-device checklist passes.

Sources:
- https://github.com/facebook/meta-wearables-dat-android/blob/main/samples/CameraAccess/gradle/libs.versions.toml
- https://github.com/facebook/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/getting-started/SKILL.md
- https://github.com/facebook/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/camera-streaming/SKILL.md
- https://github.com/facebook/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/mockdevice-testing/SKILL.md
- https://github.com/facebook/meta-wearables-dat-android#opting-out-of-data-collection
- https://developers.google.com/ml-kit/vision/face-detection/android
