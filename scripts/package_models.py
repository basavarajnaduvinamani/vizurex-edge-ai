"""Package trusted local Phase 1 outputs and backbone weights for offline use."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import Registry, CATEGORIES, model_identity, CALIBRATION_ROOT
from backend.bundles import RECIPE, file_sha, validate_bundle
import torch


def state_fingerprint(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/model-bundles')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Choose a new empty output directory; never overwrite a bundle or partial bundle')
    registry = Registry()
    catalog = {'format_version': 1, 'categories': [], 'scope': 'MVTec benchmark models only'}
    weight_hash = None
    backbone_fingerprint = None
    for category in CATEGORIES:
        model, threshold, _, _ = registry._load(category)
        fingerprint = state_fingerprint(model.backbone)
        if backbone_fingerprint is not None and fingerprint != backbone_fingerprint:
            raise ValueError('Models do not share identical backbone weights; package separately')
        backbone_fingerprint = fingerprint
        target = output / 'models' / category
        target.mkdir(parents=True, exist_ok=True)
        weights = output / 'weights/wideresnet50.pt'
        weights.parent.mkdir(parents=True, exist_ok=True)
        if not weights.exists():
            torch.save(model.backbone.state_dict(), weights)
        if weight_hash is None:
            weight_hash = file_sha(weights)
        # All current models use the same pretrained backbone, with no updates.
        for name in ('patchcore_params.pkl', 'nnscorer_search_index.faiss', 'score_stats.npy'):
            shutil.copy2(registry.folder(category) / name, target / name)
        shutil.copy2(CALIBRATION_ROOT / f'{category}.json', target / 'heatmap.json')
        paths = [target / name for name in ('patchcore_params.pkl', 'nnscorer_search_index.faiss',
                                            'score_stats.npy', 'heatmap.json')] + [weights]
        manifest = {'format_version': 1, 'category': category, 'preprocessing': RECIPE,
            'source_model_sha256': model_identity(registry.folder(category)),
            'threshold': threshold, 'weights_file': 'weights/wideresnet50.pt',
            'backbone_state_sha256': backbone_fingerprint,
            'packages': {name: importlib.metadata.version(name) for name in
                         ('torch', 'torchvision', 'numpy', 'faiss-cpu', 'timm')},
            'files': {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size,
                      'sha256': weight_hash if p == weights else file_sha(p)} for p in paths},
            'trust': 'Locally generated trusted artifacts; checksums are not publisher signatures.'}
        (target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        validate_bundle(output, category)
        catalog['categories'].append(category)
        del model
        registry.cache.clear()
        print(f'Packaged and checked {category}', flush=True)
    (output / 'catalog.json').write_text(json.dumps(catalog, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
