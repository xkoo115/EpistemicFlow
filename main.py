"""
EpistemicFlow 主应用入口
AI驱动的自动化科研平台
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import settings
from database.session import init_database, close_database, get_db_session
from api.v1 import router as v1_router
from api.stream import router as stream_router


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

# 注册SSE流式路由
app.include_router(
    stream_router,
    prefix=f"{settings.app.api_prefix}",
    tags=["stream"],
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
        "docs": "/docs" if settings.app.debug else None,
        "environment": settings.app.environment.value,
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
