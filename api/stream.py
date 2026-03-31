"""
FastAPI SSE（Server-Sent Events）流式路由模块

本模块实现全局状态流式监控，实时捕获并传输：
- 智能体思考过程（Agent Thoughts）
- 工具调用记录（Tool Calls）
- 沙箱运行日志（Sandbox Logs）
- 工作流状态变更（Workflow State Changes）

核心设计：
- 基于 FastAPI StreamingResponse 实现 SSE
- 异步事件队列，支持多客户端订阅
- 事件类型分类，便于前端过滤
- 与 agent_framework 的异步事件流无缝集成

SSE 协议规范：
- Content-Type: text/event-stream
- 数据格式: data: {json}\n\n
- 支持事件类型: event: {type}\n
"""

from typing import Optional, Dict, Any, List, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.config import settings
from core.state_manager import StateManager
from database.session import get_db_session
from database.repositories.workflow_state_repository import WorkflowStateRepository


# ============================================================================
# 枚举和常量定义
# ============================================================================

class EventType(str, Enum):
    """SSE 事件类型枚举"""
    # 智能体事件
    AGENT_THOUGHT = "agent_thought"             # 智能体思考
    AGENT_ACTION = "agent_action"               # 智能体行动
    AGENT_RESPONSE = "agent_response"           # 智能体响应

    # 工具调用事件
    TOOL_CALL_START = "tool_call_start"         # 工具调用开始
    TOOL_CALL_RESULT = "tool_call_result"       # 工具调用结果
    TOOL_CALL_ERROR = "tool_call_error"         # 工具调用错误

    # 沙箱事件
    SANDBOX_START = "sandbox_start"             # 沙箱启动
    SANDBOX_STDOUT = "sandbox_stdout"           # 沙箱标准输出
    SANDBOX_STDERR = "sandbox_stderr"           # 沙箱标准错误
    SANDBOX_COMPLETE = "sandbox_complete"       # 沙箱完成
    SANDBOX_ERROR = "sandbox_error"             # 沙箱错误

    # 工作流事件
    WORKFLOW_START = "workflow_start"           # 工作流启动
    WORKFLOW_STAGE_CHANGE = "workflow_stage_change"  # 工作流阶段变更
    WORKFLOW_CHECKPOINT = "workflow_checkpoint" # 工作流检查点
    WORKFLOW_COMPLETE = "workflow_complete"     # 工作流完成
    WORKFLOW_ERROR = "workflow_error"           # 工作流错误

    # HITL 事件
    HITL_INTERRUPT = "hitl_interrupt"           # HITL 中断
    HITL_RESUME = "hitl_resume"                 # HITL 恢复
    HITL_FEEDBACK = "hitl_feedback"             # HITL 反馈

    # 系统事件
    HEARTBEAT = "heartbeat"                     # 心跳
    ERROR = "error"                             # 错误


