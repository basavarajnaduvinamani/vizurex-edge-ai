"""Fix each model's display scale using only its normal validation images."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import CATEGORIES, MODEL_ROOT, CALIBRATION_ROOT, model_identity
from patchcore.patchcore import PatchCore
from patchcore.common import FaissNN
from patchcore.datasets.mvtec import MVTecDataset, DatasetSplit
import numpy as np
import torch


def main():
    torch.set_num_threads(4)
    CALIBRATION_ROOT.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        folder = MODEL_ROOT / category / 'evaluation/models' / ('mvtec_' + category)
        detector = PatchCore(torch.device('cpu'))
        detector.load_from_path(str(folder), torch.device('cpu'), FaissNN(False, 4))
        validation = MVTecDataset(str(ROOT / 'data/raw/mvtec_ad'), category,
                                  split=DatasetSplit.VAL, train_val_split=0.8)
        maps, manifest = [], {}
        for item in validation:
            _, prediction = detector.predict(item['image'].unsqueeze(0))
            maps.append(np.asarray(prediction[0], dtype=np.float32).ravel())
            path = Path(item['image_path'])
            manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        upper = float(np.percentile(np.concatenate(maps), 99))
        if not np.isfinite(upper) or upper <= 0:
            raise ValueError('Invalid normal-validation heatmap bound')
        result = {'category': category, 'model_sha256': model_identity(folder),
                  'method': 'normal-validation-pixel-p99', 'lower': 0.0, 'upper': upper,
                  'validation_images': len(validation), 'validation_manifest': manifest,
                  'note': 'Display scaling only, not a pixel decision threshold or probability.'}
        (CALIBRATION_ROOT / f'{category}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f'{category}: normal validation n={len(validation)}, fixed upper={upper:.6f}', flush=True)


if __name__ == '__main__':
    main()
