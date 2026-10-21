"""Read-only dataset/source audit; writes only the requested JSON report."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    upstream = root.parent / 'upstream' / 'VisureX'
    report = {'datasets': {}, 'source_comparison': {}, 'historical_predictions': {}}
    for category in sorted((root / 'data/raw/mvtec_ad').iterdir()):
        if not category.is_dir() or category.name.startswith('.'):
            continue
        train = sorted((category / 'train/good').glob('*.png'))
        test = sorted((category / 'test').rglob('*.png'))
        masks = sorted((category / 'ground_truth').rglob('*.png'))
        train_hashes = {sha(p) for p in train}
        missing_masks = []
        for p in test:
            if p.parent.name != 'good':
                mask = category / 'ground_truth' / p.parent.name / (p.stem + '_mask.png')
                if not mask.exists():
                    missing_masks.append(str(p.relative_to(category)))
        report['datasets'][category.name] = {
            'train_good': len(train), 'test_good': sum(p.parent.name == 'good' for p in test),
            'test_anomaly': sum(p.parent.name != 'good' for p in test), 'masks': len(masks),
            'exact_train_test_overlap': [str(p.relative_to(category)) for p in test if sha(p) in train_hashes],
            'missing_masks': missing_masks,
            'manifest': {str(p.relative_to(category)): sha(p) for p in train + test + masks},
        }
    for folder in ('src', 'bin'):
        for p in sorted((root / folder).rglob('*.py')):
            relative = p.relative_to(root)
            original = upstream / relative
            report['source_comparison'][relative.as_posix()] = (
                'identical' if original.exists() and sha(p) == sha(original)
                else 'modified' if original.exists() else 'development_only'
            )
    predictions = root / 'artifacts/smoke/mvtec-bottle-smoke/mvtec_bottle_predictions.csv'
    if predictions.exists():
        with predictions.open(newline='', encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        tp = sum(r['GT'] == 'ANOMALY' and r['Final_Pred'] == 'ANOMALY' for r in rows)
        fp = sum(r['GT'] == 'GOOD' and r['Final_Pred'] == 'ANOMALY' for r in rows)
        tn = sum(r['GT'] == 'GOOD' and r['Final_Pred'] == 'GOOD' for r in rows)
        fn = sum(r['GT'] == 'ANOMALY' and r['Final_Pred'] == 'GOOD' for r in rows)
        positive = [float(r['PC_Score']) for r in rows if r['GT'] == 'ANOMALY']
        negative = [float(r['PC_Score']) for r in rows if r['GT'] == 'GOOD']
        auc = sum((a > b) + 0.5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))
        report['historical_predictions'] = {
            'rows': len(rows), 'unique_image_ids': len({r['Image'] for r in rows}),
            'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'auroc_from_rounded_csv_scores': auc,
            'precision': tp / (tp + fp), 'recall': tp / (tp + fn),
            'f1': 2 * tp / (2 * tp + fp + fn), 'false_positive_rate': fp / (fp + tn),
            'review_flags': sum(r['Needs_Review'] == 'Yes' for r in rows),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({
        'datasets': {name: {k: v for k, v in data.items() if k != 'manifest'} for name, data in report['datasets'].items()},
        'historical_predictions': report['historical_predictions'],
        'modified_sources': [k for k, v in report['source_comparison'].items() if v != 'identical'],
    }, indent=2))


if __name__ == '__main__':
    main()
