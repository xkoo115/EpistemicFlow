@echo off
echo Test 1: Current directory
echo %CD%
echo.
echo Test 2: Check .env with relative path
if exist .env (
    echo [OK] .env found with relative path
) else (
    echo [FAIL] .env NOT found with relative path
)
echo.
echo Test 3: Check .env with quoted relative path
if exist ".env" (
    echo [OK] .env found with quoted relative path
) else (
    echo [FAIL] .env NOT found with quoted relative path
)
echo.
echo Test 4: Check .env with full path
if exist d:\EpistemicFlow\.env (
    echo [OK] .env found with full path
) else (
    echo [FAIL] .env NOT found with full path
)
echo.
echo Test 5: List files
dir /b .env* 2>nul
echo.
pause
