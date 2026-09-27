param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
    else { $Python = 'python' }
}
$runtimePython = Join-Path $PSScriptRoot '.runtime\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    & $Python -c "import sys,platform; assert sys.version_info[:2] == (3,12) and platform.architecture()[0] == '64bit', 'Use Python 3.12 x64 for bundled offline wheels'"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 is required. Pass -Python with its executable path.' }
    & $Python -m venv .runtime
    if ($LASTEXITCODE -ne 0) { throw 'Could not create local Python runtime.' }
}
& $runtimePython -m pip install --no-index --find-links wheels -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Offline dependency installation failed.' }
Write-Host 'Open http://127.0.0.1:8793 in your browser. Ctrl+C stops the local service.'
& $runtimePython -m aircraft_noise serve --port 8793
