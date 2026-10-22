from pathlib import Path
import tempfile
from unittest import TestCase
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.network import NetworkPolicy
from backend.test_api import FakeRegistry, image_bytes

TEST_KEY = 'test-only-access-key-not-a-real-secret-123'


class NetworkTests(TestCase):
    def test_requires_private_address_and_key(self):
        for ip in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '169.254.1.2', '::1'):
            with self.assertRaises(ValueError):
                NetworkPolicy(ip, TEST_KEY)
        with self.assertRaises(ValueError):
            NetworkPolicy('192.168.1.4', 'short')

    def test_private_mode_auth_origin_and_host(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app(FakeRegistry(), Path(root) / 'log.jsonl', NetworkPolicy('192.168.1.4', TEST_KEY))
            with TestClient(app, base_url='http://192.168.1.4:8000') as client:
                self.assertEqual(client.get('/api/health').status_code, 200)
                self.assertEqual(client.get('/api/models').status_code, 401)
                self.assertEqual(client.get('/api/models', headers={'X-Visurex-Key': 'wrong'}).status_code, 401)
                self.assertEqual(client.get('/api/models', headers={'X-Visurex-Key': TEST_KEY}).status_code, 200)
                response = client.post('/api/inspect', data={'category': 'bottle'},
                    headers={'Origin': 'http://192.168.1.4:8000', 'X-Visurex-Key': TEST_KEY},
                    files={'image': ('capture.png', image_bytes(), 'image/png')})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn(TEST_KEY, (Path(root) / 'log.jsonl').read_text())
                response = client.post('/api/inspect', headers={'Origin': 'https://foreign.example', 'X-Visurex-Key': TEST_KEY})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(client.get('/api/health', headers={'Host': '192.168.1.9'}).status_code, 400)

    def test_preflight_and_no_query_key(self):
        with TestClient(create_app(FakeRegistry(), network_policy=NetworkPolicy('10.0.0.4', TEST_KEY)),
                        base_url='http://10.0.0.4:8000') as client:
            response = client.options('/api/inspect', headers={'Origin': 'http://10.0.0.4:8000',
                'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'X-Visurex-Key'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get('/api/models?key=' + TEST_KEY).status_code, 401)
