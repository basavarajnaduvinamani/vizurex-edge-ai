# Browser-local platform contracts

Scope: the first visible workflow slice, requested 4 November 2026. Static
Vercel app, existing vanilla modules/styles, no backend, auth service, LLM/VLM
calls or research study. Existing Inspect scoring remains unchanged.

Records are versioned JSON Schema draft-07 envelopes: `schemaVersion`, `id`,
`revision`, and `fields`. Every domain field is `{value, source, confirmed}`;
source is `detector`, `asr`, `rule` or `human`. Envelope identifiers/version
metadata are not business suggestions. Observed system timestamps are marked
rule-derived/confirmed. Business suggestions retain their source and remain
highlighted until a person confirms or edits them. Human quantities/defect
information start empty. Confirming a model result does not change its score,
and feedback does not retrain or alter the inspection bank.

Contracts: `deploy/onboarding/platform/schemas/` contains Walk v1, Finding v1,
NcrRecord v1, Action v1, AuditEvent v1, CaptureEvent v1. CaptureEvent reserves
the same provenance wrapper for the future phone/glasses bridge. AJV compiles
validators for the browser; pure contract/role tests run in CI.

NCR lifecycle: draft → submitted → dispositioned → capa_open → closed.
Inspector can submit; QA lead/plant manager can disposition/open/close CAPA.
Missing quantities, unconfirmed suggestions and plant-specific defect codes
are checked before submission. Closure needs completed CAPA, closed linked
actions and an after photo. Audit rows are added with IndexedDB `add`, never
overwritten by the app; the NCR revision and audit append share a transaction.
Opening CAPA creates its action in that transaction. This is not a tamper-proof
or authenticated audit system; someone controlling their browser can change
their local storage. No signed-regulatory-compliance claim is made.

Data: Plant A (demo) and Plant B (demo), fictional stations/defect lists and
seeded examples. Seeds are idempotent. New entries are labelled local and remain
on that browser/device. Network Dashboard exposes counts only, not photos or
notes. Overdue means due date before today's UTC date and status not closed.
Escalation is a visible rule flag; no email, WhatsApp or notification is sent.
Repeat means matching plant/station/category key, not an inferred root cause.

Capture: file input with environment-camera hint; no physical phone camera or
voice accuracy is claimed tested. Browser speech can use a vendor service;
typing is the local fallback. Images are resized, decoded/re-encoded to remove
metadata and checked by MediaPipe Tasks Vision 1.2.2 with official BlazeFace
short-range float16 version 1. Face boxes are expanded, pixelated and blurred
before local storage. Failure obscures the whole image and is disclosed.
Face redaction is precautionary, not a guarantee of detecting all faces.
The synthetic-face unit checks the blur pipeline using an injected box; a
separate functional check loads the actual detector. No face dataset or
face-detection accuracy study is introduced.

WCTE's 50+ MSME network is owner-reported intended reach. No independent
deployment count or confirmed 2–3 plant pilot is supplied. The requested
“pilots starting” resume phrase is unsupported and must not be published.

Single sprint PR incorporates the previous draft inspection/sprint branches
without rewriting history. Only one main merge and final production release
are intended. S9 is a stretch only after the platform is live; real glasses
status stays “In progress”. No robustness study is started.
