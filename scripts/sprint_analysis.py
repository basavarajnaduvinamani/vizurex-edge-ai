"""Generate the frozen S2 summary without tuning any experiment setting."""
from collections import defaultdict
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
TEXTURES={'carpet','grid','leather','tile','wood'}
METHODS=['dinov2_vits14','patchcore_wrn50']
SHOTS=['1','2','4','8','16','full']


def category_bootstrap(values):
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('Bootstrap requires finite category means')
    indices=np.random.default_rng(20261101).integers(len(values),size=(10000,len(values)))
    samples=values[indices].mean(axis=1)
    return dict(mean=float(values.mean()),ci95=[float(x) for x in np.quantile(samples,[.025,.975])],
                sampling_unit='category',replicates=10000,seed=20261101)


def summarize(records):
    grouped=defaultdict(list)
    for r in records:
        grouped[(r['category'],r['method'],str(r['k']))].append(r)
    categories=sorted({r['category'] for r in records})
    if len(categories)!=15:
        raise ValueError('Incomplete breadth: need all 15 categories')
    points=[]
    for c in categories:
        for m in METHODS:
            for k in SHOTS:
                runs=grouped[(c,m,k)]
                if sorted(r['seed'] for r in runs)!=[0,1,2]:
                    raise ValueError('Incomplete or duplicate seeds: '+str((c,m,k)))
                point=dict(category=c,group='texture' if c in TEXTURES else 'object',method=m,k=k)
                for key in ['image_auroc','defect_recall','false_alarm_rate','pixel_auroc','pixel_aupro']:
                    values=np.array([r[key] for r in runs],dtype=float)
                    if not np.isfinite(values).all():raise ValueError('Missing/nonfinite metric '+key)
                    point[key]=dict(mean=float(values.mean()),std=float(values.std(ddof=0)))
                points.append(point)
    macro=[]
    for group in ['all','texture','object']:
        subset=[c for c in categories if group=='all' or (c in TEXTURES)==(group=='texture')]
        for m in METHODS:
            for k in SHOTS:
                values=[next(p['image_auroc']['mean'] for p in points if (p['category'],p['method'],p['k'])==(c,m,k)) for c in subset]
                macro.append(dict(group=group,method=m,k=k,categories=subset,**category_bootstrap(values)))
    h2=[]
    for c in categories:
        a,b=[next(p['image_auroc'] for p in points if (p['category'],p['method'],p['k'])==(c,m,'full')) for m in METHODS]
        spread=max(a['std'],b['std']);tolerance=spread if spread>0 else .01
        delta=a['mean']-b['mean']
        h2.append(dict(category=c,dinov2_minus_patchcore=delta,tolerance=tolerance,
                       met=bool(abs(delta)<=tolerance)))
    practical={m:[k for k in SHOTS[:4] if all(p['image_auroc']['mean']>=.95 and p['false_alarm_rate']['mean']<=.10
                                               for p in points if p['method']==m and p['k']==k)] for m in METHODS}
    return dict(category_results=points,macro=macro,h2=dict(verdict='met' if all(x['met'] for x in h2) else 'not met',categories=h2),
                practical_qualifying_budgets=practical,
                warning='Category-bootstrap uncertainty on this fixed benchmark; no factory/onboarding claim. V1 primary results were previously inspected.')


def main():
    from sprint_breadth import CATEGORIES,OUTPUT
    records=[];sources=[]
    for c in CATEGORIES:
        path=OUTPUT/c/'results.json'
        payload=json.loads(path.read_text(encoding='utf-8'))
        if not payload['dataset_checks'] or not all(x['passed'] for x in payload['dataset_checks']):
            raise ValueError('Dataset validation failed: '+c)
        for r in payload['runs']:
            row=dict(r);row['result_source']=str(path.relative_to(ROOT));records.append(row)
        sources.append(str(path.relative_to(ROOT)))
    result=summarize(records)
    result.update(protocol='docs/FEWSHOT_PROTOCOL_v2.md',sources=sources,
                  configurations=len(records),reused=sum('reused_from' in r for r in records))
    target=ROOT/'docs/sprint/S2_RESULTS'
    target.mkdir(parents=True,exist_ok=True)
    (target/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (target/'per_seed.csv').open('w',newline='',encoding='utf-8') as stream:
        fields=['category','method','k','seed','image_auroc','defect_recall','false_alarm_rate','pixel_auroc','pixel_aupro','result_source']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    lines=['# S2: all-category few-shot results','',result['warning'],'',
           'Source: `S2_RESULTS/summary.json`; every configuration: `S2_RESULTS/per_seed.csv`.','',
           '| Group | Method | k | Macro AUROC | Category-bootstrap 95% interval |',
           '|---|---|---|---:|---|']
    for r in result['macro']:
        lines.append(f"| {r['group']} | {r['method']} | {r['k']} | {r['mean']} | {r['ci95']} |")
    lines += ['', '## Per-category results','',
              '| Category | Method | k | AUROC mean | Population seed SD |',
              '|---|---|---|---:|---:|']
    for p in result['category_results']:
        lines.append(f"| {p['category']} | {p['method']} | {p['k']} | {p['image_auroc']['mean']} | {p['image_auroc']['std']} |")
    lines += ['', 'H2 verdict: '+result['h2']['verdict'],
              'Practical qualifying budgets: '+json.dumps(result['practical_qualifying_budgets']),
              'Original H1 finding remains in docs/results/FEWSHOT_2026-10-30/criteria.md.']
    (ROOT/'docs/sprint/S2_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(configurations=len(records),h2=result['h2']['verdict'])))


if __name__=='__main__':main()
