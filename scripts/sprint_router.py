"""One registered normal-only selector; selection precedes test-metric access."""
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from sprint_analysis import category_bootstrap
from sprint_breadth import CATEGORIES,SHOTS,OUTPUT,ROOT


def dispersion(scores):
    values=np.asarray(scores,dtype=float)
    if values.ndim!=1 or len(values)<2 or not np.isfinite(values).all() or (values<0).any():
        raise ValueError('Need finite nonnegative normal validation scores')
    median=float(np.median(values))
    return float((np.quantile(values,.99)-median)/(abs(median)+1e-12))


def choose(normal_scores):
    stats={m:dispersion(normal_scores[m]) for m in ['patchcore_wrn50','dinov2_vits14']}
    return min(stats,key=stats.get),stats


def main():
    private=ROOT/'artifacts/sprint-2026-11-01/router'
    private.mkdir(parents=True,exist_ok=True)
    choice_path=private/'choices.json'
    if choice_path.exists():raise FileExistsError('Preserve prior router analysis')
    choices=[]
    for c in CATEGORIES:
        for k in SHOTS:
            for seed in [0,1,2]:
                scores={};sources={}
                for m in ['patchcore_wrn50','dinov2_vits14']:
                    path=OUTPUT/c/'predictions'/f'{c}__{m}__k{k}__seed{seed}_calibration.json'
                    value=json.loads(path.read_text())
                    scores[m]=value['validation_scores']
                    sources[m]=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                method,stats=choose(scores)
                choices.append(dict(category=c,k=k,seed=seed,method=method,normal_dispersion=stats,sources=sources))
    choice_payload=dict(selection_completed_utc=datetime.now(timezone.utc).isoformat(),
                        input='Normal calibration sidecars only; test metric CSV not opened yet',choices=choices)
    choice_path.write_text(json.dumps(choice_payload,indent=2),encoding='utf-8')
    # Test outcomes enter only after the complete selection manifest is saved.
    source=ROOT/'docs/sprint/S2_RESULTS/per_seed.csv'
    with source.open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    lookup={(r['category'],r['method'],r['k'],int(r['seed'])):float(r['image_auroc']) for r in rows}
    outcomes=[]
    for r in choices:
        values={m:lookup[(r['category'],m,r['k'],r['seed'])] for m in ['dinov2_vits14','patchcore_wrn50']}
        outcomes.append(dict(category=r['category'],k=r['k'],seed=r['seed'],router=values[r['method']],
                             oracle=max(values.values()),**values))
    category=[];macro=[];contrasts=[]
    for k in SHOTS:
        for c in CATEGORIES:
            found=[r for r in outcomes if r['category']==c and r['k']==k]
            category.append(dict(category=c,k=k,choices=[r['method'] for r in choices if r['category']==c and r['k']==k],
                                 **{m:float(np.mean([r[m] for r in found])) for m in ['router','oracle','dinov2_vits14','patchcore_wrn50']}))
        for m in ['router','oracle','dinov2_vits14','patchcore_wrn50']:
            macro.append(dict(k=k,method=m,**category_bootstrap([r[m] for r in category if r['k']==k])))
        for m in ['dinov2_vits14','patchcore_wrn50']:
            contrasts.append(dict(k=k,contrast='router minus '+m,
                                  **category_bootstrap([r['router']-r[m] for r in category if r['k']==k])))
    summary=dict(protocol='docs/ROUTER_PROTOCOL_SPRINT.md',test_source=str(source.relative_to(ROOT)),
                 choices_source=str(choice_path.relative_to(ROOT)),macro=macro,paired_differences=contrasts,
                 per_category=category,
                 verdict='met' if all(r['ci95'][0]>0 for r in contrasts if r['k']=='8') else 'not met',
                 limitation='Previously inspected benchmark; fixed rule with no cross-category fitting. Oracle uses test labels and is not deployable.')
    target=ROOT/'docs/sprint/S3_RESULTS';target.mkdir(parents=True,exist_ok=True)
    (target/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (target/'choices.json').write_text(json.dumps(choice_payload,indent=2),encoding='utf-8')
    lines=['# S3: normal-only model selection','',
           'A selection experiment extending WCTE\'s inherited PatchCore comparison. '+summary['limitation'],'',
           'Source: `S3_RESULTS/summary.json`. Selection provenance: `S3_RESULTS/choices.json`.','',
           '| k | Method | Macro AUROC | Category-bootstrap 95% interval |','|---|---|---:|---|']
    for r in macro:lines.append(f"| {r['k']} | {r['method']} | {r['mean']} | {r['ci95']} |")
    lines += ['', '| k | Comparison | Mean difference | Paired 95% interval |','|---|---|---:|---|']
    for r in contrasts:lines.append(f"| {r['k']} | {r['contrast']} | {r['mean']} | {r['ci95']} |")
    lines += ['', 'Registered k=8 comparison criterion: '+summary['verdict'], '',
              '| Category at k=8 | Choices across seeds | Router | DINOv2 | PatchCore | Oracle |',
              '|---|---|---:|---:|---:|---:|']
    for r in category:
        if r['k']=='8':lines.append(f"| {r['category']} | {', '.join(r['choices'])} | {r['router']} | {r['dinov2_vits14']} | {r['patchcore_wrn50']} | {r['oracle']} |")
    (ROOT/'docs/sprint/S3_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['verdict','limitation']}))


if __name__=='__main__':main()
