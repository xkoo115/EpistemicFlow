@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================================
:: EpistemicFlow 一键启动脚本 (Windows)
:: ============================================================================
::
:: 功能说明:
::   1. 检查环境配置文件 (.env)
::   2. 检查并创建 Python 虚拟环境
::   3. 安装后端依赖
::   4. 安装前端依赖
::   5. 初始化数据库
::   6. 启动后端服务 (FastAPI)
::   7. 启动前端服务 (Vite)
::
:: 使用方法:
::   双击运行此脚本，或在命令行执行: start.bat
::
:: 配置说明:
::   首次运行前，请复制 .env.example 为 .env 并配置 API Key
::   必需配置项:
::     - LLM_DEEPSEEK__API_KEY (或其他大模型的 API Key)
::     - LLM_DEEPSEEK__BASE_URL (API 地址)
::     - DEFAULT_LLM (默认使用的模型)
::
:: ============================================================================

echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║                    EpistemicFlow 一键启动脚本                              ║
echo ║                    AI 驱动的自动化科研平台                                  ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: ============================================================================
:: 步骤 1: 检查环境配置文件
:: ============================================================================
echo [步骤 1/7] 检查环境配置文件...
echo.

if not exist ".env" (
    echo ⚠️  未找到 .env 配置文件
    echo.

    if exist ".env.example" (
        echo 📋 正在从 .env.example 创建 .env 配置文件...
        copy ".env.example" ".env" >nul
        echo ✅ 已创建 .env 配置文件
        echo.
        echo ⚠️  请编辑 .env 文件，配置以下必需项:
        echo    - LLM_DEEPSEEK__API_KEY (大模型 API 密钥)
        echo    - LLM_DEEPSEEK__BASE_URL (API 地址)
        echo    - DEFAULT_LLM (默认模型)
        echo.
        echo 按任意键打开 .env 文件进行编辑...
        pause >nul
        notepad ".env"
        echo.
        echo 配置完成后，请重新运行此脚本。
        pause
        exit /b 1
    ) else (
        echo ❌ 未找到 .env.example 模板文件
        echo 请手动创建 .env 文件并配置必要参数
        pause
        exit /b 1
    )
) else (
    echo ✅ 找到 .env 配置文件
)

echo.

:: ============================================================================
:: 步骤 2: 检查 Python 环境
:: ============================================================================
echo [步骤 2/7] 检查 Python 环境...
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python 版本: %PYTHON_VERSION%

:: 检查虚拟环境
if not exist ".venv" (
    echo.
    echo 📦 正在创建 Python 虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo ✅ 虚拟环境创建成功
) else (
    echo ✅ 虚拟环境已存在
)

:: 激活虚拟环境
call .venv\Scripts\activate.bat
echo ✅ 虚拟环境已激活

echo.

:: ============================================================================
:: 步骤 3: 安装后端依赖
:: ============================================================================
echo [步骤 3/7] 安装后端依赖...
echo.

if exist "requirements.txt" (
    echo 📦 正在安装 Python 依赖...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo ⚠️  部分依赖安装失败，尝试继续...
    ) else (
        echo ✅ 后端依赖安装完成
    )
) else (
    echo ⚠️  未找到 requirements.txt
)

echo.

:: ============================================================================
:: 步骤 4: 安装前端依赖
:: ============================================================================
echo [步骤 4/7] 安装前端依赖...
echo.

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=1" %%i in ('node --version 2^>^&1') do set NODE_VERSION=%%i
echo ✅ Node.js 版本: %NODE_VERSION%

:: 检查 npm
for /f "tokens=1" %%i in ('npm --version 2^>^&1') do set NPM_VERSION=%%i
echo ✅ npm 版本: %NPM_VERSION%

cd frontend

if not exist "node_modules" (
    echo 📦 正在安装前端依赖...
    npm install
    if errorlevel 1 (
        echo ❌ 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    echo ✅ 前端依赖安装完成
) else (
    echo ✅ 前端依赖已存在
)

:: 安装 Playwright 浏览器
echo 📦 检查 Playwright 浏览器...
npx playwright install chromium 2>nul
echo ✅ Playwright 准备就绪

cd ..

echo.

:: ============================================================================
:: 步骤 5: 初始化数据库
:: ============================================================================
echo [步骤 5/7] 初始化数据库...
echo.

if exist "scripts\init.py" (
    python scripts\init.py
    if errorlevel 1 (
        echo ⚠️  数据库初始化脚本执行失败，将使用自动初始化
    ) else (
        echo ✅ 数据库初始化完成
    )
) else (
    echo ℹ️  数据库将在首次启动时自动初始化
)

echo.

:: ============================================================================
:: 步骤 6: 启动后端服务
:: ============================================================================
echo [步骤 6/7] 启动后端服务 (FastAPI)...
echo.

echo 🚀 正在启动后端服务...
echo 📍 后端地址: http://localhost:8000
echo 📍 API 文档: http://localhost:8000/docs
echo.

:: 在新窗口启动后端
start "EpistemicFlow Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: 等待后端启动
echo ⏳ 等待后端服务启动...
timeout /t 5 /nobreak >nul

:: 检查后端是否启动
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠️  后端服务可能仍在启动中，请稍候...
    timeout /t 3 /nobreak >nul
) else (
    echo ✅ 后端服务启动成功
)

echo.

:: ============================================================================
:: 步骤 7: 启动前端服务
:: ============================================================================
echo [步骤 7/7] 启动前端服务 (Vite)...
echo.

echo 🚀 正在启动前端服务...
echo 📍 前端地址: http://localhost:5173
echo.

:: 在新窗口启动前端
cd frontend
start "EpistemicFlow Frontend" cmd /k "npm run dev -- --host"
cd ..

:: 等待前端启动
echo ⏳ 等待前端服务启动...
timeout /t 5 /nobreak >nul

echo.

:: ============================================================================
:: 启动完成
:: ============================================================================
echo.
echo ╔══════════════════════════════════════════════════════════════════════════╗
echo ║                          🎉 启动完成！                                     ║
echo ╚══════════════════════════════════════════════════════════════════════════╝
echo.
echo 📍 访问地址:
echo    • 前端界面: http://localhost:5173
echo    • 后端 API: http://localhost:8000
echo    • API 文档: http://localhost:8000/docs
echo    • ReDoc:    http://localhost:8000/redoc
echo.
echo 📝 使用说明:
echo    • 首次使用请确保已在 .env 中配置 API Key
echo    • 按 Ctrl+C 可停止服务
echo    • 关闭命令行窗口也可停止对应服务
echo.
echo 🧪 运行测试:
echo    • E2E 测试: cd frontend ^&^& npm run e2e
echo    • 单元测试: cd frontend ^&^& npm run test
echo.
echo ══════════════════════════════════════════════════════════════════════════
echo.

:: 自动打开浏览器
echo 🌐 正在打开浏览器...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo 按任意键退出此脚本 (服务将继续运行)...
pause >nul

exit /b 0
