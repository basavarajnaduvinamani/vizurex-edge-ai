"""Evaluate the pre-written success criteria from actual few-shot records."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from visurex_fewshot.report import summarize

CATEGORIES=['bottle','grid','transistor']
SHOTS=['1','2','4','8']


def evaluate(payload):
    rows={(r['category'],r['method'],r['k']):r for r in summarize(payload['runs'])}
    h1={};practical={};h2={}
    for category in CATEGORIES:
        comparisons={}
        for k in SHOTS:
            a=rows.get((category,'dinov2_vits14',k))
            b=rows.get((category,'patchcore_wrn50',k))
            complete=a is not None and b is not None and a['seeds']==[0,1,2] and b['seeds']==[0,1,2]
            if not complete:
                comparisons[k]=dict(verdict='inconclusive',reason='Missing expected method or seed')
                continue
            difference=a['image_auroc_mean']-b['image_auroc_mean']
            spread=max(a['image_auroc_std'],b['image_auroc_std'])
            comparisons[k]=dict(dinov2_mean=a['image_auroc_mean'],patchcore_mean=b['image_auroc_mean'],
                difference=difference,larger_seed_std=spread,verdict='met' if difference>spread else 'not met')
        verdicts=[r['verdict'] for r in comparisons.values()]
        h1[category]=dict(points=comparisons,verdict='met' if all(v=='met' for v in verdicts)
            else ('not met' if 'not met' in verdicts else 'inconclusive'))
    supported=sum(r['verdict']=='met' for r in h1.values())
    incomplete=any(r['verdict']=='inconclusive' for r in h1.values())
    h1_verdict='met' if supported>=2 else ('inconclusive' if incomplete else 'not met')
    for method in ['patchcore_wrn50','dinov2_vits14']:
        qualifying=[];points={};missing=False
        for k in SHOTS:
            point={}
            for category in CATEGORIES:
                row=rows.get((category,method,k))
                if row is None or row['seeds']!=[0,1,2]:
                    point[category]=dict(verdict='inconclusive');missing=True;continue
                point[category]=dict(image_auroc_mean=row['image_auroc_mean'],
                    false_alarm_rate_mean=row['false_alarm_rate_mean'],
                    verdict='met' if row['image_auroc_mean']>=0.95 and row['false_alarm_rate_mean']<=0.10 else 'not met')
            if all(r['verdict']=='met' for r in point.values()):qualifying.append(k)
            points[k]=point
        practical[method]=dict(qualifying_k=qualifying,points=points,
            verdict='met' if qualifying else ('inconclusive' if missing else 'not met'))
    for category in CATEGORIES:
        a=rows.get((category,'dinov2_vits14','full'));b=rows.get((category,'patchcore_wrn50','full'))
        if a is None or b is None:
            h2[category]=dict(verdict='inconclusive',reason='Missing full-shot result');continue
        difference=abs(a['image_auroc_mean']-b['image_auroc_mean'])
        h2[category]=dict(dinov2_mean=a['image_auroc_mean'],patchcore_mean=b['image_auroc_mean'],
            absolute_difference=difference,within_descriptive_0_01=difference<=0.01,
            full_shot_seeds=a['seeds'],verdict='inconclusive',
            reason='Protocol runs full once; seed spread is unavailable, not an observed zero standard deviation.')
    overall_practical='met' if any(r['verdict']=='met' for r in practical.values()) else (
        'inconclusive' if any(r['verdict']=='inconclusive' for r in practical.values()) else 'not met')
    return dict(h1=dict(verdict=h1_verdict,supported_categories=supported,categories=h1),
        practical=dict(verdict=overall_practical,methods=practical,
            interpretation='One shared k must meet the criterion in all primary categories; primary methods evaluated separately.'),
        h2=dict(verdict='inconclusive',categories=h2),
        standard_deviation='Population standard deviation (ddof=0), matching the pre-existing report.summarize implementation.',
        calibration_limitation='k references exclude extra held-out normal calibration images. No factory onboarding or worker-time experiment was performed.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    payload=json.loads(args.results.read_text(encoding='utf-8'))
    result=evaluate(payload)
    protocol=ROOT/'docs/FEWSHOT_PROTOCOL.md'
    result.update(source=str(args.results),source_sha256=hashlib.sha256(args.results.read_bytes()).hexdigest(),
                  protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),command=sys.argv)
    if args.output.exists():raise FileExistsError('Preserve earlier criterion evaluation')
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
