@echo off
echo Testing .env detection...
echo Current dir: %CD%
echo.
if exist ".env" (
    echo SUCCESS: .env found
) else (
    echo FAIL: .env not found
)
pause
