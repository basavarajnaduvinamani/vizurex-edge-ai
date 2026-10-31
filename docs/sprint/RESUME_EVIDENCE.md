# Sprint resume evidence

Statements distinguish inherited detector code from project extensions; no publication, factory pilot or public deployment is claimed.

## S1: numeric reach not supported

Not supported: No independently verified WCTE organisation count or sector target was found.

Sources: `docs/sprint/S1_SCOPE_EVIDENCE.md`.

No independently verified WCTE organisation count or sector target was found.

## S2: supported benchmark claim

Benchmarked training-free DINOv2 against inherited WCTE PatchCore across 15 MVTec AD categories (k=1-16, three seeds): k=8 macro AUROC 0.9560 (95% category-bootstrap CI [0.9267, 0.9814]) versus 0.9242 ([0.8684, 0.9682]), with a higher DINOv2 texture-category mean.

Sources: `docs/sprint/S2_RESULTS/summary.json`.

k counts reference images, not the additional normal-calibration images. Registered practical-use and H2 criteria were not met. Previously inspected v1 results are disclosed.

## S3: supported negative exploratory result

Evaluated a fixed normal-validation-only backbone selector across 15 categories: k=8 macro AUROC 0.9454 versus 0.9560 for fixed DINOv2; rejected the selector after its registered comparison criterion failed.

Sources: `docs/sprint/S3_RESULTS/summary.json`.

Previously inspected benchmark; no trained cross-category meta-model or unseen-category confirmation.

## S4: supported export candidate, not device deployment

Built a FastAPI inspection workflow, offline bundles and Android companion around inherited WCTE PatchCore; verified an ONNX candidate with 261/261 held-out decisions preserved and bottle CPU model-call p50/p95 167.9/179.1 ms; 59 Python tests and 31 frontend checks in CI.

Sources: `docs/sprint/S4_RESULTS/summary.json`, `docs/ANDROID_COMPANION.md`, `docs/results/SOFTWARE_AND_STRESS_2026-10-22.md`, `artifacts/sprint-2026-11-01/s6-tests.xml`, `artifacts/sprint-2026-11-01/s7-frontend/console.log`.

Warm laptop model calls; decoding/network/UI excluded. No phone or glasses timing. Serving app not switched to the new ONNX candidate.

## S5: live public hosting not supported

Prepared and locally tested a sample-only inference demo with a separate generated reference bank and an allowlisted Docker review package; public deployment remains pending.

Sources: `docs/sprint/S5_RESULTS/status.json`.

No public deployment approval or account plan confirmed; no container build or public endpoint is claimed.

## S6: supported product planning, not user impact

Defined product requirements and go/no-go decisions for a WCTE inspection prototype extending inherited PatchCore; retained supervised review after blur-stress and few-shot findings, with inspector interviews and factory impact measurement still planned.

Sources: `docs/sprint/S6_PRD.md`, `docs/sprint/S6_GO_NO_GO.md`, `docs/sprint/S6_EVIDENCE.json`.

No verified organisation count, end-user research, saved onboarding time or industrial impact. RETAKE is not a validated blur solution.
