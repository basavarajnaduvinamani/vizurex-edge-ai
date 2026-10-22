"""Fixed synthetic capture stress test. Never substitutes for factory validation.

Uses every available held-out test image, unchanged anomaly threshold and a
predefined capture policy. Rejected defects are counted explicitly, not hidden.
"""
import csv
import json
from pathlib import Path
import sys
from collections import defaultdict
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import Registry, CATEGORIES
from backend.quality import assess_capture, POLICY_VERSION


def main():
    registry = Registry(bundle_root=ROOT / 'artifacts/model-bundles')
    transforms = {'original': lambda im: im,
                  'blur_radius_5': lambda im: im.filter(ImageFilter.GaussianBlur(5)),
                  'brightness_0.08': lambda im: ImageEnhance.Brightness(im).enhance(0.08),
                  'brightness_4': lambda im: ImageEnhance.Brightness(im).enhance(4)}
    counts = defaultdict(lambda: dict(total=0, defects=0, accepted=0, accepted_defects=0,
                                     accepted_true_positive=0, accepted_false_positive=0,
                                     rejected_defects=0, baseline_true_positive=0,
                                     baseline_false_positive=0))
    output = ROOT / 'artifacts/phase3/capture-stress'
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'per_image.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['category', 'image', 'condition', 'is_defect',
                                'score', 'threshold', 'baseline_decision', 'capture_accepted', 'reasons'])
        writer.writeheader()
        for category in CATEGORIES:
            root = ROOT / 'data/raw/mvtec_ad' / category / 'test'
            for path in sorted(root.glob('*/*.png')):
                defect = path.parent.name != 'good'
                with Image.open(path) as source:
                    original = source.convert('RGB')
                for condition, transform in transforms.items():
                    image = transform(original)
                    quality = assess_capture(image)
                    result = registry.inspect(category, image)
                    positive = result['decision'] == 'ANOMALY'
                    accepted = quality['passed']
                    row = counts[(category, condition)]
                    row['total'] += 1
                    row['defects'] += int(defect)
                    row['accepted'] += int(accepted)
                    row['accepted_defects'] += int(accepted and defect)
                    row['accepted_true_positive'] += int(accepted and defect and positive)
                    row['accepted_false_positive'] += int(accepted and not defect and positive)
                    row['rejected_defects'] += int(not accepted and defect)
                    row['baseline_true_positive'] += int(defect and positive)
                    row['baseline_false_positive'] += int(not defect and positive)
                    writer.writerow(dict(category=category, image=path.relative_to(root).as_posix(),
                        condition=condition, is_defect=defect, score=result['anomaly_score'],
                        threshold=result['threshold'], baseline_decision=result['decision'],
                        capture_accepted=accepted, reasons=' | '.join(quality['reasons'])))
            print('Stress test finished:', category, flush=True)
            registry.cache.clear()
    summary = []
    for (category, condition), row in counts.items():
        summary.append(dict(category=category, condition=condition, **row,
            coverage=row['accepted'] / row['total'],
            accepted_defect_recall=(row['accepted_true_positive'] / row['accepted_defects'])
                if row['accepted_defects'] else None,
            end_to_end_defect_detection_rate=row['accepted_true_positive'] / row['defects']))
    (output / 'summary.json').write_text(json.dumps({'policy': POLICY_VERSION,
        'scope': 'Synthetic corruptions of MVTec test images; no factory/glasses claims.',
        'conditions_fixed_before_run': list(transforms), 'results': summary}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
