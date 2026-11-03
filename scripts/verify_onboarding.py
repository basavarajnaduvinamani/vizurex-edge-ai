"""Independent Python score/parity and timing analysis on generated samples.

Uses browser-decoded pixels explicitly; does not claim decoder equivalence.
AnomalyDINO: https://arxiv.org/abs/2405.14529 . PatchCore: 2106.08265.
"""
import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
import torch
import timm
from safetensors.torch import load_file
from scipy.stats import beta
from timm.models.vision_transformer import checkpoint_filter_fn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from visurex_fewshot.detector import KShotPatchNN, DetectorConfig


def main():
    folder = ROOT / 'artifacts/onboarding/verification'
    browser = json.loads((folder / 'browser.json').read_text())
    pixels = browser['snapshot']['pixels']
    frozen = browser['snapshot']['frozen']
    intake = json.loads((ROOT / 'artifacts/finish-fewshot/model-intake.json').read_text())
    entry = next(x for x in intake['weights'] if x['path'].endswith('.safetensors'))
    checkpoint = ROOT / entry['path']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == entry['sha256']
    model = timm.create_model('vit_small_patch14_dinov2.lvd142m', pretrained=False,
                              img_size=224, num_classes=0)
    model.load_state_dict(checkpoint_filter_fn(load_file(str(checkpoint)), model))
    model.eval(); torch.set_num_threads(4)
    mean = np.array([.485, .456, .406], dtype=np.float32)[:, None, None]
    std = np.array([.229, .224, .225], dtype=np.float32)[:, None, None]
    cache = {}
    decode_deltas = []

    def embed(key):
        if key in cache:
            return cache[key]
        image = Image.open(io.BytesIO(base64.b64decode(pixels[key].split(',')[1]))).convert('RGB')
        array = np.asarray(image).transpose(2, 0, 1).astype(np.float32) / 255
        tensor = torch.from_numpy((array - mean) / std).unsqueeze(0)
        with torch.no_grad():
            features = model.forward_features(tensor)[:, 1:, :].numpy()
        cache[key] = features
        # Separately report browser-vs-PIL preprocessing on the original sample.
        source = ROOT / 'artifacts/onboarding/assets' / key
        if source.exists():
            original = Image.open(source).convert('RGB')
            scale = 256 / min(original.size)
            w, h = (int(x * scale) for x in original.size)
            resized = original.resize((w, h), Image.Resampling.BILINEAR)
            left, top = round((w - 224) / 2), round((h - 224) / 2)
            pil = np.asarray(resized.crop((left, top, left + 224, top + 224)))
            decode_deltas.append(float(np.abs(pil.astype(float) - np.asarray(image)).max()))
        return features

    bank = np.concatenate([embed(key) for key in frozen['referenceIds']])
    detector = KShotPatchNN(DetectorConfig(), num_workers=4).fit(bank, (16, 16))
    cal = [float(detector.predict(embed(key))[0][0]) for key in frozen['calibrationIds']]
    threshold = float(np.quantile(cal, .99))
    rows = []
    for item in browser['measured']:
        score = float(detector.predict(embed(item['source']))[0][0])
        decision = 'ANOMALY' if score >= threshold else 'GOOD'
        rows.append(dict(source=item['source'], label=item['label'], python_score=score,
                         browser_score=item['score'], delta=abs(score - item['score']),
                         python_decision=decision, browser_decision=item['decision'],
                         same=decision == item['decision'], latency_ms=item['latencyMs'],
                         embed_ms=item['embedMs']))
    n = len(rows); agree = sum(x['same'] for x in rows)
    lo = 0 if agree == 0 else float(beta.ppf(.025, agree, n - agree + 1))
    hi = 1 if agree == n else float(beta.ppf(.975, agree + 1, n - agree))
    rng = np.random.default_rng(20261104)
    times = np.array([r['latency_ms'] for r in rows])
    bootstrap = rng.choice(times, size=(10000, n), replace=True)
    timing = {}
    for name, q in [('p50', .5), ('p95', .95)]:
        timing[name] = dict(ms=float(np.quantile(times, q)),
                            ci95=np.quantile(np.quantile(bootstrap, q, axis=1), [.025, .975]).tolist())
    max_delta = max(r['delta'] for r in rows)
    result = dict(date='2026-11-04', n=n, agreeing=agree,
                  agreement_ci95= [lo, hi], interval='Clopper-Pearson; generated pairs are not independent factory trials',
                  max_score_delta=max_delta, python_threshold=threshold,
                  browser_threshold=frozen['threshold'], threshold_delta=abs(threshold-frozen['threshold']),
                  passed=agree == n and max_delta <= .001,
                  preprocessing_scope='Python receives identical browser-decoded/cropped RGB pixels. Numerical normalization differs only by float evaluation. Not decoder parity.',
                  browser_vs_pil_max_pixel_delta=max(decode_deltas),
                  timing=timing, timing_scope='20 warm generated checks; decode, preprocessing, capture check, encoder and score; not model download/onboarding or device population',
                  model=json.loads((ROOT / 'artifacts/onboarding/assets/model.json').read_text()),
                  browser=browser['browser'], provider=browser['provider'], threads=browser['threads'],
                  checks=browser['checks'], page_errors=browser['errors'], external_requests=browser['external'],
                  generated_false_alarms=sum(r['browser_decision']=='ANOMALY' and r['label']=='normal' for r in rows),
                  generated_missed_changes=sum(r['browser_decision']=='GOOD' and r['label']=='scratch' for r in rows),
                  rows=rows)
    target = ROOT / 'docs/step1'
    target.mkdir(exist_ok=True)
    (target / 'browser_parity.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
    if not result['passed']:
        raise SystemExit('Browser parity gate failed; no release')


if __name__ == '__main__':
    main()
