"""
全局配置管理模块
基于 pydantic-settings 实现，支持多环境配置和模型不可知性
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """环境枚举"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """大模型提供商枚举"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMConfig(BaseSettings):
    """单个大模型配置"""

    provider: LLMProvider = Field(..., description="模型提供商")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    model_name: str = Field(..., description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大token数")
    timeout: int = Field(30, description="请求超时时间(秒)")

    # 自定义参数，用于存储特定提供商的额外配置
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="额外参数")

    @validator("api_key")
    def validate_api_key(
        cls, v: Optional[str], values: Dict[str, Any]
    ) -> Optional[str]:
        """验证API密钥"""
        provider = values.get("provider")
        if provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC] and not v:
            raise ValueError(f"{provider.value} 需要提供 api_key")
        return v

    class Config:
        env_prefix = "LLM_"
        case_sensitive = False


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    url: str = Field("sqlite+aiosqlite:///./epistemicflow.db", description="数据库URL")
    echo: bool = Field(False, description="是否输出SQL日志")
    pool_size: int = Field(5, description="连接池大小")
    max_overflow: int = Field(10, description="最大溢出连接数")
    pool_timeout: int = Field(30, description="连接池超时时间(秒)")

    class Config:
        env_prefix = "DB_"
        case_sensitive = False


class AppConfig(BaseSettings):
    """应用配置"""

    environment: Environment = Field(Environment.DEVELOPMENT, description="运行环境")
    debug: bool = Field(True, description="调试模式")
    host: str = Field("0.0.0.0", description="服务监听地址")
    port: int = Field(8000, description="服务监听端口")
    cors_origins: List[str] = Field(
        ["http://localhost:3000"], description="CORS允许的源"
    )
    api_prefix: str = Field("/api", description="API前缀")

    class Config:
        env_prefix = "APP_"
        case_sensitive = False


class Settings(BaseSettings):
    """全局设置类，整合所有配置"""

    # 应用配置
    app: AppConfig = Field(default_factory=AppConfig)

    # 数据库配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # 大模型配置列表，支持多模型配置
    llms: Dict[str, LLMConfig] = Field(
        default_factory=dict, description="大模型配置字典"
    )

    # 默认使用的大模型
    default_llm: str = Field("gpt-4", description="默认使用的大模型名称")

    # 工作流配置
    workflow_timeout: int = Field(3600, description="工作流超时时间(秒)")
    checkpoint_interval: int = Field(60, description="检查点保存间隔(秒)")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @validator("llms", pre=True)
    def parse_llms_config(cls, v: Any) -> Dict[str, LLMConfig]:
        """解析大模型配置"""
        if isinstance(v, dict):
            result = {}
            for key, config in v.items():
                if isinstance(config, dict):
                    result[key] = LLMConfig(**config)
                elif isinstance(config, LLMConfig):
                    result[key] = config
            return result
        return v

    def get_llm_config(self, llm_name: Optional[str] = None) -> LLMConfig:
        """获取指定大模型配置"""
        name = llm_name or self.default_llm
        if name not in self.llms:
            raise ValueError(f"未找到大模型配置: {name}")
        return self.llms[name]

    def add_llm_config(self, name: str, config: LLMConfig) -> None:
        """添加大模型配置"""
        self.llms[name] = config


# 全局配置实例
settings = Settings()


def init_settings() -> Settings:
    """初始化配置（可用于重新加载配置）"""
    global settings
    settings = Settings()
    return settings


# 示例配置加载方式
if __name__ == "__main__":
    # 打印当前配置
    print("当前配置:")
    print(f"环境: {settings.app.environment}")
    print(f"数据库URL: {settings.database.url}")
    print(f"可用大模型: {list(settings.llms.keys())}")
    print(f"默认大模型: {settings.default_llm}")