class EventPriority(str, Enum):
    """事件优先级枚举"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Pydantic 模型定义
# ============================================================================

class SSEEvent(BaseModel):
    """SSE 事件模型"""
    event_type: EventType = Field(description="事件类型")
    event_id: Optional[str] = Field(
        default=None,
        description="事件 ID（用于去重）",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="时间戳",
    )
    priority: EventPriority = Field(
        default=EventPriority.NORMAL,
        description="优先级",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="会话 ID",
    )
    agent_name: Optional[str] = Field(
        default=None,
        description="智能体名称",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="事件数据",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据",
    )


class StreamSubscription(BaseModel):
    """流订阅信息"""
    session_id: str = Field(description="会话 ID")
    event_types: List[EventType] = Field(
        default_factory=list,
        description="订阅的事件类型（空列表表示订阅所有）",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="创建时间",
    )


# ============================================================================
# 事件总线（Event Bus）
# ============================================================================

class EventBus:
    """
    事件总线

    管理事件的发布和订阅，支持：
    - 多客户端订阅
    - 事件类型过滤
    - 异步事件队列
    - 背压控制

    使用单例模式，确保全局唯一。
    """

    _instance: Optional['EventBus'] = None

    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """初始化事件总线"""
        # 会话 -> 事件队列映射
        self._queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        # 会话 -> 订阅信息映射
        self._subscriptions: Dict[str, StreamSubscription] = {}

        # 全局事件历史（用于新客户端回放）
        self._event_history: List[SSEEvent] = []
        self._max_history = 1000

        # 锁
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        session_id: str,
        event_types: Optional[List[EventType]] = None,
    ) -> asyncio.Queue:
        """
        订阅事件流

        Args:
            session_id: 会话 ID
            event_types: 订阅的事件类型列表（None 表示订阅所有）

        Returns:
            事件队列
        """
        async with self._lock:
            # 创建订阅信息
            subscription = StreamSubscription(
                session_id=session_id,
                event_types=event_types or [],
            )
            self._subscriptions[session_id] = subscription

            # 返回队列
            return self._queues[session_id]

    async def unsubscribe(self, session_id: str) -> None:
        """
        取消订阅

        Args:
            session_id: 会话 ID
        """
        async with self._lock:
            if session_id in self._subscriptions:
                del self._subscriptions[session_id]
            if session_id in self._queues:
                # 清空队列
                queue = self._queues[session_id]
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                del self._queues[session_id]

    async def publish(self, event: SSEEvent) -> None:
        """
        发布事件

        将事件推送到所有订阅了该事件类型的客户端。

        Args:
            event: SSE 事件
        """
        # 记录到历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # 推送到订阅者
        async with self._lock:
            for session_id, subscription in self._subscriptions.items():
                # 检查 session_id 匹配（如果事件有 session_id）
                if event.session_id and event.session_id != session_id:
                    continue

                # 检查事件类型过滤
                if subscription.event_types and event.event_type not in subscription.event_types:
                    continue

                # 推送到队列
                try:
                    await self._queues[session_id].put(event)
                except asyncio.QueueFull:
                    # 队列满，丢弃旧事件
                    try:
                        self._queues[session_id].get_nowait()
                        await self._queues[session_id].put(event)
                    except:
                        pass

    async def get_event(self, session_id: str, timeout: float = 30.0) -> Optional[SSEEvent]:
        """
        获取事件（带超时）

        Args:
            session_id: 会话 ID
            timeout: 超时时间（秒）

        Returns:
            SSE 事件，超时返回 None
        """
        if session_id not in self._queues:
            return None

        try:
            return await asyncio.wait_for(
                self._queues[session_id].get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    def get_history(
        self,
        event_types: Optional[List[EventType]] = None,
        limit: int = 100,
    ) -> List[SSEEvent]:
        """
        获取事件历史

        Args:
            event_types: 事件类型过滤
            limit: 最大数量

        Returns:
            事件列表
        """
        history = self._event_history[-limit:]

        if event_types:
            history = [e for e in history if e.event_type in event_types]

        return history


# 全局事件总线实例
event_bus = EventBus()


# ============================================================================
# SSE 流式响应生成器
# ============================================================================

async def generate_sse_stream(
    session_id: str,
    event_types: Optional[List[EventType]] = None,
    include_history: bool = False,
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[str]:
    """
    生成 SSE 流

    Args:
        session_id: 会话 ID
        event_types: 订阅的事件类型
        include_history: 是否包含历史事件
        heartbeat_interval: 心跳间隔（秒）

    Yields:
        SSE 格式的字符串
    """
    # 订阅事件流
    queue = await event_bus.subscribe(session_id, event_types)

    try:
        # 发送历史事件（如果请求）
        if include_history:
            history = event_bus.get_history(event_types, limit=50)
            for event in history:
                yield format_sse_event(event)

        # 发送连接成功事件
        connect_event = SSEEvent(
            event_type=EventType.WORKFLOW_START,
            session_id=session_id,
            data={"message": "SSE 连接已建立", "session_id": session_id},
        )
        yield format_sse_event(connect_event)

        # 主循环
        last_heartbeat = datetime.now()

        while True:
            # 检查心跳
            now = datetime.now()
            if (now - last_heartbeat).total_seconds() >= heartbeat_interval:
                heartbeat_event = SSEEvent(
                    event_type=EventType.HEARTBEAT,
                    session_id=session_id,
                    data={"timestamp": now.isoformat()},
                )
                yield format_sse_event(heartbeat_event)
                last_heartbeat = now

            # 获取事件
            event = await event_bus.get_event(session_id, timeout=1.0)

            if event:
                yield format_sse_event(event)
                last_heartbeat = datetime.now()

    except asyncio.CancelledError:
        # 客户端断开连接
        pass

    finally:
        # 取消订阅
        await event_bus.unsubscribe(session_id)


def format_sse_event(event: SSEEvent) -> str:
    """
    格式化 SSE 事件

    SSE 格式：
    ```
    event: {event_type}
    id: {event_id}
    data: {json_data}

    ```

    Args:
        event: SSE 事件

    Returns:
        SSE 格式字符串
    """
    lines = []

    # 事件类型
    lines.append(f"event: {event.event_type.value}")

    # 事件 ID
    if event.event_id:
        lines.append(f"id: {event.event_id}")

    # 数据（JSON 格式）
    data = {
        "timestamp": event.timestamp,
        "priority": event.priority.value,
        "session_id": event.session_id,
        "agent_name": event.agent_name,
        "data": event.data,
        "metadata": event.metadata,
    }
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")

    # 空行结束
    lines.append("")
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# 事件发布辅助函数
# ============================================================================

async def publish_agent_thought(
    session_id: str,
    agent_name: str,
    thought: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    发布智能体思考事件

    Args:
        session_id: 会话 ID
        agent_name: 智能体名称
        thought: 思考内容
        metadata: 元数据
    """
    event = SSEEvent(
        event_type=EventType.AGENT_THOUGHT,
        session_id=session_id,
        agent_name=agent_name,
        data={"thought": thought},
        metadata=metadata or {},
    )
    await event_bus.publish(event)


