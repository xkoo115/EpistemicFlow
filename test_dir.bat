@echo off
echo Test: Using dir command to check .env
dir /b .env >nul 2>&1
echo Exit code: %errorlevel%
if errorlevel 1 (
    echo Result: .env NOT found
) else (
    echo Result: .env found
)
pause
