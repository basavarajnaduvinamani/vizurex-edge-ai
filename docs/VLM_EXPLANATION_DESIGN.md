# VLM operator-instruction layer: design only

Status: **design proposal. No code, no API integration and no evaluation exist.**
Nothing here changes the detector, the threshold or the RETAKE policy.

## Goal

After an inspection, show and optionally speak one short operator instruction, such as
"Possible chip on the upper-right rim; set this part aside for a second check", instead
of only GOOD / ANOMALY and a heatmap. The target user is a line operator at an MSME who
may be wearing glasses or holding a tablet, not an ML engineer.

## Non-negotiable boundary: the VLM never decides

| Owned by the existing pipeline (unchanged) | Owned by the VLM layer (new, optional) |
|---|---|
| GOOD / ANOMALY decision (PatchCore score vs frozen threshold) | Wording of one instruction for an already-made decision |
| RETAKE from the capture checks | Plain-language restatement of the capture-check reason |
| Score, threshold, heatmap, model version, audit log | Region description ("upper-right rim") from the heatmap peak |

Rules the implementation must enforce in code, not only in the prompt:

1. The decision is passed in as a fixed field and copied unchanged into the UI. The
   VLM's output is never parsed for a decision, and it cannot flip, soften or override one.
2. Output is checked before display: one sentence, at most about 20 words, no numbers
   other than ones supplied, no probability or confidence words ("98% sure",
   "definitely"), no new defect class unless it is in the category's allowed list.
   Anything that fails is replaced by a fixed template ("Anomaly detected near the
   upper right. Set the part aside for review.").
3. A template fallback exists for every outcome, so the system works offline, with the
   VLM disabled, slow or unavailable. Inspection latency never waits on the VLM; the
   instruction appears when ready or the template is kept.
4. The UI labels the sentence as an automated description, separate from the decision.
5. For RETAKE, the VLM may only restate the supplied capture-check reasons as an action
   ("Move to brighter light and retake"); it never comments on defects.

## Inputs and output

Input (structured, built by the backend from the existing response):

```json
{
  "decision": "ANOMALY",
  "category": "bottle",
  "allowed_defect_words": ["crack", "chip", "contamination", "broken"],
  "heatmap_peak": {"region": "upper-right", "area_fraction": 0.04},
  "processed_crop_png": "<224x224 centre crop>",
  "overlay_png": "<crop with heatmap>",
  "capture_reasons": []
}
```

The region label and area fraction come from deterministic code over the fixed-scale
heatmap (3x3 grid of the crop), so location is not left to the VLM. Output: one string.

## Model options

- **Gemini Flash (cloud)**: good image description and low latency, but images leave
  the device. Allowed only with explicit customer consent, an opt-in setting, and never
  for images under customer-data restrictions. Prototype candidate for wording quality.
- **Small on-device or laptop VLM** (for example a 2–4B open model): keeps images local,
  matching the current "no cloud AI API" handover statement; quality and latency must be
  measured on the actual laptop/tablet before use.
- **Template only** (baseline): deterministic sentences from decision + region. Every
  VLM variant must beat this baseline in the evaluation below or it is not shipped.

## Privacy and cost

Default is off. Cloud use sends only the 224 px crop and overlay, never the original
upload or filename, and is logged as such in the inspection metadata. Record per-call
cost and latency. Speech stays on the offline TTS path described in the handover.

## Evaluation plan

Data: a fixed set of past inspection records with their images, drawn from MVTec test
images for the three Phase 1 categories first, then consented WCT captures. Include
GOOD, ANOMALY (true and false positives) and RETAKE cases. Freeze the set and the
prompts before scoring.

Measures, per variant (template, cloud VLM, local VLM):

1. **Decision fidelity (must be 100%)**: automatic check that no instruction contradicts
   or hedges the supplied decision (for example "looks fine" on an ANOMALY). Any
   violation blocks release of that variant.
2. **Grounding**: two reviewers mark whether the described location matches the heatmap
   peak and, where masks exist, the true defect region. Report agreement (Cohen's kappa).
3. **Hallucination rate**: share of instructions naming a defect type or detail not
   visible or not in the allowed list.
4. **Operator usefulness**: short task study with operators or WCT staff: time to
   correct action and preference against the template baseline, with blinded order.
5. **Guardrail rate**: fraction of outputs rejected by the validator and replaced by the
   template; latency p50/p95; cost per 1,000 inspections.
6. **False-positive handling**: on known false alarms, the wording must still direct a
   human check rather than assert a defect; report separately.

Go criteria (decided before evaluation): 100% decision fidelity, hallucination rate below
an agreed limit set with WCT, usefulness at least equal to the template baseline, and
latency that never delays the decision display. Otherwise keep the template baseline.

## Out of scope

No VLM-based anomaly detection, zero-shot defect classification, threshold tuning,
or automatic accept/reject. Those would need their own protocol and evidence.
