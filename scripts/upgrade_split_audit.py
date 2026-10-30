"""Audit all split pairs from immutable per-run input manifests."""
import argparse
import json
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
    result=dict(command=[sys.executable,*sys.argv],
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        records=records,exact_overlap_pairs=sum(bool(v) for r in records for v in r['overlapping_sha256'].values()),
        limitation='Exact file hashes only; physical-part, acquisition-session and near-duplicate independence UNKNOWN.')
    target=ROOT/'results/2026-10-30/step2-split-audit.json'
    if target.exists():raise FileExistsError('Preserve earlier audit')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
