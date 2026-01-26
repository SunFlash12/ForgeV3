#!/usr/bin/env bash
# check-all.sh - Run all checks locally before pushing
# Usage: ./scripts/check-all.sh [--quick] [--fix] [--python-only] [--skip-tests] [--skip-security]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse flags
QUICK=false
FIX=false
PYTHON_ONLY=false
SKIP_TESTS=false
SKIP_SECURITY=false

for arg in "$@"; do
  case $arg in
    --quick)       QUICK=true ;;
    --fix)         FIX=true ;;
    --python-only) PYTHON_ONLY=true ;;
    --skip-tests)  SKIP_TESTS=true ;;
    --skip-security) SKIP_SECURITY=true ;;
    --help|-h)
      echo "Usage: $0 [--quick] [--fix] [--python-only] [--skip-tests] [--skip-security]"
      echo ""
      echo "Flags:"
      echo "  --quick         Run Phase 1+2 only (lint, format, types)"
      echo "  --fix           Auto-fix formatting and lint issues"
      echo "  --python-only   Skip frontend/marketplace checks"
      echo "  --skip-tests    Skip test phase"
      echo "  --skip-security Skip security phase"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# Project root (relative to script location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FORGE_DIR="$PROJECT_ROOT/forge-cascade-v2"
FRONTEND_DIR="$FORGE_DIR/frontend"
MARKETPLACE_DIR="$PROJECT_ROOT/marketplace"

PASS=0
FAIL=0
SKIP=0

run_check() {
  local name="$1"
  shift
  printf "${BLUE}[CHECK]${NC} %s... " "$name"
  if "$@" > /dev/null 2>&1; then
    printf "${GREEN}PASS${NC}\n"
    PASS=$((PASS + 1))
  else
    printf "${RED}FAIL${NC}\n"
    FAIL=$((FAIL + 1))
    # Re-run to show errors
    echo "---"
    "$@" 2>&1 || true
    echo "---"
  fi
}

skip_check() {
  local name="$1"
  printf "${YELLOW}[SKIP]${NC} %s\n" "$name"
  SKIP=$((SKIP + 1))
}

echo ""
echo "============================================"
echo "  Forge V3 - Comprehensive Check Suite"
echo "============================================"
echo ""

# =========================================================================
# Phase 1: Formatting & Lint
# =========================================================================
echo "${BLUE}Phase 1: Formatting & Lint${NC}"
echo "-------------------------------------------"

if $FIX; then
  printf "${BLUE}[FIX]${NC} Auto-fixing ruff lint issues... "
  (cd "$FORGE_DIR" && python -m ruff check --fix forge/) > /dev/null 2>&1 && printf "${GREEN}OK${NC}\n" || printf "${YELLOW}PARTIAL${NC}\n"
  printf "${BLUE}[FIX]${NC} Auto-formatting with ruff... "
  (cd "$FORGE_DIR" && python -m ruff format forge/ tests/) > /dev/null 2>&1 && printf "${GREEN}OK${NC}\n" || printf "${RED}FAIL${NC}\n"
fi

run_check "Ruff lint" bash -c "cd '$FORGE_DIR' && python -m ruff check forge/"
run_check "Ruff format" bash -c "cd '$FORGE_DIR' && python -m ruff format --check forge/ tests/"

if ! $PYTHON_ONLY; then
  if [ -d "$FRONTEND_DIR" ] && [ -f "$FRONTEND_DIR/package.json" ]; then
    run_check "ESLint (frontend)" bash -c "cd '$FRONTEND_DIR' && npm run lint"
  else
    skip_check "ESLint (frontend) - directory not found"
  fi
fi

echo ""

# =========================================================================
# Phase 2: Type Checking
# =========================================================================
echo "${BLUE}Phase 2: Type Checking${NC}"
echo "-------------------------------------------"

run_check "MyPy (Python types)" bash -c "cd '$FORGE_DIR' && python -m mypy forge/ --config-file=pyproject.toml"

if ! $PYTHON_ONLY; then
  if [ -d "$FRONTEND_DIR" ] && [ -f "$FRONTEND_DIR/tsconfig.json" ]; then
    run_check "TypeScript (frontend)" bash -c "cd '$FRONTEND_DIR' && npx tsc --noEmit"
  else
    skip_check "TypeScript (frontend) - directory not found"
  fi

  if [ -d "$MARKETPLACE_DIR" ] && [ -f "$MARKETPLACE_DIR/tsconfig.json" ]; then
    run_check "TypeScript (marketplace)" bash -c "cd '$MARKETPLACE_DIR' && npx tsc --noEmit"
  else
    skip_check "TypeScript (marketplace) - directory not found"
  fi
fi

echo ""

if $QUICK; then
  echo "${YELLOW}--quick mode: Skipping Phase 3 (Tests) and Phase 4 (Security)${NC}"
  echo ""
else
  # =========================================================================
  # Phase 3: Tests
  # =========================================================================
  if $SKIP_TESTS; then
    skip_check "Phase 3: Tests (skipped with --skip-tests)"
  else
    echo "${BLUE}Phase 3: Tests${NC}"
    echo "-------------------------------------------"

    run_check "pytest (unit tests)" bash -c "cd '$FORGE_DIR' && python -m pytest tests/ -v --tb=short -m 'not integration and not e2e' --cov=forge --cov-report=term-missing --cov-fail-under=70"
  fi

  echo ""

  # =========================================================================
  # Phase 4: Security
  # =========================================================================
  if $SKIP_SECURITY; then
    skip_check "Phase 4: Security (skipped with --skip-security)"
  else
    echo "${BLUE}Phase 4: Security${NC}"
    echo "-------------------------------------------"

    run_check "Bandit (security lint)" bash -c "cd '$FORGE_DIR' && python -m bandit -r forge/ -ll -ii"
    run_check "Safety (dependency vulns)" bash -c "cd '$FORGE_DIR' && safety check -r requirements-base.txt --output text"
  fi

  echo ""
fi

# =========================================================================
# Summary
# =========================================================================
echo "============================================"
TOTAL=$((PASS + FAIL + SKIP))
echo "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}, ${YELLOW}$SKIP skipped${NC} ($TOTAL total)"
echo "============================================"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "${RED}Some checks failed. Fix issues before pushing.${NC}"
  exit 1
else
  echo ""
  echo "${GREEN}All checks passed!${NC}"
  exit 0
fi
