"""
测试配置文件
定义pytest fixtures和测试配置
"""

import asyncio
from typing import AsyncGenerator, Dict, Any
import pytest


from core.config import (
    Settings,
    Environment,
    LLMConfig,
    LLMProvider,
    AppConfig,
    DatabaseConfig,
)
from database.session import DatabaseManager, get_db_session


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """测试配置fixture"""
    # 创建测试配置
    settings = Settings(
        app=AppConfig(
            environment=Environment.TESTING,
            debug=True,
            host="127.0.0.1",
            port=9999,
            cors_origins=["http://localhost:3000"],
            api_prefix="/api",
        ),
        database=DatabaseConfig(
            url="sqlite+aiosqlite:///:memory:",
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
        ),
        llms={
            "test-gpt": LLMConfig(
                provider=LLMProvider.OPENAI,
                api_key="test-api-key",
                base_url="http://localhost:8080",
                model_name="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=1000,
                timeout=30,
            ),
            "test-ollama": LLMConfig(
                provider=LLMProvider.OLLAMA,
                base_url="http://localhost:11434",
                model_name="llama2",
                temperature=0.8,
                timeout=60,
            ),
        },
        default_llm="test-gpt",
        workflow_timeout=300,
        checkpoint_interval=30,
    )

    return settings


@pytest.fixture(scope="session")
async def test_db_manager(test_settings: Settings):
    """测试数据库管理器fixture"""
    from models.workflow_state import Base

    # 临时替换全局settings
    import core.config
    original_settings = core.config.settings
    core.config.settings = test_settings

    # 创建数据库管理器
    db_manager = DatabaseManager()
    db_manager.init_engine()

    # 创建所有表
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield db_manager

    # 清理
    await db_manager.close()
    core.config.settings = original_settings


@pytest.fixture
async def db_session(test_db_manager):
    """数据库会话fixture"""
    async for session in test_db_manager.get_session():
        yield session


@pytest.fixture
def sample_workflow_data() -> Dict[str, Any]:
    """示例工作流数据fixture"""
    return {
        "session_id": "test-session-123",
        "workflow_name": "test-workflow",
        "current_stage": "conception",
        "status": "pending",
        "agent_state": {
            "concept": "测试概念",
            "keywords": ["测试", "AI", "科研"],
            "progress": 0.1,
        },
        "metadata": {
            "creator": "test-user",
            "priority": "high",
            "tags": ["test", "development"],
        },
    }


@pytest.fixture
def sample_llm_config() -> LLMConfig:
    """示例LLM配置fixture"""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="test-api-key-123",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=2000,
        timeout=30,
    )
