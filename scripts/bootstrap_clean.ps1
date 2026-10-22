param([string]$BasePython = 'python', [string]$Environment = '.venv-clean', [switch]$PortableExport)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $projectRoot
if (-not (Test-Path "$Environment\Scripts\python.exe")) {
    & $BasePython -m venv $Environment
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated environment' }
}
$phasePython = Join-Path $Environment 'Scripts\python.exe'
& $phasePython -m pip install --timeout 120 'torch==2.7.0+cpu' 'torchvision==0.22.0+cpu' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed' }
& $phasePython -m pip install --timeout 120 -r requirements-software-windows-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Application dependency installation failed' }
if ($PortableExport) {
    & $phasePython -m pip install --timeout 120 -r requirements-portable-export.txt
    if ($LASTEXITCODE -ne 0) { throw 'Portable export dependency installation failed' }
}
& $phasePython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed' }
& $phasePython -c "import sys; assert sys.prefix != sys.base_prefix; print('Isolated environment ready:',sys.executable)"
