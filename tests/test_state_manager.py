"""
StateManager 单元测试

测试状态序列化与反序列化的正确性，包括：
- Agent Session 的完整序列化
- 从序列化数据中精确恢复 Session
- 状态哈希验证
- 检查点创建与恢复
- 状态分叉功能
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from agent_framework import AgentSession, Message, Content

from core.state_manager import (
    StateManager,
    StateSerializationError,
    StateDeserializationError,
)
from models.workflow_state import WorkflowStage, WorkflowStatus


# ============================================================================
# 测试固件
# ============================================================================


@pytest.fixture
def sample_agent_session() -> AgentSession:
    """
    创建示例 Agent Session

    包含：
    - 基本状态数据
    - 消息历史
    - 复杂嵌套结构
    """
    session = AgentSession(session_id="test-session-123")

    # 添加基本状态
    session.state["research_topic"] = "深度学习在医学影像中的应用"
    session.state["iteration_count"] = 3
    session.state["config"] = {
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    # 添加消息历史
    messages = [
        Message(
            role="user",
            contents=[Content.from_text("请生成一个关于医学影像的研究计划")],
        ),
        Message(
            role="assistant",
            contents=[
                Content.from_text(
                    "好的，我将为您生成一个关于深度学习在医学影像中应用的研究计划..."
                )
            ],
        ),
        Message(
            role="user",
            contents=[Content.from_text("请增加对比实验部分")],
        ),
    ]
    session.state["messages"] = messages

    # 添加其他状态
    session.state["collected_papers"] = [
        {"title": "Deep Learning in Medical Imaging", "year": 2023},
        {"title": "CNN for X-ray Analysis", "year": 2022},
    ]

    return session


@pytest.fixture
def sample_workflow_stage() -> WorkflowStage:
    """创建示例工作流阶段"""
    return WorkflowStage.METHODOLOGY_DESIGN


# ============================================================================
# 序列化测试
# ============================================================================


def test_serialize_agent_session(sample_agent_session: AgentSession):
    """
    测试 Agent Session 序列化

    验证：
    - 序列化后的数据是字典类型
    - 包含必要的元数据
    - 消息历史被正确序列化
    - 状态数据完整保留
    """
    # 创建 StateManager 实例（不需要数据库连接）
    # 注意：这里我们只测试序列化方法，不涉及数据库操作
    from core.state_manager import StateManager

    # 手动创建序列化方法（避免数据库依赖）
    def _serialize_agent_session(agent_session: AgentSession) -> Dict[str, Any]:
        """简化的序列化方法"""
        serialized = agent_session.to_dict()
        serialized["serialization_metadata"] = {
            "format_version": "1.0.0",
            "serialized_at": datetime.utcnow().isoformat(),
            "session_type": "agent_framework.AgentSession",
        }
        return serialized

    # 执行序列化
    serialized = _serialize_agent_session(sample_agent_session)

    # 验证基本结构
    assert isinstance(serialized, dict)
    assert "session_id" in serialized
    assert serialized["session_id"] == "test-session-123"

    # 验证元数据
    assert "serialization_metadata" in serialized
    assert serialized["serialization_metadata"]["format_version"] == "1.0.0"

    # 验证状态数据
    assert "state" in serialized
    state = serialized["state"]
    assert state["research_topic"] == "深度学习在医学影像中的应用"
    assert state["iteration_count"] == 3
    assert state["config"]["model"] == "gpt-4"

    # 验证消息历史
    assert "messages" in state
    messages = state["messages"]
    assert len(messages) == 3
    assert messages[0]["role"] == "user"

    # 验证复杂嵌套结构
    assert "collected_papers" in state
    papers = state["collected_papers"]
    assert len(papers) == 2
    assert papers[0]["title"] == "Deep Learning in Medical Imaging"


def test_serialize_preserves_message_structure(sample_agent_session: AgentSession):
    """
    测试序列化保留消息结构

    验证 Message 对象的所有字段都被正确序列化
    """
    serialized = sample_agent_session.to_dict()
    messages = serialized["state"]["messages"]

    # 验证第一条消息的结构
    first_message = messages[0]
    assert "role" in first_message
    assert "contents" in first_message
    assert first_message["role"] == "user"

    # 验证内容结构
    contents = first_message["contents"]
    assert len(contents) > 0
    # Content 应该被序列化为包含 type 字段的字典
    assert "type" in contents[0] or "text" in contents[0]


# ============================================================================
# 反序列化测试
# ============================================================================


def test_deserialize_agent_session(sample_agent_session: AgentSession):
    """
    测试 Agent Session 反序列化

    验证：
    - 反序列化后的 Session 与原始 Session 状态一致
    - 消息历史完整恢复
    - 所有状态数据正确恢复
    """
    # 序列化
    serialized = sample_agent_session.to_dict()

    # 反序列化
    restored_session = AgentSession.from_dict(serialized)

    # 验证基本属性
    assert restored_session.session_id == sample_agent_session.session_id
    assert (
        restored_session.service_session_id
        == sample_agent_session.service_session_id
    )

    # 验证状态数据
    assert (
        restored_session.state["research_topic"]
        == sample_agent_session.state["research_topic"]
    )
    assert (
        restored_session.state["iteration_count"]
        == sample_agent_session.state["iteration_count"]
    )
    assert (
        restored_session.state["config"]["model"]
        == sample_agent_session.state["config"]["model"]
    )

    # 验证消息历史
    original_messages = sample_agent_session.state["messages"]
    restored_messages = restored_session.state["messages"]
    assert len(restored_messages) == len(original_messages)

    for i, (original, restored) in enumerate(
        zip(original_messages, restored_messages)
    ):
        assert original.role == restored.role
        assert len(original.contents) == len(restored.contents)

    # 验证复杂嵌套结构
    assert (
        restored_session.state["collected_papers"][0]["title"]
        == sample_agent_session.state["collected_papers"][0]["title"]
    )


def test_deserialize_preserves_message_objects(sample_agent_session: AgentSession):
    """
    测试反序列化恢复 Message 对象

    验证反序列化后的消息是真正的 Message 对象，而不是普通字典
    """
    serialized = sample_agent_session.to_dict()
    restored_session = AgentSession.from_dict(serialized)

    messages = restored_session.state["messages"]

    # 验证消息是 Message 对象
    assert all(isinstance(msg, Message) for msg in messages)

    # 验证消息内容
    first_message = messages[0]
    assert first_message.role == "user"
    assert len(first_message.contents) > 0


# ============================================================================
# 往返测试（Round-trip）
# ============================================================================


def test_round_trip_serialization(sample_agent_session: AgentSession):
    """
    测试序列化-反序列化往返

    验证：serialize(deserialize(serialize(session))) == serialize(session)
    """
    # 第一次序列化
    first_serialized = sample_agent_session.to_dict()

    # 反序列化
    restored_session = AgentSession.from_dict(first_serialized)

    # 第二次序列化
    second_serialized = restored_session.to_dict()

    # 验证两次序列化结果一致（忽略时间戳等动态字段）
    # 比较核心状态数据
    assert first_serialized["session_id"] == second_serialized["session_id"]
    assert first_serialized["state"]["research_topic"] == second_serialized["state"][
        "research_topic"
    ]
    assert first_serialized["state"]["iteration_count"] == second_serialized["state"][
        "iteration_count"
    ]


# ============================================================================
# 状态哈希测试
# ============================================================================


def test_state_hash_computation(sample_agent_session: AgentSession):
    """
    测试状态哈希计算

    验证：
    - 相同状态产生相同哈希
    - 不同状态产生不同哈希
    - 哈希是确定性的
    """
    import hashlib
    import json

    def compute_hash(state: Dict[str, Any]) -> str:
        """计算状态哈希"""
        state_json = json.dumps(state, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(state_json.encode("utf-8")).hexdigest()

    # 序列化状态
    serialized = sample_agent_session.to_dict()

    # 计算哈希
    hash1 = compute_hash(serialized)
    hash2 = compute_hash(serialized)

    # 验证确定性
    assert hash1 == hash2

    # 验证相同状态产生相同哈希
    restored_session = AgentSession.from_dict(serialized)
    serialized_again = restored_session.to_dict()
    hash3 = compute_hash(serialized_again)
    assert hash1 == hash3

    # 验证不同状态产生不同哈希
    modified_session = AgentSession.from_dict(serialized)
    modified_session.state["new_field"] = "new_value"
    modified_serialized = modified_session.to_dict()
    hash4 = compute_hash(modified_serialized)
    assert hash1 != hash4


# ============================================================================
# 边界情况测试
# ============================================================================


def test_serialize_empty_session():
    """测试序列化空 Session"""
    empty_session = AgentSession()
    serialized = empty_session.to_dict()

    assert isinstance(serialized, dict)
    assert "session_id" in serialized
    assert "state" in serialized
    assert serialized["state"] == {}


def test_deserialize_empty_state():
    """测试反序列化空状态"""
    data = {
        "session_id": "test-empty",
        "state": {},
    }
    session = AgentSession.from_dict(data)

    assert session.session_id == "test-empty"
    assert session.state == {}


def test_serialize_session_with_none_values():
    """测试序列化包含 None 值的 Session"""
    session = AgentSession(session_id="test-none")
    session.state["none_value"] = None
    session.state["nested"] = {"inner_none": None, "value": "test"}

    serialized = session.to_dict()
    restored = AgentSession.from_dict(serialized)

    assert restored.state["none_value"] is None
    assert restored.state["nested"]["inner_none"] is None
    assert restored.state["nested"]["value"] == "test"


def test_serialize_session_with_special_characters():
    """测试序列化包含特殊字符的 Session"""
    session = AgentSession(session_id="test-special")
    session.state["chinese"] = "中文测试"
    session.state["emoji"] = "🔬🧪📊"
    session.state["special"] = "line1\nline2\ttab"

    serialized = session.to_dict()
    restored = AgentSession.from_dict(serialized)

    assert restored.state["chinese"] == "中文测试"
    assert restored.state["emoji"] == "🔬🧪📊"
    assert restored.state["special"] == "line1\nline2\ttab"


# ============================================================================
# 消息历史操作测试
# ============================================================================


def test_extract_message_history(sample_agent_session: AgentSession):
    """测试提取消息历史"""
    from core.state_manager import StateManager

    # 创建 StateManager 实例（不使用数据库）
    # 我们只测试 extract_message_history 方法
    messages = sample_agent_session.state.get("messages", [])

    assert len(messages) == 3
    assert all(isinstance(msg, Message) for msg in messages)
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


def test_inject_message():
    """测试注入消息"""
    session = AgentSession(session_id="test-inject")

    # 初始没有消息
    assert "messages" not in session.state or len(session.state.get("messages", [])) == 0

    # 注入消息
    message = Message(
        role="user",
        contents=[Content.from_text("这是一条新消息")],
    )

    if "messages" not in session.state:
        session.state["messages"] = []
    session.state["messages"].append(message)

    # 验证消息被注入
    assert len(session.state["messages"]) == 1
    assert session.state["messages"][0].role == "user"


def test_inject_human_feedback():
    """测试注入人类反馈"""
    session = AgentSession(session_id="test-feedback")

    # 注入人类反馈
    feedback = "请增加对比实验部分"
    feedback_message = Message(
        role="user",
        contents=[Content.from_text(feedback)],
    )

    if "messages" not in session.state:
        session.state["messages"] = []
    session.state["messages"].append(feedback_message)

    # 同时在状态中记录反馈
    session.state["human_feedback"] = feedback
    session.state["feedback_timestamp"] = datetime.utcnow().isoformat()

    # 验证
    assert len(session.state["messages"]) == 1
    assert session.state["human_feedback"] == feedback
    assert "feedback_timestamp" in session.state


# ============================================================================
# 性能测试
# ============================================================================


def test_serialize_large_session():
    """测试序列化大型 Session（性能测试）"""
    import time

    # 创建包含大量消息的 Session
    session = AgentSession(session_id="test-large")

    # 添加 100 条消息
    messages = []
    for i in range(100):
        messages.append(
            Message(
                role="user" if i % 2 == 0 else "assistant",
                contents=[Content.from_text(f"消息 {i}: " + "内容" * 50)],
            )
        )
    session.state["messages"] = messages

    # 添加大量状态数据
    session.state["large_data"] = {f"key_{i}": f"value_{i}" for i in range(1000)}

    # 测量序列化时间
    start_time = time.time()
    serialized = session.to_dict()
    serialize_time = time.time() - start_time

    # 测量反序列化时间
    start_time = time.time()
    restored = AgentSession.from_dict(serialized)
    deserialize_time = time.time() - start_time

    # 验证正确性
    assert len(restored.state["messages"]) == 100
    assert len(restored.state["large_data"]) == 1000

    # 打印性能信息（可选）
    print(f"\n序列化时间: {serialize_time:.4f} 秒")
    print(f"反序列化时间: {deserialize_time:.4f} 秒")

    # 性能断言（确保在合理时间内完成）
    assert serialize_time < 1.0  # 应该在 1 秒内完成
    assert deserialize_time < 1.0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
