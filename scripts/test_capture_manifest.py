import csv
from pathlib import Path
import tempfile
from unittest import TestCase
from scripts.validate_capture_manifest import validate


class CaptureManifestTests(TestCase):
    def test_duplicates_and_group_leaks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, data in [('a.png', b'one'), ('b.png', b'two'), ('c.png', b'one')]:
                (root / name).write_bytes(data)
            manifest = root / 'manifest.csv'
            with manifest.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['path', 'product_id', 'part_id', 'session_id', 'split', 'label'])
                writer.writerows([
                    ['a.png', 'p', 'part1', 'day1', 'train', 'good'],
                    ['b.png', 'p', 'part1', 'day1', 'validation', 'good'],
                    ['c.png', 'p', 'part3', 'day3', 'test', 'anomaly']])
            errors = validate(manifest, root)['errors']
            self.assertTrue(any('physical part' in item for item in errors))
            self.assertTrue(any('capture session' in item for item in errors))
            self.assertTrue(any('exact duplicate' in item for item in errors))
