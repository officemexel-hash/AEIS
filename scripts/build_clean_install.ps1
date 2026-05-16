# Builds a clean AEIS installation package from the current workspace.
# The package is intended for a fresh machine: source code + docs + install
# scripts only, with no runtime databases, logs, evidence, generated projects,
# caches, credentials, or local agent worktrees.

param(
    [string]$OutputRoot = "",
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot "dist"
}

$Stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$PackageName = "aeis-clean-install-$Stamp"
$PackageRoot = Join-Path $OutputRoot $PackageName
$AppRoot = Join-Path $PackageRoot "aeis"

New-Item -ItemType Directory -Force -Path $AppRoot | Out-Null

$AllowedRootDirs = @(
    "src",
    "docs",
    "infra",
    "manifests",
    "operator-mobile",
    "scripts",
    "tools",
    "tests"
)

$AllowedRootFiles = @(
    "README.md",
    "INSTALL.md",
    "HOW_TO_RUN.md",
    "API_REFERENCE.md",
    "CHANGELOG.md",
    "ROLLBACK.md",
    "SKILL_MANIFEST.md",
    "AEIS_SYSTEM_BOOK_2026.md",
    "VERSION",
    "MANIFEST.json"
)

$ExcludedSegments = @(
    ".git",
    ".claude",
    ".ai",
    ".audit_500",
    ".next",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tools",
    ".venv",
    "__pycache__",
    "node_modules",
    "playwright-report",
    "test-results",
    "screenshots",
    "evidence",
    "logs",
    "results",
    "data",
    "secrets",
    "workspace_uploads",
    "output",
    "proofs",
    "dist",
    "build"
)

$ExcludedRelPrefixes = @(
    "docs/v9 audit test",
    "docs/claude_parallel",
    "docs/claude_system_audit",
    "docs/codex_system_audit",
    "docs/system_audit",
    "docs/_drafts",
    "src/logs",
    "src/results",
    "src/sylion-pipeline/data",
    "src/sylion-pipeline/evidence",
    "src/sylion-pipeline/logs",
    "src/sylion-pipeline/results",
    "src/sylion-pipeline/reports",
    "src/sylion-pipeline/secrets",
    "src/sylion-pipeline/workspace_uploads",
    "src/sylion-frontend/evidence",
    "src/sylion-frontend/output",
    "src/sylion-frontend/playwright-report",
    "src/sylion-frontend/screenshots",
    "src/sylion-frontend/test-results"
)

$ExcludedRelPaths = @(
    "src/sylion-pipeline/tests/test_api_keys_ui_v591.py",
    "src/sylion-pipeline/tests/aeis/advisor/_e2e/test_advisor_rest_routes.py"
)

$ExcludedFileNames = @(
    ".env",
    ".env.local",
    ".env.generated",
    ".coverage",
    ".audit_token",
    ".backend.pid",
    ".frontend.pid",
    "hmac_key.bin",
    "openapi_dump.json",
    "final_run.json"
)

$ExcludedExtensions = @(
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".pid",
    ".pyc",
    ".pyo",
    ".zip",
    ".7z",
    ".rar",
    ".gz",
    ".jsonl",
    ".tsbuildinfo"
)

