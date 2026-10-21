"""Run isolated single-backbone feasibility tests and verify model round-trips."""
import argparse
import csv
import json
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--categories', nargs='+', default=['bottle', 'grid', 'transistor'])
    parser.add_argument('--output', type=Path, default=Path('artifacts/phase1-20261021/runs'))
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'src'))
    import numpy as np
    import psutil
    import torch
    from sklearn.metrics import roc_auc_score, average_precision_score, confusion_matrix
    from patchcore.common import FaissNN
    from patchcore.patchcore import PatchCore
    from patchcore.datasets.mvtec import MVTecDataset, DatasetSplit

    torch.set_num_threads(4)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'environment.json').write_text(json.dumps({
        'python': sys.version, 'executable': sys.executable,
        'packages': {name: importlib.metadata.version(name) for name in
                     ('torch', 'torchvision', 'numpy', 'faiss-cpu', 'timm',
                      'scikit-learn', 'Pillow', 'psutil')},
    }, indent=2), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(root / 'src'), OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
    summary = []
    for category in args.categories:
        run_dir = output / category
        run_dir.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        if not args.verify_only:
            # The inherited runner overwrites files in its output folder; each
            # category and rerun therefore needs its own new directory.
            if (run_dir / 'evaluation').exists():
                raise FileExistsError(f'Refusing to overwrite existing run: {run_dir}')
            command = [sys.executable, '-c',
                'import torch,runpy; torch.set_num_threads(4); runpy.run_path("bin/run_patchcore1.py",run_name="__main__")',
                '--seed', '0', '--log_project', 'evaluation', '--save_patchcore_model', str(run_dir),
                'patch_core', '-b', 'wideresnet50', '-le', 'layer2', '-le', 'layer3',
                '--pretrain_embed_dimension', '1024', '--target_embed_dimension', '384',
                '--anomaly_scorer_num_nn', '1', '--patchsize', '3',
                'sampler', '-p', '0.01', 'approx_greedy_coreset', 'dataset',
                '--train_val_split', '0.8', '--batch_size', '1', '--num_workers', '0',
                '--resize', '256', '--imagesize', '224', '-d', category,
                'mvtec', str(root / 'data/raw/mvtec_ad')]
            (run_dir / 'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
            with (run_dir / 'training.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
                peak = 0
                while process.poll() is None:
                    try:
                        parent = psutil.Process(process.pid)
                        processes = [parent] + parent.children(recursive=True)
                        peak = max(peak, sum(p.memory_info().rss for p in processes))
                    except psutil.Error:
                        pass
                    time.sleep(0.5)
                if process.returncode:
                    raise RuntimeError(f'{category} failed; see {run_dir}/training.log')
            train_seconds = time.perf_counter() - start
            # A Windows venv launcher can hide its actual worker from process
            # enumeration. Do not report a tiny launcher RSS as training memory.
            if peak < 64 * 1024 * 1024:
                peak = None
        else:
            peak, train_seconds = None, None

        model_dir = run_dir / 'evaluation' / 'models' / ('mvtec_' + category)
        # Load only artifacts generated locally by this project, never an
        # untrusted downloaded pickle.
        stats = np.load(model_dir / 'score_stats.npy', allow_pickle=True).item()
        detector = PatchCore(torch.device('cpu'))
        detector.load_from_path(str(model_dir), torch.device('cpu'), FaissNN(False, 4))
        dataset = MVTecDataset(str(root / 'data/raw/mvtec_ad'), category, split=DatasetSplit.TEST)
        calibration = MVTecDataset(str(root / 'data/raw/mvtec_ad'), category,
            split=DatasetSplit.VAL, train_val_split=0.8)
        val_scores = []
        for item in calibration:
            score, _ = detector.predict(item['image'].unsqueeze(0))
            val_scores.append(float(score[0]))
        recalculated = float(np.percentile(val_scores, 99))
        threshold_error = abs(recalculated - float(stats['pc_threshold']))
        if threshold_error > 1e-4:
            raise AssertionError(f'Validation threshold round-trip mismatch: {threshold_error}')
        with (run_dir / 'evaluation' / f'mvtec_{category}_predictions.csv').open(newline='') as stream:
            previous = {row['Image']: row for row in csv.DictReader(stream)}
        scores, labels, durations, details = [], [], [], []
        for item in dataset:
            begin = time.perf_counter()
            score, mask = detector.predict(item['image'].unsqueeze(0))
            elapsed = time.perf_counter() - begin
            score = float(score[0])
            key = Path(item['image_path']).relative_to(root / 'data/raw/mvtec_ad' / category / 'test').as_posix()
            old = previous[key]
            predicted = score >= stats['pc_threshold']
            if abs(score - float(old['PC_Score'])) > 0.0002:
                raise AssertionError(f'Saved-model score mismatch: {key}')
            if predicted != (old['PC_Pred'] == 'ANOMALY'):
                raise AssertionError(f'Saved-model decision mismatch: {key}')
            if not np.isfinite(mask).all():
                raise AssertionError(f'Nonfinite anomaly map: {key}')
            scores.append(score); labels.append(item['is_anomaly']); durations.append(elapsed)
            details.append({'image': key, 'label': item['is_anomaly'], 'score': score,
                            'predicted': bool(predicted), 'inference_seconds': elapsed})
        tn, fp, fn, tp = confusion_matrix(labels, np.array(scores) >= stats['pc_threshold'], labels=[0, 1]).ravel()
        result = {'category': category, 'test_count': len(scores),
            'auroc': roc_auc_score(labels, scores), 'average_precision': average_precision_score(labels, scores),
            'tp': int(tp), 'fp': int(fp), 'tn': int(tn), 'fn': int(fn),
            'recall': float(tp / (tp + fn)), 'false_positive_rate': float(fp / (fp + tn)),
            'median_model_inference_seconds': float(np.median(durations)),
            'p95_model_inference_seconds': float(np.percentile(durations, 95)),
            'training_process_peak_rss_bytes': peak, 'training_and_evaluation_seconds': train_seconds,
            'artifact_bytes': sum(p.stat().st_size for p in model_dir.rglob('*') if p.is_file()),
            'saved_model_score_and_decision_parity': True, 'validation_threshold_error': threshold_error,
            'torch_threads': 4, 'device': 'cpu', 'backbone': 'wideresnet50', 'seed': 0}
        (run_dir / 'verification.json').write_text(json.dumps({'summary': result, 'predictions': details}, indent=2), encoding='utf-8')
        summary.append(result)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
