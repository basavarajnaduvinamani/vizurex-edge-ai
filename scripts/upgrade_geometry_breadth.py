"""Seed-independent inherited radial branch, with verified vectorised sampling."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from upgrade_metrics import image_metrics

ROOT=Path(__file__).resolve().parents[1]


def radial_profile(gray, cy, cx, radius):
    angles=np.linspace(0,2*np.pi,360,endpoint=False)
    radii=np.arange(200,dtype=np.float64)/200*radius
    yi=np.rint(cy+np.sin(angles)[:,None]*radii).astype(np.int64)
    xi=np.rint(cx+np.cos(angles)[:,None]*radii).astype(np.int64)
    h,w=gray.shape
    valid=(yi>=0)&(yi<h)&(xi>=0)&(xi<w)
    values=gray[np.clip(yi,0,h-1),np.clip(xi,0,w-1)].astype(np.float64)
    count=valid.sum(axis=0)
    return np.divide((values*valid).sum(axis=0),count,
                     out=np.zeros(200,dtype=np.float64),where=count>0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--stages',nargs='+',required=True)
    args=p.parse_args();sys.path.insert(0,str(ROOT/'src'))
    spec=importlib.util.spec_from_file_location('inherited_geometry',ROOT/'bin/run_patchcore1.py')
    geo=importlib.util.module_from_spec(spec);spec.loader.exec_module(geo)
    original=geo._geo_radial_profile
    categories={}
    for stage in args.stages:
        for path in (ROOT/'results/2026-10-30'/stage).glob('*/summary.json'):
            row=json.loads(path.read_text())
            if row['engine']=='current':categories.setdefault(row['category'],[]).append(path)
    out=ROOT/'results/2026-10-30/step2-geometry';out.mkdir(parents=True,exist_ok=True)
    summaries=[];failures=[]
    for category,source_paths in sorted(categories.items()):
        try:
            base=ROOT/'data/raw/mvtec_ad'/category
            normals=sorted((base/'train/good').glob('*.png'));cut=int(len(normals)*0.8)
            train,val=normals[:cut],normals[cut:]
            geo._geo_radial_profile=original
            reference=[geo._get_profile(str(x)) for x in train[:5]]
            geo._geo_radial_profile=radial_profile
            fast=[geo._get_profile(str(x)) for x in train[:5]]
            parity=all(a is not None and b is not None and np.array_equal(a,b) for a,b in zip(reference,fast))
            if not parity:raise ValueError('Vectorised profile failed exact training-sample parity')
            def profiles(paths):
                values=[geo._get_profile(str(x)) for x in paths]
                if any(v is None for v in values):raise ValueError('Geometric profile unavailable')
                return np.array(values)
            tr=profiles(train);mean,std=tr.mean(0),tr.std(0)
            vals=[geo._profile_anomaly_score(x,mean,std) for x in profiles(val)]
            threshold=float(np.percentile(vals,99))
            if threshold<=0:raise ValueError('Degenerate geometric threshold')
            first=list(csv.DictReader(source_paths[0].with_name('predictions.csv').open()))
            image_keys=[r['image'] for r in first]
            test_scores=[geo._profile_anomaly_score(x,mean,std) for x in profiles([base/'test'/k for k in image_keys])]
            calibration=dict(category=category,training_mean=mean.tolist(),training_std=std.tolist(),
                validation_scores=vals,threshold=threshold,test_scores=test_scores,test_images=image_keys,
                train_manifest=[dict(image=str(x.relative_to(base)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in train],
                validation_manifest=[dict(image=str(x.relative_to(base)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in val],
                training_profile_parity=parity,parity_cases=len(reference),
                inherited_source_sha256=hashlib.sha256((ROOT/'bin/run_patchcore1.py').read_bytes()).hexdigest())
            (out/(category+'_calibration.json')).write_text(json.dumps(calibration,indent=2),encoding='utf-8')
            for source in sorted(source_paths):
                meta=json.loads(source.read_text())
                rows=list(csv.DictReader(source.with_name('predictions.csv').open()))
                if [r['image'] for r in rows]!=image_keys:raise ValueError('Test manifest order mismatch')
                fused=np.maximum(np.array([float(r['score']) for r in rows])/meta['metrics']['threshold'],
                                 np.array(test_scores)/threshold)
                result=dict(category=category,seed=meta['seed'],metrics=image_metrics(
                    [int(r['label']) for r in rows],fused,1.0),source=str(source.relative_to(ROOT)),
                    calibration_file=category+'_calibration.json',
                    execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    command=[sys.executable,*sys.argv],
                    scope='full inherited radial branch incl industrial preprocessing; validation-only threshold; no test tuning')
                key=f'{category}_seed{meta["seed"]}'
                (out/(key+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
                with (out/(key+'_predictions.csv')).open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=['image','label','score','predicted']);w.writeheader()
                    w.writerows(dict(image=r['image'],label=r['label'],score=float(score),predicted=int(score>=1.0))
                                for r,score in zip(rows,fused))
                summaries.append(result);print(json.dumps(result),flush=True)
        except Exception as exc:
            failures.append(dict(category=category,error=str(exc)))
        (out/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
        (out/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    aggregate={}
    for category in sorted(categories):
        rows=[r for r in summaries if r['category']==category]
        if rows:
            aggregate[category]=dict(seeds=[r['seed'] for r in rows],metrics={k:dict(
                mean=float(np.mean([r['metrics'][k] for r in rows])),
                std_sample=float(np.std([r['metrics'][k] for r in rows],ddof=1)) if len(rows)>1 else None)
                for k in ['image_auroc','f1','missed_defects','false_alarms']})
    (out/'aggregate.json').write_text(json.dumps(aggregate,indent=2),encoding='utf-8')


if __name__=='__main__':main()
