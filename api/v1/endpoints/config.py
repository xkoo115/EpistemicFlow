"""
配置API端点
提供配置管理的RESTful接口
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import (
    Settings,
    LLMConfig,
    LLMProvider,
    Environment,
    settings as global_settings,
)


# Pydantic模型定义
class LLMConfigCreate(BaseModel):
    """创建LLM配置请求模型"""

    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    provider: LLMProvider = Field(..., description="提供商")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="基础URL")
    model_name: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    timeout: int = Field(30, description="超时时间(秒)")
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="额外参数")


class LLMConfigResponse(BaseModel):
    """LLM配置响应模型"""

    name: str
    provider: LLMProvider
    model_name: str
    base_url: Optional[str]
    temperature: float
    max_tokens: Optional[int]
    timeout: int
    has_api_key: bool
    extra_params: Dict[str, Any]


class AppConfigResponse(BaseModel):
    """应用配置响应模型"""

    environment: Environment
    debug: bool
    host: str
    port: int
    cors_origins: List[str]
    api_prefix: str


class DatabaseConfigResponse(BaseModel):
    """数据库配置响应模型"""

    url: str
    echo: bool
    pool_size: int
    max_overflow: int
    pool_timeout: int


class ConfigSummary(BaseModel):
    """配置摘要模型"""

    app: AppConfigResponse
    database: DatabaseConfigResponse
    llm_configs: List[str]
    default_llm: str
    workflow_timeout: int
    checkpoint_interval: int


# 创建路由器
router = APIRouter()


@router.get("/summary", response_model=ConfigSummary)
async def get_config_summary() -> ConfigSummary:
    """获取配置摘要

    Returns:
        ConfigSummary: 配置摘要
    """
    return ConfigSummary(
        app=AppConfigResponse(
            environment=global_settings.app.environment,
            debug=global_settings.app.debug,
            host=global_settings.app.host,
            port=global_settings.app.port,
            cors_origins=global_settings.app.cors_origins,
            api_prefix=global_settings.app.api_prefix,
        ),
        database=DatabaseConfigResponse(
            url=global_settings.database.url,
            echo=global_settings.database.echo,
            pool_size=global_settings.database.pool_size,
            max_overflow=global_settings.database.max_overflow,
            pool_timeout=global_settings.database.pool_timeout,
        ),
        llm_configs=list(global_settings.llms.keys()),
        default_llm=global_settings.default_llm,
        workflow_timeout=global_settings.workflow_timeout,
        checkpoint_interval=global_settings.checkpoint_interval,
    )


@router.get("/llms", response_model=List[LLMConfigResponse])
async def get_llm_configs() -> List[LLMConfigResponse]:
    """获取所有LLM配置

    Returns:
        List[LLMConfigResponse]: LLM配置列表
    """
    configs = []
    for name, config in global_settings.llms.items():
        configs.append(
            LLMConfigResponse(
                name=name,
                provider=config.provider,
                model_name=config.model_name,
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
                has_api_key=config.api_key is not None,
                extra_params=config.extra_params,
            )
        )

    return configs


@router.get("/llms/{name}", response_model=LLMConfigResponse)
async def get_llm_config(name: str) -> LLMConfigResponse:
    """获取指定LLM配置

    Args:
        name: 配置名称

    Returns:
        LLMConfigResponse: LLM配置
    """
    try:
        config = global_settings.get_llm_config(name)

        return LLMConfigResponse(
            name=name,
            provider=config.provider,
            model_name=config.model_name,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            has_api_key=config.api_key is not None,
            extra_params=config.extra_params,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/llms", response_model=LLMConfigResponse)
async def create_llm_config(
    config_data: LLMConfigCreate,
) -> LLMConfigResponse:
    """创建LLM配置

    Args:
        config_data: 配置数据

    Returns:
        LLMConfigResponse: 创建的LLM配置
    """
    try:
        # 创建配置对象
        llm_config = LLMConfig(
            provider=config_data.provider,
            api_key=config_data.api_key,
            base_url=config_data.base_url,
            model_name=config_data.model_name,
            temperature=config_data.temperature,
            max_tokens=config_data.max_tokens,
            timeout=config_data.timeout,
            extra_params=config_data.extra_params,
        )

        # 添加到全局配置
        global_settings.add_llm_config(config_data.name, llm_config)

        return LLMConfigResponse(
            name=config_data.name,
            provider=llm_config.provider,
            model_name=llm_config.model_name,
            base_url=llm_config.base_url,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            timeout=llm_config.timeout,
            has_api_key=llm_config.api_key is not None,
            extra_params=llm_config.extra_params,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建LLM配置失败: {str(e)}")


@router.put("/llms/{name}/default")
async def set_default_llm(name: str) -> Dict[str, Any]:
    """设置默认LLM

    Args:
        name: 配置名称

    Returns:
        Dict[str, Any]: 操作结果
    """
    try:
        # 验证配置是否存在
        global_settings.get_llm_config(name)

        # 更新默认配置
        global_settings.default_llm = name

        return {
            "message": "默认LLM设置成功",
            "default_llm": name,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置默认LLM失败: {str(e)}")


@router.get("/environment")
async def get_environment() -> Dict[str, Any]:
    """获取当前环境信息

    Returns:
        Dict[str, Any]: 环境信息
    """
    return {
        "environment": global_settings.app.environment.value,
        "debug": global_settings.app.debug,
        "is_development": global_settings.app.environment == Environment.DEVELOPMENT,
        "is_production": global_settings.app.environment == Environment.PRODUCTION,
        "is_testing": global_settings.app.environment == Environment.TESTING,
    }


@router.get("/health/detailed")
async def get_detailed_health() -> Dict[str, Any]:
    """获取详细健康状态

    Returns:
        Dict[str, Any]: 健康状态详情
    """
    from datetime import datetime

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "epistemicflow",
        "version": "0.1.0",
        "config": {
            "environment": global_settings.app.environment.value,
            "llm_count": len(global_settings.llms),
            "database_url": global_settings.database.url,
        },
        "checks": {
            "config_loaded": True,
            "llm_configs_available": len(global_settings.llms) > 0,
            "default_llm_set": global_settings.default_llm in global_settings.llms,
        },
    }


@router.post("/reload")
async def reload_config() -> Dict[str, Any]:
    """重新加载配置

    Returns:
        Dict[str, Any]: 重新加载结果
    """
    try:
        from core.config import init_settings

        # 重新加载配置
        new_settings = init_settings()

        return {
            "message": "配置重新加载成功",
            "environment": new_settings.app.environment.value,
            "llm_count": len(new_settings.llms),
            "default_llm": new_settings.default_llm,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")
