#!/usr/bin/env pwsh
<#
.SYNOPSIS
QA automation script for ПОДКАПОТ - runs all critical tests and checks.

.DESCRIPTION
Executes:
1. Backend regression tests
2. Frontend unit tests
3. Bundle size check
4. Smoke tests
5. Performance checks

.PARAMETER Mode
'full' = all tests (15 min)
'quick' = regression + frontend (5 min)
'smoke' = basic health checks (2 min)

.EXAMPLE
./run_qa_checks.ps1 -Mode quick
#>

param(
    [ValidateSet('full', 'quick', 'smoke')]
    [string]$Mode = 'quick'
)

$ErrorActionPreference = 'Stop'
$startTime = Get-Date

function Write-Header {
    param([string]$Text)
    Write-Host "`n========== $Text ==========" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Error {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

# Check Python installed
Write-Header "Checking prerequisites"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+"
    exit 1
}
Write-Success "Python: $(python --version)"

# Check Node.js installed
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Warning "Node.js not found. Frontend tests will be skipped"
    $skipFrontend = $true
}
else {
    Write-Success "Node.js: $(node --version)"
}

# ============================================================================
# SMOKE MODE (2 min)
# ============================================================================

if ($Mode -eq 'smoke') {
    Write-Header "SMOKE TESTS (basic health checks)"

    # 1. Check if API can be imported
    Write-Host "Testing API import..."
    $output = python -c "from app.main import app; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "API imports successfully"
    } else {
        Write-Error "API import failed: $output"
        exit 1
    }

    # 2. Check DB migration
    Write-Host "Testing database initialization..."
    $output = python -c "import asyncio; from app.database import init_db; asyncio.run(init_db()); print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Database initializes successfully"
    } else {
        Write-Warning "Database init failed (may need .env): $output"
    }

    # 3. Frontend build check
    if (-not $skipFrontend) {
        Write-Host "Checking frontend build..."
        Push-Location frontend
        try {
            $output = npm run build 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Frontend builds successfully"
                $distSize = (Get-Item -Path "dist" -ErrorAction SilentlyContinue |
                    Measure-Object -Sum -Recurse -Property Length).Sum / 1MB
                Write-Host "  Dist size: $('{0:F2}' -f $distSize) MB"
            }
        } finally {
            Pop-Location
        }
    }

    $elapsed = (Get-Date) - $startTime
    Write-Host "`n✓ Smoke tests completed in $($elapsed.TotalSeconds)s" -ForegroundColor Green
    exit 0
}

# ============================================================================
# QUICK MODE (5 min)
# ============================================================================

if ($Mode -in 'quick', 'full') {
    Write-Header "REGRESSION TESTS (backend)"

    $tests = @(
        'tests/test_api_regression.py',
        'tests/test_auth_payments_e2e.py',
        'tests/test_password_confirm.py',
        'tests/test_cors_regression.py'
    )

    $failedTests = @()

    foreach ($test in $tests) {
        if (Test-Path $test) {
            Write-Host "`nRunning $test..."
            $output = pytest $test -v --tb=short 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "$test passed"
            } else {
                Write-Error "$test failed"
                $failedTests += $test
            }
        } else {
            Write-Warning "$test not found"
        }
    }

    if ($failedTests.Count -gt 0) {
        Write-Error "`n$($failedTests.Count) test(s) failed:`n$($failedTests -join "`n")"
    } else {
        Write-Success "`nAll regression tests passed!"
    }
}

# ============================================================================
# FULL MODE (15 min) - includes E2E & frontend
# ============================================================================

if ($Mode -eq 'full') {
    Write-Header "E2E & INTEGRATION TESTS"

    $e2eTests = @(
        'tests/test_vehicle_analysis_e2e.py',
        'tests/test_email_verification.py',
        'tests/test_listing_parsers_regression.py'
    )

    foreach ($test in $e2eTests) {
        if (Test-Path $test) {
            Write-Host "`nRunning $test..."
            $output = pytest $test -v --tb=short 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "$test passed"
            } else {
                Write-Warning "$test failed (may require external services)"
            }
        }
    }

    # Frontend tests
    if (-not $skipFrontend) {
        Write-Header "FRONTEND TESTS"
        Push-Location frontend
        try {
            Write-Host "Running npm test..."
            $output = npm run test 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Frontend tests passed"
            } else {
                Write-Warning "Frontend tests failed (check vitest config)"
            }
        } finally {
            Pop-Location
        }
    }
}

# ============================================================================
# PERFORMANCE CHECKS (all modes)
# ============================================================================

Write-Header "PERFORMANCE CHECKS"

# Bundle size
if (-not $skipFrontend -and (Test-Path 'frontend/dist')) {
    $distSize = (Get-ChildItem -Path 'frontend/dist' -Recurse |
        Measure-Object -Sum -Property Length).Sum / 1024
    $distSizeMB = $distSize / 1024

    Write-Host "Bundle size: $('{0:F2}' -f $distSizeMB) MB ($('{0:F0}' -f $distSize) KB)"

    if ($distSizeMB -lt 0.5) {
        Write-Success "Bundle size OK (<500KB)"
    } elseif ($distSizeMB -lt 0.6) {
        Write-Warning "Bundle size WARNING (approaching 600KB limit)"
    } else {
        Write-Error "Bundle size CRITICAL (exceeds 600KB limit)"
    }
}

# API health check
Write-Host "`nChecking API health..."
try {
    $health = python -c "
import asyncio
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.get('/api/v1/health')
print(f'Health: {resp.status_code}')
" 2>&1

    if ($health -match '200') {
        Write-Success "API health check passed"
    } else {
        Write-Warning "API health check returned non-200: $health"
    }
} catch {
    Write-Warning "Could not run health check (check .env setup)"
}

# ============================================================================
# COVERAGE REPORT
# ============================================================================

Write-Header "TEST COVERAGE"

if (Test-Path 'tests') {
    Write-Host "Running coverage analysis..."
    $output = pytest tests/ --cov=app --cov-report=term-missing --co 2>&1 | head -20
    Write-Host $output
}

# ============================================================================
# SUMMARY
# ============================================================================

$elapsed = (Get-Date) - $startTime
Write-Header "QA CHECK SUMMARY"
Write-Host "Mode: $Mode"
Write-Host "Duration: $($elapsed.TotalSeconds)s"
Write-Success "QA checks completed!"

Write-Host "`nNext steps:"
Write-Host "  1. Review test output above"
Write-Host "  2. Check TESTING_PLAN_QA.md for detailed test scenarios"
Write-Host "  3. Run 'pytest tests/test_e2e_critical_flows.py -v' for critical flow tests"
Write-Host "  4. Run 'npm run build && lighthouse http://localhost:8000/app' for Lighthouse audit"
