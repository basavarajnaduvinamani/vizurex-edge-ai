"""Create private model-import ZIPs only from parity-verified candidates."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.bundles import file_sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', choices=('bottle', 'grid', 'transistor'), required=True)
    parser.add_argument('--version', default='v2')
    args = parser.parse_args()
    if not args.version.isalnum():
        raise ValueError('Version must contain letters and digits only')
    root = ROOT / 'artifacts/portable-candidate' / args.version / args.category
    record = json.loads((root / 'verification.json').read_text())
    if record['failures'] or record['images_checked'] < 1:
        raise ValueError('Candidate verification must pass before packaging')
    model = root / 'detector.onnx'
    if file_sha(model) != record['model_sha256'] or model.stat().st_size != record['bytes']:
        raise ValueError('Candidate was changed after verification')
    record['format_version'] = 1
    destination = root / f'visurex-{args.category}-mobile.zip'
    if destination.exists():
        raise FileExistsError('Existing mobile bundle preserved')
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        archive.write(model, 'detector.onnx')
        archive.writestr('manifest.json', json.dumps(record, indent=2))
    print(f'Created {destination} ({destination.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
