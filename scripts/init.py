"""
EpistemicFlow 初始化脚本
用于快速初始化和验证项目配置
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def init_database():
    """初始化数据库"""
    try:
        from database.session import init_database as init_db

        await init_db()
        print("✅ 数据库初始化成功")
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False


async def test_config():
    """测试配置加载"""
    try:
        from core.config import settings

        print("📋 配置信息:")
        print(f"  环境: {settings.app.environment}")
        print(f"  调试模式: {settings.app.debug}")
        print(f"  数据库URL: {settings.database.url}")
        print(f"  可用大模型: {list(settings.llms.keys())}")
        print(f"  默认大模型: {settings.default_llm}")

        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


async def test_database_connection():
    """测试数据库连接"""
    try:
        from database.session import db_manager
        from sqlalchemy import text

        db_manager.init_engine()

        async with db_manager.engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar()

            if value == 1:
                print("✅ 数据库连接测试成功")
                return True
            else:
                print("❌ 数据库连接测试失败")
                return False

    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        return False


async def create_sample_data():
    """创建示例数据"""
    try:
        from database.session import db_manager
        from database.repositories.workflow_state_repository import (
            WorkflowStateRepository,
        )
        from models.workflow_state import WorkflowStage, WorkflowStatus

        db_manager.init_engine()

        async with db_manager.session_factory() as session:
            repository = WorkflowStateRepository(session)

            # 创建示例工作流状态
            workflow_state = await repository.create(
                session_id="sample-session-001",
                workflow_name="sample-research-workflow",
                current_stage=WorkflowStage.CONCEPTION,
                status=WorkflowStatus.PENDING,
                agent_state={
                    "concept": "AI驱动的科研自动化",
                    "keywords": ["AI", "科研", "自动化"],
                    "progress": 0.1,
                },
                metadata={
                    "creator": "system",
                    "description": "示例研究工作流",
                    "tags": ["sample", "test"],
                },
            )

            print(f"✅ 示例数据创建成功 (ID: {workflow_state.id})")
            return True

    except Exception as e:
        print(f"❌ 示例数据创建失败: {e}")
        return False


async def run_all_checks():
    """运行所有检查"""
    print("🚀 开始 EpistemicFlow 初始化检查...")
    print("=" * 50)

    checks = [
        ("配置加载", test_config),
        ("数据库初始化", init_database),
        ("数据库连接", test_database_connection),
        ("示例数据", create_sample_data),
    ]

    results = []
    for check_name, check_func in checks:
        print(f"\n🔍 正在检查: {check_name}")
        result = await check_func()
        results.append((check_name, result))

    print("\n" + "=" * 50)
    print("📊 检查结果汇总:")

    all_passed = True
    for check_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {check_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有检查通过！EpistemicFlow 已准备就绪。")
        print("\n下一步:")
        print("  1. 启动服务: uvicorn main:app --reload")
        print("  2. 访问文档: http://localhost:8000/docs")
        print("  3. 运行测试: pytest")
    else:
        print("⚠️  部分检查失败，请检查错误信息。")

    return all_passed


def main():
    """主函数"""
    try:
        asyncio.run(run_all_checks())
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
    except Exception as e:
        print(f"\n💥 初始化过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
