@echo off
REM Forge V3 - Start All Servers (Windows Batch)
REM
REM Starts all three API servers in separate windows:
REM - Cascade API (port 8001)
REM - Compliance API (port 8002)
REM - Virtuals API (port 8003)

echo ============================================================
echo FORGE V3 - Starting API Servers
echo ============================================================

cd /d "%~dp0"

echo Starting Cascade API on port 8001...
start "Forge Cascade API" cmd /k "python -m uvicorn forge.api.app:app --host 0.0.0.0 --port 8001"

echo Starting Compliance API on port 8002...
start "Forge Compliance API" cmd /k "python run_compliance.py"

echo Starting Virtuals API on port 8003...
start "Forge Virtuals API" cmd /k "python run_virtuals.py"

echo.
echo ============================================================
echo All servers starting in separate windows:
echo   - Cascade API:    http://localhost:8001
echo   - Compliance API: http://localhost:8002
echo   - Virtuals API:   http://localhost:8003
echo ============================================================
echo.
echo Close the individual windows to stop each server.
echo.
pause
