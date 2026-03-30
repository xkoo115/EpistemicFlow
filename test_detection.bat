@echo off
echo Test 1: PowerShell Test-Path
powershell -Command "if (Test-Path '.env') { exit 0 } else { exit 1 }"
echo Exit code: %errorlevel%
if errorlevel 1 (
    echo Result: .env NOT found
) else (
    echo Result: .env found
)
echo.
echo Test 2: Direct CMD if exist
if exist ".env" (
    echo Result: .env found
) else (
    echo Result: .env NOT found
)
pause
