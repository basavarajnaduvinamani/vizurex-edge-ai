"""Evaluate only freshly generated maps; preserve definitions and provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from upgrade_metrics import pixel_metrics

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--stages',nargs='+',required=True)
    args=p.parse_args();result=[]
    out=ROOT/'results/2026-10-30/step3'
    out.mkdir(parents=True,exist_ok=True)
    for stage in args.stages:
        for summary_path in sorted((ROOT/'results/2026-10-30'/stage).glob('*/summary.json')):
            summary=json.loads(summary_path.read_text())
            maps_path=ROOT/summary['maps_path']
            if hashlib.sha256(maps_path.read_bytes()).hexdigest()!=summary['maps_sha256']:
                raise ValueError('Map artifact hash mismatch')
            with np.load(maps_path) as data:
                metrics=pixel_metrics(data['masks'],data['maps'])
            row=dict(run=summary_path.parent.name,category=summary['category'],seed=summary['seed'],
                engine=summary['engine'],metrics=metrics,map_sha256=summary['maps_sha256'],
                run_provenance=str(summary_path.relative_to(ROOT)),
                execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                command=__import__('sys').argv)
            result.append(row)
            (out/(summary_path.parent.name+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
            (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(row),flush=True)
    aggregates={}
    for category in sorted({r['category'] for r in result}):
        current=[r for r in result if r['category']==category and r['engine']=='current']
        aggregates[category]={metric:dict(mean=float(np.mean([r['metrics'][metric] for r in current])),
            std_sample=float(np.std([r['metrics'][metric] for r in current],ddof=1)) if len(current)>1 else None,
            seeds=[r['seed'] for r in current]) for metric in ['pixel_auroc','aupro_fpr_0_3']}
    (out/'aggregate.json').write_text(json.dumps(aggregates,indent=2),encoding='utf-8')


if __name__=='__main__':main()
