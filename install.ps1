[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RepositoryRoot = $PSScriptRoot
$RuntimeDirectory = Join-Path $RepositoryRoot ".runtime"
$DownloadsDirectory = Join-Path $RuntimeDirectory "downloads"
$VersionsFile = Join-Path (Join-Path $RepositoryRoot "bootstrap") "runtime-versions.env"

function Read-VersionFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            throw "Invalid runtime metadata line: $line"
        }

        $key = $trimmed.Substring(0, $separator)
        $value = $trimmed.Substring($separator + 1)
        $values[$key] = $value
    }
    return $values
}

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-RuntimePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $runtimePrefix = [IO.Path]::GetFullPath($RuntimeDirectory).TrimEnd("\") + "\"
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($runtimePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the project runtime directory: $resolved"
    }
}

function Remove-RuntimePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-RuntimePath -Path $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Reset-RuntimeDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Remove-RuntimePath -Path $Path
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Get-VerifiedDownload {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    Assert-RuntimePath -Path $Destination
    if (Test-Path -LiteralPath $Destination) {
        $existingHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existingHash -eq $ExpectedSha256) {
            Write-Host "Using verified cached download: $(Split-Path -Leaf $Destination)"
            return
        }
    }

    $partial = "$Destination.part"
    if (Test-Path -LiteralPath $partial) {
        Remove-Item -LiteralPath $partial -Force
    }

    Write-Host "Downloading $Uri"
    Invoke-WebRequest -Uri $Uri -OutFile $partial -UseBasicParsing
    $actualHash = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedSha256) {
        Remove-Item -LiteralPath $partial -Force
        throw "Checksum mismatch for $Uri. Expected $ExpectedSha256, received $actualHash."
    }

    Move-Item -LiteralPath $partial -Destination $Destination -Force
}

