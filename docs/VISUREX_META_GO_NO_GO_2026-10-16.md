# VisureX validation and Meta glasses integration decision

**Status as of 16 October 2026**

## Recommendation

I recommend a **controlled go-ahead**. The MVTec bottle run is enough to show
that the VisureX anomaly-detection path is real and executable. It is not enough
to claim that the model is ready for deployment across different products or
factory conditions.

The sensible approach is to start the Meta glasses capture-and-audio loop now,
while validating the detector on a few more representative categories in
parallel. We should not wait for every research experiment before touching the
glasses, but we should also not present the present detector as production-ready.

| Question | Decision |
|---|---|
| Does the pipeline run end to end? | **Yes.** Training, calibration, inference, metrics, evidence export and model saving worked. |
| Is the earlier Top-view result trustworthy? | **No.** It had train-test duplication. |
| Is the new bottle result leakage-free? | **Yes for exact duplicates.** No exact train-test overlap was found. |
| Is one MVTec category enough to start integration? | **Yes, for a prototype.** |
| Is one category enough for a paper or general performance claim? | **No.** |
| Are all 15 categories compulsory immediately? | **No.** They are needed later for a proper benchmark. |
| Is a multi-backbone system compulsory? | **No.** One backbone is preferable for the first edge version. |

## What has been established

The smoke test used the MVTec AD `bottle` category, WideResNet-50, one seed and a
1% PatchCore coreset. The split contained 167 normal training images, 42 normal
validation images and 83 untouched test images. The test set had 63 anomalous
and 20 normal samples. Exact SHA-256 checking found no train-test duplicates.

| AUROC | F1 | Precision | Recall | TP | FP | TN | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.9921 | 0.9844 | 1.0000 | 63 | 1 | 19 | 0 |

This is a strong smoke-test result: all 63 anomalous bottle images were detected
and one normal image was incorrectly flagged. It proves that the inherited core
is not a hollow prototype. However, bottle is only one comparatively clean
object category. A perfect ranking on it does not prove performance on textures,
small defects, new components, motion blur, glare or a head-mounted camera.

MVTec AD contains **15 categories**, not 15 backbones. We tested one category
with one backbone. These are two different experiment axes.

| Evidence level | Minimum work | What we can say afterwards |
|---|---|---|
| Completed smoke test | Bottle, one backbone, one seed | “The pipeline works end to end on clean external data.” |
| Integration gate | 3 representative categories, one backbone | “The detector is stable enough to connect to the glasses prototype.” |
| Benchmark | All 15 categories, matched baseline | “We have measured general benchmark performance.” |
| Research claim | 15 categories, 3 seeds, ablations | “This VisureX addition improves accuracy, efficiency or robustness.” |

For the three-category gate, I would use `bottle` for an object, `carpet` for a
texture, and `transistor` or `metal_nut` for small structured defects. If these
runs complete without leakage or pipeline failures, glasses work can proceed
without waiting for multi-backbone ablations. The full 15-category experiment
can run later on Colab, Kaggle or the WCTE lab GPU.

## Proposed glasses architecture

