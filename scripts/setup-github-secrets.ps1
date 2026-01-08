# Forge V3 - GitHub Secrets Setup Script (PowerShell)
#
# This script sets up the required GitHub secrets for CI/CD.
# Requires: GitHub CLI (gh) authenticated with your account
#
# Usage:
#   .\scripts\setup-github-secrets.ps1
#
# Or set secrets manually at:
#   https://github.com/SunFlash12/ForgeV3/settings/secrets/actions

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Forge V3 - GitHub Secrets Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if gh is installed
$ghPath = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghPath) {
    Write-Host "GitHub CLI (gh) is not installed." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it from: https://cli.github.com/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or set secrets manually at:" -ForegroundColor Yellow
    Write-Host "  https://github.com/SunFlash12/ForgeV3/settings/secrets/actions" -ForegroundColor White
    Write-Host ""
    Write-Host "Required secrets:" -ForegroundColor Yellow
    Write-Host "  - NEO4J_URI" -ForegroundColor White
    Write-Host "  - NEO4J_USERNAME" -ForegroundColor White
    Write-Host "  - NEO4J_PASSWORD" -ForegroundColor White
    exit 1
}

# Check if authenticated
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Please authenticate with GitHub first:" -ForegroundColor Red
    Write-Host "  gh auth login" -ForegroundColor Yellow
    exit 1
}

Write-Host "Enter your Neo4j credentials:" -ForegroundColor Green
Write-Host ""

# Get Neo4j URI
$NEO4J_URI = Read-Host "NEO4J_URI (e.g., neo4j+s://xxx.databases.neo4j.io)"
if ([string]::IsNullOrEmpty($NEO4J_URI)) {
    Write-Host "Error: NEO4J_URI is required" -ForegroundColor Red
    exit 1
}

# Get Neo4j Username
$NEO4J_USERNAME = Read-Host "NEO4J_USERNAME [neo4j]"
if ([string]::IsNullOrEmpty($NEO4J_USERNAME)) {
    $NEO4J_USERNAME = "neo4j"
}

# Get Neo4j Password
$securePassword = Read-Host "NEO4J_PASSWORD" -AsSecureString
$NEO4J_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
if ([string]::IsNullOrEmpty($NEO4J_PASSWORD)) {
    Write-Host "Error: NEO4J_PASSWORD is required" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setting GitHub secrets..." -ForegroundColor Green
Write-Host ""

# Set secrets
$NEO4J_URI | gh secret set NEO4J_URI
Write-Host "  ✓ NEO4J_URI set" -ForegroundColor Green

$NEO4J_USERNAME | gh secret set NEO4J_USERNAME
Write-Host "  ✓ NEO4J_USERNAME set" -ForegroundColor Green

$NEO4J_PASSWORD | gh secret set NEO4J_PASSWORD
Write-Host "  ✓ NEO4J_PASSWORD set" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "All secrets configured successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your CI/CD pipeline is now ready to use." -ForegroundColor White
Write-Host "Push to master or create a PR to trigger the workflow." -ForegroundColor White
