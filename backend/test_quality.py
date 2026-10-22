"""Capture rejection must never turn into a fabricated GOOD decision."""
import io
import tempfile
from pathlib import Path
from unittest import TestCase
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app
from backend.quality import assess_capture


class MustNotInfer:
    def inspect(self, *args):
        raise AssertionError('Rejected capture reached the detector')


class QualityTests(TestCase):
    def test_dark_and_white_capture(self):
        for value in (0, 255):
            self.assertFalse(assess_capture(Image.new('RGB', (256, 256), (value,) * 3))['passed'])

    def test_retake_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(MustNotInfer(), Path(folder) / 'audit.jsonl'),
                            base_url='http://localhost:8000') as client:
                stream = io.BytesIO()
                Image.new('RGB', (256, 256), 'black').save(stream, format='PNG')
                response = client.post('/api/inspect', data={'category': 'bottle', 'quality_mode': 'quality_gated'},
                                       files={'image': ('capture.png', stream.getvalue(), 'image/png')})
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                self.assertEqual(result['decision'], 'RETAKE')
                self.assertNotIn('anomaly_score', result)
                self.assertNotIn('images', result)
                self.assertTrue(result['quality']['reasons'])

    def test_invalid_mode(self):
        with TestClient(create_app(MustNotInfer()), base_url='http://localhost:8000') as client:
            response = client.post('/api/inspect', data={'category': 'bottle', 'quality_mode': 'unknown'},
                                   files={'image': ('capture.png', b'invalid', 'image/png')})
            self.assertEqual(response.status_code, 400)
