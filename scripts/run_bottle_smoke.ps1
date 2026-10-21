param(
    [string]$Python = "python",
    [string]$DatasetRoot = "$PSScriptRoot\..\data\raw\mvtec_ad"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$datasetRootResolved = (Resolve-Path $DatasetRoot).Path
$env:PYTHONPATH = Join-Path $projectRoot "src"

& $Python (Join-Path $projectRoot "scripts\validate_mvtec_category.py") `
    $datasetRootResolved --category bottle
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python (Join-Path $projectRoot "bin\run_patchcore1.py") `
    --seed 0 `
    --log_group bottle-cpu-seed0 `
    --log_project mvtec-bottle-smoke `
    --save_patchcore_model `
    (Join-Path $projectRoot "artifacts\smoke") `
    patch_core `
    -b wideresnet50 `
    -le layer2 `
    -le layer3 `
    --pretrain_embed_dimension 1024 `
    --target_embed_dimension 384 `
    --anomaly_scorer_num_nn 1 `
    --patchsize 3 `
    sampler `
    -p 0.01 `
    approx_greedy_coreset `
    dataset `
    --train_val_split 0.8 `
    --batch_size 1 `
    --num_workers 0 `
    --resize 256 `
    --imagesize 224 `
    -d bottle `
    mvtec `
    $datasetRootResolved
exit $LASTEXITCODE
