"""Inventory, checkpoint and run only missing frozen v2 configurations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = 'bottle cable capsule carpet grid hazelnut leather metal_nut pill screw tile toothbrush transistor wood zipper'.split()
METHODS = ['patchcore_wrn50', 'dinov2_vits14']
SHOTS = ['1', '2', '4', '8', '16', 'full']
OUTPUT = ROOT / 'artifacts/sprint-2026-11-01/breadth'
DOCS = ROOT / 'docs/sprint'
OLD = ROOT / 'artifacts/fewshot-run1/results.json'


def inventory():
    rows = []
    for source in [OLD, ROOT/'artifacts/fewshot-masked-run1/results.json', ROOT/'artifacts/fewshot-smoke/results.json']:
        data = json.loads(source.read_text(encoding='utf-8'))
        for r in data['runs']:
            rows.append(dict(category=r['category'], method=r['method'], k=r['k'], seed=r['seed'],
                             source=str(source.relative_to(ROOT)),
                             reusable_for_s2=source == OLD and r['method'] in METHODS))
    # Different full-data harness: retain inventory, never substitute its scores.
    for source in (ROOT/'results/2026-10-30').rglob('summary.json'):
        if not source.parent.name.endswith('_current'):
            continue
        parts = source.parent.name.rsplit('_seed', 1)
        if len(parts) != 2 or parts[0] not in CATEGORIES:
            continue
        record = json.loads(source.read_text(encoding='utf-8'))
        if not record:
            continue
        rows.append(dict(category=parts[0], method='separate_baseline_harness', k='full',
                         seed=int(parts[1].split('_')[0]), source=str(source.relative_to(ROOT)),
                         reusable_for_s2=False))
    payload = dict(created_utc=datetime.now(timezone.utc).isoformat(), records=rows,
                   reuse_source=str(OLD.relative_to(ROOT)),
                   missing=[dict(category=c, method=m, k=k, seed=s)
                            for c in CATEGORIES for m in METHODS for k in SHOTS for s in [0,1,2]
                            if not any(r['reusable_for_s2'] and (r['category'],r['method'],str(r['k']),r['seed']) == (c,m,k,s) for r in rows)])
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS/'S2_INVENTORY.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    text = '# S2 existing-results inventory\n\nGenerated from existing results; configuration rows are in `S2_INVENTORY.json`.\n\n'
    text += '| Category | Matching few-shot records reused | Missing v2 records | Other existing evidence |\n|---|---:|---:|---|\n'
    for c in CATEGORIES:
        valid = [r for r in rows if r['category']==c and r['reusable_for_s2']]
        other = sorted(set(r['source'] for r in rows if r['category']==c and not r['reusable_for_s2']))
        text += f"| {c} | {len(valid)} | {sum(r['category']==c for r in payload['missing'])} | {'; '.join(other)} |\n"
    text += '\nOnly the matching primary few-shot source is reused. Masked, smoke and separate full-data baseline results are listed but not substituted. Paths and every method/k/seed are in the JSON.\n'
    (DOCS/'S2_INVENTORY.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(reuse=sum(r['reusable_for_s2'] for r in rows),missing=len(payload['missing']))))
    return payload


def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if (OUTPUT/'work-plan.json').exists():
        raise FileExistsError('Preserve previous work plan; recovery needs a fresh attempt')
    commands=[]
    for c in CATEGORIES:
        command=[sys.executable,str(ROOT/'scripts/run_fewshot.py'),'--data-root','data/raw/mvtec_ad',
                 '--categories',c,'--full-shot-all-seeds','--output',str(OUTPUT/c)]
        if c in ['bottle','grid','transistor']:
            command += ['--reuse-results',str(OLD)]
        commands.append(dict(category=c,command=command))
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),commands=commands,
              protocol_sha256=hashlib.sha256((ROOT/'docs/FEWSHOT_PROTOCOL_v2.md').read_bytes()).hexdigest())
    (OUTPUT/'work-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    completed=[]
    for entry in commands:
        command=[sys.executable,str(ROOT/'scripts/record_run.py'),'--record-dir',str(OUTPUT/('run-'+entry['category'])),'--',*entry['command']]
        result=subprocess.run(command,cwd=ROOT)
        completed.append(dict(category=entry['category'],exit_status=result.returncode))
        (OUTPUT/'progress.json').write_text(json.dumps(completed,indent=2),encoding='utf-8')
        if result.returncode:
            raise SystemExit(result.returncode)
    subprocess.run([sys.executable,str(ROOT/'scripts/sprint_analysis.py')],cwd=ROOT,check=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.run:run()
    else:inventory()
