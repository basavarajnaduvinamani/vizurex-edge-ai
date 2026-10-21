"""Trusted local model registry and benchmark-matched image processing."""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
import time

import numpy as np
from PIL import Image, ImageOps
import torch
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from patchcore.common import FaissNN
from patchcore.patchcore import PatchCore

CATEGORIES = ('bottle', 'grid', 'transistor')
MODEL_ROOT = ROOT / 'artifacts/phase1-20261021/runs'
CALIBRATION_ROOT = ROOT / 'artifacts/phase2/heatmaps'
IMAGE_SIZE = 224
RESIZE = 256
TRANSFORM = transforms.Compose([
    transforms.Resize(RESIZE), transforms.CenterCrop(IMAGE_SIZE), transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
DISPLAY_TRANSFORM = transforms.Compose([transforms.Resize(RESIZE), transforms.CenterCrop(IMAGE_SIZE)])


def model_identity(path):
    digest = hashlib.sha256()
    for name in ('patchcore_params.pkl', 'nnscorer_search_index.faiss', 'score_stats.npy'):
        digest.update(name.encode())
        digest.update((path / name).read_bytes())
    return digest.hexdigest()


def png_url(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode('ascii')


def render_maps(image, raw_map, upper):
    """A fixed model-specific scale; never uses this request's extrema."""
    scaled = np.clip(np.asarray(raw_map, dtype=np.float32) / upper, 0, 1)
    # Blue -> cyan -> yellow -> red, fixed for every image of the same model.
    stops = np.array([[20, 45, 100], [0, 170, 210], [255, 210, 55], [220, 35, 40]], dtype=float)
    positions = np.linspace(0, 1, len(stops))
    colours = np.stack([np.interp(scaled, positions, stops[:, c]) for c in range(3)], axis=-1).astype('uint8')
    heatmap = Image.fromarray(colours)
    processed = DISPLAY_TRANSFORM(image)
    overlay = Image.blend(processed, heatmap, 0.45)
    return {'processed': png_url(processed), 'heatmap': png_url(heatmap), 'overlay': png_url(overlay)}


class Registry:
    def __init__(self, model_root=MODEL_ROOT, calibration_root=CALIBRATION_ROOT):
        self.model_root = Path(model_root)
        self.calibration_root = Path(calibration_root)
        self.lock = threading.Lock()
        self.cache = {}
        torch.set_num_threads(4)

    def folder(self, category):
        if category not in CATEGORIES:
            raise ValueError('Unsupported category')
        return self.model_root / category / 'evaluation/models' / ('mvtec_' + category)

    def available(self):
        return [{'category': category,
                 'artifacts_present': all((self.folder(category) / name).is_file() for name in
                    ('patchcore_params.pkl', 'nnscorer_search_index.faiss', 'score_stats.npy')),
                 'heatmap_calibration_present': (self.calibration_root / f'{category}.json').is_file(),
                 'loaded': category in self.cache} for category in CATEGORIES]

    def _load(self, category):
        if category not in self.cache:
            folder = self.folder(category)
            identity = model_identity(folder)
            calibration = json.loads((self.calibration_root / f'{category}.json').read_text())
            if calibration['model_sha256'] != identity:
                raise ValueError('Heatmap calibration does not match model')
            upper = float(calibration['upper'])
            if not np.isfinite(upper) or upper <= 0:
                raise ValueError('Invalid heatmap calibration')
            detector = PatchCore(torch.device('cpu'))
            # These artifacts are trusted, locally generated Phase 1 outputs.
            # No upload or request can supply a pickle or model path.
            detector.load_from_path(str(folder), torch.device('cpu'), FaissNN(False, 4))
            if tuple(detector.input_shape) != (3, IMAGE_SIZE, IMAGE_SIZE):
                raise ValueError('Unexpected model shape')
            stats = np.load(folder / 'score_stats.npy', allow_pickle=True).item()
            threshold = float(stats['pc_threshold'])
            if not np.isfinite(threshold):
                raise ValueError('Invalid decision threshold')
            self.cache[category] = detector, threshold, upper, identity
        return self.cache[category]

    def inspect(self, category, image):
        with self.lock:
            cold = category not in self.cache
            detector, threshold, upper, identity = self._load(category)
            batch = TRANSFORM(image).unsqueeze(0)
            start = time.perf_counter()
            scores, maps = detector.predict(batch)
            inference_ms = (time.perf_counter() - start) * 1000
            score = float(scores[0])
            if not np.isfinite(score) or not np.isfinite(maps[0]).all():
                raise ValueError('Nonfinite model output')
            images = render_maps(image, maps[0], upper)
            return {'category': category, 'decision': 'ANOMALY' if score >= threshold else 'GOOD',
                    'anomaly_score': score, 'threshold': threshold,
                    'model_version': f'phase1-{category}-{identity[:12]}', 'cold_start': cold,
                    'model_inference_ms': inference_ms, 'images': images,
                    'heatmap_scale': {'lower': 0.0, 'upper': upper,
                        'method': 'normal-validation-pixel-p99', 'is_probability': False},
                    'preprocessing': {'resize_short_edge': RESIZE, 'center_crop': IMAGE_SIZE,
                        'display_region': 'processed image and overlays show only the centre crop'}}
