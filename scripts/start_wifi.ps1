param([Parameter(Mandatory=$true)][string]$LaptopIPv4)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$env:VISUREX_LAN_IP = $LaptopIPv4
$env:VISUREX_BUNDLE_ROOT = Join-Path $projectRoot 'artifacts\model-bundles'
$runtime = Join-Path $projectRoot '.venv-clean\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Run the clean environment bootstrap first.' }
# The key is ephemeral: not saved to a file, URL, browser storage or audit log.
$randomBytes = New-Object byte[] 32
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$generator.GetBytes($randomBytes)
$generator.Dispose()
$env:VISUREX_ACCESS_KEY = [Convert]::ToBase64String($randomBytes)
try {
    & $runtime -c 'import os; from backend.network import NetworkPolicy; NetworkPolicy(os.environ["VISUREX_LAN_IP"],os.environ["VISUREX_ACCESS_KEY"])'
    if ($LASTEXITCODE -ne 0) { throw 'Invalid LAN configuration; server not started.' }
    if (-not (Test-Path -LiteralPath (Join-Path $env:VISUREX_BUNDLE_ROOT 'catalog.json'))) { throw 'Offline model bundles missing.' }
    Write-Host 'Trusted-network demo only. HTTP is not encrypted. Use non-sensitive benchmark images.'
    Write-Host "Phone browser URL: http://${LaptopIPv4}:8000"
    Write-Host "Session access key (paste into the app): $env:VISUREX_ACCESS_KEY"
    Write-Host 'No firewall rules are changed. Stop with Ctrl+C; restart rotates the key.'
    & $runtime -m uvicorn backend.app:app --host $LaptopIPv4 --port 8000
    if ($LASTEXITCODE -ne 0) { throw 'Wi-Fi server stopped with an error.' }
}
finally {
    Remove-Item Env:VISUREX_ACCESS_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:VISUREX_LAN_IP -ErrorAction SilentlyContinue
}
