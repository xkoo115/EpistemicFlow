"""
API v1 路由模块
"""

from fastapi import APIRouter
from .endpoints import workflow, config

# 创建v1路由器
router = APIRouter()

# 注册子路由
router.include_router(workflow.router, prefix="/workflows", tags=["workflows"])
router.include_router(config.router, prefix="/config", tags=["config"])
