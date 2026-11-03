# Browser-local workflow slice

Date: 2026-11-04. Owner-specified architecture: vanilla existing app, IndexedDB,
one release, no backend or additional framework.

PANEL: photo redaction for local evidence
Options: A) native browser FaceDetector only; B) official MediaPipe CPU detector.
Key views: Platform: native availability varies; package the pinned official runtime.
Privacy: redact before persistence; failure obscures the whole image.
Research: synthetic masking test is not detector accuracy or a new method.
Call: B with disclosed failure fallback. Reversible: yes.
Resume impact: SDE local pipeline; APM evidence/review workflow, no impact claim.

Technical trade-offs: local role switcher and append-only app audit, not server
authentication or tamper-proof logs. JSON Schema domain fields carry provenance.
Plant data is explicitly fictional; no measured factory/pilot claims. Import
compatibility for WCTE NCR exports remains unverified. Browser ASR can use the
browser provider; typed notes avoid that optional service.
