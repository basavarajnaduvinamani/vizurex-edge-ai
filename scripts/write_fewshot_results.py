"""Publish only completed aggregate evidence; keep private sidecars in artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def tables(path):
    blocks=[];current=[]
    for line in path.read_text(encoding='utf-8').splitlines()+['']:
        if line.startswith('|'):current.append(line)
        elif current:blocks.append('\n'.join(current));current=[]
    return blocks


def main():
    p=argparse.ArgumentParser();p.add_argument('--date',required=True);args=p.parse_args()
    date=args.date
    main_dir=ROOT/'artifacts/fewshot-run1';masked_dir=ROOT/'artifacts/fewshot-masked-run1'
    run_root=ROOT/'artifacts/finish-fewshot/runs'
    executions={name:read(run_root/name/'execution.json') for name in
        ['dependencies','model-intake','clean-pip-check','clean-tests','clean-frontend','sanity','main','masked']}
    if any(r['exit_status']!=0 for r in executions.values()):raise ValueError('Incomplete or failed run; do not publish completion')
    primary=read(main_dir/'results.json');masked=read(masked_dir/'results.json');criteria=read(main_dir/'criteria.json')
    for payload,categories,methods in [(primary,['bottle','grid','transistor'],['patchcore_wrn50','dinov2_vits14']),
                                       (masked,['bottle','transistor'],['dinov2_vits14_masked'])]:
        expected={(category,method,k,seed) for category in categories for method in methods
            for k in ['1','2','4','8','16','full'] for seed in ([0] if k=='full' else [0,1,2])}
        observed=[(r['category'],r['method'],r['k'],r['seed']) for r in payload['runs']]
        if len(observed)!=len(set(observed)) or set(observed)!=expected:raise ValueError('Incomplete/duplicate registered record grid')
        if payload['resize']!=256 or payload['imagesize']!=224:raise ValueError('Unexpected resolution')
        if not all(r['passed'] for r in payload['dataset_checks']):raise ValueError('Dataset validation failed')
    intake=read(ROOT/'artifacts/finish-fewshot/model-intake.json')
    protocol=ROOT/'docs/FEWSHOT_PROTOCOL.md'
    if hashlib.sha256(protocol.read_bytes()).hexdigest()!=intake['protocol_sha256']:
        raise ValueError('Protocol changed after model intake; review before publishing')
    destination=ROOT/'docs/results'/('FEWSHOT_'+date)
    document=destination.with_suffix('.md')
    if destination.exists() or document.exists():raise FileExistsError('Preserve existing published evidence')
    destination.mkdir(parents=True)
    for name,source in [('primary',main_dir),('masked',masked_dir),('sanity',ROOT/'artifacts/fewshot-smoke')]:
        target=destination/name;target.mkdir()
        for filename in ['results.json','results.md','fewshot_auroc.png','environment.json']:
            shutil.copy2(source/filename,target/filename)
    shutil.copy2(main_dir/'criteria.json',destination/'primary/criteria.json')
    (destination/'executions.json').write_text(json.dumps(executions,indent=2),encoding='utf-8')
    (destination/'model-intake.json').write_text(json.dumps(intake,indent=2),encoding='utf-8')
    shutil.copy2(ROOT/'artifacts/finish-fewshot/clean-test-summary.json',destination/'test-summary.json')
    distinct_test_counts={row['category']:row['test'] for row in primary['timings']}
    study=dict(primary_configurations=len(primary['runs']),masked_configurations=len(masked['runs']),
        distinct_test_images=sum(distinct_test_counts.values()),distinct_test_images_by_category=distinct_test_counts,
        policy='The same official held-out images are evaluated repeatedly across configurations; configurations are not independent test-image samples.')
    (destination/'study-summary.json').write_text(json.dumps(study,indent=2),encoding='utf-8')
    comparison=[]
    for row in primary['runs']:
        if row['method']!='patchcore_wrn50' or row['k']!='full':continue
        oldpath=ROOT/f'results/2026-10-30/step1/{row["category"]}_seed0_current/summary.json'
        old=read(oldpath)['metrics']
        comparison.append(dict(category=row['category'],matched_baseline_image_auroc=old['image_auroc'],
            fewshot_harness_image_auroc=row['image_auroc'],difference=row['image_auroc']-old['image_auroc'],
            matched_baseline_fn=old['missed_defects'],harness_fn=row['fn'],
            matched_baseline_fp=old['false_alarms'],harness_fp=row['fp'],baseline_source=str(oldpath.relative_to(ROOT))))
    (destination/'baseline-comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
    comparison_md='| Category | Matched baseline AUROC | Few-shot harness full-shot AUROC | Baseline FN / FP | Harness FN / FP |\n|---|---:|---:|---|---|\n'
    for row in comparison:
        comparison_md+=f'| {row["category"]} | {row["matched_baseline_image_auroc"]} | {row["fewshot_harness_image_auroc"]} | {row["matched_baseline_fn"]} / {row["matched_baseline_fp"]} | {row["harness_fn"]} / {row["harness_fp"]} |\n'
    (destination/'baseline-comparison.md').write_text(comparison_md,encoding='utf-8')
    criterion_md='| Registered criterion | Verdict | Evidence |\n|---|---|---|\n'
    criterion_md+=f'| H1 | {criteria["h1"]["verdict"]} | {criteria["h1"]["supported_categories"]} primary categories meet every registered low-shot comparison |\n'
    criterion_md+=f'| Practical few-shot use | {criteria["practical"]["verdict"]} | See per-method qualifying budgets in primary/criteria.json |\n'
    criterion_md+=f'| H2 | {criteria["h2"]["verdict"]} | Full-shot seed spread is unmeasured; descriptive AUROC differences are retained in criteria.json |\n'
    (destination/'criteria.md').write_text(criterion_md,encoding='utf-8')
    macro=criteria['macro_auroc'];dino=macro['dinov2_vits14']['8']['image_auroc'];wrn=macro['patchcore_wrn50']['8']['image_auroc']
    resume=dict(source='primary/criteria.json',pre_doc=(
        'Benchmarked training-free DINOv2 k-shot anomaly detection against PatchCore on three MVTec AD categories '
        f'(k=1-16, three seeds): macro AUROC {dino:.4f} at k=8 versus {wrn:.4f} for PatchCore.'),
        apm='Not supported: the practical-use criterion was not met across the primary categories, and no factory onboarding study was performed.')
    (destination/'resume-evidence.json').write_text(json.dumps(resume,indent=2),encoding='utf-8')
    stem=destination.name
    lines=[f'# Few-shot anomaly detection - {date}','', '## Decision','',
        f'The registered H1 criterion is **{criteria["h1"]["verdict"]}** and the practical-use criterion is **{criteria["practical"]["verdict"]}**. '
        'The category-average result at the registered low-shot budget favours DINOv2, but the per-category results are mixed. '
        'This supports a benchmark report, not a factory-onboarding or deployment claim.','',
        f'Primary execution commit: `{executions["main"]["execution_commit"]}`. Masked execution commit: `{executions["masked"]["execution_commit"]}`. '
        f'Sources: [{stem}/executions.json]({stem}/executions.json), private local run folders `artifacts/fewshot-run1` and `artifacts/fewshot-masked-run1`.','',
        '## Primary comparison','',f'Tables copied verbatim from [{stem}/primary/results.md]({stem}/primary/results.md).','']
    captions=['Image ranking, operating-point errors and localisation','CPU feature extraction','End-to-end category wall time']
    for caption,block in zip(captions,tables(main_dir/'results.md')):lines += ['### '+caption,'',block,'']
    lines += ['## Masked ablation','',f'Tables copied verbatim from [{stem}/masked/results.md]({stem}/masked/results.md).','']
    for caption,block in zip(captions,tables(masked_dir/'results.md')):lines += ['### '+caption,'',block,'']
    lines += ['## Registered success criteria','',f'Generated from [{stem}/primary/criteria.json]({stem}/primary/criteria.json).','',criterion_md,'',
        'H2 is formally inconclusive because the protocol runs full-shot once. An unavailable seed spread is not an observed zero spread. '
        'The per-category differences and the descriptive comparison against the fallback tolerance remain visible in the criterion file.','',
        '## Full-shot baseline comparison','',f'Generated from [{stem}/baseline-comparison.json]({stem}/baseline-comparison.json). '
        'The matched-baseline sources are identified per row in that file. Differences are reported without editing either experiment.','',comparison_md,'',
        '## Protocol and integrity','',
        '- The preregistered shot counts, seeds, methods, image size and normal-validation threshold policy were unchanged. '
        f'Protocol SHA-256: `{intake["protocol_sha256"]}` ([model intake]({stem}/model-intake.json)).',
        '- Every category passed the existing readability, exact-overlap and mask-pairing validator; the validator outputs are retained in each results.json.',
        '- Thresholds use the held-out normal validation set and are fixed before test scoring. Reference filenames, per-run configuration and confusion counts are retained.',
        '- Private per-image scores and normal-validation calibration files remain under the original ignored artifacts folders. '
        'Their relative paths and SHA-256 values are recorded in results.json; these files are not copied into this published aggregate folder.',
        '- Model weights, benchmark images and company data are excluded. The committed plots contain aggregate results only.','',
        '## Limitations','',
        '- The finite-shot rows use three seeds; full-shot uses only seed 0. The generated spread is population standard deviation (ddof=0), not a confidence interval.',
        '- k counts reference images only. The additional normal calibration set is still required; this is not a deployment using only k labelled normal images.',
        '- The recipes differ in distance, image-score aggregation and full-shot memory-bank construction. This does not isolate the causal effect of the backbone alone.',
        '- The fixed centre crop can exclude defects. The few-shot AUPRO implementation uses normal-quantile thresholds and default connected-component labelling; '
        'the separate baseline upgrade uses exact thresholds and eight-connected regions. Those AUPRO columns must not be treated as an identical evaluator.',
        '- Masking changes image-score aggregation; its nearest-neighbour pixel maps remain unmasked. The foreground rule is a simplified PCA heuristic.',
        '- Timings are laptop CPU measurements even though a CUDA-capable environment was installed. Model-call timings exclude loading/preprocessing; '
        'total embedding and category wall times include additional work. The large first-category wall time is retained without claiming a diagnosed cause.',
        '- DINOv2 and PatchCore are established methods; this work is a controlled comparison and engineering extension of the inherited WCTE pipeline.',
        '- No industrial pilot, tablet-local inference or Meta glasses test was run. The capture-quality checks and earlier synthetic blur failure remain unresolved research limitations.',
        '- MVTec AD is used for non-commercial research. This benchmark does not grant a production-data or deployment licence.','',
        '## Resume evidence','',f'Source: [{stem}/resume-evidence.json]({stem}/resume-evidence.json).','',
        'Pre-doc: '+resume['pre_doc'],'','APM: '+resume['apm'],'']
    document.write_text('\n'.join(lines),encoding='utf-8')
    print(str(document),flush=True)


if __name__=='__main__':main()
