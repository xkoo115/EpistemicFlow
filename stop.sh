#!/bin/bash

# ============================================================================
# EpistemicFlow 停止脚本 (Linux/macOS)
# ============================================================================

echo ""
echo "🛑 正在停止 EpistemicFlow 服务..."
echo ""

# 从 PID 文件读取并停止
if [ -f ".backend.pid" ]; then
    BACKEND_PID=$(cat .backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo "✅ 后端服务已停止 (PID: $BACKEND_PID)"
    else
        echo "ℹ️  后端服务未运行"
    fi
    rm -f .backend.pid
else
    echo "ℹ️  未找到后端 PID 文件"
fi

if [ -f ".frontend.pid" ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        echo "✅ 前端服务已停止 (PID: $FRONTEND_PID)"
    else
        echo "ℹ️  前端服务未运行"
    fi
    rm -f .frontend.pid
else
    echo "ℹ️  未找到前端 PID 文件"
fi

# 停止可能残留的进程
pkill -f "uvicorn main:app" 2>/dev/null && echo "✅ 已停止残留的 uvicorn 进程"
pkill -f "vite" 2>/dev/null && echo "✅ 已停止残留的 vite 进程"

echo ""
echo "✅ 所有服务已停止"
echo ""
