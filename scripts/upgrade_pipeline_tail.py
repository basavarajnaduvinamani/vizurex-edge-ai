"""Ordered post-benchmark analysis; checkpoint each step before starting another."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/2026-10-30'
REPORT = ROOT / '07_build_walmart.md'
ATTEMPT = 'initial'


def run(name, script, *args, allow_failure=False):
    command = ([sys.executable,'-m',script.split(':',1)[1],*args] if script.startswith('module:')
               else [sys.executable, str(ROOT / 'scripts' / script), *args])
    metadata = dict(command=command, started_at=datetime.now().astimezone().isoformat(),
                    execution_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    record = OUT / (name + '-' + ATTEMPT + '-execution.json')
    if record.exists():
        raise FileExistsError('Preserve earlier execution evidence: ' + str(record))
    record.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    with (OUT / (name + '-' + ATTEMPT + '-execution.log')).open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    metadata.update(returncode=result.returncode, finished_at=datetime.now().astimezone().isoformat())
    record.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    if result.returncode and not allow_failure:
        raise RuntimeError('Inspect execution log: ' + name)
    return 'results/2026-10-30/' + record.name


def append(lines):
    with REPORT.open('a', encoding='utf-8') as stream:
        stream.write('\n' + '\n'.join(lines) + '\n')


def main():
    global ATTEMPT
    p = argparse.ArgumentParser()
    p.add_argument('--stages', nargs='+', required=True)
    p.add_argument('--attempt',default='initial')
    args = p.parse_args()
    if not args.attempt.replace('-','').isalnum():raise ValueError('Use an alphanumeric attempt label')
    ATTEMPT=args.attempt
    if '## Step 2' in REPORT.read_text(encoding='utf-8'):
        raise ValueError('Step 2 already recorded; do not duplicate completed evidence')
    metric_validation=run('metric-validation','module:pytest','scripts/test_upgrade_metrics.py','-q',
                          '--junitxml=results/2026-10-30/metric-tests-'+ATTEMPT+'.xml')
    retry_seeds={}
    for stage in args.stages:
        failed=OUT/stage/'failures.json'
        for item in json.loads(failed.read_text()) if failed.exists() else []:
            if not item.get('blocked'):continue
            category,seed,engine=item['run'].rsplit('_',2)
            if engine=='current':retry_seeds.setdefault(category,set()).add(int(seed.removeprefix('seed')))
    # One retry for memory-terminated runs, with exactly the same seed/config/cap.
    # No completed metric is discarded or used to select which runs to retry.
    retry_executions=[]
    for category,seeds in sorted(retry_seeds.items()):
        stage='step2-resource-retry-'+category
        retry_executions.append(run(stage,'upgrade_execute.py','--stage',stage,
            '--categories',category,'--seeds',*[str(x) for x in sorted(seeds)],
            '--engines','current',allow_failure=True))
        args.stages.append(stage)
    integrity_execution = run('step2-split-audit', 'upgrade_split_audit.py', '--stages', *args.stages)
    geometry_execution = run('step2-geometry', 'upgrade_geometry_breadth.py', '--stages', *args.stages)
    summary_execution = run('step2-summary', 'upgrade_summarise.py', '--stages', *args.stages,
                            '--output', 'results/2026-10-30/step2-summary.json')
    path = 'results/2026-10-30/step2-summary.json'
    result = json.loads((ROOT / path).read_text())
    lines = ['## Step 2: breadth and seeds',
             'what was done: current-core category/seed results aggregated without rounding; inherited radial branch evaluated with training-only fit and normal-validation cutoff. [' + path + ']',
             'commands: ' + summary_execution + '; ' + geometry_execution + ' [' + summary_execution + ']',
             'files changed: scripts/upgrade_geometry_breadth.py; scripts/upgrade_summarise.py; results/2026-10-30/step2-* [scripts/upgrade_geometry_breadth.py]',
             'std definition: ' + result['std_definition'] + ' [' + path + ']']
    lines.append('metric validation: independently specified metric fixtures and failed-worker exclusion test executed before aggregate reporting. ['+metric_validation+']')
    for execution in retry_executions:
        lines.append('resource retry: one retry of a memory-terminated seed, unchanged protocol and memory cap; completed metrics were not selected for rerun. ['+execution+']')
    integrity=json.loads((OUT/'step2-split-audit.json').read_text())
    lines += ['split audit execution: '+integrity_execution+' ['+integrity_execution+']',
              f'exact-overlap split pairs: {integrity["exact_overlap_pairs"]} [results/2026-10-30/step2-split-audit.json]',
              f'pinned mirror SHA-256 verification: {integrity["verified_files"]} files matched; mismatches: {integrity["hash_mismatches"]} [results/2026-10-30/step2-split-audit.json]',
              'data source: pinned foersben/mvtec-ad Hugging Face mirror, revision and individual LFS hashes retained; official archive byte equivalence UNKNOWN. [results/2026-10-30/step2-intake/source.json]',
              'split independence limitation: '+integrity['limitation']+' [results/2026-10-30/step2-split-audit.json]']
    for variant, aggregates, source in [
        ('core', result['aggregates'], path),
        ('core + inherited radial branch', json.loads((OUT / 'step2-geometry/aggregate.json').read_text()),
         'results/2026-10-30/step2-geometry/aggregate.json')]:
        for category, row in sorted(aggregates.items()):
            lines.append(f'category: {category} | variant: {variant} | seeds: {row["seeds"]} [{source}]')
            for metric, values in row['metrics'].items():
                lines.append(f'new results: {metric} | mean {values["mean"]} ± sample std {values["std_sample"]} | official test, fixed normal train/validation fold | vs old value: historical single-seed result is not a multi-seed estimate | {source} [{source}]')
    for stage in args.stages:
        failed = OUT / stage / 'failures.json'
        if failed.exists():
            lines.append(f'run failures: {failed.read_text()} [results/2026-10-30/{stage}/failures.json]')
    lines += ['geometry failures: ' + (OUT / 'step2-geometry/failures.json').read_text() + ' [results/2026-10-30/step2-geometry/failures.json]',
              'provenance: every successful core run retains run.json (command, seed, commit, settings, source hashes), predictions.csv, calibration.json and dataset_manifest.json; aggregate runs[].source identifies each folder. [' + path + ']',
              'what is still open: official-reference matching was performed only for the original categories at seed 0; defect-bank fitting remains BLOCKED without a separate labelled bank. No factory or glasses performance established. [results/2026-10-30/step1/comparison.json]',
              'possible resume bullet: Built a reproducible multi-seed evaluation of PatchCore and an inherited geometric-stage ablation, retaining per-image errors and calibration provenance. [' + path + ']']
    append(lines)
    print('STEP 2 CHECKPOINT WRITTEN', flush=True)
    execution = run('step3', 'upgrade_localisation.py', '--stages', *args.stages)
    path = 'results/2026-10-30/step3/aggregate.json'
    aggregates = json.loads((ROOT / path).read_text())
    lines = ['## Step 3: localisation',
             'what was done: pixel AUROC and exact-threshold AUPRO to false-positive rate 0.3 on fresh maps and nearest-neighbour aligned ground-truth masks; maps are model centre crops. [scripts/upgrade_metrics.py]',
             'commands: ' + execution + ' [' + execution + ']',
             'files changed: scripts/upgrade_localisation.py; scripts/upgrade_metrics.py; results/2026-10-30/step3 [scripts/upgrade_localisation.py]']
    for category, metrics in sorted(aggregates.items()):
        for metric, value in metrics.items():
            lines.append(f'new results: {category} / {metric} | mean {value["mean"]} ± sample std {value["std_sample"]} | seeds {value["seeds"]}, official test | vs old value: UNKNOWN, not previously measured in this run | {path} [{path}]')
    lines += ['what is still open: evaluation applies to PatchCore pixel maps, not the image-level geometric fusion; centre cropping can remove annotated defects. Per-run mask/map hashes and connected-region definition are retained. [results/2026-10-30/step3/summary.json]',
              'possible resume bullet: Added mask-based localisation evaluation with pixel AUROC and connected-region AUPRO, with independently tested tie handling and endpoint integration. [scripts/test_upgrade_metrics.py]']
    append(lines)
    print('STEP 3 CHECKPOINT WRITTEN', flush=True)
    execution = run('step4', 'upgrade_error_audit.py')
    path = 'results/2026-10-30/step4/cases.json'
    result = json.loads((ROOT / path).read_text())
    append(['## Step 4: error taxonomy',
            'what was done: matched every historical Phase 1 error to this session seed-0 prediction; measured annotation retention after the frozen model crop; visual review PENDING. [' + path + ']',
            'commands: ' + execution + ' [' + execution + ']',
            'files changed: scripts/upgrade_error_audit.py; results/2026-10-30/step4/cases.json [scripts/upgrade_error_audit.py]',
            f'new results: audited cases | {result["total_cases"]} | historical errors matched to new seed-0 official test | vs old value: retrospective selection, not a new accuracy claim | {path} [{path}]',
            'what is still open: visual review required before advancing; causes beyond directly measured crop removal remain UNKNOWN. No model or thresholds were tuned on these inspected cases. [' + path + ']',
            'possible resume bullet: Audited every baseline error and measured the effect of preprocessing on defect visibility, preserving an untouched calibration policy. [' + path + ']'])
    print('STEP 4 CHECKPOINT WRITTEN; STOPPED FOR VISUAL REVIEW', flush=True)


if __name__ == '__main__':
    main()
