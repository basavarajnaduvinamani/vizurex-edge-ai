# VisureX inspection prototype: product requirements

**Purpose.** Help an MSME line inspector or QA lead capture a part, review a
model's finding and keep an inspection record. The project extends WCTE's
inherited PatchCore pipeline. The student's work adds evaluation, application
and portable-model tooling. The confirmed scope contains no verified count of
organisations or official sector list; see `S1_SCOPE_EVIDENCE.md`.

**User interviews: planned, not done.** No factory usage, saved inspection time,
onboarding-time reduction or escaped-defect reduction has been measured. These
requirements reflect technical stakeholder discussions and prototype evidence;
they are assumptions to validate with inspectors and QA leads.

**Job to be done.** When checking a known part family, obtain a traceable visual
suggestion, understand whether another capture is needed, and record the human's
final assessment without losing the original prediction.

**Initial scope.** A supervised pilot on an agreed part family, subject to WCTE
approval, suitable labelled captures and acceptance criteria. Begin with the
existing local workflow. Phone/glasses capture and physical-device performance
remain unverified. NCR capture and analytics integration are possible follow-on
applications, not completed integrations.

**Required workflow.** Capture -> model suggestion or RETAKE -> operator review
-> accept/correct/request recapture -> audit record. A correction must retain
the original score, threshold, model version and image reference, alongside a
reviewer reference, reason and final disposition. The review/correction controls
are planned work; existing logging does not constitute a feedback-learning loop.

**Learning policy.** One operator correction does not alter the production model.
QA-reviewed normal examples may enter a future reference-bank development set;
defect examples stay separately labelled. Evaluate a versioned update against a
separate frozen holdout before approval and release. Keep test images out of
fitting. Capture-selection evaluation remains blocked without new real captures.

**North-star metric.** Correctly reviewed inspections per active operator-hour,
with correctness independently audited. Measure the complete workflow, including
retakes and corrections. Baseline and target are not yet established.

**Guardrails.** False alarms per shift, accompanied by the number of normal parts
inspected and shift duration; missed defects on an independently labelled pilot
holdout; operator review coverage and successful traceability of corrections.
Agree tolerances with the QA lead before a pilot. No universal accuracy promise.

**Go/no-go.** Keep the prototype supervised and benchmark-scoped. The existing
blur study exposes a failure that the heuristic gate did not catch reliably.
The expanded few-shot study and normal-only router do not justify replacing the
current detector. Evidence: `S6_GO_NO_GO.md`. Public hosting is approval-gated;
its separate generated-sample mode is not an industrial deployment.
