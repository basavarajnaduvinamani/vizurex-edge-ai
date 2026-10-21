"""Inference for trusted local MVTec models, with benchmark preprocessing.

This is not the inherited industrial multi-view preprocessing pipeline.
"""
import argparse
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--resize', type=int, default=256)
    parser.add_argument('--imagesize', type=int, default=224)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    import numpy as np
    import torch
    import psutil
    from PIL import Image
    from torchvision import transforms
    from patchcore.patchcore import PatchCore
    from patchcore.common import FaissNN
    torch.set_num_threads(4)
    detector = PatchCore(torch.device('cpu'))
    detector.load_from_path(str(args.model), torch.device('cpu'), FaissNN(False, 4))
    if tuple(detector.input_shape) != (3, args.imagesize, args.imagesize):
        raise ValueError('Image size does not match the saved model input shape')
    stats = np.load(args.model / 'score_stats.npy', allow_pickle=True).item()
    transform = transforms.Compose([
        transforms.Resize(args.resize), transforms.CenterCrop(args.imagesize),
        transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    with Image.open(args.image) as image:
        batch = transform(image.convert('RGB')).unsqueeze(0)
    begin = time.perf_counter()
    scores, _ = detector.predict(batch)
    elapsed = time.perf_counter() - begin
    score = float(scores[0])
    memory = psutil.Process().memory_info()
    print(json.dumps({'image': str(args.image), 'score': score,
        'threshold': float(stats['pc_threshold']),
        'decision': 'ANOMALY' if score >= stats['pc_threshold'] else 'GOOD',
        'model_inference_seconds': elapsed, 'device': 'cpu',
        'process_rss_bytes': memory.rss,
        'process_peak_working_set_bytes': getattr(memory, 'peak_wset', None),
        'note': 'Anomaly score is not a calibrated probability. Excludes model load, image decode and transport.'}))


if __name__ == '__main__':
    main()