function Assert-NativeSuccess {
    param([Parameter(Mandatory = $true)][string]$Action)
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

$Versions = Read-VersionFile -Path $VersionsFile
$UvVersion = $Versions["UV_VERSION"]
$PythonVersion = $Versions["PYTHON_VERSION"]
$NodeVersion = $Versions["NODE_VERSION"]
$PnpmVersion = $Versions["PNPM_VERSION"]

$RawArchitecture = if ($env:PROCESSOR_ARCHITEW6432) {
    $env:PROCESSOR_ARCHITEW6432
} else {
    $env:PROCESSOR_ARCHITECTURE
}

switch ($RawArchitecture.ToUpperInvariant()) {
    "AMD64" { $Architecture = "X64" }
    "ARM64" { $Architecture = "ARM64" }
    default { throw "Unsupported Windows architecture: $RawArchitecture. Supported: x64, ARM64." }
}

$UvArchiveName = $Versions["UV_WINDOWS_${Architecture}_FILE"]
$UvArchiveHash = $Versions["UV_WINDOWS_${Architecture}_SHA256"]
$NodeArchiveName = $Versions["NODE_WINDOWS_${Architecture}_FILE"]
$NodeArchiveHash = $Versions["NODE_WINDOWS_${Architecture}_SHA256"]

New-Item -ItemType Directory -Path $DownloadsDirectory -Force | Out-Null

$UvDirectory = Join-Path $RuntimeDirectory "uv"
$UvExecutable = Join-Path $UvDirectory "uv.exe"
$UvInstalledVersion = ""
if (Test-Path -LiteralPath $UvExecutable) {
    $UvInstalledVersion = (& $UvExecutable --version 2>$null)
}

if ($UvInstalledVersion -notmatch "^uv $([regex]::Escape($UvVersion))\b") {
    Write-Step "Installing uv $UvVersion locally"
    $UvArchive = Join-Path $DownloadsDirectory $UvArchiveName
    $UvUri = "https://releases.astral.sh/github/uv/releases/download/$UvVersion/$UvArchiveName"
    Get-VerifiedDownload -Uri $UvUri -Destination $UvArchive -ExpectedSha256 $UvArchiveHash

    $UvStaging = Join-Path $RuntimeDirectory "staging-uv"
    Reset-RuntimeDirectory -Path $UvStaging
    Expand-Archive -LiteralPath $UvArchive -DestinationPath $UvStaging -Force
    $UvCandidate = Get-ChildItem -LiteralPath $UvStaging -Filter "uv.exe" -File -Recurse |
        Select-Object -First 1
    if ($null -eq $UvCandidate) {
        throw "The verified uv archive did not contain uv.exe."
    }

    Reset-RuntimeDirectory -Path $UvDirectory
    Copy-Item -LiteralPath $UvCandidate.FullName -Destination $UvExecutable
    Remove-RuntimePath -Path $UvStaging
} else {
    Write-Host "Using local uv $UvVersion"
}

$env:UV_CACHE_DIR = Join-Path $RuntimeDirectory "uv-cache"
$env:UV_PYTHON_BIN_DIR = Join-Path $RuntimeDirectory "python-bin"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $RuntimeDirectory "python"
$env:UV_PYTHON_NO_REGISTRY = "1"
$env:UV_NO_MODIFY_PATH = "1"

Write-Step "Installing managed Python $PythonVersion locally"
& $UvExecutable python install $PythonVersion --install-dir $env:UV_PYTHON_INSTALL_DIR --no-bin --no-registry
Assert-NativeSuccess -Action "Python installation"

Write-Step "Synchronizing locked Python dependencies"
Push-Location $RepositoryRoot
try {
    & $UvExecutable sync --locked --all-groups --managed-python --python $PythonVersion
    Assert-NativeSuccess -Action "Python dependency synchronization"
} finally {
    Pop-Location
}

$NodeDirectory = Join-Path $RuntimeDirectory "node"
$NodeExecutable = Join-Path $NodeDirectory "node.exe"
$NodeInstalledVersion = ""
if (Test-Path -LiteralPath $NodeExecutable) {
    $NodeInstalledVersion = (& $NodeExecutable --version 2>$null)
}

if ($NodeInstalledVersion -ne "v$NodeVersion") {
    Write-Step "Installing Node.js $NodeVersion locally"
    $NodeArchive = Join-Path $DownloadsDirectory $NodeArchiveName
    $NodeUri = "https://nodejs.org/dist/v$NodeVersion/$NodeArchiveName"
    Get-VerifiedDownload -Uri $NodeUri -Destination $NodeArchive -ExpectedSha256 $NodeArchiveHash

    $NodeStaging = Join-Path $RuntimeDirectory "staging-node"
    Reset-RuntimeDirectory -Path $NodeStaging
    Expand-Archive -LiteralPath $NodeArchive -DestinationPath $NodeStaging -Force
    $NodeCandidate = Get-ChildItem -LiteralPath $NodeStaging -Filter "node.exe" -File -Recurse |
        Select-Object -First 1
    if ($null -eq $NodeCandidate) {
        throw "The verified Node.js archive did not contain node.exe."
    }

    $ExtractedNodeDirectory = $NodeCandidate.Directory.FullName
    Remove-RuntimePath -Path $NodeDirectory
    Move-Item -LiteralPath $ExtractedNodeDirectory -Destination $NodeDirectory
    Remove-RuntimePath -Path $NodeStaging
} else {
    Write-Host "Using local Node.js $NodeVersion"
}

$NpmCli = Join-Path $NodeDirectory "node_modules\npm\bin\npm-cli.js"
$PnpmDirectory = Join-Path $RuntimeDirectory "pnpm"
$PnpmCli = Join-Path $PnpmDirectory "node_modules\pnpm\bin\pnpm.cjs"
$PnpmInstalledVersion = ""
if (Test-Path -LiteralPath $PnpmCli) {
    $PnpmInstalledVersion = (& $NodeExecutable $PnpmCli --version 2>$null)
}

$env:npm_config_cache = Join-Path $RuntimeDirectory "npm-cache"
$env:npm_config_update_notifier = "false"
$env:PNPM_HOME = $PnpmDirectory
$env:PATH = "$NodeDirectory;$PnpmDirectory;$env:PATH"

if ($PnpmInstalledVersion -ne $PnpmVersion) {
    Write-Step "Installing pnpm $PnpmVersion locally"
    Reset-RuntimeDirectory -Path $PnpmDirectory
    & $NodeExecutable $NpmCli install --global --prefix $PnpmDirectory "pnpm@$PnpmVersion" --no-audit --no-fund
    Assert-NativeSuccess -Action "pnpm installation"
} else {
    Write-Host "Using local pnpm $PnpmVersion"
}

if (-not (Test-Path -LiteralPath $PnpmCli)) {
    throw "pnpm was installed but its command could not be found at $PnpmCli."
}

Write-Step "Installing locked frontend dependencies"
$FrontendDirectory = Join-Path $RepositoryRoot "frontend"
$PnpmStore = Join-Path $RuntimeDirectory "pnpm-store"
Push-Location $FrontendDirectory
try {
    & $NodeExecutable $PnpmCli install --frozen-lockfile --store-dir $PnpmStore
    Assert-NativeSuccess -Action "Frontend dependency installation"

    Write-Step "Building the frontend"
    & $NodeExecutable $PnpmCli build
    Assert-NativeSuccess -Action "Frontend build"
} finally {
    Pop-Location
}

Write-Host "`nJerome's Laboratory is installed." -ForegroundColor Green
Write-Host "Run .\start.ps1 (or double-click start.bat) to launch it."
