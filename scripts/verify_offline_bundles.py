"""Verify every held-out prediction against Phase 1 with downloads prohibited."""
import csv
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from backend.engine import Registry, CATEGORIES


def main():
    registry = Registry(bundle_root=ROOT / 'artifacts/model-bundles')
    evidence = []
    with patch('torch.hub.download_url_to_file', side_effect=AssertionError('Offline model attempted a download')):
        for category in CATEGORIES:
            predictions = ROOT / f'artifacts/phase1-20261021/runs/{category}/evaluation/mvtec_{category}_predictions.csv'
            with predictions.open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            errors, durations = [], []
            for row in rows:
                path = ROOT / 'data/raw/mvtec_ad' / category / 'test' / row['Image']
                with Image.open(path) as source:
                    result = registry.inspect(category, source.convert('RGB'))
                delta = abs(result['anomaly_score'] - float(row['PC_Score']))
                if delta > 0.0002 or result['decision'] != row['PC_Pred']:
                    errors.append({'image': row['Image'], 'delta': delta})
                durations.append(result['model_inference_ms'])
            evidence.append({'category': category, 'images': len(rows), 'failures': errors,
                             'mean_inference_ms': sum(durations) / len(durations)})
            print(category, len(rows), 'checked;', len(errors), 'failures', flush=True)
            registry.cache.clear()
    output = ROOT / 'artifacts/phase3/offline_parity.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    if any(item['failures'] for item in evidence):
        raise SystemExit('Offline parity failed')


if __name__ == '__main__':
    main()
