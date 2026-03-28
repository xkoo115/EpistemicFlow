"""
配置管理测试
测试全局配置管理的功能
"""

import os
from typing import Dict, Any
import pytest
from pydantic import ValidationError

from core.config import (
    Settings,
    AppConfig,
    DatabaseConfig,
    LLMConfig,
    LLMProvider,
    Environment,
    init_settings,
)


class TestLLMConfig:
    """LLM配置测试"""

    def test_llm_config_creation(self):
        """测试LLM配置创建"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            timeout=30,
        )

        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "test-key"
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.timeout == 30

    def test_llm_config_defaults(self):
        """测试LLM配置默认值"""
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model_name="llama2",
        )

        assert config.provider == LLMProvider.OLLAMA
        assert config.api_key is None
        assert config.base_url is None
        assert config.model_name == "llama2"
        assert config.temperature == 0.7
        assert config.max_tokens is None
        assert config.timeout == 30

    def test_llm_config_validation(self):
        """测试LLM配置验证"""
        # 测试温度范围验证
        with pytest.raises(ValidationError):
            LLMConfig(
                provider=LLMProvider.OPENAI,
                model_name="gpt-4",
                temperature=2.5,  # 超出范围
            )

        # 测试必填字段验证
        with pytest.raises(ValidationError):
            LLMConfig(
                provider=LLMProvider.OPENAI,
                model_name="gpt-4",
                api_key=None,  # OpenAI需要api_key
            )

    def test_llm_config_extra_params(self):
        """测试LLM配置额外参数"""
        config = LLMConfig(
            provider=LLMProvider.CUSTOM,
            model_name="custom-model",
            extra_params={
                "custom_param": "value",
                "max_context_length": 8192,
            },
        )

        assert config.extra_params["custom_param"] == "value"
        assert config.extra_params["max_context_length"] == 8192


class TestAppConfig:
    """应用配置测试"""

    def test_app_config_creation(self):
        """测试应用配置创建"""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            debug=True,
            host="0.0.0.0",
            port=8000,
            cors_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            api_prefix="/api",
        )

        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert len(config.cors_origins) == 2
        assert config.api_prefix == "/api"

    def test_app_config_defaults(self):
        """测试应用配置默认值"""
        config = AppConfig()

        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.cors_origins == ["http://localhost:3000"]
        assert config.api_prefix == "/api"


class TestDatabaseConfig:
    """数据库配置测试"""

    def test_database_config_creation(self):
        """测试数据库配置创建"""
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@localhost/db",
            echo=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=60,
        )

        assert config.url == "postgresql+asyncpg://user:pass@localhost/db"
        assert config.echo is True
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.pool_timeout == 60

    def test_database_config_defaults(self):
        """测试数据库配置默认值"""
        config = DatabaseConfig()

        assert config.url == "sqlite+aiosqlite:///./epistemicflow.db"
        assert config.echo is False
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30


class TestSettings:
    """全局设置测试"""

    def test_settings_creation(self, sample_llm_config: LLMConfig):
        """测试全局设置创建"""
        settings = Settings(
            app=AppConfig(environment=Environment.PRODUCTION, debug=False),
            database=DatabaseConfig(url="sqlite:///test.db"),
            llms={"test-model": sample_llm_config},
            default_llm="test-model",
            workflow_timeout=1800,
            checkpoint_interval=120,
        )

        assert settings.app.environment == Environment.PRODUCTION
        assert settings.app.debug is False
        assert settings.database.url == "sqlite:///test.db"
        assert "test-model" in settings.llms
        assert settings.default_llm == "test-model"
        assert settings.workflow_timeout == 1800
        assert settings.checkpoint_interval == 120

    def test_settings_defaults(self):
        """测试全局设置默认值"""
        settings = Settings()

        assert settings.app.environment == Environment.DEVELOPMENT
        assert settings.app.debug is True
        assert settings.database.url == "sqlite+aiosqlite:///./epistemicflow.db"
        assert settings.llms == {}
        assert settings.default_llm == "gpt-4"
        assert settings.workflow_timeout == 3600
        assert settings.checkpoint_interval == 60

    def test_get_llm_config(self, sample_llm_config: LLMConfig):
        """测试获取LLM配置"""
        settings = Settings(
            llms={
                "gpt-4": sample_llm_config,
                "llama2": LLMConfig(
                    provider=LLMProvider.OLLAMA,
                    model_name="llama2",
                ),
            },
            default_llm="gpt-4",
        )

        # 测试获取默认配置
        config = settings.get_llm_config()
        assert config.model_name == "gpt-4"

        # 测试获取指定配置
        config = settings.get_llm_config("llama2")
        assert config.model_name == "llama2"
        assert config.provider == LLMProvider.OLLAMA

        # 测试获取不存在的配置
        with pytest.raises(ValueError, match="未找到大模型配置"):
            settings.get_llm_config("non-existent")

    def test_add_llm_config(self):
        """测试添加LLM配置"""
        settings = Settings()

        # 初始为空
        assert settings.llms == {}

        # 添加配置
        new_config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-3.5-turbo",
            api_key="new-key",
        )
        settings.add_llm_config("gpt-3.5", new_config)

        # 验证添加成功
        assert "gpt-3.5" in settings.llms
        assert settings.llms["gpt-3.5"].model_name == "gpt-3.5-turbo"

    def test_init_settings(self):
        """测试初始化设置"""
        # 保存原始设置
        original_settings = Settings()

        # 重新初始化
        new_settings = init_settings()

        # 验证是新实例
        assert new_settings is not original_settings
        assert isinstance(new_settings, Settings)


class TestEnvironmentVariables:
    """环境变量测试"""

    def test_env_var_loading(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量加载"""
        # 设置环境变量
        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("DB_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setenv("LLM_GPT4__PROVIDER", "openai")
        monkeypatch.setenv("LLM_GPT4__API_KEY", "env-key")
        monkeypatch.setenv("LLM_GPT4__MODEL_NAME", "gpt-4")

        # 重新加载设置
        settings = init_settings()

        # 验证环境变量生效
        assert settings.app.environment == Environment.PRODUCTION
        assert settings.app.debug is False
        assert settings.database.url == "postgresql://test:test@localhost/test"
        assert "gpt4" in settings.llms
        assert settings.llms["gpt4"].api_key == "env-key"
        assert settings.llms["gpt4"].model_name == "gpt-4"
