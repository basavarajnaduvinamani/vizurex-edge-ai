"""Few-shot anomaly detection experiment: k in {1,2,4,8,16,full} x seeds.

Compares the repository's WideResNet-50 PatchCore embedding with frozen DINOv2
patch features under identical reference images, splits, thresholds and
metrics. Protocol: docs/FEWSHOT_PROTOCOL.md. Every category first passes
scripts/validate_mvtec_category.py; a failing category is skipped and reported.

Writes to --output (refuses to overwrite an existing results.json):
  environment.json  packages, threads, command line
  results.json      dataset checks, per-backbone timings and one record per run
  results.md        table generated from results.json
  fewshot_auroc.png image AUROC against k, generated from results.json

Example (owner's machine or Colab, MVTec AD extracted under data/raw/mvtec_ad):
  python scripts/run_fewshot.py --data-root data/raw/mvtec_ad --output artifacts/fewshot-run1
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_SHOTS = ["1", "2", "4", "8", "16", "full"]
DEFAULT_SEEDS = [0, 1, 2]
METHODS = {
    # name: (backbone key, detector settings). The backbone key lets methods
    # that differ only in scoring share one cached feature extraction.
    "patchcore_wrn50": ("wrn50", dict(metric="l2", aggregation="max")),
    "dinov2_vits14": ("dinov2_vits14", dict(metric="cosine", aggregation="mean_top", top_fraction=0.01)),
    "dinov2_vits14_masked": ("dinov2_vits14", dict(metric="cosine", aggregation="mean_top",
                                                   top_fraction=0.01, masking=True)),
    # Random weights; checks the pipeline only. Never report its numbers.
    "tiny_random": ("tiny_random", dict(metric="cosine", aggregation="mean_top", top_fraction=0.01)),
}


def build_backbone(key, args):
    import torch
    from visurex_fewshot import backbones

    device = torch.device("cpu")
    if key == "wrn50":
        return backbones.PatchCoreBackbone("wideresnet50", ("layer2", "layer3"), args.imagesize,
                                           1024, 384, 3, pretrained=True, device=device)
    if key == "dinov2_vits14":
        return backbones.DinoV2Backbone("vit_small_patch14_dinov2.lvd142m", args.imagesize,
                                        pretrained=True, device=device)
    if key == "tiny_random":
        return backbones.TinyRandomBackbone()
    raise KeyError(key)


def check_dataset(data_root: Path, category: str) -> dict:
    """Run the repository's dataset validator unchanged and keep its report."""
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_mvtec_category.py"), str(data_root),
         "--category", category], capture_output=True, text=True)
    return {"category": category, "passed": completed.returncode == 0,
            "report": completed.stdout.strip().splitlines()}


def environment(args):
    packages = {}
    for name in ("torch", "torchvision", "timm", "numpy", "faiss-cpu", "scikit-learn", "scipy", "Pillow"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": sys.version, "platform": platform.platform(), "processor": platform.processor(),
            "packages": packages, "torch_threads": args.threads, "argv": sys.argv}


def write_reports(output: Path, payload: dict) -> None:
    from visurex_fewshot import report

    summary = report.summarize(payload["runs"])
    (output / "results.md").write_text(
        report.markdown_table(summary, payload.get("timings", []), "results.json"), encoding="utf-8")
    if summary:
        report.plot(summary, output / "fewshot_auroc.png")


