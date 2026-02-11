#!/usr/bin/env bash
# Pre-commit checks for wikidata-collector
# Runs all CI checks locally before committing
set -e

echo "🔍 Running pre-commit checks for wikidata-collector..."
echo ""

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

run_check() {
    local step_num=$1
    local step_name=$2
    shift 2
    
    echo -e "${BLUE}${step_num} ${step_name}...${NC}"
    if "$@"; then
        echo -e "${GREEN}✓ ${step_name} passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ ${step_name} failed${NC}"
        echo ""
        exit 1
    fi
}

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install it first.${NC}"
    echo "Visit: https://github.com/astral-sh/uv"
    exit 1
fi

# 1. Type checking
run_check "1️⃣" "Type checking (pyright)" uv run pyright wikidata_collector tests

# 2. Code formatting
run_check "2️⃣" "Code formatting (ruff format)" uv run ruff format wikidata_collector tests

# 3. Linting
run_check "3️⃣" "Linting (ruff check)" uv run ruff check --fix wikidata_collector tests

# 4. Unit tests
run_check "4️⃣" "Unit tests" uv run pytest tests/unit -v

# 5. Integration tests (non-live)
run_check "5️⃣" "Integration tests (non-live)" uv run pytest tests/integration -v -m "not live"

echo ""
echo -e "${GREEN}✅ All pre-commit checks passed!${NC}"
echo -e "${GREEN}You can now commit your changes.${NC}"
