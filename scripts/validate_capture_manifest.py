"""Check operator-labelled real capture splits before training/evaluation.

CSV columns: path,product_id,part_id,session_id,split,label
Images remain local. Do not infer group IDs or labels from filenames.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def validate(manifest, image_root):
    image_root = Path(image_root).resolve()
    with Path(manifest).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'path', 'product_id', 'part_id', 'session_id', 'split', 'label'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Missing required columns: ' + ', '.join(sorted(required)))
        rows = list(reader)
    if not rows:
        raise ValueError('Manifest is empty')
    errors, hashes, part_splits, session_splits = [], {}, {}, {}
    totals = {}
    for number, row in enumerate(rows, 2):
        if any(not row.get(key, '').strip() for key in required):
            errors.append(f'Row {number}: required value missing')
            continue
        split, label = row['split'], row['label']
        if split not in ('train', 'validation', 'test') or label not in ('good', 'anomaly'):
            errors.append(f'Row {number}: invalid split or label')
        if split == 'train' and label != 'good':
            errors.append(f'Row {number}: anomaly cannot enter normal-only training')
        path = (image_root / row['path']).resolve()
        if not path.is_relative_to(image_root) or not path.is_file():
            errors.append(f'Row {number}: image missing or outside dataset root')
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            errors.append(f'Row {number}: exact duplicate of row {hashes[digest][0]} ({hashes[digest][1]})')
        else:
            hashes[digest] = (number, split)
        for groups, identity, name in (
                (part_splits, (row['product_id'], row['part_id']), 'physical part'),
                (session_splits, (row['product_id'], row['session_id']), 'capture session')):
            previous = groups.setdefault(identity, split)
            if previous != split:
                errors.append(f'Row {number}: {name} crosses splits')
        totals[split + '/' + label] = totals.get(split + '/' + label, 0) + 1
    for split in ('train', 'validation', 'test'):
        if not any(row['split'] == split for row in rows):
            errors.append(f'Missing {split} split')
    return {'images': len(rows), 'counts': totals, 'errors': errors,
            'limitation': 'Exact hashing cannot rule out near-duplicates or incorrect operator group labels.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('image_root', type=Path)
    args = parser.parse_args()
    report = validate(args.manifest, args.image_root)
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report['errors']))
