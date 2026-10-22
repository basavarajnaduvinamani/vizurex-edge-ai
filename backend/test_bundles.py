"""Small synthetic bundle fixtures: no trained models or downloads required."""
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from backend.bundles import checked_path, file_sha, RECIPE, validate_bundle


class BundleTests(TestCase):
    def test_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                checked_path(root, '../not-a-model')

    def test_integrity_and_recipe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / 'models/bottle'
            model.mkdir(parents=True)
            paths = ['models/bottle/' + name for name in (
                'patchcore_params.pkl', 'nnscorer_search_index.faiss', 'score_stats.npy', 'heatmap.json')]
            paths.append('weights.pt')
            for name in paths:
                (root / name).write_bytes(b'synthetic fixture; never deserialize')
            manifest = {'format_version': 1, 'category': 'bottle', 'preprocessing': RECIPE,
                        'weights_file': 'weights.pt',
                        'files': {name: {'bytes': (root / name).stat().st_size,
                                         'sha256': file_sha(root / name)} for name in paths}}
            file = model / 'manifest.json'
            file.write_text(json.dumps(manifest))
            validate_bundle(root, 'bottle')
            (root / 'weights.pt').write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                validate_bundle(root, 'bottle')
            manifest['preprocessing'] = {}
            file.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate_bundle(root, 'bottle')
