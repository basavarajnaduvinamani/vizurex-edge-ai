"""Pinned, resumable public benchmark intake; never commits image data."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REVISION='c75b39616f84db43677bcc8228caaafaf5096d7f'
REPO='foersben/mvtec-ad'
CATEGORIES=['bottle','cable','capsule','carpet','grid','hazelnut','leather','metal_nut',
            'pill','screw','tile','toothbrush','transistor','wood','zipper']


def get(url):
    with urllib.request.urlopen(url,timeout=120) as r:return json.load(r)


def main():
    p=argparse.ArgumentParser();p.add_argument('--categories',nargs='+',default=CATEGORIES)
    args=p.parse_args();evidence=ROOT/'results/2026-10-30/step2-intake'
    evidence.mkdir(parents=True,exist_ok=True)
    entries=[]
    for category in args.categories:
        # MVTec categories have fewer than 1,000 entries each; explicit pagination
        # is nevertheless required to avoid mistaking an incomplete page for all data.
        url=f'https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/{category}?recursive=true&limit=1000'
        while url:
            with urllib.request.urlopen(url,timeout=120) as r:
                page=json.load(r);link=r.headers.get('Link','')
            entries.extend(x for x in page if x['type']=='file' and x['path'].endswith('.png'))
            import re
            match=re.search(r'<([^>]+)>; rel="next"',link)
            url=match.group(1) if match else None
    missing=[e for e in entries if not (ROOT/'data/raw/mvtec_ad'/e['path']).exists()]
    manifest=dict(repository=REPO,revision=REVISION,categories=args.categories,files=entries,
        requested_bytes=sum(e['size'] for e in missing),free_bytes=shutil.disk_usage(ROOT).free,
        licence='CC BY-NC-SA 4.0; non-commercial research only',
        licence_source='https://www.mvtec.com/research-teaching/datasets/mvtec-ad')
    (evidence/'source.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if manifest['requested_bytes']>manifest['free_bytes']:
        raise OSError('Insufficient free disk space for requested bytes')
    print(json.dumps(dict(files=len(entries),missing_files=len(missing),requested_bytes=manifest['requested_bytes'])),flush=True)
    def fetch(e):
        dest=ROOT/'data/raw/mvtec_ad'/e['path']
        if dest.exists():
            if dest.stat().st_size!=e['size']:raise ValueError('Existing size mismatch; not overwriting '+str(dest))
            return
        dest.parent.mkdir(parents=True,exist_ok=True);temporary=dest.with_suffix('.download-part')
        for attempt in range(3):
            try:
                with urllib.request.urlopen(f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{e["path"]}',timeout=120) as r:
                    content=r.read()
                if len(content)!=e['size']:raise ValueError('download size mismatch')
                if e.get('lfs',{}).get('oid') and hashlib.sha256(content).hexdigest()!=e['lfs']['oid']:
                    raise ValueError('LFS sha256 mismatch')
                temporary.write_bytes(content);temporary.replace(dest);return
            except Exception:
                if attempt==2:raise
                time.sleep(attempt+1)
    failures=[];done=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(fetch,e):e for e in entries}
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc:failures.append(dict(path=futures[future]['path'],error=str(exc)))
            done+=1
            if done%100==0:print(f'Completed {done}/{len(entries)}',flush=True)
    (evidence/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    print(json.dumps(dict(completed=done,failures=len(failures))),flush=True)
    if failures:raise RuntimeError('Dataset intake incomplete; inspect failures.json')


if __name__=='__main__':main()
