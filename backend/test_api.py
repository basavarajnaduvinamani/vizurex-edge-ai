"""API boundary tests. Fake inference is confined to tests, never app runtime."""
import io
import json
import tempfile
from pathlib import Path
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app, MAX_FILE_BYTES


def image_bytes(format='PNG', size=(32, 32)):
    stream = io.BytesIO()
    Image.new('RGB', size, 'grey').save(stream, format=format)
    return stream.getvalue()


class FakeRegistry:
    def available(self):
        return []

    def inspect(self, category, image):
        return {'category': category, 'decision': 'GOOD', 'anomaly_score': 0.2,
                'threshold': 1.0, 'model_version': 'TEST-ONLY', 'model_inference_ms': 1.0,
                'images': {}, 'cold_start': False}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name) / 'inspections.jsonl'
        self.client = TestClient(create_app(FakeRegistry(), self.log), base_url='http://localhost:8000')

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def request(self, content=None, category='bottle', **kwargs):
        return self.client.post('/api/inspect', data={'category': category},
            files={'image': ('private-filename.png', image_bytes() if content is None else content, 'image/png')}, **kwargs)

    def test_health(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)

    def test_real_contract_and_no_image_retention(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        record = json.loads(self.log.read_text())
        self.assertEqual(result['inspection_id'], record['inspection_id'])
        self.assertNotIn('images', record)
        self.assertNotIn('private-filename', self.log.read_text())
        self.assertIn('server_processing_ms', result['timing'])

    def test_invalid_category(self):
        self.assertEqual(self.request(category='../../anything').status_code, 400)

    def test_bad_image(self):
        self.assertEqual(self.request(b'not an image').status_code, 400)

    def test_empty(self):
        self.assertEqual(self.request(b'').status_code, 400)

    def test_gif_rejected(self):
        self.assertEqual(self.request(image_bytes('GIF')).status_code, 415)

    def test_oversize_body(self):
        self.assertEqual(self.request(b'x' * (MAX_FILE_BYTES + 100_000)).status_code, 413)

    def test_pixel_limit(self):
        self.assertEqual(self.request(image_bytes(size=(4001, 4000))).status_code, 413)

    def test_foreign_origin(self):
        self.assertEqual(self.request(headers={'Origin': 'https://untrusted.example'}).status_code, 403)

    def test_untrusted_host(self):
        self.assertEqual(self.client.get('/api/health', headers={'Host': 'untrusted.example'}).status_code, 400)

    def test_missing_image(self):
        self.assertEqual(self.client.post('/api/inspect', data={'category': 'bottle'}).status_code, 422)

    def test_repeated_requests_have_distinct_ids(self):
        self.assertNotEqual(self.request().json()['inspection_id'], self.request().json()['inspection_id'])


if __name__ == '__main__':
    unittest.main()
