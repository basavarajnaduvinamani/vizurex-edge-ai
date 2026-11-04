param([string[]]$Tasks = @('testDebugUnitTest', 'assembleDebug'))
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$toolsDir = Join-Path $projectDir '.tools'
$gradleVersion = '8.13'
$gradleDir = Join-Path $toolsDir "gradle-$gradleVersion"
$env:GRADLE_USER_HOME = Join-Path $projectDir '.gradle/user-home'
if (-not (Test-Path "$gradleDir/bin/gradle.bat")) {
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    $archive = Join-Path $toolsDir "gradle-$gradleVersion-bin.zip"
    $distribution = "https://services.gradle.org/distributions/gradle-$gradleVersion-bin.zip"
    $expected = (Invoke-RestMethod "$distribution.sha256").Trim()
    Invoke-WebRequest $distribution -OutFile $archive
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw 'Gradle distribution checksum mismatch; refusing execution.' }
    Expand-Archive -LiteralPath $archive -DestinationPath $toolsDir -Force
}
Push-Location $projectDir
try { & "$gradleDir/bin/gradle.bat" --no-daemon @Tasks; if ($LASTEXITCODE -ne 0) { throw "Gradle failed: $LASTEXITCODE" } }
finally { Pop-Location }
