# Should few-shot onboarding replace full-data PatchCore?

**Decision: NO-GO for replacing the current supervised prototype with a universal few-shot detector or the tested router.**

This decision concerns extensions of WCTE's inherited PatchCore system. Keep the shipped benchmark prototype supervised; the research recipes are offline comparisons, not a validated factory release. User interviews are planned, not done.

Source tables: `S2_RESULTS/summary.json`, `S3_RESULTS/summary.json`; extracted decision inputs: `S6_EVIDENCE.json`.

| Budget | Method | Macro AUROC | Category-bootstrap 95% interval |
|---|---|---:|---|
| 8 | dinov2_vits14 | 0.9559548864755482 | [0.9267271214489124, 0.9814284315802512] |
| full | dinov2_vits14 | 0.979589117948715 | [0.9658920781589411, 0.9911318649849041] |
| 8 | patchcore_wrn50 | 0.9241817986386065 | [0.8683754398956554, 0.9682405328716578] |
| full | patchcore_wrn50 | 0.9861788198733356 | [0.9775819446606449, 0.9934728227079871] |
| 8 | router | 0.9454243595009459 | [0.9098949346505976, 0.9753376795752801] |
| 8 | oracle | 0.9635509437948442 | [0.9372063249393212, 0.985434721954194] |

## Why

DINOv2 has the higher low-shot macro result, but neither recipe meets the registered all-category practical criterion. The full-shot H2 criterion is not met. The tested normal-only router criterion is not met. A favourable average can conceal an unsuitable part family. Recipes also differ in distance, aggregation and memory policy; this is not a pure causal backbone ablation. Extra normal calibration images are required beyond k.

The prior synthetic blur study (`docs/results/SOFTWARE_AND_STRESS_2026-10-22.md`) found that blurred normal images became false alarms and the heuristic gate rejected none of the blurred images. RETAKE exists as a workflow state; it is not a demonstrated solution to blur. Keep manual review and test realistic capture conditions before promotion.

## Product trade-off and next gate

Fewer reference images could make onboarding easier, but neither onboarding time nor factory inspection quality has been measured. Keep the existing frozen detector as the benchmark default, continue few-shot research, and defer automatic routing. Do not claim an achieved operational saving.

Agree a part family and error costs with a QA lead, collect separate development/test captures, and measure complete review tasks including retakes and corrections. The operator correction feature must preserve the original prediction. Curated feedback can support a later versioned model update; it must not silently change a deployed bank after a button click. No contact, pilot or deployment was performed by this memo.
