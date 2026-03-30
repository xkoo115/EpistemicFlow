@echo off
setlocal

echo ================================================================================
echo                    EpistemicFlow Stop Script
echo ================================================================================
echo.

echo [*] Stopping EpistemicFlow services...
echo.

REM Stop backend service
taskkill /FI "WINDOWTITLE eq EpistemicFlow Backend*" /F >nul 2>&1
if errorlevel 1 (
    echo [i] Backend service not running or already stopped
) else (
    echo [OK] Backend service stopped
)

REM Stop frontend service
taskkill /FI "WINDOWTITLE eq EpistemicFlow Frontend*" /F >nul 2>&1
if errorlevel 1 (
    echo [i] Frontend service not running or already stopped
) else (
    echo [OK] Frontend service stopped
)

REM Stop any remaining uvicorn processes
taskkill /IM "python.exe" /FI "WINDOWTITLE eq *uvicorn*" /F >nul 2>&1

REM Stop any remaining node processes (only Vite related)
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST ^| findstr "PID:"') do (
    for /f "tokens=*" %%j in ('wmic process where "ProcessId=%%i" get CommandLine /value 2^>nul ^| findstr "vite"') do (
        taskkill /PID %%i /F >nul 2>&1
    )
)

echo.
echo [OK] All services stopped
echo.

pause
