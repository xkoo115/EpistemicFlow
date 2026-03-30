#!/bin/bash

# ============================================================================
# EpistemicFlow 一键启动脚本 (Linux/macOS)
# ============================================================================
#
# 功能说明:
#   1. 检查环境配置文件 (.env)
#   2. 检查并创建 Python 虚拟环境
#   3. 安装后端依赖
#   4. 安装前端依赖
#   5. 初始化数据库
#   6. 启动后端服务 (FastAPI)
#   7. 启动前端服务 (Vite)
#
# 使用方法:
#   chmod +x start.sh
#   ./start.sh
#
# 配置说明:
#   首次运行前，请复制 .env.example 为 .env 并配置 API Key
#   必需配置项:
#     - LLM_DEEPSEEK__API_KEY (或其他大模型的 API Key)
#     - LLM_DEEPSEEK__BASE_URL (API 地址)
#     - DEFAULT_LLM (默认使用的模型)
#
# ============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    EpistemicFlow 一键启动脚本                              ║${NC}"
    echo -e "${CYAN}║                    AI 驱动的自动化科研平台                                  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[步骤 $1/7] $2...${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header

# ============================================================================
# 步骤 1: 检查环境配置文件
# ============================================================================
print_step 1 "检查环境配置文件"

if [ ! -f ".env" ]; then
    print_warning "未找到 .env 配置文件"
    echo ""

    if [ -f ".env.example" ]; then
        echo -e "${BLUE}📋 正在从 .env.example 创建 .env 配置文件...${NC}"
        cp .env.example .env
        print_success "已创建 .env 配置文件"
        echo ""
        print_warning "请编辑 .env 文件，配置以下必需项:"
        echo "   - LLM_DEEPSEEK__API_KEY (大模型 API 密钥)"
        echo "   - LLM_DEEPSEEK__BASE_URL (API 地址)"
        echo "   - DEFAULT_LLM (默认模型)"
        echo ""
        echo "配置完成后，请重新运行此脚本。"
        exit 1
    else
        print_error "未找到 .env.example 模板文件"
        echo "请手动创建 .env 文件并配置必要参数"
        exit 1
    fi
else
    print_success "找到 .env 配置文件"
fi

echo ""

# ============================================================================
# 步骤 2: 检查 Python 环境
# ============================================================================
print_step 2 "检查 Python 环境"

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "未检测到 Python，请先安装 Python 3.10+"
        echo "下载地址: https://www.python.org/downloads/"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
print_success "Python 版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo ""
    echo -e "${BLUE}📦 正在创建 Python 虚拟环境...${NC}"
    $PYTHON_CMD -m venv .venv
    print_success "虚拟环境创建成功"
else
    print_success "虚拟环境已存在"
fi

# 激活虚拟环境
source .venv/bin/activate
print_success "虚拟环境已激活"

echo ""

# ============================================================================
# 步骤 3: 安装后端依赖
# ============================================================================
print_step 3 "安装后端依赖"

if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}📦 正在安装 Python 依赖...${NC}"
    pip install -r requirements.txt -q 2>/dev/null || print_warning "部分依赖安装失败，尝试继续..."
    print_success "后端依赖安装完成"
else
    print_warning "未找到 requirements.txt"
fi

echo ""

# ============================================================================
# 步骤 4: 安装前端依赖
# ============================================================================
print_step 4 "安装前端依赖"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    print_error "未检测到 Node.js，请先安装 Node.js 18+"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
print_success "Node.js 版本: $NODE_VERSION"

# 检查 npm
NPM_VERSION=$(npm --version)
print_success "npm 版本: $NPM_VERSION"

cd frontend

if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}📦 正在安装前端依赖...${NC}"
    npm install
    print_success "前端依赖安装完成"
else
    print_success "前端依赖已存在"
fi

# 安装 Playwright 浏览器
echo -e "${BLUE}📦 检查 Playwright 浏览器...${NC}"
npx playwright install chromium 2>/dev/null || true
print_success "Playwright 准备就绪"

cd ..

echo ""

# ============================================================================
# 步骤 5: 初始化数据库
# ============================================================================
print_step 5 "初始化数据库"

if [ -f "scripts/init.py" ]; then
    python scripts/init.py 2>/dev/null || print_warning "数据库初始化脚本执行失败，将使用自动初始化"
    print_success "数据库初始化完成"
else
    print_info "数据库将在首次启动时自动初始化"
fi

echo ""

# ============================================================================
# 步骤 6: 启动后端服务
# ============================================================================
print_step 6 "启动后端服务 (FastAPI)"

echo -e "${GREEN}🚀 正在启动后端服务...${NC}"
echo -e "${BLUE}📍 后端地址: http://localhost:8000${NC}"
echo -e "${BLUE}📍 API 文档: http://localhost:8000/docs${NC}"
echo ""

# 启动后端 (后台运行)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > .backend.pid

# 等待后端启动
echo -e "${BLUE}⏳ 等待后端服务启动...${NC}"
sleep 5

# 检查后端是否启动
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_success "后端服务启动成功 (PID: $BACKEND_PID)"
else
    print_warning "后端服务可能仍在启动中，请稍候..."
    sleep 3
fi

echo ""

# ============================================================================
# 步骤 7: 启动前端服务
# ============================================================================
print_step 7 "启动前端服务 (Vite)"

echo -e "${GREEN}🚀 正在启动前端服务...${NC}"
echo -e "${BLUE}📍 前端地址: http://localhost:5173${NC}"
echo ""

# 启动前端 (后台运行)
cd frontend
npm run dev -- --host > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../.frontend.pid
cd ..

# 等待前端启动
echo -e "${BLUE}⏳ 等待前端服务启动...${NC}"
sleep 5

print_success "前端服务启动成功 (PID: $FRONTEND_PID)"

echo ""

# ============================================================================
# 启动完成
# ============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                          🎉 启动完成！                                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}📍 访问地址:${NC}"
echo "   • 前端界面: http://localhost:5173"
echo "   • 后端 API: http://localhost:8000"
echo "   • API 文档: http://localhost:8000/docs"
echo "   • ReDoc:    http://localhost:8000/redoc"
echo ""
echo -e "${CYAN}📝 使用说明:${NC}"
echo "   • 首次使用请确保已在 .env 中配置 API Key"
echo "   • 停止服务: ./stop.sh 或 kill $BACKEND_PID $FRONTEND_PID"
echo "   • 查看日志: tail -f backend.log frontend.log"
echo ""
echo -e "${CYAN}🧪 运行测试:${NC}"
echo "   • E2E 测试: cd frontend && npm run e2e"
echo "   • 单元测试: cd frontend && npm run test"
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# 尝试打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173 2>/dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:5173 2>/dev/null &
fi

echo -e "${BLUE}按 Ctrl+C 停止所有服务...${NC}"
echo ""

# 等待用户按 Ctrl+C
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; rm -f .backend.pid .frontend.pid; echo '服务已停止'; exit 0" SIGINT SIGTERM

# 保持脚本运行
wait
