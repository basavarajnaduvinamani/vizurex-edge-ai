# S4: frozen shipped-model ONNX check

Portable wrapper around WCTE's inherited PatchCore. Warm preprocessed model calls only; portable Torch and ONNX return raw maps; shipped Torch returns smoothed maps. Not device or end-to-end timing.

Source: `S4_RESULTS/summary.json`.

| Category | Images | Max score delta | Decisions agreeing | Portable Torch p50 / p95 ms | ONNX p50 / p95 ms | Shipped Torch, smoothed map p50 / p95 ms |
|---|---:|---:|---:|---|---|---|
| bottle | 83 | 2.8133392333984375e-05 | 83 | 289.93820000323467 / 320.8238000050187 | 167.85349999554455 / 179.12230999500025 | 261.6678000049433 / 287.3957700023311 |
| grid | 78 | 4.6253204345703125e-05 | 78 | 294.00644999259384 / 309.3592149911273 | 166.9164000049932 / 176.40402999604703 | 264.3440499959979 / 279.6354650039575 |
| transistor | 100 | 4.696846008300781e-05 | 100 | 293.79665000305977 / 404.47088500295644 | 163.3739999961108 / 200.3312449916848 | 266.88280000234954 / 301.661059998878 |

DINOv2 export and INT8 quantisation were not executed. The serving app was not changed to ONNX; this is an export/parity/timing candidate. Physical-device testing remains pending.
