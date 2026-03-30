@echo off
setlocal enabledelayedexpansion

echo ================================================================================
echo                    EpistemicFlow Quick Start Script
echo                    AI-Powered Research Automation Platform
echo ================================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Current directory: %CD%
echo.

echo [Step 1/7] Checking environment configuration...
echo.

REM Skip .env check since it already exists
echo [OK] .env configuration file found

echo.
echo [Step 2/7] Checking Python environment...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python not detected, please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python version: %PYTHON_VERSION%

if not exist ".venv" (
    echo.
    echo [*] Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [X] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated

echo.
echo [Step 3/7] Installing backend dependencies...
echo.

if exist "requirements.txt" (
    echo [*] Installing Python dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [!] Some dependencies failed to install, trying to continue...
    ) else (
        echo [OK] Backend dependencies installed
    )
) else (
    echo [!] requirements.txt not found
)

echo.
echo [Step 4/7] Installing frontend dependencies...
echo.

node --version >nul 2>&1
if errorlevel 1 (
    echo [X] Node.js not detected, please install Node.js 18+
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=1" %%i in ('node --version 2^>^&1') do set NODE_VERSION=%%i
echo [OK] Node.js version: %NODE_VERSION%

for /f "tokens=1" %%i in ('npm --version 2^>^&1') do set NPM_VERSION=%%i
echo [OK] npm version: %NPM_VERSION%

cd frontend

if not exist "node_modules" (
    echo [*] Installing frontend dependencies...
    npm install
    if errorlevel 1 (
        echo [X] Frontend dependencies installation failed
        cd ..
        pause
        exit /b 1
    )
    echo [OK] Frontend dependencies installed
) else (
    echo [OK] Frontend dependencies already exist
)

cd ..

echo.
echo [Step 5/7] Initializing database...
echo.

if exist "scripts\init.py" (
    python scripts\init.py
    if errorlevel 1 (
        echo [!] Database initialization script failed, will use auto-initialization
    ) else (
        echo [OK] Database initialized
    )
) else (
    echo [i] Database will be auto-initialized on first startup
)

echo.
echo [Step 6/7] Starting backend service (FastAPI)...
echo.

echo [*] Starting backend service...
echo [i] Backend URL: http://localhost:8000
echo [i] API Docs: http://localhost:8000/docs
echo.

start "EpistemicFlow Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [*] Waiting for backend service to start...
timeout /t 5 /nobreak >nul

curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [!] Backend service may still be starting, please wait...
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Backend service started successfully
)

echo.
echo [Step 7/7] Starting frontend service (Vite)...
echo.

echo [*] Starting frontend service...
echo [i] Frontend URL: http://localhost:5173
echo.

cd frontend
start "EpistemicFlow Frontend" cmd /k "npm run dev -- --host"
cd ..

echo [*] Waiting for frontend service to start...
timeout /t 5 /nobreak >nul

echo.
echo ================================================================================
echo                          *** Startup Complete! ***
echo ================================================================================
echo.
echo [i] Access URLs:
echo    - Frontend:  http://localhost:5173
echo    - Backend:   http://localhost:8000
echo    - API Docs:  http://localhost:8000/docs
echo    - ReDoc:     http://localhost:8000/redoc
echo.
echo [i] Instructions:
echo    - For first-time use, ensure API Key is configured in .env
echo    - Press Ctrl+C to stop services
echo    - Closing command windows will also stop corresponding services
echo.
echo [i] Running E2E tests (optional):
echo    - First time: npx playwright install chromium
echo    - Run tests:  cd frontend ^&^& npm run e2e
echo.
echo ================================================================================
echo.

echo [*] Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo Press any key to exit this script (services will continue running)...
pause >nul

exit /b 0