Meta's Wearables Device Access Toolkit 1.0 supports Android and iOS mobile apps
and exposes camera, microphone, audio, motion and IMU capabilities. It also has
a Mock Device Kit, so development can begin before every hardware path is ready.
Ray-Ban Meta glasses are sold in India. Displayless Ray-Ban models can return the
result through their open-ear speakers; the detailed image and history remain on
the phone. Meta states that the glasses still pair through the Meta AI mobile
app. [Meta SDK and device FAQ](https://developers.meta.com/wearables/faq/),
[India availability](https://about.fb.com/news/2025/05/ray-ban-meta-glasses-come-to-india-experience-the-future-with-meta-ai-integrated-and-multiple-styles-on-offer/)

```mermaid
flowchart LR
    G[Meta glasses\ncamera + microphone] -->|Device Access Toolkit| P[Android phone]
    P --> Q[Frame quality gate\nblur, glare, distance]
    Q --> M[On-device VisureX\nPatchCore inference]
    M --> U{Confidence}
    U -->|High| A[Audio result through glasses\n+ result on phone]
    U -->|Low| H[Ask user to recapture\nor optional cloud review]
    A --> L[Local encrypted inspection log]
    H --> L
    L -. optional sync .-> C[WCTE dashboard / server]
```

The first build should be **event-driven**, not continuous video inference. The
operator says “inspect”, the app captures a short burst, rejects blurred or
glare-heavy frames, selects the best frame and runs one local inference. This is
cheaper, easier on battery and easier to audit than uploading a continuous
factory video stream.

The present WideResNet model is acceptable for integration testing, but mobile
latency is still unmeasured. The edge version should eventually compare it with
a smaller backbone or a distilled/quantised model. Accuracy, latency, memory and
battery use must all be reported on the actual phone.

## Cost model

The Meta SDK is the device interface; it is not the anomaly-detection server.
Meta does not publish a per-camera-call charge in the cited SDK material. If the
model and logs remain on the phone, there is no inference-server bill. Costs
begin only when we add cloud storage, dashboards, remote model updates or a
cloud AI fallback.

Planning assumptions below: 50 inspections per operator per working day, 22
days per month, one compressed image per inspection, and ₹90 per US dollar.
These are engineering estimates, not vendor quotations.

| Architecture | 1 operator / month | 100 operators / month | Main trade-off |
|---|---:|---:|---|
| Phone-only inference, local logs | **₹0 server inference** | **₹0 server inference** | Lowest cost and strongest privacy; phone performance must be validated. |
| Phone inference + small backend for users, model versions and selected logs | ₹0–₹1,500 during prototype | Roughly ₹5,000–₹20,000 | Useful for fleet management; range depends on retention and support level. |
| Hybrid: local inference, cloud review for 5% uncertain cases | Usually below ₹100 in model calls, plus backend | Roughly ₹500–₹8,000 in model calls, plus backend | Good fallback without uploading every frame. |
| Cloud vision for every inspection | Roughly ₹100–₹1,500 | Roughly ₹10,000–₹1.5 lakh | Easy to prototype but weaker privacy and dependent on connectivity. |
| Dedicated cloud GPU running continuously | Unnecessary for the prototype | Commonly tens of thousands of rupees per month | Only justified by sustained volume or server-side models. |

The cloud-AI ranges are deliberately broad because image cost changes with the
chosen model, resolution, detail level and response length. OpenAI bills vision
inputs as tokens and provides an official image-cost calculator. The Responses
API itself is not a separate “decision API”; model input and output usage is what
is billed. [OpenAI vision guide](https://developers.openai.com/api/docs/guides/images-vision),
[image cost calculator](https://developers.openai.com/api/docs/guides/image-cost-calculator),
[API pricing](https://developers.openai.com/api/docs/pricing)

Continuous streaming should be avoided. A 2 Mbps stream used for eight hours a
day is about 158 GB per operator per month, before protocol overhead. Event-based
still images reduce bandwidth by orders of magnitude and make the inspection
record easier to review.

## JEPA and OpenAI vision: where they fit

I have interpreted “Jeff model” as **JEPA**, most likely Meta's V-JEPA. V-JEPA 2
is a self-supervised video world model for learning representations, motion and
prediction. It is not a ready-made industrial defect decision API. It could
later help with temporal consistency, machine-state changes or choosing a useful
frame from a short clip, but replacing PatchCore with V-JEPA now would add a new
research problem before the basic product loop is complete.
[Meta V-JEPA 2](https://ai.meta.com/research/vjepa/)

| Component | Best role in this project | Recommendation now |
|---|---|---|
| PatchCore / VisureX | Fast part-specific anomaly score from normal training images | **Primary detector** |
| Small frame-quality model | Reject blur, glare, bad angle and excessive distance | **Build into the first mobile prototype** |
| V-JEPA | Video representation, temporal change and frame selection | Later research ablation |
| OpenAI vision model | Describe an uncertain image or produce a human-readable explanation | Optional cloud second opinion only |

A general vision-language model should not be the sole pass/fail judge for a
manufacturing defect. It may be faster to demonstrate because no training is
needed, but it can miss tiny tolerances, vary between prompts and return a
confident explanation without measurement evidence. The safer design is:

**local detector → confidence check → recapture or optional VLM explanation → human review for critical cases.**

## Immediate execution plan

1. Run the three-category single-backbone gate. Multi-backbone work can wait.
2. Build the Android app against Meta's Mock Device Kit: connect, capture, send
   a frame into a placeholder detector and return an audio response.
3. Export the current detector to an Android-compatible runtime and measure
   latency, memory and battery use on the paired phone.
4. Test with real glasses using one controlled component and fixed capture
   instructions. Collect failures caused by blur, angle, lighting and glare.
5. Run the complete 15-category benchmark and backbone ablations on GPU for the
   thesis/paper, without blocking the integration prototype.

This keeps the project safe without making it slow: the glasses interface can
start now, the detector receives one additional validation gate, and any claim
of general performance waits for the complete benchmark.
