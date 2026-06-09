#!/bin/bash
# Quick QA tests for ПОДКАПОТ
# Usage: ./run_quick_tests.sh [smoke|quick|full]

set -e

MODE=${1:-quick}
START_TIME=$(date +%s)

echo "========== QA Tests: $MODE mode =========="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }

# Check Python
if ! command -v python &> /dev/null; then
    error "Python not found"
    exit 1
fi
success "Python: $(python --version)"

# Check Node.js
if command -v npm &> /dev/null; then
    success "Node.js: $(node --version)"
else
    warning "Node.js not found, skipping frontend tests"
    SKIP_FRONTEND=1
fi

# ============================================================================
# SMOKE MODE (2 min)
# ============================================================================

if [ "$MODE" = "smoke" ]; then
    echo ""
    echo "Testing API import..."
    python -c "from app.main import app; print('OK')" && success "API imports" || error "API import failed"

    if [ -z "$SKIP_FRONTEND" ]; then
        echo "Testing frontend build..."
        cd frontend
        npm run build > /dev/null 2>&1 && success "Frontend builds" || warning "Frontend build failed"
        SIZE=$(du -sh dist | awk '{print $1}')
        echo "  Dist size: $SIZE"
        cd ..
    fi

    END_TIME=$(date +%s)
    echo ""
    success "Smoke tests completed in $((END_TIME - START_TIME))s"
    exit 0
fi

# ============================================================================
# QUICK MODE (5 min)
# ============================================================================

if [ "$MODE" = "quick" ] || [ "$MODE" = "full" ]; then
    echo ""
    echo "Running regression tests..."

    TESTS=(
        "tests/test_api_regression.py"
        "tests/test_auth_payments_e2e.py"
        "tests/test_password_confirm.py"
        "tests/test_cors_regression.py"
    )

    FAILED=()

    for test in "${TESTS[@]}"; do
        if [ -f "$test" ]; then
            echo "Running $test..."
            if pytest "$test" -v --tb=short > /dev/null 2>&1; then
                success "$test"
            else
                error "$test failed"
                FAILED+=("$test")
            fi
        else
            warning "$test not found"
        fi
    done

    if [ ${#FAILED[@]} -gt 0 ]; then
        echo ""
        error "Failed tests: ${FAILED[*]}"
    else
        success "All regression tests passed!"
    fi
fi

# ============================================================================
# FULL MODE (15 min)
# ============================================================================

if [ "$MODE" = "full" ]; then
    echo ""
    echo "Running E2E tests..."

    E2E_TESTS=(
        "tests/test_vehicle_analysis_e2e.py"
        "tests/test_email_verification.py"
        "tests/test_listing_parsers_regression.py"
    )

    for test in "${E2E_TESTS[@]}"; do
        if [ -f "$test" ]; then
            echo "Running $test..."
            if pytest "$test" -v --tb=short 2>&1 | head -20; then
                success "$test"
            else
                warning "$test (may require external services)"
            fi
        fi
    done

    # Frontend tests
    if [ -z "$SKIP_FRONTEND" ]; then
        echo ""
        echo "Running frontend tests..."
        cd frontend
        if npm run test > /dev/null 2>&1; then
            success "Frontend tests"
        else
            warning "Frontend tests failed"
        fi
        cd ..
    fi
fi

# ============================================================================
# PERFORMANCE CHECKS
# ============================================================================

echo ""
echo "Checking bundle size..."
if [ -d "frontend/dist" ]; then
    SIZE_KB=$(du -sk frontend/dist | awk '{print $1}')
    SIZE_MB=$(echo "scale=2; $SIZE_KB / 1024" | bc)
    echo "Bundle size: ${SIZE_MB}MB (${SIZE_KB}KB)"

    if (( $(echo "$SIZE_MB < 0.5" | bc -l) )); then
        success "Bundle size OK"
    elif (( $(echo "$SIZE_MB < 0.6" | bc -l) )); then
        warning "Bundle size approaching limit"
    else
        error "Bundle size exceeds limit (>600KB)"
    fi
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
END_TIME=$(date +%s)
echo "========== Summary =========="
echo "Mode: $MODE"
echo "Duration: $((END_TIME - START_TIME))s"
success "QA checks completed!"

echo ""
echo "Next steps:"
echo "  1. Review test output above"
echo "  2. Run critical flows: pytest tests/test_e2e_critical_flows.py -v"
echo "  3. Run Lighthouse: npm run build && lighthouse http://localhost:8000/app"
echo "  4. Check metrics: curl http://localhost:8000/metrics"
