"""Portable local model bundle validation. Hashes are integrity, not signatures."""
import hashlib
import json
from pathlib import Path

RECIPE = {'resize_short_edge': 256, 'center_crop': 224, 'colour': 'RGB',
          'mean': [0.485, 0.456, 0.406], 'std': [0.229, 0.224, 0.225],
          'backbone_weights': 'Wide_ResNet50_2_Weights.IMAGENET1K_V1'}


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def checked_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Bundle path escapes configured root')
    return path


def validate_bundle(root, category):
    if category not in ('bottle', 'grid', 'transistor'):
        raise ValueError('Unsupported bundle category')
    root = Path(root).resolve()
    manifest = json.loads((root / 'models' / category / 'manifest.json').read_text())
    if manifest.get('format_version') != 1 or manifest.get('category') != category:
        raise ValueError('Invalid bundle identity')
    if manifest.get('preprocessing') != RECIPE:
        raise ValueError('Unsupported preprocessing recipe')
    required = {f'models/{category}/{name}' for name in (
        'patchcore_params.pkl', 'nnscorer_search_index.faiss', 'score_stats.npy', 'heatmap.json')}
    if not isinstance(manifest.get('weights_file'), str) or not isinstance(manifest.get('files'), dict):
        raise ValueError('Malformed model bundle manifest')
    required.add(manifest['weights_file'])
    if not required.issubset(manifest['files']):
        raise ValueError('Incomplete model bundle')
    for relative, info in manifest['files'].items():
        if not isinstance(info, dict) or not isinstance(info.get('bytes'), int) or not isinstance(info.get('sha256'), str):
            raise ValueError('Malformed file integrity entry')
        path = checked_path(root, relative)
        if path.stat().st_size != info['bytes'] or file_sha(path) != info['sha256']:
            raise ValueError('Model bundle checksum mismatch: ' + relative)
    return manifest
