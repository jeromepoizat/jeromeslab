[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepositoryRoot = $PSScriptRoot
$PythonExecutable = Join-Path (Join-Path $RepositoryRoot ".venv") "Scripts\python.exe"
$FrontendIndex = Join-Path (Join-Path (Join-Path $RepositoryRoot "frontend") "dist") "index.html"

if (-not (Test-Path -LiteralPath $PythonExecutable) -or -not (Test-Path -LiteralPath $FrontendIndex)) {
    Write-Host "Jerome's Laboratory is not installed yet." -ForegroundColor Yellow
    Write-Host "Run .\install.ps1 first."
    exit 1
}

Set-Location $RepositoryRoot
& $PythonExecutable -m jeromes_laboratory.launcher.main
exit $LASTEXITCODE
