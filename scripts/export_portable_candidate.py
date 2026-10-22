"""Export and verify a portable model candidate; not mobile performance evidence."""
import argparse
import csv
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import Registry, TRANSFORM, CATEGORIES
from backend.bundles import RECIPE, file_sha
from backend.portable_model import PortablePatchCore


def main():
    import onnx
    import onnxruntime as ort
    ort.disable_telemetry_events()
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', choices=CATEGORIES, default='bottle')
    parser.add_argument('--version', default='v2')
    args = parser.parse_args()
    category = args.category
    if not args.version.isalnum():
        raise ValueError('Version must contain letters and digits only')
    output = ROOT / 'artifacts/portable-candidate' / args.version / category
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'detector.onnx'
    if destination.exists():
        raise FileExistsError('Existing candidate preserved; choose a new version before re-exporting')
    registry = Registry(bundle_root=ROOT / 'artifacts/model-bundles')
    detector, threshold, _, identity = registry._load(category)
    candidate = PortablePatchCore(detector).eval()
    sample = torch.zeros((1, 3, 224, 224))
    with torch.no_grad():
        reference = np.asarray(detector._embed(sample))
        portable = candidate.embed(sample).numpy()
    if not np.allclose(reference, portable, rtol=1e-4, atol=1e-5):
        raise ValueError('Tensor embedding parity failed before export')
    # Explicit legacy exporter for the pinned PyTorch 2.7 fixed-shape graph.
    torch.onnx.export(candidate, (sample,), str(destination), opset_version=17, dynamo=False,
                      input_names=['normalised_rgb'], output_names=['anomaly_score', 'patch_distances'])
    onnx.checker.check_model(str(destination))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(destination), sess_options=options, providers=['CPUExecutionProvider'])
    with (ROOT / f'artifacts/phase1-20261021/runs/{category}/evaluation/mvtec_{category}_predictions.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    errors, times, deltas = [], [], []
    for row in rows:
        with Image.open(ROOT / 'data/raw/mvtec_ad' / category / 'test' / row['Image']) as source:
            tensor = TRANSFORM(source.convert('RGB')).unsqueeze(0).numpy()
        start = time.perf_counter()
        score, patches = session.run(None, {'normalised_rgb': tensor})
        times.append((time.perf_counter() - start) * 1000)
        value = float(score[0])
        delta = abs(value - float(row['PC_Score']))
        deltas.append(delta)
        decision = 'ANOMALY' if value >= threshold else 'GOOD'
        if delta > 0.001 or decision != row['PC_Pred'] or not np.isfinite(patches).all():
            errors.append({'image': row['Image'], 'delta': delta, 'decision': decision})
    record = {'category': category, 'source_model_sha256': identity, 'preprocessing': RECIPE,
        'model_sha256': file_sha(destination), 'bytes': destination.stat().st_size,
        'input': 'float32 [1,3,224,224], preprocessed externally exactly as the reference',
        'threshold': threshold, 'images_checked': len(rows), 'max_score_delta': max(deltas),
        'failures': errors, 'mean_laptop_ort_ms': float(np.mean(times)),
        'scope': 'Portable CPU graph candidate. Not tested on Android/iOS; no mobile performance claim.',
        'outputs': 'normalised image score; raw squared-distance 28x28 map, not a probability or final smoothed overlay'}
    (output / 'verification.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2), flush=True)
    if errors:
        raise SystemExit('Portable candidate parity failed; do not deploy')


if __name__ == '__main__':
    main()
