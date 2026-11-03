# MILESTONE_REPORT_STEP1

Date: 4 November 2026. Step 1 only; no robustness study started.

## 1. Outcome and scope

Built a separate, browser-only eight-reference onboarding demo with generated
S5 washer samples and local-photo uploads. Nothing was merged to main.
Protected preview URL: NONE — BLOCKED; no deployment created
Draft PR: https://github.com/basavarajnaduvinamani/vizurex-edge-ai/pull/4
Source commit: `46d4e515d3657a053dcb98ca5f0b6b9c4935776d`. Requested environment: preview, authentication required.
G4 status: BLOCKED_FIRST_DEPLOYMENT_REQUIRES_PRODUCTION. The new project has zero deployments.
Public release and production remain gated on explicit owner “deploy”.
Source: `docs/step1/preview.json`.

## 2. Preflight and attribution

Base: draft PR #3, head `d1c2937d5f5a79a7b0e4fcd7aaf0c7f299c3f5e0`.
New branch: `claude/demo-onboarding-2026-11`. Original stash preserved.
S5 contained FastAPI sample-only app, page, requirements, Dockerfile, README,
licenses/notices and reused patch-feature source. It used a separate generated
WRN patch-NN bank: normal score 0.05514240264892578 (GOOD), scratch score
1.0108609199523926 (ANOMALY), normal-only threshold 0.06378932237625122;
functional checks passed, not an accuracy estimate or prior deployment.
Source: `docs/sprint/S5_RESULTS/status.json`.

AnomalyDINO (Damm et al., WACV 2025), confirmed from the paper:
https://arxiv.org/html/2405.14529v3 ; official code linked there:
https://github.com/dammsi/AnomalyDINO . Our ViT-S/14 cosine patch-neighbour,
top-1%-mean baseline uses 224px crops, no masking/rotations by default,
and a disjoint normal-only p99 threshold. It differs from the paper's
448/672px preprocessing, masking and rotation settings. Benchmarked/adapted
and studied; not a new detection method or exact paper-result reproduction.
PatchCore: https://arxiv.org/abs/2106.08265 .

## 3. Working product

- Teach: eight normal thumbnails; separate normal calibration (eight generated
  calibration drawings; visitor minimum two, explicitly unvalidated).
- Check: generated or local image, real GOOD/ANOMALY, frozen threshold, score,
  fixed-scale patch heatmap and measured request latency.
- RETAKE: capture check runs before scoring; no fabricated score on rejection.
  Known benchmark blur failures remain visible. Not a reliable OOD/quality gate.
- Same-device WASM CPU, one thread. No inference server, analytics or transmitted
  photo upload. Test-time images never update the bank/threshold.
- Real photos and 2–3 owned sample parts remain pending; capture plan:
  `CAPTURE_SAMPLES.md`. Generated samples cannot establish real-part accuracy.

Sources: `deploy/onboarding/`, `docs/step1/browser_parity.json`.

## 4. Export, parity and latency

| Measurement | Final measured value | Source |
|---|---|---|
| DINOv2 exported model | 86,619,987 bytes | `docs/step1/browser_parity.json` |
| Graph SHA-256 | `110589286462b8c6858de9e65a5b6feccd3c4dbc0b23214f3c212f5edee6c171` | same |
| Browser vs Python decisions | 20/20 (agreement CI [0.8315665290169146, 1]) | same |
| Max absolute score difference | 5.30481338501e-06 | same |
| Threshold difference | 2.5913119316e-06 | same |
| Browser warm p50 | 361.4 ms [95% CI 350.5, 444.9] | same |
| Browser warm p95 | 602.8 ms [95% CI 460.9, 634.4] | same |
| Runtime | Chrome 156.0.8078.74; WASM, one CPU thread | same |

Timing n=20 sequential warm generated-image checks; includes decode,
preprocessing, capture check, encoder and scoring. Excludes model download and
bank onboarding. Percentile CIs bootstrap requests within this session, not
different devices. Final run is used even though earlier runs were faster.
Python receives the identical browser-decoded/cropped pixels. This is scoring
parity, not decoder parity; maximum browser-versus-PIL pixel difference was
1.0. Agreement interval is descriptive;
synthetic paired samples are not independent factory trials. No factory accuracy claim.

## 5. Existing benchmark evidence shown on the page

| k=8 macro AUROC | Mean and category-bootstrap 95% CI | Source |
|---|---|---|
| DINOv2 | 0.9560 [0.9267, 0.9814] | `docs/sprint/S2_RESULTS/summary.json` |
| PatchCore | 0.9242 [0.8684, 0.9682] | same |

Page also shows all measured k=1,2,4,8,16 rows and intervals, texture/object
splits, the negative router result, and the earlier separate PatchCore ONNX
parity/timing. No MVTec images are distributed. Benchmark thresholds need
additional normal calibration beyond k. Not eight photos total.
Sources: `docs/sprint/S2_RESULTS.md`, `S3_RESULTS.md`, `S4_RESULTS.md`.

## 6. Gates and verification

