"""Integration tests using the real, locally trained Phase 1 models."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.engine import CATEGORIES, ROOT, Registry


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.registry = Registry()
        cls.client = TestClient(create_app(cls.registry, Path(cls.temp.name) / 'log.jsonl'),
                                base_url='http://localhost:8000')

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()

    def test_predictions_and_fixed_heatmaps(self):
        evidence = []
        for category in CATEGORIES:
            folder = ROOT / 'artifacts/phase1-20261021/runs' / category / 'evaluation'
            with (folder / f'mvtec_{category}_predictions.csv').open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            samples = [next(row for row in rows if row['GT'] == label) for label in ('GOOD', 'ANOMALY')]
            first = None
            for row in samples:
                path = ROOT / 'data/raw/mvtec_ad' / category / 'test' / row['Image']
                response = self.client.post('/api/inspect', data={'category': category},
                    files={'image': ('sample.png', path.read_bytes(), 'image/png')})
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result['decision'], row['PC_Pred'])
                self.assertAlmostEqual(result['anomaly_score'], float(row['PC_Score']), delta=0.0002)
                self.assertTrue(result['images']['overlay'].startswith('data:image/png;base64,'))
                self.assertFalse(result['heatmap_scale']['is_probability'])
                evidence.append({key: result[key] for key in ('category', 'decision', 'anomaly_score',
                                 'threshold', 'model_version', 'cold_start', 'timing')})
                if first is None:
                    first = (path, result)
            # Repeat the first image after an anomaly: its overlay must be identical.
            path, original = first
            repeated = self.client.post('/api/inspect', data={'category': category},
                files={'image': ('sample.png', path.read_bytes(), 'image/png')}).json()
            self.assertEqual(repeated['images'], original['images'])
            self.assertFalse(repeated['cold_start'])
        output = ROOT / 'artifacts/phase2/api_real_model_tests.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
