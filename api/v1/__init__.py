"""
API v1 路由模块

注册所有 API 端点，包括：
- 工作流管理（CRUD、HITL、Saga）
- 工作流启动与导出
- 配置管理
"""

from fastapi import APIRouter
from .endpoints import workflow, config, workflow_start

# 创建v1路由器
router = APIRouter()

# 注册子路由
router.include_router(workflow.router, prefix="/workflows", tags=["workflows"])
router.include_router(workflow_start.router, prefix="/workflows", tags=["workflows"])
router.include_router(config.router, prefix="/config", tags=["config"])