function Get-RelativePath([string]$FullName) {
    $root = $RepoRoot.TrimEnd("\") + "\"
    $rootUri = New-Object System.Uri($root)
    $fileUri = New-Object System.Uri($FullName)
    return [System.Uri]::UnescapeDataString(
        $rootUri.MakeRelativeUri($fileUri).ToString()
    ).Replace("\", "/")
}

function Test-ExcludedRelativePath([string]$RelPath, [string]$LeafName, [bool]$IsDirectory) {
    $rel = $RelPath.Replace("\", "/")
    $segments = @($rel -split "/")
    foreach ($segment in $segments) {
        if ($ExcludedSegments -contains $segment) {
            return $true
        }
    }
    foreach ($prefix in $ExcludedRelPrefixes) {
        if ($rel -eq $prefix -or $rel.StartsWith("$prefix/")) {
            return $true
        }
    }
    if ($ExcludedRelPaths -contains $rel) {
        return $true
    }
    if ($IsDirectory) {
        return $false
    }
    if ($ExcludedFileNames -contains $LeafName) {
        return $true
    }
    $ext = [System.IO.Path]::GetExtension($LeafName).ToLowerInvariant()
    if ($ExcludedExtensions -contains $ext) {
        return $true
    }
    if ($LeafName -like "*.db-shm" -or $LeafName -like "*.db-wal") {
        return $true
    }
    if ($LeafName -like "*.sqlite-shm" -or $LeafName -like "*.sqlite-wal") {
        return $true
    }
    return $false
}

function Copy-FilteredTree([string]$SourceDir) {
    Get-ChildItem -LiteralPath $SourceDir -Force | ForEach-Object {
        $rel = Get-RelativePath $_.FullName
        if ($_.PSIsContainer) {
            if (-not (Test-ExcludedRelativePath $rel $_.Name $true)) {
                Copy-FilteredTree $_.FullName
            }
            return
        }
        if (Test-ExcludedRelativePath $rel $_.Name $false) {
            return
        }
        $dest = Join-Path $AppRoot $rel
        $destDir = Split-Path -Parent $dest
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }
}

foreach ($fileName in $AllowedRootFiles) {
    $src = Join-Path $RepoRoot $fileName
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $AppRoot $fileName) -Force
    }
}

foreach ($dirName in $AllowedRootDirs) {
    $src = Join-Path $RepoRoot $dirName
    if (Test-Path -LiteralPath $src) {
        Copy-FilteredTree $src
    }
}

$RuntimeDirs = @(
    "data",
    "logs",
    "evidence",
    "output",
    "results",
    "workspace_uploads"
)
foreach ($dir in $RuntimeDirs) {
    $runtimePath = Join-Path $AppRoot $dir
    New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
    Set-Content -Encoding ASCII -Path (Join-Path $runtimePath ".gitkeep") -Value ""
}

$frontendEnvExample = Join-Path $AppRoot "src\sylion-frontend\.env.local.example"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $frontendEnvExample) | Out-Null
Set-Content -Encoding ASCII -Path $frontendEnvExample -Value @"
NEXT_PUBLIC_API_URL=http://localhost:8000
"@

Set-Content -Encoding ASCII -Path (Join-Path $AppRoot "install_clean.ps1") -Value @'
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "src\sylion-pipeline"
$Frontend = Join-Path $Root "src\sylion-frontend"
$Venv = Join-Path $Root ".venv"
$EnvFile = Join-Path $Root ".env.generated"

Write-Host "AEIS clean install" -ForegroundColor Cyan
Write-Host "Root: $Root"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python 3.11+ not found in PATH." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js 20+ not found in PATH." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm not found in PATH." -ForegroundColor Red
    exit 1
}

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.11+ is required." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r (Join-Path $Backend "requirements.txt")

Push-Location $Frontend
npm ci
if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.local.example" ".env.local"
}
Pop-Location

foreach ($dir in @("data","logs","evidence","output","results","workspace_uploads")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $dir) | Out-Null
}

if (-not (Test-Path $EnvFile)) {
    $jwt = & $Py -c "import secrets; print(secrets.token_urlsafe(64))"
    $internal = & $Py -c "import secrets; print('internal_' + secrets.token_urlsafe(32))"
    Set-Content -Encoding ASCII -Path $EnvFile -Value @(
        "# Auto-generated by AEIS clean installer",
        "SYLION_JWT_SECRET=$jwt",
        "SYLION_INTERNAL_API_KEY=$internal",
        "SYLION_HOME=$Root",
        "SYLION_AEIS_ENV=dev",
        "SYLION_ENV=dev",
        "SYLION_AUTH_BYPASS=1",
        "SYLION_RBAC_DISABLED=1",
        "SYLION_RATE_LIMIT_DISABLED=1",
        "LITELLM_LOCAL_MODEL_COST_MAP=True",
        "LITELLM_DO_NOT_TRACK=True"
    )
}