async def publish_agent_action(
    session_id: str,
    agent_name: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """
    发布智能体行动事件

    Args:
        session_id: 会话 ID
        agent_name: 智能体名称
        action: 行动名称
        params: 行动参数
    """
    event = SSEEvent(
        event_type=EventType.AGENT_ACTION,
        session_id=session_id,
        agent_name=agent_name,
        data={"action": action, "params": params or {}},
    )
    await event_bus.publish(event)


async def publish_tool_call(
    session_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """
    发布工具调用事件

    Args:
        session_id: 会话 ID
        tool_name: 工具名称
        arguments: 调用参数
        result: 调用结果
        error: 错误信息
    """
    if error:
        event_type = EventType.TOOL_CALL_ERROR
        data = {"tool": tool_name, "arguments": arguments, "error": error}
    elif result is not None:
        event_type = EventType.TOOL_CALL_RESULT
        data = {"tool": tool_name, "arguments": arguments, "result": result}
    else:
        event_type = EventType.TOOL_CALL_START
        data = {"tool": tool_name, "arguments": arguments}

    event = SSEEvent(
        event_type=event_type,
        session_id=session_id,
        data=data,
    )
    await event_bus.publish(event)


async def publish_sandbox_log(
    session_id: str,
    log_type: str,  # "stdout" or "stderr"
    content: str,
    execution_id: Optional[str] = None,
) -> None:
    """
    发布沙箱日志事件

    Args:
        session_id: 会话 ID
        log_type: 日志类型
        content: 日志内容
        execution_id: 执行 ID
    """
    event_type = EventType.SANDBOX_STDOUT if log_type == "stdout" else EventType.SANDBOX_STDERR
    event = SSEEvent(
        event_type=event_type,
        session_id=session_id,
        data={"content": content, "execution_id": execution_id},
    )
    await event_bus.publish(event)


async def publish_workflow_stage_change(
    session_id: str,
    from_stage: str,
    to_stage: str,
    reason: Optional[str] = None,
) -> None:
    """
    发布工作流阶段变更事件

    Args:
        session_id: 会话 ID
        from_stage: 原阶段
        to_stage: 新阶段
        reason: 变更原因
    """
    event = SSEEvent(
        event_type=EventType.WORKFLOW_STAGE_CHANGE,
        session_id=session_id,
        data={
            "from_stage": from_stage,
            "to_stage": to_stage,
            "reason": reason,
        },
    )
    await event_bus.publish(event)


async def publish_hitl_interrupt(
    session_id: str,
    interrupt_reason: str,
    context: Dict[str, Any],
) -> None:
    """
    发布 HITL 中断事件

    Args:
        session_id: 会话 ID
        interrupt_reason: 中断原因
        context: 上下文
    """
    event = SSEEvent(
        event_type=EventType.HITL_INTERRUPT,
        session_id=session_id,
        priority=EventPriority.HIGH,
        data={"reason": interrupt_reason, "context": context},
    )
    await event_bus.publish(event)


# ============================================================================
# FastAPI 路由
# ============================================================================

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/events/{session_id}")
async def stream_events(
    session_id: str,
    event_types: Optional[str] = Query(
        None,
        description="订阅的事件类型（逗号分隔）",
    ),
    include_history: bool = Query(
        False,
        description="是否包含历史事件",
    ),
):
    """
    SSE 流式事件端点

    订阅指定会话的事件流，实时接收智能体思考、工具调用、沙箱日志等事件。

    **使用示例**:
    ```javascript
    const eventSource = new EventSource('/api/stream/events/session123');
    eventSource.addEventListener('agent_thought', (e) => {
        console.log('Agent thought:', JSON.parse(e.data));
    });
    ```

    **事件类型**:
    - `agent_thought`: 智能体思考
    - `agent_action`: 智能体行动
    - `tool_call_start`: 工具调用开始
    - `tool_call_result`: 工具调用结果
    - `sandbox_stdout`: 沙箱标准输出
    - `sandbox_stderr`: 沙箱标准错误
    - `workflow_stage_change`: 工作流阶段变更
    - `hitl_interrupt`: HITL 中断
    - `heartbeat`: 心跳
    """
    # 解析事件类型
    types = None
    if event_types:
        try:
            types = [EventType(t.strip()) for t in event_types.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的事件类型: {e}")

    # 返回 SSE 流
    return StreamingResponse(
        generate_sse_stream(
            session_id=session_id,
            event_types=types,
            include_history=include_history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get("/history")
async def get_event_history(
    event_types: Optional[str] = Query(None, description="事件类型过滤"),
    limit: int = Query(100, ge=1, le=1000, description="最大数量"),
):
    """
    获取事件历史

    返回最近的事件记录，用于调试和回放。
    """
    types = None
    if event_types:
        try:
            types = [EventType(t.strip()) for t in event_types.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的事件类型: {e}")

    history = event_bus.get_history(types, limit)

    return {
        "total": len(history),
        "events": [event.model_dump() for event in history],
    }


@router.post("/publish")
async def manual_publish_event(
    event: SSEEvent,
):
    """
    手动发布事件（用于测试）

    允许客户端手动发布事件到事件总线。
    """
    await event_bus.publish(event)
    return {"status": "ok", "event_id": event.event_id}


@router.get("/subscriptions")
async def list_subscriptions():
    """
    列出所有活跃订阅

    返回当前所有 SSE 连接的订阅信息。
    """
    subscriptions = []
    for session_id, sub in event_bus._subscriptions.items():
        subscriptions.append({
            "session_id": session_id,
            "event_types": [t.value for t in sub.event_types],
            "created_at": sub.created_at,
            "queue_size": event_bus._queues[session_id].qsize() if session_id in event_bus._queues else 0,
        })

    return {
        "total": len(subscriptions),
        "subscriptions": subscriptions,
    }


# ============================================================================
# 与 agent_framework 集成的钩子
# ============================================================================

class AgentEventHook:
    """
    智能体事件钩子

    将 agent_framework 的内部事件转换为 SSE 事件并发布。

    使用方法：
    ```python
    hook = AgentEventHook(session_id="session123")
    agent = Agent(client=client, hooks=[hook])
    ```
    """

    def __init__(self, session_id: str, agent_name: str):
        """
        初始化钩子

        Args:
            session_id: 会话 ID
            agent_name: 智能体名称
        """
        self._session_id = session_id
        self._agent_name = agent_name

    async def on_thought(self, thought: str) -> None:
        """思考钩子"""
        await publish_agent_thought(
            self._session_id,
            self._agent_name,
            thought,
        )

    async def on_action(self, action: str, params: Dict[str, Any]) -> None:
        """行动钩子"""
        await publish_agent_action(
            self._session_id,
            self._agent_name,
            action,
            params,
        )

    async def on_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """工具调用开始钩子"""
        await publish_tool_call(
            self._session_id,
            tool_name,
            arguments,
        )

    async def on_tool_result(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
    ) -> None:
        """工具调用结果钩子"""
        await publish_tool_call(
            self._session_id,
            tool_name,
            arguments,
            result=result,
        )

    async def on_tool_error(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        error: str,
    ) -> None:
        """工具调用错误钩子"""
        await publish_tool_call(
            self._session_id,
            tool_name,
            arguments,
            error=error,
        )


# ============================================================================
# 与沙箱集成的钩子
# ============================================================================

class SandboxEventHook:
    """
    沙箱事件钩子

    将沙箱执行日志转换为 SSE 事件并发布。
    """

    def __init__(self, session_id: str, execution_id: str):
        """
        初始化钩子

        Args:
            session_id: 会话 ID
            execution_id: 执行 ID
        """
        self._session_id = session_id
        self._execution_id = execution_id

    async def on_stdout(self, content: str) -> None:
        """标准输出钩子"""
        await publish_sandbox_log(
            self._session_id,
            "stdout",
            content,
            self._execution_id,
        )

    async def on_stderr(self, content: str) -> None:
        """标准错误钩子"""
        await publish_sandbox_log(
            self._session_id,
            "stderr",
            content,
            self._execution_id,
        )
