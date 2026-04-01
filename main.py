"""
EpistemicFlow 主应用入口
AI驱动的自动化科研平台

架构版本：agent_framework 原生架构
- 使用 WorkflowBuilder 构建工作流拓扑
- 使用原生 WorkflowEvent 事件流
- 使用 CheckpointStorage 管理状态
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import settings
from database.session import init_database, close_database, get_db_session
from api.v1 import router as v1_router
from api.stream import router as stream_router

# 导入原生架构路由（可选启用）
from api.stream_native import router as stream_native_router
from api.v1.endpoints.workflow_start_native import router as workflow_native_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    Args:
        app: FastAPI应用实例
    """
    # 启动时初始化数据库
    print("初始化数据库...")
    await init_database()

    yield

    # 关闭时清理资源
    print("关闭数据库连接...")
    await close_database()


# 创建FastAPI应用
app = FastAPI(
    title="EpistemicFlow",
    description="AI驱动的自动化科研平台",
    version="0.1.0",
    docs_url="/docs" if settings.app.debug else None,
    redoc_url="/redoc" if settings.app.debug else None,
    lifespan=lifespan,
)

# 配置CORS
if settings.app.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 注册API路由
app.include_router(
    v1_router,
    prefix=f"{settings.app.api_prefix}/v1",
    tags=["v1"],
)

# 注册SSE流式路由（保留旧版以兼容）
app.include_router(
    stream_router,
    prefix=f"{settings.app.api_prefix}",
    tags=["stream"],
)

# 注册原生 SSE 流式路由（新版）
app.include_router(
    stream_native_router,
    prefix=f"{settings.app.api_prefix}/native",
    tags=["stream-native"],
)

# 注册原生工作流路由（新版）
app.include_router(
    workflow_native_router,
    prefix=f"{settings.app.api_prefix}/v1/workflows/native",
    tags=["workflow-native"],
)


@app.get("/")
async def root():
    """根端点

    Returns:
        dict: 欢迎信息
    """
    return {
        "message": "欢迎使用 EpistemicFlow - AI驱动的自动化科研平台",
        "version": "0.1.0",
        "architecture": "agent_framework_native",
        "docs": "/docs" if settings.app.debug else None,
        "environment": settings.app.environment.value,
        "endpoints": {
            "legacy": {
                "start": f"{settings.app.api_prefix}/v1/workflows/start",
                "stream": f"{settings.app.api_prefix}/stream/workflow/{{session_id}}",
            },
            "native": {
                "start": f"{settings.app.api_prefix}/v1/workflows/native/start",
                "stream": f"{settings.app.api_prefix}/native/stream/workflow/{{session_id}}",
                "resume": f"{settings.app.api_prefix}/v1/workflows/native/resume",
                "checkpoints": f"{settings.app.api_prefix}/v1/workflows/native/{{session_id}}/checkpoints",
            },
        },
    }


@app.get("/health")
async def health_check():
    """健康检查端点

    Returns:
        dict: 健康状态
    """
    return {
        "status": "healthy",
        "service": "epistemicflow",
        "timestamp": "2024-01-01T00:00:00Z",  # 实际应用中应使用当前时间
    }


@app.get("/config")
async def get_config():
    """获取当前配置（仅开发环境）

    Returns:
        dict: 配置信息
    """
    if settings.app.environment != Environment.DEVELOPMENT:
        return {"error": "配置信息仅在开发环境可用"}

    return {
        "app": {
            "environment": settings.app.environment.value,
            "debug": settings.app.debug,
            "host": settings.app.host,
            "port": settings.app.port,
            "api_prefix": settings.app.api_prefix,
        },
        "database": {
            "url": settings.database.url,
            "echo": settings.database.echo,
            "pool_size": settings.database.pool_size,
        },
        "llms": {
            name: {
                "provider": config.provider.value,
                "model_name": config.model_name,
                "base_url": config.base_url,
            }
            for name, config in settings.llms.items()
        },
        "default_llm": settings.default_llm,
    }


if __name__ == "__main__":
    """主程序入口"""
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level="debug" if settings.app.debug else "info",
    )
