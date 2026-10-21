"""Download only grid and transistor from a public MVTec AD mirror, no tokens."""
import concurrent.futures
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'foersben/mvtec-ad'


def get_json(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return json.load(response)


def main():
    # Resolve a fixed dataset commit, and retain file sizes for resumability.
    revision = get_json('https://huggingface.co/api/datasets/' + REPO)['sha']
    entries = []
    for category in ('grid', 'transistor'):
        url = f'https://huggingface.co/api/datasets/{REPO}/tree/{revision}/{category}?recursive=true&limit=1000'
        data = get_json(url)
        entries.extend(e for e in data if e['type'] == 'file')
    target = ROOT / 'data/raw/mvtec_ad'
    manifest = {'repo': REPO, 'revision': revision, 'files': entries}
    evidence = ROOT / 'artifacts/phase1-20261021'
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / 'download_source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'{len(entries)} files, {sum(e["size"] for e in entries)/1e6:.1f} MB; revision={revision}', flush=True)

    def download(entry):
        path = target / entry['path']
        if path.exists() and path.stat().st_size == entry['size']:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://huggingface.co/datasets/{REPO}/resolve/{revision}/{entry["path"]}'
        last = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as response:
                    content = response.read()
                if len(content) != entry['size']:
                    raise ValueError('Download size mismatch: ' + entry['path'])
                path.write_bytes(content)
                return
            except Exception as exc:
                last = exc
        raise last

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for index, _ in enumerate(pool.map(download, entries), 1):
            if index % 50 == 0:
                print(f'{index}/{len(entries)} files completed', flush=True)
    print('Download complete.', flush=True)


if __name__ == '__main__':
    main()
