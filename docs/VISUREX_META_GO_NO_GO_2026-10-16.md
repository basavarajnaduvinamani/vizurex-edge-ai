# VisureX Technical Validation and Meta Glasses Integration Plan

**Status as of 16 October 2026**

## 1. Summary and recommendation

The current results support a controlled continuation of VisureX. The inherited anomaly-detection pipeline has completed training, validation, testing, metric generation, evidence export and model saving on an external benchmark category. This confirms that the core pipeline is functional.

The result is sufficient to begin the Meta glasses integration prototype, but it is not yet sufficient to claim that VisureX will generalise across different products or factory conditions. The next stage should therefore run on two parallel tracks:

1. Validate the detector on a small but diverse set of MVTec AD categories.
2. Build the glasses-to-phone capture, inference and audio-response workflow.

| Technical question | Current conclusion |
|---|---|
| Does the VisureX pipeline run end to end? | **Yes.** Training, calibration, inference, evaluation and model export completed successfully. |
| Can the original Top-view result be used as final evidence? | **No.** Exact train-test duplication affected 46 of 50 normal test images. |
| Is the new bottle experiment free from exact train-test duplication? | **Yes.** SHA-256 comparison found no exact overlap. |
| Can Meta glasses integration begin? | **Yes.** Integration can begin while broader detector validation continues. |
| Is one MVTec category enough for a general performance claim? | **No.** It is an initial feasibility result. |
| Is a multi-backbone system required now? | **No.** A single backbone is preferable for the first integration and latency study. |

## 2. Completed validation

The initial external benchmark test used the `bottle` category from MVTec AD. The experiment used a WideResNet-50 feature backbone, features from `layer2` and `layer3`, a 1% approximate greedy coreset and seed 0.

The test used **one MVTec AD category and one feature backbone**. These are two separate experiment settings:

- **Dataset coverage:** 1 of the 15 MVTec AD categories has been tested.
- **Model configuration:** WideResNet-50 is the only backbone tested in this run.

The dataset split contained 167 normal training images, 42 normal validation images and 83 untouched test images. The test set contained 63 anomalous images and 20 normal images. The anomalous samples covered `broken_large`, `broken_small` and `contamination`. Exact SHA-256 checking found no duplicate images between the training and test sets.

| AUROC | F1 | Precision | Recall | TP | FP | TN | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.0000 | 0.9921 | 0.9844 | 1.0000 | 63 | 1 | 19 | 0 |

All 63 anomalous bottle images were detected, while one normal image was incorrectly flagged. This is a strong feasibility result for the selected category. It demonstrates that the pipeline can learn from clean normal samples and separate them from multiple anomaly types on unseen benchmark images.

The result should still be interpreted within its scope. Bottle is one relatively controlled object category. This experiment does not yet measure performance on textures, small structured defects, unfamiliar components, motion blur, glare or images captured from a head-mounted camera.

### Validation levels

| Stage | Experiment coverage | Purpose |
|---|---|---|
| Completed feasibility test | Bottle, one backbone, one seed | Confirm that the full pipeline works on clean external benchmark data. |
| Integration gate | Three representative categories, one backbone | Check that the pipeline remains stable across different visual structures before the first field-style pilot. |
| General benchmark | All 15 MVTec AD categories | Measure overall benchmark performance across objects and textures. |
| Research evaluation | All 15 categories, repeated seeds and controlled ablations | Support claims about accuracy, efficiency, robustness or architectural improvement. |

For the three-category gate, the proposed categories are `bottle` for a regular object, `carpet` for a texture and `transistor` or `metal_nut` for small structured defects. A single backbone is sufficient for this stage. Additional backbones should be treated as later ablation experiments, not as a prerequisite for starting the glasses prototype.

## 3. Proposed Meta glasses system

Meta's Wearables Device Access Toolkit 1.0 supports Android and iOS applications and provides access to camera, microphone, audio, motion and IMU capabilities. It also includes a Mock Device Kit, which allows application development before the complete hardware workflow is available. Ray-Ban Meta glasses are available in India.

The first system should use the glasses as the capture and audio interface, while the paired Android phone performs image-quality checks, anomaly detection and local logging.

```text
Meta glasses camera and microphone
                |
                v
        Paired Android phone
                |
                v
 Frame-quality check: blur, glare, angle and distance
                |
                v
       Local VisureX inference
                |
                v
        Confidence assessment
          /                 \
 high confidence        low confidence
       |                      |
 audio result          recapture or optional
 through glasses          cloud review
          \                 /
                v
       Local inspection log
                |
                v
      Optional WCTE dashboard
```

The first version should be event-driven rather than based on continuous video. The operator starts an inspection, the application captures a short burst, removes poor-quality frames, selects the best frame and runs one inference. This reduces battery use, bandwidth and unnecessary data collection while producing a clear inspection record.

The existing WideResNet-50 model can be used to prove the integration path. It should not automatically become the final mobile model. Once the workflow is functional, a smaller backbone or a quantised model can be compared using four measurements: detection quality, latency, memory consumption and battery impact on the paired phone.

