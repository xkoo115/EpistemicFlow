@echo off
chcp 65001 >nul
setlocal

:: ============================================================================
:: EpistemicFlow 停止脚本 (Windows)
:: ============================================================================

echo.
echo 🛑 正在停止 EpistemicFlow 服务...
echo.

:: 停止后端服务
taskkill /FI "WINDOWTITLE eq EpistemicFlow Backend*" /F >nul 2>&1
if errorlevel 1 (
    echo ℹ️  后端服务未运行或已停止
) else (
    echo ✅ 后端服务已停止
)

:: 停止前端服务
taskkill /FI "WINDOWTITLE eq EpistemicFlow Frontend*" /F >nul 2>&1
if errorlevel 1 (
    echo ℹ️  前端服务未运行或已停止
) else (
    echo ✅ 前端服务已停止
)

:: 停止可能残留的 uvicorn 进程
taskkill /IM "python.exe" /FI "WINDOWTITLE eq *uvicorn*" /F >nul 2>&1

:: 停止可能残留的 node 进程 (仅停止 Vite 相关)
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST ^| findstr "PID:"') do (
    for /f "tokens=*" %%j in ('wmic process where "ProcessId=%%i" get CommandLine /value 2^>nul ^| findstr "vite"') do (
        taskkill /PID %%i /F >nul 2>&1
    )
)

echo.
echo ✅ 所有服务已停止
echo.

pause
