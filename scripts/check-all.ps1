# check-all.ps1 - Run all checks locally before pushing (PowerShell)
# Usage: .\scripts\check-all.ps1 [-Quick] [-Fix] [-PythonOnly] [-SkipTests] [-SkipSecurity]

param(
    [switch]$Quick,
    [switch]$Fix,
    [switch]$PythonOnly,
    [switch]$SkipTests,
    [switch]$SkipSecurity,
    [switch]$Help
)

$ErrorActionPreference = "Continue"

if ($Help) {
    Write-Host "Usage: .\scripts\check-all.ps1 [-Quick] [-Fix] [-PythonOnly] [-SkipTests] [-SkipSecurity]"
    Write-Host ""
    Write-Host "Flags:"
    Write-Host "  -Quick         Run Phase 1+2 only (lint, format, types)"
    Write-Host "  -Fix           Auto-fix formatting and lint issues"
    Write-Host "  -PythonOnly    Skip frontend/marketplace checks"
    Write-Host "  -SkipTests     Skip test phase"
    Write-Host "  -SkipSecurity  Skip security phase"
    exit 0
}

# Project paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ForgeDir = Join-Path $ProjectRoot "forge-cascade-v2"
$FrontendDir = Join-Path $ForgeDir "frontend"
$MarketplaceDir = Join-Path $ProjectRoot "marketplace"

$Pass = 0
$Fail = 0
$Skip = 0

function Run-Check {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command
    )

    Write-Host "[CHECK] $Name... " -NoNewline -ForegroundColor Cyan

    $prevDir = Get-Location
    Set-Location $WorkDir

    try {
        $output = Invoke-Expression "$Command 2>&1" | Out-String
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PASS" -ForegroundColor Green
            $script:Pass++
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            $script:Fail++
            Write-Host "---"
            Write-Host $output
            Write-Host "---"
        }
    } catch {
        Write-Host "FAIL" -ForegroundColor Red
        $script:Fail++
        Write-Host "---"
        Write-Host $_.Exception.Message
        Write-Host "---"
    } finally {
        Set-Location $prevDir
    }
}

function Skip-Check {
    param([string]$Name)
    Write-Host "[SKIP] $Name" -ForegroundColor Yellow
    $script:Skip++
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Forge V3 - Comprehensive Check Suite"
Write-Host "============================================"
Write-Host ""

# =========================================================================
# Phase 1: Formatting & Lint
# =========================================================================
Write-Host "Phase 1: Formatting & Lint" -ForegroundColor Cyan
Write-Host "-------------------------------------------"

if ($Fix) {
    Write-Host "[FIX] Auto-fixing ruff lint issues... " -NoNewline -ForegroundColor Cyan
    Push-Location $ForgeDir
    python -m ruff check --fix forge/ 2>&1 | Out-Null
    Write-Host "OK" -ForegroundColor Green
    Write-Host "[FIX] Auto-formatting with ruff... " -NoNewline -ForegroundColor Cyan
    python -m ruff format forge/ tests/ 2>&1 | Out-Null
    Write-Host "OK" -ForegroundColor Green
    Pop-Location
}

Run-Check -Name "Ruff lint" -WorkDir $ForgeDir -Command "python -m ruff check forge/"
Run-Check -Name "Ruff format" -WorkDir $ForgeDir -Command "python -m ruff format --check forge/ tests/"

if (-not $PythonOnly) {
    if (Test-Path (Join-Path $FrontendDir "package.json")) {
        Run-Check -Name "ESLint (frontend)" -WorkDir $FrontendDir -Command "npm run lint"
    } else {
        Skip-Check "ESLint (frontend) - directory not found"
    }
}

Write-Host ""

# =========================================================================
# Phase 2: Type Checking
# =========================================================================
Write-Host "Phase 2: Type Checking" -ForegroundColor Cyan
Write-Host "-------------------------------------------"

Run-Check -Name "MyPy (Python types)" -WorkDir $ForgeDir -Command "python -m mypy forge/ --config-file=pyproject.toml"

if (-not $PythonOnly) {
    if (Test-Path (Join-Path $FrontendDir "tsconfig.json")) {
        Run-Check -Name "TypeScript (frontend)" -WorkDir $FrontendDir -Command "npx tsc --noEmit"
    } else {
        Skip-Check "TypeScript (frontend) - directory not found"
    }

    if (Test-Path (Join-Path $MarketplaceDir "tsconfig.json")) {
        Run-Check -Name "TypeScript (marketplace)" -WorkDir $MarketplaceDir -Command "npx tsc --noEmit"
    } else {
        Skip-Check "TypeScript (marketplace) - directory not found"
    }
}

Write-Host ""

if ($Quick) {
    Write-Host "-Quick mode: Skipping Phase 3 (Tests) and Phase 4 (Security)" -ForegroundColor Yellow
    Write-Host ""
} else {
    # =========================================================================
    # Phase 3: Tests
    # =========================================================================
    if ($SkipTests) {
        Skip-Check "Phase 3: Tests (skipped with -SkipTests)"
    } else {
        Write-Host "Phase 3: Tests" -ForegroundColor Cyan
        Write-Host "-------------------------------------------"

        Run-Check -Name "pytest (unit tests)" -WorkDir $ForgeDir -Command "python -m pytest tests/ -v --tb=short -m 'not integration and not e2e' --cov=forge --cov-report=term-missing --cov-fail-under=70"
    }

    Write-Host ""

    # =========================================================================
    # Phase 4: Security
    # =========================================================================
    if ($SkipSecurity) {
        Skip-Check "Phase 4: Security (skipped with -SkipSecurity)"
    } else {
        Write-Host "Phase 4: Security" -ForegroundColor Cyan
        Write-Host "-------------------------------------------"

        Run-Check -Name "Bandit (security lint)" -WorkDir $ForgeDir -Command "python -m bandit -r forge/ -ll -ii"
        Run-Check -Name "Safety (dependency vulns)" -WorkDir $ForgeDir -Command "safety check -r requirements-base.txt --output text"
    }

    Write-Host ""
}

# =========================================================================
# Summary
# =========================================================================
$Total = $Pass + $Fail + $Skip
Write-Host "============================================"
Write-Host "  Results: " -NoNewline
Write-Host "$Pass passed" -NoNewline -ForegroundColor Green
Write-Host ", " -NoNewline
Write-Host "$Fail failed" -NoNewline -ForegroundColor Red
Write-Host ", " -NoNewline
Write-Host "$Skip skipped" -NoNewline -ForegroundColor Yellow
Write-Host " ($Total total)"
Write-Host "============================================"

if ($Fail -gt 0) {
    Write-Host ""
    Write-Host "Some checks failed. Fix issues before pushing." -ForegroundColor Red
    exit 1
} else {
    Write-Host ""
    Write-Host "All checks passed!" -ForegroundColor Green
    exit 0
}