Write-Host "Install complete." -ForegroundColor Green
Write-Host "Next: .\start_clean.ps1"
'@

Set-Content -Encoding ASCII -Path (Join-Path $AppRoot "start_clean.ps1") -Value @'
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "src\sylion-pipeline"
$Frontend = Join-Path $Root "src\sylion-frontend"
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env.generated"

if (-not (Test-Path $Py)) {
    Write-Host "Missing venv. Run .\install_clean.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $EnvFile)) {
    Write-Host "Missing .env.generated. Run .\install_clean.ps1 first." -ForegroundColor Red
    exit 1
}

Get-Content $EnvFile | Where-Object { $_ -notmatch "^\s*#" -and $_ -match "=" } | ForEach-Object {
    $k, $v = $_ -split "=", 2
    [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

$backendCmd = @"
`$env:PYTHONPATH='$Backend';
Set-Location '$Backend';
& '$Py' -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 10
"@

$frontendCmd = @"
`$env:NEXT_PUBLIC_API_URL='http://localhost:8000';
Set-Location '$Frontend';
npm run dev
"@

Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-Command",$backendCmd) -WorkingDirectory $Root -WindowStyle Normal
Start-Sleep -Seconds 3
Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-Command",$frontendCmd) -WorkingDirectory $Root -WindowStyle Normal

Write-Host "AEIS starting:" -ForegroundColor Cyan
Write-Host "  API:       http://localhost:8000"
Write-Host "  Dashboard: http://localhost:3000"
'@

Set-Content -Encoding ASCII -Path (Join-Path $AppRoot "verify_clean.ps1") -Value @'
param([switch]$PackageMode)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bad = Get-ChildItem -LiteralPath $Root -Recurse -Force -File | Where-Object {
    $_.Name -match "\.(db|sqlite|sqlite3)$" -or
    $_.Name -match "\.(db|sqlite|sqlite3)-(shm|wal)$" -or
    $_.Name -match "\.log$" -or
    $_.Name -match "\.pid$" -or
    $_.Name -match "\.jsonl$" -or
    (
        $PackageMode -and (
            $_.FullName -match "\\node_modules\\" -or
            $_.FullName -match "\\.next\\" -or
            $_.FullName -match "\\.venv\\" -or
            $_.FullName -match "\\test-results\\"
        )
    )
}
if ($bad) {
    Write-Host "Clean install guard failed:" -ForegroundColor Red
    $bad | Select-Object -First 50 FullName
    exit 2
}
if ($PackageMode) {
    Write-Host "Clean package guard: PASS" -ForegroundColor Green
} else {
    Write-Host "Clean runtime data guard: PASS" -ForegroundColor Green
}
'@

Set-Content -Encoding ASCII -Path (Join-Path $AppRoot "FIRST_RUN_CLEAN.md") -Value @'
# AEIS clean install - first run

This package contains source code and documentation only. It intentionally
does not contain operator data, audit evidence, generated projects, databases,
logs, node_modules, .venv, .env files, API keys, or local model cache.

## Windows quick start

1. Install Python 3.11+ and Node.js 20+.
2. Open PowerShell in this folder.
3. Optional package check before install:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_clean.ps1 -PackageMode
```

4. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_clean.ps1
```

5. Start AEIS:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_clean.ps1
```

6. Open:

```text
http://localhost:3000/onboarding
```

## Runtime data

Runtime data will be created only after first start in:

- data/
- logs/
- evidence/
- output/
- results/
- workspace_uploads/

Do not put real API keys into source files. Put local secrets only into
.env.generated or environment variables.
'@

function Test-ForbiddenArtifacts {
    $bad = Get-ChildItem -LiteralPath $AppRoot -Recurse -Force -File | Where-Object {
        $_.Name -match "\.(db|sqlite|sqlite3)$" -or
        $_.Name -match "\.(db|sqlite|sqlite3)-(shm|wal)$" -or
        $_.Name -match "\.log$" -or
        $_.Name -match "\.pid$" -or
        $_.Name -match "\.jsonl$" -or
        $_.FullName -match "\\node_modules\\" -or
        $_.FullName -match "\\.next\\" -or
        $_.FullName -match "\\test-results\\" -or
        $_.FullName -match "\\playwright-report\\"
    }
    return @($bad)
}

function Test-SecretScan {
    $patterns = @(
        @{ Name = "openai"; Regex = "sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{30,}" },
        @{ Name = "anthropic"; Regex = "sk-ant-[A-Za-z0-9_-]{20,}" },
        @{ Name = "perplexity"; Regex = "pplx-[A-Za-z0-9_-]{20,}" },
        @{ Name = "openrouter"; Regex = "sk-or-v1-[A-Za-z0-9_-]{20,}" },
        @{ Name = "kimi"; Regex = "sk-kimi-[A-Za-z0-9_-]{20,}" },
        @{ Name = "google"; Regex = "AIza[0-9A-Za-z_-]{20,}" }
    )
    $textExt = @(".ps1",".psm1",".py",".ts",".tsx",".js",".jsx",".json",".md",".txt",".toml",".yaml",".yml",".env",".example",".sh",".bat",".css",".html",".mjs")
    $findings = New-Object System.Collections.Generic.List[string]
    Get-ChildItem -LiteralPath $AppRoot -Recurse -Force -File | Where-Object {
        $textExt -contains ([System.IO.Path]::GetExtension($_.Name).ToLowerInvariant())
    } | ForEach-Object {
        $content = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $content) { return }
        foreach ($pattern in $patterns) {
            if ($content -match $pattern.Regex) {
                $rel = $_.FullName.Substring($AppRoot.Length + 1)
                $findings.Add("$($pattern.Name): $rel")
            }
        }
    }
    return @($findings)
}

$forbidden = Test-ForbiddenArtifacts
if ($forbidden.Count -gt 0) {
    $forbidden | Select-Object -ExpandProperty FullName | Set-Content -Encoding UTF8 (Join-Path $PackageRoot "FORBIDDEN_ARTIFACTS.txt")
    throw "Clean package contains forbidden runtime artifacts. See FORBIDDEN_ARTIFACTS.txt"
}

$secretFindings = Test-SecretScan
if ($secretFindings.Count -gt 0) {
    $secretFindings | Set-Content -Encoding UTF8 (Join-Path $PackageRoot "SECRET_SCAN_FINDINGS.txt")
    throw "Clean package secret scan failed. See SECRET_SCAN_FINDINGS.txt"
}

$fileCount = (Get-ChildItem -LiteralPath $AppRoot -Recurse -Force -File | Measure-Object).Count
$manifest = [ordered]@{
    package_name = $PackageName
    generated_at = (Get-Date).ToString("o")
    source_root = $RepoRoot
    app_root = $AppRoot
    file_count = $fileCount
    clean_runtime_artifacts = "PASS"
    secret_scan = "PASS"
    runtime_dirs = $RuntimeDirs
    excluded_segments = $ExcludedSegments
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $PackageRoot "CLEAN_INSTALL_MANIFEST.json")

$zipPath = $null
if (-not $NoZip) {
    $zipPath = Join-Path $OutputRoot "$PackageName.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $AppRoot -DestinationPath $zipPath -Force
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath
    Set-Content -Encoding ASCII -Path (Join-Path $PackageRoot "SHA256SUMS.txt") -Value "$($hash.Hash)  $($zipPath | Split-Path -Leaf)"
}

Write-Host "Clean install package built." -ForegroundColor Green
Write-Host "Folder: $AppRoot"
if ($zipPath) {
    Write-Host "Zip:    $zipPath"
}
Write-Host "Files:  $fileCount"