| Gate | Result | Evidence |
|---|---|---|
| Python | 62 passed | `artifacts/onboarding/final-gates/python.xml` |
| Existing frontend | 31 checks passed | `artifacts/onboarding/final-gates/frontend.log` |
| New JS/core/build tests | 7 passed | `artifacts/onboarding/final-gates/onboarding.log` |
| Dependency consistency | passed | `artifacts/onboarding/final-gates/dependency.log` |
| Browser acceptance | 25 checks, desktop + 390px, light + dark | `artifacts/onboarding/verification/browser.json` |
| Mobile Lighthouse performance / accessibility / best practices / SEO | 100 / 100 / 100 / 100 | `docs/step1/lighthouse.json` |
| Protected preview (G4) | BLOCKED: first deployment requires Production; none created | `docs/step1/preview.json` |

Lighthouse 12.5.1 measures initial lazy-loading page, not inference.
Screenshots: `artifacts/onboarding/verification/screenshots/` (16 full-page PNGs).
Build guard checks forbidden data paths, image filename allowlist and generated
image hashes. Hosted GitHub status: PENDING; configured
CI checks are distinguished from a confirmed hosted run. Two local build-output
tests use ignored assets and do not run in the lightweight hosted workflow.

## 7. Limitations and deviations

- No owned-part photos, physical glasses test, factory pilot or deployment impact.
- Only generated functional examples; no tuning/reliability study was started.
- Shared-pixel parity does not prove identical decoding across browsers/devices.
- Browser heatmap is unsmoothed patch distance, not benchmark segmentation.
- The initial suite hit global pytest-temp permissions (61 passed, 1 setup
  error). The final run used a fresh workspace temp directory; tests unchanged.
- Browser harness fixes retained the restrictive CSP and distinguished local
  blob thumbnails from external traffic; no privacy checks were disabled.
- Cloud creation was initially auto-review blocked; owner then explicitly
  authorized a protected preview. No billing changes or production promotion.
- Vercel CLI refused the first Preview deployment because this new project
  requires its first deployment to be Production. No --prod or API workaround
  was used. Only an empty protected project exists; no public/preview URL.
  Official source: https://vercel.com/docs/domains/working-with-domains/deploying-and-redirecting
- Referenced `_COMMON_RULES.txt`/R9 and design brief were unavailable. This report
  states actual evidence in explicit sections rather than claiming that template was read.

## 8. Resume lines supported by generated evidence

**SDE:** Built and locally verified an in-browser few-shot inspection demo (DINOv2 ONNX in WebAssembly): 361.4 ms median per warm generated-image check on laptop CPU; browser/Python decision parity 20/20; 98 checks configured in CI. Hosting is blocked.

**APM:** Turned a 15-category benchmark into an eight-reference onboarding flow with separate normal calibration and a RETAKE capture check for a proposed line-inspector workflow; user validation pending.

**PRE:** Benchmarked DINOv2 k-NN (AnomalyDINO-style) versus PatchCore across 15 MVTec AD categories: 0.9560 [0.9267, 0.9814] versus 0.9242 [0.8684, 0.9682] macro AUROC at k=8 (category-bootstrap 95% CIs); pre-registered router rejected.

Sources: `docs/step1/tests.json`, `browser_parity.json`, `preview.json`,
`docs/sprint/S2_RESULTS/summary.json`, `docs/sprint/S3_RESULTS.md`.
“Shipped”, “public demo”, real-part reliability, user adoption and factory impact are not supported.

## 9. Stop

Strongest result: a measured browser-only flow with matching generated-sample decisions.
Weakest gap: no owned-part/real capture qualification.
One next upgrade: collect the pre-split owned-part capture pack, only after the next instruction.
STOP. No robustness study, main merge, production release or public-access change.

## Add-on: source publication and header, 4 November 2026

The later owner instruction explicitly authorized publishing the source after
a full-history audit. Final audited candidate: `8ac3574`; 67 commits and 889
unique blobs; no secret, weight, raw restricted-data/image or notebook-output
findings. Six tracked image versions were inspected: synthetic UI screenshots
and numeric result plots. Existing Apache-2.0 LICENSE matches upstream exactly.
Source: `docs/PUBLICATION_AUDIT_2026-11-04.md`.

Repository PUBLIC status verified:
https://github.com/basavarajnaduvinamani/vizurex-edge-ai . Publication receipt:
`docs/step1/publication.json`. No history was rewritten.

Added the exact prototype date line and textual affiliation, header/footer
GitHub links, and an evidence-linked Done/Next status box. Updated the README
with scope, evidence, method attribution and inherited-versus-own contributions.
The update passed 25 browser checks at desktop/390px in light/dark and the seven
existing JavaScript/build checks. Mobile Lighthouse remained 100/100/100/100.
Sources: `docs/step1/header_update.json`, `docs/step1/lighthouse.json`.
Screenshots: `artifacts/onboarding/verification-header/screenshots/`.
The earlier parity/timing result remains the original recorded measurement,
not a new speed claim from this copy/layout update.

Changes are on draft PR #4; main remains the default branch and has not been
merged. The owner controls that merge. Source visibility is now public under
the add-on approval; G4 site hosting remains blocked and there is no live demo URL.
