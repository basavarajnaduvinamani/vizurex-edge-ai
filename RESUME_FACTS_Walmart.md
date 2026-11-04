# VisureX — verified sprint facts

Date: 4 November 2026. Counts below are deterministic software checks, not sampled
accuracy estimates; confidence intervals do not apply to these counts.

| Fact | Number / status | Source file |
|---|---|---|
| Browser workflow modules | 5: Inspect, Walk, NCR, Actions, Dashboard | `docs/platform/results.json` |
| Business objects with versioned field-provenance schemas | 6 | `docs/platform/results.json`; `deploy/onboarding/platform/schemas/` |
| Final local software tests | 80 (62 Python + 18 Node), plus 31 frontend checks | `docs/platform/results.json`; `artifacts/platform/final/software/` |
| Hosted CI | Both final-candidate checks green; 78 configured tests + 31 frontend checks | `artifacts/platform/final/github-before-merge.json`; `.github/workflows/software-checks.yml` |
| Browser acceptance | 86 platform + 25 Inspect checks across 4 width/theme variants | `docs/platform/browser.json`; `artifacts/platform/final/inspect/browser.json` |
| Lighthouse initial page | 100 performance, 100 accessibility, 100 best practices, 100 SEO | `docs/platform/lighthouse.json`; lazy model load excluded |
| Platform release | PR #5 merged; main `5388c26ce57f230aa58b54d8890de226980476c5` | `artifacts/platform/final/merge.json` |
| Production demo | https://visurex-demo.vercel.app | `artifacts/platform/final/deployment.json`; `live-confirmation.json` |
| Android DAT dependency | Official SDK 1.0.1, core/camera/mockdevice | `android-companion/app/build.gradle.kts` |
| Android unit tests | 23 passed, 0 failures/errors | `docs/glasses/build.json`; `docs/glasses/TEST-*.xml` |
| Mock Device Kit | 1 Android 14 emulator test passed: registration, pairing, denied permission | `docs/glasses/mock-result.txt`; `GlassesMockTest.kt` |
| Kotlin → browser schema compatibility | 2 generated envelopes validated | `docs/glasses/schema-check.json`; `scripts/verify_glasses_records.mjs` |
| Debug APK | 157,027,956 bytes; SHA-256 in build record | `docs/glasses/build.json` |
| Real phone/glasses validation | NOT RUN | `docs/glasses/build.json`; `GLASSES_FIRST_LIGHT.md` |
| Users / pilots / factory deployment | No verified evidence; no numerical claim | `docs/platform/results.json` limits |
| WCTE network impact | 50+ MSMEs is owner-reported intended reach, not measured adoption | `README.md`; no independently verified network source in this sprint |

## Supported resume wording

- **APM:** Built a five-module WCTE prototype connecting visual inspection,
  shop-floor findings, NCR workflows and corrective actions; defined review and
  closure rules with field provenance. No pilot claim.
- **SDE:** Shipped a browser-local inspection and workflow prototype with six
  versioned schemas, 78 tests plus 31 frontend checks in hosted CI; built a Kotlin
  DAT 1.0.1 bridge with 23 passing unit tests and one emulator Mock Device Kit test.
- **Pre-doc:** Built a reproducible inspection interface with explicit provenance,
  frozen model outputs and cross-language schema checks; physical capture
  evaluation remains pending. This sprint establishes software, not a novel method.

## Do not say

- “100% accurate”, “factory validated”, “deployed to 50+ MSMEs”, or “pilots started”.
- “Tested on real glasses/phone”, glasses latency, battery life or speaker success.
- Full mock stream/photo/ONNX coverage; the executed mock test covers only the
  cases named above.
- Browser DINOv2 and Android portable PatchCore are the same model, or that schema
  compatibility proves numerical model parity.
- Role switching is authentication, local audit is tamper-proof, or JSON export
  is verified compatibility with WCTE's internal NCR system.
- Face masking guarantees no faces remain; Lighthouse measures model inference.

## Interview questions

1. **What did you add?** The browser-local Walk/NCR/Actions/Dashboard workflows,
   provenance contracts and a development glasses bridge. PatchCore, DINOv2,
   ONNX Runtime and Meta DAT are existing methods/tools, credited as such.
2. **What actually ran?** The final platform gates, Android unit tests, two schema
   checks and one emulator Mock Device Kit test. No physical-glasses run.
3. **What is the biggest gap?** Real captures and one supervised pilot. The next
   step is the first-light checklist before collecting any effectiveness data.
