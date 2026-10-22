param([switch]$LegacyModels)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
Remove-Item Env:VISUREX_LAN_IP -ErrorAction SilentlyContinue
Remove-Item Env:VISUREX_ACCESS_KEY -ErrorAction SilentlyContinue
$runtime = Join-Path $projectRoot '.venv-clean\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    throw 'Run scripts/bootstrap_clean.ps1 first.'
}
if (-not $LegacyModels) {
    $env:VISUREX_BUNDLE_ROOT = Join-Path $projectRoot 'artifacts\model-bundles'
    if (-not (Test-Path -LiteralPath (Join-Path $env:VISUREX_BUNDLE_ROOT 'catalog.json'))) {
        throw 'Offline bundles missing. Package the trusted local models first.'
    }
} else {
    Remove-Item Env:VISUREX_BUNDLE_ROOT -ErrorAction SilentlyContinue
}
# Remain loopback-only. A physical tablet can connect through USB adb reverse.
& $runtime -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
