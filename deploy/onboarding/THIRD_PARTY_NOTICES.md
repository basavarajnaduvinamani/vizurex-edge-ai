# Third-party components

The DINOv2 checkpoint is independently pretrained, distributed under
Apache License 2.0 by Meta Platforms, Inc. and affiliates. This export changes
the graph format and input resolution; it is not the original checkpoint.
Source: https://github.com/facebookresearch/dinov2
License text: `licenses/DINOv2-Apache-2.0.txt`.

ONNX Runtime Web is Copyright (c) Microsoft Corporation, MIT licensed.
Source: https://github.com/microsoft/onnxruntime
License text: `licenses/ONNX-Runtime-MIT.txt`.

Generated example drawings originate from this project's S5 drawing function,
not a benchmark dataset. No MVTec AD imagery is included.

MediaPipe Tasks Vision 1.2.2 and BlazeFace short-range model are used only for
on-device photo redaction. No face embeddings or unredacted photos are stored.
Source: https://github.com/google-ai-edge/mediapipe (Apache-2.0).
Model: https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite
If detection cannot run, the entire image is obscured before local persistence.
This precaution is not a guarantee that every face will be detected.

Method attribution: AnomalyDINO (Damm et al., WACV 2025):
https://arxiv.org/abs/2405.14529 and https://github.com/dammsi/AnomalyDINO .
PatchCore (Roth et al., CVPR 2022): https://arxiv.org/abs/2106.08265 .