Official references: [Meta Wearables SDK FAQ](https://developers.meta.com/wearables/faq/) and [Ray-Ban Meta availability in India](https://about.fb.com/news/2025/05/ray-ban-meta-glasses-come-to-india-experience-the-future-with-meta-ai-integrated-and-multiple-styles-on-offer/).

## 4. Deployment and running-cost estimate

The Meta toolkit provides the connection to the glasses. It is not an anomaly-detection server and does not create a separate inference charge by itself. If inference and inspection logs remain on the phone, the system has no cloud inference-server cost. Cloud costs arise only if the project adds central storage, dashboards, remote model management or an external AI fallback.

The estimates below assume 50 inspections per operator per working day, 22 working days per month, one compressed image per inspection and an exchange rate of ₹90 per US dollar. These figures are planning estimates rather than vendor quotations.

| Architecture | One operator per month | 100 operators per month | Main consideration |
|---|---:|---:|---|
| Phone-only inference and local logs | **₹0 inference-server cost** | **₹0 inference-server cost** | Best privacy and lowest recurring cost; phone performance must be measured. |
| Phone inference with a small management backend | ₹0–₹1,500 during the prototype | Approximately ₹5,000–₹20,000 | Adds user management, model versions and selected log synchronisation. |
| Local inference with cloud review for 5% uncertain cases | Usually below ₹10 in model calls, plus backend | Approximately ₹100–₹1,000 in model calls, plus backend | Retains local processing for most inspections. |
| OpenAI Decisions for every inspection | Approximately ₹10–₹50, plus backend | Approximately ₹1,000–₹5,000, plus backend | Simple typed outputs, but images are processed outside the device. |
| Jev vision for every inspection | Expected to be in a similar low-cost range; provider must be fixed first | Expected to remain in the low-thousands range or below, plus backend | Vision support, pricing and hosting conditions vary by provider and version. |
| Continuously running cloud GPU | Not required for the prototype | Commonly tens of thousands of rupees | Justified only by sustained server-side workloads. |

Continuous streaming is not recommended. A 2 Mbps stream running for eight hours a day and 22 days a month produces roughly 158 GB of data per operator before protocol overhead. Event-based still-image capture reduces this by orders of magnitude.

## 5. Jev and OpenAI Decisions as fast decision models

Jev and the OpenAI Decisions API can be evaluated as cloud challengers to the local PatchCore pipeline. They are designed to return constrained decisions rather than long generated responses.

Jev is TypeSafe AI's System One decision model. It supports decision forms such as yes/no probability, selection from fixed choices and numerical scoring. Jev 1.14 documentation also describes experimental PNG/JPEG input and bounding-box output. Because vision availability and pricing differ across hosts and versions, the exact endpoint should be confirmed before reporting final latency or cost.

OpenAI Decisions is a separate beta endpoint at `POST /v1/decisions`, powered by `gpt-6-luna`. It accepts text and images and can return a predicate probability, a fixed choice or a rubric score. The documented price is $0.10 per million input tokens with no output-token fee.

| Component | Proposed role | Current recommendation |
|---|---|---|
| PatchCore / VisureX | Part-specific anomaly detection learned from normal samples | Primary local baseline |
| Frame-quality model | Reject blurred, reflective, distant or badly angled captures | Include in the first mobile prototype |
| Jev vision | Fast cloud decision for defect presence, class or severity | Evaluate after confirming the vision endpoint and provider |
| OpenAI Decisions | Fast image predicates, choices and scores | Benchmark as a cloud challenger |

These services may accelerate a general demonstration because they do not require a separate PatchCore model for every part. However, they cannot be assumed to recognise small scratches, manufacturing tolerances or uncommon surface defects reliably. Their outputs must be evaluated on the same labelled images used for VisureX.

The safest hybrid design is:

**local VisureX inference → confidence check → Jev or OpenAI review for uncertain cases → human review for safety-critical cases**

The comparison should use the same image set and report AUROC, precision, recall, latency and cost for each method.

References: [Jev documentation](https://jevmodel.org/docs/), [Cloudflare Jev model listing](https://developers.cloudflare.com/ai/models/typesafe/jev/), [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions) and [OpenAI Decisions API reference](https://developers.openai.com/api/reference/resources/decisions/methods/create).

## 6. Immediate work plan

| Phase | Work | Output |
|---|---|---|
| 1. Detector validation | Run the same single-backbone pipeline on carpet and transistor or metal nut. | Three-category feasibility result with leakage checks and comparable metrics. |
| 2. Cloud comparison | Evaluate Jev vision and OpenAI Decisions on the same test images using fixed questions for defect presence, type and severity. | Accuracy, latency and cost comparison. |
| 3. Mobile integration | Use Meta's Mock Device Kit to connect the Android application, capture a frame, call a placeholder detector and return an audio response. | End-to-end glasses interaction prototype. |
| 4. Edge inference | Export the detector to an Android-compatible runtime and measure latency, memory and battery use. | Phone-side performance report and model-selection decision. |
| 5. Controlled hardware test | Test one component with fixed capture instructions using the actual glasses. | Failure analysis for blur, angle, distance, lighting and glare. |
| 6. Final benchmark | Run all 15 MVTec AD categories and the required backbone ablations on GPU. | Thesis and paper-quality benchmark evidence. |

This plan allows the glasses interface and detector validation to progress together. It keeps the immediate demonstration achievable while reserving broader performance claims for the complete benchmark and controlled hardware evaluation.