def run_category(category, args, payload, save):
    import torch
    from visurex_fewshot import data, detector, metrics

    splits = data.load_splits(str(args.data_root), category, args.resize, args.imagesize)
    pool_names = [row[2] for row in splits["train"].data_to_iterate]
    cache = {}
    for method in args.methods:
        backbone_key, settings = METHODS[method]
        if backbone_key not in cache:
            torch.manual_seed(0)
            backbone = build_backbone(backbone_key, args)
            begin = time.perf_counter()
            embedded = {name: data.embed_split(backbone, splits[name], keep_masks=(name == "test"))
                        for name in ("train", "val", "test")}
            total = time.perf_counter() - begin
            seconds = np.concatenate([embedded[n].seconds_per_image for n in embedded])
            cache[backbone_key] = embedded
            payload["timings"].append({
                "category": category, "method": method, "backbone": backbone.name,
                "images_embedded": int(seconds.size), "embed_seconds_total": total,
                "embed_ms_median": float(np.median(seconds) * 1000),
                "embed_ms_p95": float(np.percentile(seconds, 95) * 1000),
                "torch_threads": args.threads, "device": "cpu",
                "train_pool": len(embedded["train"].names), "validation": len(embedded["val"].names),
                "test": len(embedded["test"].names)})
            save()
        embedded = cache[backbone_key]
        train, val, test = embedded["train"], embedded["val"], embedded["test"]
        for k in args.shots:
            # A full reference set is the same images for every seed; only a
            # stochastic coreset could differ, so run it once with seed 0.
            for seed in ([args.seeds[0]] if k == "full" else args.seeds):
                if k != "full" and int(k) > len(train.names):
                    print(f"skip {category} {method} k={k}: only {len(train.names)} pool images", flush=True)
                    continue
                indices = data.select_shots(len(train.names), k, seed)
                use_coreset = method == "patchcore_wrn50" and k == "full" and args.coreset_full
                config = detector.DetectorConfig(
                    coreset_fraction=args.coreset_full if use_coreset else None, **settings)
                begin = time.perf_counter()
                model = detector.KShotPatchNN(config, seed=seed, num_workers=args.threads)
                model.fit(train.features[indices], train.grid)
                fit_seconds = time.perf_counter() - begin
                val_scores, _ = model.predict(val.features)
                threshold = metrics.validation_threshold(val_scores)
                nn_seconds = []
                test_scores, test_maps = [], []
                for i in range(len(test.names)):
                    begin = time.perf_counter()
                    score, image_map = model.predict(test.features[i:i + 1],
                                                     image_size=(args.imagesize, args.imagesize))
                    nn_seconds.append(time.perf_counter() - begin)
                    test_scores.append(score[0])
                    test_maps.append(image_map[0])
                record = {"category": category, "method": method, "k": k, "seed": seed,
                          "references": [Path(pool_names[i]).name for i in indices],
                          "memory_bank_patches": model.memory_size, "detector": config.to_dict(),
                          "fit_seconds": fit_seconds, "validation_count": len(val_scores),
                          "test_count": len(test_scores),
                          "nn_ms_per_image_median": float(np.median(nn_seconds) * 1000)}
                record.update(metrics.image_metrics(test_scores, test.labels, threshold))
                # Private sidecars make aggregate metrics independently auditable;
                # they contain no image pixels and do not alter any scoring rule.
                evidence=Path(args.output)/'predictions'
                evidence.mkdir(parents=True,exist_ok=True)
                key=f'{category}__{method}__k{k}__seed{seed}'
                predictions=evidence/(key+'.csv')
                with predictions.open('w',newline='',encoding='utf-8') as stream:
                    writer=csv.DictWriter(stream,fieldnames=['image','label','score','threshold','predicted'])
                    writer.writeheader()
                    for entry,label,score in zip(splits['test'].data_to_iterate,test.labels,test_scores):
                        image=Path(entry[2]).resolve().relative_to(args.data_root.resolve()/category/'test').as_posix()
                        writer.writerow(dict(image=image,label=int(label),score=float(score),
                                             threshold=threshold,predicted=int(score>=threshold)))
                calibration=evidence/(key+'_calibration.json')
                calibration.write_text(json.dumps(dict(threshold=threshold,validation_scores=val_scores.tolist(),
                    validation_images=[Path(entry[2]).name for entry in splits['val'].data_to_iterate],
                    policy='Normal validation only, computed before test scoring'),indent=2),encoding='utf-8')
                record.update(predictions_path=predictions.relative_to(args.output).as_posix(),
                    predictions_sha256=hashlib.sha256(predictions.read_bytes()).hexdigest(),
                    calibration_path=calibration.relative_to(args.output).as_posix(),
                    calibration_sha256=hashlib.sha256(calibration.read_bytes()).hexdigest())
                record["pixel_auroc"] = record["pixel_aupro"] = None
                if args.pixel_metrics and test.masks is not None and test.masks.any():
                    maps = np.stack(test_maps)
                    record["pixel_auroc"] = metrics.pixel_auroc(test.masks, maps)
                    record["pixel_aupro"] = metrics.compute_aupro(test.masks, maps)
                payload["runs"].append(record)
                save()
                print(json.dumps({key: record[key] for key in
                                  ("category", "method", "k", "seed", "image_auroc", "defect_recall",
                                   "false_alarm_rate", "pixel_aupro")}), flush=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-root", type=Path, required=True, help="Folder containing MVTec AD category folders")
    parser.add_argument("--categories", nargs="+", default=None, help="Default: every MVTec category found")
    parser.add_argument("--methods", nargs="+", default=["patchcore_wrn50", "dinov2_vits14"], choices=sorted(METHODS))
    parser.add_argument("--shots", nargs="+", default=DEFAULT_SHOTS)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resize", type=int, default=256)
    parser.add_argument("--imagesize", type=int, default=224)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--coreset-full", type=float, default=0.01,
                        help="PatchCore greedy coreset fraction at k=full (Phase 1 used 0.01); 0 disables")
    parser.add_argument("--no-pixel-metrics", dest="pixel_metrics", action="store_false")
    parser.add_argument("--report-only", action="store_true", help="Regenerate results.md and plot from results.json")
    args = parser.parse_args(argv)
    for k in args.shots:
        if k != "full" and (not k.isdigit() or int(k) < 1):
            parser.error(f"invalid shot count: {k}")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    output = args.output.resolve()
    results_path = output / "results.json"
    if args.report_only:
        write_reports(output, json.loads(results_path.read_text(encoding="utf-8")))
        return 0
    if results_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing results: {results_path}")

    import torch
    from visurex_fewshot import data

    torch.set_num_threads(args.threads)
    output.mkdir(parents=True, exist_ok=True)
    (output / "environment.json").write_text(json.dumps(environment(args), indent=2), encoding="utf-8")
    categories = data.find_categories(str(args.data_root), args.categories)
    if not categories:
        print(f"No MVTec AD categories found under {args.data_root}", file=sys.stderr)
        return 1
    payload = {"protocol": "docs/FEWSHOT_PROTOCOL.md", "data_root_name": args.data_root.name,
               "shots": args.shots, "seeds": args.seeds, "methods": args.methods,
               "resize": args.resize, "imagesize": args.imagesize,
               "threshold_rule": "99th percentile of normal validation scores (last 20% of sorted train/good)",
               "dataset_checks": [], "timings": [], "runs": []}

    def save():
        results_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    failed = False
    for category in categories:
        check = check_dataset(args.data_root, category)
        payload["dataset_checks"].append(check)
        save()
        if not check["passed"]:
            failed = True
            print(f"dataset check failed for {category}; skipped:\n" + "\n".join(check["report"]), flush=True)
            continue
        begin = time.perf_counter()
        run_category(category, args, payload, save)
        print(f"{category} finished in {time.perf_counter() - begin:.1f} s", flush=True)
    write_reports(output, payload)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
