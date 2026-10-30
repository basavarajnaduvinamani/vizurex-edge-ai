"""New-session matched runs. Never modifies inherited data or earlier evidence."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results/2026-10-30'
PRIVATE = ROOT / 'artifacts/upgrade-2026-10-30'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def provenance(args):
    return dict(command=[sys.executable, *sys.argv], seed=args.seed,
                execution_commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                source_sha256={str(p.relative_to(ROOT)): sha(p) for p in
                    [Path(__file__), ROOT / 'scripts/upgrade_metrics.py']},
                config=vars(args), started_at=__import__('datetime').datetime.now().astimezone().isoformat())


def run(args):
    import numpy as np
    import psutil
    import torch
    from PIL import Image
    from torchvision import transforms
    # Only the algorithm package changes. The data loader/split stays identical.
    local_dataset_file = ROOT / 'src/patchcore/datasets/mvtec.py'
    spec = importlib.util.spec_from_file_location('upgrade_dataset', local_dataset_file)
    datasets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(datasets)
    package_root = ROOT / ('artifacts/reference-patchcore/src' if args.engine == 'official' else 'src')
    sys.path.insert(0, str(package_root))
    import patchcore.backbones
    from patchcore.patchcore import PatchCore
    from patchcore.common import FaissNN
    from patchcore.sampler import ApproximateGreedyCoresetSampler
    from upgrade_metrics import image_metrics
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    key = f'{args.category}_seed{args.seed}_{args.engine}'
    out = RESULTS / args.stage / key
    if (out / 'summary.json').exists():
        raise FileExistsError(f'Refusing to replace completed run: {out}')
    out.mkdir(parents=True, exist_ok=True)
    meta = provenance(args)
    meta['official_reference_commit'] = git('rev-parse', 'HEAD', cwd=ROOT / 'artifacts/reference-patchcore')
    meta['dataset_loader_sha256'] = sha(local_dataset_file)
    meta['package_files'] = {n: sha(package_root / 'patchcore' / n) for n in
                              ['patchcore.py', 'common.py', 'sampler.py', 'backbones.py']}
    meta['settings'] = dict(backbone='wide_resnet50_2 IMAGENET1K_V1', layers=['layer2', 'layer3'],
        resize=256, center_crop=224, embedding_pretrain=1024, embedding_target=384,
        patchsize=3, coreset=0.01, nearest_neighbours=1, batch_size=1, torch_threads=4,
        train_val_split=0.8, split_rule='sorted filenames, first floor(n*.8) train',
        normalisation='validation min / validation raw p99; floor at zero, no upper clip',
        threshold='99th percentile of normalised held-out normal validation scores')
    dump(out / 'run.json', meta)
    train = datasets.MVTecDataset(str(ROOT / 'data/raw/mvtec_ad'), args.category,
        split=datasets.DatasetSplit.TRAIN, train_val_split=0.8)
    val = datasets.MVTecDataset(str(ROOT / 'data/raw/mvtec_ad'), args.category,
        split=datasets.DatasetSplit.VAL, train_val_split=0.8)
    test = datasets.MVTecDataset(str(ROOT / 'data/raw/mvtec_ad'), args.category,
        split=datasets.DatasetSplit.TEST)
    manifest = {}
    for split, ds in [('train', train), ('validation', val), ('test', test)]:
        manifest[split] = [dict(image=Path(x[2]).relative_to(ROOT / 'data/raw/mvtec_ad').as_posix(),
            sha256=sha(x[2]), mask_sha256=sha(x[3]) if x[3] else None) for x in ds.data_to_iterate]
    train_hashes = {x['sha256'] for x in manifest['train']}
    if train_hashes & {x['sha256'] for x in manifest['validation']+manifest['test']}:
        raise ValueError('Exact split leakage detected')
    dump(out / 'dataset_manifest.json', manifest)
    started = time.perf_counter()
    backbone = patchcore.backbones.load('wideresnet50'); backbone.name = 'wideresnet50'
    model = PatchCore(torch.device('cpu'))
    model.load(backbone, ['layer2', 'layer3'], torch.device('cpu'), (3,224,224), 1024,384,
        patchsize=3, anomaly_score_num_nn=1,
        featuresampler=ApproximateGreedyCoresetSampler(0.01, torch.device('cpu')),
        nn_method=FaissNN(False,4))
    model.fit(torch.utils.data.DataLoader(train, batch_size=1, num_workers=0, shuffle=False))
    fit_seconds = time.perf_counter()-started
    val_raw = np.array([float(model.predict(x['image'].unsqueeze(0))[0][0]) for x in val])
    low, high = float(val_raw.min()), float(np.percentile(val_raw,99))
    if high-low <= 1e-8:
        raise ValueError('Degenerate validation range')
    normalise = lambda a: np.maximum((np.asarray(a)-low)/(high-low),0)
    val_norm = normalise(val_raw)
    threshold = float(np.percentile(val_norm,99))
    dump(out / 'calibration.json', dict(validation_raw_scores=val_raw.tolist(),
        validation_normalised_scores=val_norm.tolist(), low=low, high=high, threshold=threshold,
        fit_seconds=fit_seconds, train_images=len(train), validation_images=len(val)))
    rows, maps, masks, paths = [], [], [], []
    nearest_mask = transforms.Compose([transforms.Resize(256, interpolation=transforms.InterpolationMode.NEAREST),
                                      transforms.CenterCrop(224), transforms.PILToTensor()])
    for item, entry in zip(test, test.data_to_iterate):
        tick=time.perf_counter(); score, anomaly_map = model.predict(item['image'].unsqueeze(0))
        elapsed=time.perf_counter()-tick
        s=float(normalise(float(score[0])))
        path=Path(entry[2]); relative=path.relative_to(ROOT/'data/raw/mvtec_ad'/args.category/'test').as_posix()
        rows.append(dict(image=relative,label=int(item['is_anomaly']),score=s,
                         predicted=int(s>=threshold),model_seconds=elapsed))
        maps.append(np.asarray(anomaly_map[0],dtype='float32'))
        if entry[3]:
            with Image.open(entry[3]) as mask:
                masks.append(nearest_mask(mask.convert('L')).numpy()[0]>0)
        else:
            masks.append(np.zeros((224,224),dtype=bool))
        paths.append(relative)
    with (out/'predictions.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    private=PRIVATE/args.stage/key;private.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(private/'maps.npz',maps=np.stack(maps),masks=np.stack(masks),paths=np.array(paths))
    metrics=image_metrics([r['label'] for r in rows],[r['score'] for r in rows],threshold)
    summary=dict(category=args.category,seed=args.seed,engine=args.engine,metrics=metrics,
                 train_images=len(train),validation_images=len(val),fit_seconds=fit_seconds,
                 worker_pid=os.getpid(),worker_peak_working_set_bytes=getattr(psutil.Process().memory_info(),'peak_wset',None),
                 maps_path=str((private/'maps.npz').relative_to(ROOT)),maps_sha256=sha(private/'maps.npz'),
                 zero_mask_defect_images=sum(r['label'] and not masks[i].any() for i,r in enumerate(rows)),
                 provenance_file=str((out/'run.json').relative_to(ROOT)))
    # Reference parity compares source implementations; historical phase1 is separately labelled.
    historical=ROOT/f'artifacts/phase1-20261021/runs/{args.category}/evaluation/mvtec_{args.category}_predictions.csv'
    if historical.exists():
        old={r['Image']:r for r in csv.DictReader(historical.open())}
        summary['historical_phase1_comparison']=dict(
            matching_decisions=sum(r['predicted']==(old[r['image']]['PC_Pred']=='ANOMALY') for r in rows),
            max_score_delta=max(abs(r['score']-float(old[r['image']]['PC_Score'])) for r in rows),
            note='historical CSV rounded; old values are not new session results')
    if args.geometry:
        if args.engine!='current':raise ValueError('Geometry ablation uses current engine only')
        gs=importlib.util.spec_from_file_location('inherited_judges',ROOT/'bin/run_patchcore1.py')
        geo=importlib.util.module_from_spec(gs);gs.loader.exec_module(geo)
        def profiles(ds):
            outp=[]
            for entry in ds.data_to_iterate:
                profile=geo._get_profile(entry[2])
                if profile is None:raise ValueError('Geometric profile unavailable: '+entry[2])
                outp.append(profile)
            return np.array(outp)
        train_p=profiles(train);mean,std=train_p.mean(0),train_p.std(0)
        v=[geo._profile_anomaly_score(p,mean,std) for p in profiles(val)]
        geo_threshold=float(np.percentile(v,99))
        gscores=[geo._profile_anomaly_score(p,mean,std) for p in profiles(test)]
        fused=np.maximum(np.array([r['score'] for r in rows])/threshold,np.asarray(gscores)/geo_threshold)
        summary['geometry_ablation']=image_metrics([r['label'] for r in rows],fused,1.0)
        summary['geometry_policy']='Inherited radial profile and industrial preprocessing; training mean/std; validation p99 threshold; OR via max of threshold-scaled scores. Not meaningful spatial geometry for every MVTec category.'
        dump(out/'geometry.json',dict(training_mean=mean.tolist(),training_std=std.tolist(),
            validation_scores=v,threshold=geo_threshold,test_scores=gscores,fused_scores=fused.tolist(),
            inherited_source_sha256=sha(ROOT/'bin/run_patchcore1.py')))
    summary['defect_bank_status']='BLOCKED: MVTec train/good provides no separate labelled known-defect bank. Official test anomalies were not used for fitting.'
    dump(out/'summary.json',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--category',required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--engine',choices=['official','current'],required=True)
    p.add_argument('--stage',required=True)
    p.add_argument('--geometry',action='store_true')
    run(p.parse_args())
