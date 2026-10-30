"""Audit all split pairs from immutable per-run input manifests."""
import argparse
import json
import hashlib
from itertools import combinations
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--stages',nargs='+',required=True)
    args=p.parse_args();records=[]
    for stage in args.stages:
        for path in sorted((ROOT/'results/2026-10-30'/stage).glob('*/dataset_manifest.json')):
            data=json.loads(path.read_text())
            pairs={}
            for a,b in combinations(['train','validation','test'],2):
                left={r['sha256'] for r in data[a]};right={r['sha256'] for r in data[b]}
                pairs[a+'__'+b]=sorted(left & right)
            records.append(dict(source=str(path.relative_to(ROOT)),overlapping_sha256=pairs))
    intake=json.loads((ROOT/'results/2026-10-30/step2-intake/source.json').read_text())
    verification=[]
    for item in intake['files']:
        path=ROOT/'data/raw/mvtec_ad'/item['path']
        actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        verification.append(dict(path=item['path'],sha256=actual,expected_sha256=item.get('lfs',{}).get('oid'),
                                 matched=actual is not None and actual==item.get('lfs',{}).get('oid')))
    result=dict(command=[sys.executable,*sys.argv],
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        records=records,exact_overlap_pairs=sum(bool(v) for r in records for v in r['overlapping_sha256'].values()),
        pinned_download_verification=verification,verified_files=sum(r['matched'] for r in verification),
        hash_mismatches=[r['path'] for r in verification if not r['matched']],
        limitation='Exact file hashes only; physical-part, acquisition-session and near-duplicate independence UNKNOWN.')
    target=ROOT/'results/2026-10-30/step2-split-audit.json'
    if target.exists():raise FileExistsError('Preserve earlier audit')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
