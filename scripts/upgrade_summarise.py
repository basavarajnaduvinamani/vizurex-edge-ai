"""Aggregate only completed new-session runs; no rounding or silent failures."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--stages',nargs='+',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args();rows=[];comparisons=[]
    for stage in args.stages:
        failures=ROOT/'results/2026-10-30'/stage/'failures.json'
        excluded={r['run'] for r in json.loads(failures.read_text())} if failures.exists() else set()
        for path in sorted((ROOT/'results/2026-10-30'/stage).glob('*/summary.json')):
            if path.parent.name in excluded:continue
            s=json.loads(path.read_text());s['source']=str(path.relative_to(ROOT));rows.append(s)
            geo=path.parent/'geometry.json'
            if geo.exists():
                scores=json.loads(geo.read_text())['fused_scores']
                baseline=list(csv.DictReader((path.parent/'predictions.csv').open()))
                with (path.parent/'geometry_predictions.csv').open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=['image','label','score','predicted'])
                    w.writeheader();w.writerows(dict(image=r['image'],label=r['label'],score=score,
                        predicted=int(score>=1.0)) for r,score in zip(baseline,scores))
    aggregates={}
    for category in sorted({r['category'] for r in rows}):
        current=[r for r in rows if r['category']==category and r['engine']=='current']
        if not current:continue
        seeds=[r['seed'] for r in current]
        if len(seeds)!=len(set(seeds)):raise ValueError('Duplicate category/seed would double-count evidence')
        aggregates[category]=dict(seeds=seeds,
            metrics={key:dict(mean=float(np.mean([r['metrics'][key] for r in current])),
                std_sample=float(np.std([r['metrics'][key] for r in current],ddof=1)) if len(current)>1 else None)
                for key in ['image_auroc','f1','missed_defects','false_alarms']})
        for ref in [r for r in rows if r['category']==category and r['engine']=='official']:
            match=[r for r in current if r['seed']==ref['seed']]
            if match:
                a=list(csv.DictReader((ROOT/ref['source']).parent.joinpath('predictions.csv').open()))
                b=list(csv.DictReader((ROOT/match[0]['source']).parent.joinpath('predictions.csv').open()))
                if [r['image'] for r in a]!=[r['image'] for r in b]:raise ValueError('Comparison order mismatch')
                comparisons.append(dict(category=category,seed=ref['seed'],
                    matched_predictions=sum(x['predicted']==y['predicted'] for x,y in zip(a,b)),
                    total=len(a),max_score_delta=max(abs(float(x['score'])-float(y['score'])) for x,y in zip(a,b)),
                    official=ref['source'],current=match[0]['source']))
    output=ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True)
    result=dict(command=[sys.executable,*sys.argv],execution_commit=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),runs=rows,
        aggregates=aggregates,official_current_comparisons=comparisons,
        std_definition='sample standard deviation, ddof=1, same fixed split, seed changes sampling only; null for one seed')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(aggregates=aggregates,official_current_comparisons=comparisons)),flush=True)


if __name__=='__main__':main()
