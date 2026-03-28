# ============================================================================
# EpistemicFlow 生产级 Dockerfile
# 多阶段构建，优化镜像体积和安全性
# ============================================================================

# ----------------------------------------------------------------------------
# 阶段一：构建阶段（Builder）
# 用于安装依赖和编译，不包含在最终镜像中
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖（构建时需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv

# 激活虚拟环境
ENV PATH="/opt/venv/bin:$PATH"

# 复制依赖文件
COPY requirements.txt pyproject.toml ./

# 安装 Python 依赖（包括 PostgreSQL 驱动）
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install "asyncpg>=0.29.0"  # PostgreSQL 异步驱动

# ----------------------------------------------------------------------------
# 阶段二：生产阶段（Runner）
# 最小化镜像，仅包含运行时必需的组件
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS runner

# 设置标签
LABEL maintainer="EpistemicFlow Team" \
      version="0.1.0" \
      description="AI驱动的自动化科研平台"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # 应用配置
    APP_ENVIRONMENT=production \
    APP_DEBUG=false \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# 安装运行时系统依赖
# libpq5: PostgreSQL 客户端库（asyncpg 需要）
# curl: 用于健康检查
# docker-cli: 用于 Docker out of Docker（DooD）沙箱执行
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置 PATH 使用虚拟环境
ENV PATH="/opt/venv/bin:$PATH"

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r epistemicflow && \
    useradd -r -g epistemicflow -d /app -s /sbin/nologin epistemicflow

# 创建应用目录
WORKDIR /app

# 创建必要的目录结构
RUN mkdir -p /app/storage /app/logs /app/data && \
    chown -R epistemicflow:epistemicflow /app

# 复制应用代码
COPY --chown=epistemicflow:epistemicflow . .

# 切换到非 root 用户
USER epistemicflow

# 暴露端口
# FastAPI 默认端口 8000
EXPOSE 8000

# 健康检查
# 使用 curl 检查 /health 端点
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
# 使用 uvicorn 运行 FastAPI 应用
# --host 0.0.0.0: 监听所有网络接口
# --port 8000: 使用端口 8000
# --workers 1: 单 worker（生产环境建议使用 gunicorn + uvicorn worker）
# --no-access-log: 禁用访问日志（减少日志量）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
