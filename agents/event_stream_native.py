"""
原生事件流监听与 SSE 桥接模块 (Native Event Streaming)

本模块实现 agent_framework 原生事件流到 FastAPI SSE 的桥接。

核心变更：
- 废弃之前前端手动组装的 SSE 日志
- 直接监听 agent_framework 底层的原生事件总线
- 将 WorkflowEvent 实时拦截并透传给前端

原生事件类型映射：
- WorkflowEvent.started -> SSE workflow_start
- WorkflowEvent.executor_invoked -> SSE agent_thought
- WorkflowEvent.data -> SSE tool_call_start/result
- WorkflowEvent.output -> SSE workflow_complete

设计原则：
- 透明透传：保持原生事件的完整语义
- 类型安全：使用 WorkflowEvent 的类型系统
- 低延迟：异步流式处理，无阻塞
"""

from typing import Any, Dict, List, Optional, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from agent_framework import (
    WorkflowEvent,
    WorkflowEventType,
    WorkflowRunState,
    WorkflowErrorDetails,
)


# ============================================================================
# SSE 事件类型定义
# ============================================================================

class SSEEventType(str, Enum):
    """SSE 事件类型枚举（与前端约定）"""
    # 工作流事件
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STATUS = "workflow_status"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"
    
    # 执行器事件
    EXECUTOR_INVOKED = "executor_invoked"
    EXECUTOR_COMPLETED = "executor_completed"
    EXECUTOR_FAILED = "executor_failed"
    
    # Agent 事件
    AGENT_THOUGHT = "agent_thought"
    AGENT_RESPONSE = "agent_response"
    
    # 工具调用事件
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    
    # 数据事件
    DATA = "data"
    OUTPUT = "output"
    
    # 超步事件
    SUPERSTEP_STARTED = "superstep_started"
    SUPERSTEP_COMPLETED = "superstep_completed"
    
    # 心跳
    HEARTBEAT = "heartbeat"


# ============================================================================
# SSE 事件模型
# ============================================================================

@dataclass
class SSEEvent:
    """SSE 事件数据结构"""
    event_type: SSEEventType
    """事件类型"""
    data: Dict[str, Any]
    """事件数据"""
    event_id: Optional[str] = None
    """事件 ID（用于去重）"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """时间戳"""
    
    def to_sse_format(self) -> str:
        """
        转换为 SSE 协议格式
        
        SSE 协议：
        event: {event_type}
        data: {json_data}
        id: {event_id}
        
        Returns:
            SSE 格式字符串
        """
        lines = []
        lines.append(f"event: {self.event_type.value}")
        lines.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        lines.append("")  # 空行结束
        lines.append("")  # 额外空行确保分隔
        return "\n".join(lines)


# ============================================================================
# 原生事件到 SSE 事件的转换器
# ============================================================================

class NativeEventToSSEConverter:
    """
    原生事件到 SSE 事件的转换器
    
    将 agent_framework 的 WorkflowEvent 转换为前端约定的 SSE 事件格式。
    
    转换规则：
    - started -> workflow_start
    - status -> workflow_status
    - failed -> workflow_error
    - executor_invoked -> executor_invoked / agent_thought
    - executor_completed -> executor_completed
    - executor_failed -> executor_failed
    - data -> data / tool_call_start / tool_call_result
    - output -> output / workflow_complete
    - superstep_started -> superstep_started
    - superstep_completed -> superstep_completed
    """
    
    def convert(self, event: WorkflowEvent) -> Optional[SSEEvent]:
        """
        转换单个事件
        
        Args:
            event: 原生工作流事件
        
        Returns:
            SSE 事件，如果不需要转发则返回 None
        """
        # 根据事件类型分发
        if event.type == "started":
            return self._convert_started(event)
        elif event.type == "status":
            return self._convert_status(event)
        elif event.type == "failed":
            return self._convert_failed(event)
        elif event.type == "executor_invoked":
            return self._convert_executor_invoked(event)
        elif event.type == "executor_completed":
            return self._convert_executor_completed(event)
        elif event.type == "executor_failed":
            return self._convert_executor_failed(event)
        elif event.type == "data":
            return self._convert_data(event)
        elif event.type == "output":
            return self._convert_output(event)
        elif event.type == "superstep_started":
            return self._convert_superstep_started(event)
        elif event.type == "superstep_completed":
            return self._convert_superstep_completed(event)
        else:
            # 未知事件类型，不转发
            return None
    
    def _convert_started(self, event: WorkflowEvent) -> SSEEvent:
        """转换 started 事件"""
        return SSEEvent(
            event_type=SSEEventType.WORKFLOW_START,
            data={
                "message": "工作流启动",
                "origin": event.origin.value if hasattr(event.origin, 'value') else str(event.origin),
            },
        )
    
    def _convert_status(self, event: WorkflowEvent) -> SSEEvent:
        """转换 status 事件"""
        state = event.state.value if hasattr(event.state, 'value') else str(event.state)
        
        return SSEEvent(
            event_type=SSEEventType.WORKFLOW_STATUS,
            data={
                "state": state,
                "message": f"工作流状态变更: {state}",
            },
        )
    
    def _convert_failed(self, event: WorkflowEvent) -> SSEEvent:
        """转换 failed 事件"""
        details = event.details
        error_data = {}
        
        if details:
            error_data = {
                "error_type": details.error_type,
                "message": details.message,
                "executor_id": details.executor_id,
            }
        
        return SSEEvent(
            event_type=SSEEventType.WORKFLOW_ERROR,
            data={
                "message": "工作流失败",
                "error": error_data,
            },
        )
    
    def _convert_executor_invoked(self, event: WorkflowEvent) -> SSEEvent:
        """
        转换 executor_invoked 事件
        
        根据执行器类型，可能转换为 agent_thought 或 executor_invoked
        """
        executor_id = event.executor_id or "unknown"
        
        # 判断是否为 Agent 执行器
        if "agent" in executor_id.lower() or "researcher" in executor_id.lower():
            # Agent 执行器，转换为 agent_thought
            return SSEEvent(
                event_type=SSEEventType.AGENT_THOUGHT,
                data={
                    "agent_id": executor_id,
                    "message": f"Agent {executor_id} 开始执行",
                    "thought": event.data if event.data else {},
                },
            )
        else:
            # 普通执行器
            return SSEEvent(
                event_type=SSEEventType.EXECUTOR_INVOKED,
                data={
                    "executor_id": executor_id,
                    "message": f"执行器 {executor_id} 被调用",
                },
            )
    
    def _convert_executor_completed(self, event: WorkflowEvent) -> SSEEvent:
        """转换 executor_completed 事件"""
        executor_id = event.executor_id or "unknown"
        
        return SSEEvent(
            event_type=SSEEventType.EXECUTOR_COMPLETED,
            data={
                "executor_id": executor_id,
                "message": f"执行器 {executor_id} 完成",
                "result": self._serialize_data(event.data),
            },
        )
    
    def _convert_executor_failed(self, event: WorkflowEvent) -> SSEEvent:
        """转换 executor_failed 事件"""
        executor_id = event.executor_id or "unknown"
        details = event.details
        
        error_data = {}
        if details:
            error_data = {
                "error_type": details.error_type,
                "message": details.message,
            }
        
        return SSEEvent(
            event_type=SSEEventType.EXECUTOR_FAILED,
            data={
                "executor_id": executor_id,
                "message": f"执行器 {executor_id} 失败",
                "error": error_data,
            },
        )
    
    def _convert_data(self, event: WorkflowEvent) -> SSEEvent:
        """
        转换 data 事件
        
        根据数据内容，可能转换为：
        - tool_call_start: 工具调用开始
        - tool_call_result: 工具调用结果
        - agent_response: Agent 响应
        - data: 通用数据
        """
        executor_id = event.executor_id or "unknown"
        data = event.data
        
        # 判断数据类型
        if isinstance(data, dict):
            # 检查是否为工具调用
            if "tool_call" in data or "function_call" in data:
                return SSEEvent(
                    event_type=SSEEventType.TOOL_CALL_START,
                    data={
                        "executor_id": executor_id,
                        "tool_name": data.get("name", "unknown"),
                        "arguments": data.get("arguments", {}),
                    },
                )
            elif "tool_result" in data or "function_result" in data:
                return SSEEvent(
                    event_type=SSEEventType.TOOL_CALL_RESULT,
                    data={
                        "executor_id": executor_id,
                        "result": data.get("result", ""),
                    },
                )
            else:
                # 通用数据
                return SSEEvent(
                    event_type=SSEEventType.DATA,
                    data={
                        "executor_id": executor_id,
                        "payload": self._serialize_data(data),
                    },
                )
        
        # 检查是否为 AgentResponse
        if hasattr(data, 'text'):
            return SSEEvent(
                event_type=SSEEventType.AGENT_RESPONSE,
                data={
                    "executor_id": executor_id,
                    "text": data.text,
                    "finish_reason": getattr(data, 'finish_reason', None),
                },
            )
        
        # 默认：通用数据
        return SSEEvent(
            event_type=SSEEventType.DATA,
            data={
                "executor_id": executor_id,
                "payload": self._serialize_data(data),
            },
        )
    
    def _convert_output(self, event: WorkflowEvent) -> SSEEvent:
        """转换 output 事件"""
        executor_id = event.executor_id or "unknown"
        
        return SSEEvent(
            event_type=SSEEventType.OUTPUT,
            data={
                "executor_id": executor_id,
                "message": f"执行器 {executor_id} 输出最终结果",
                "output": self._serialize_data(event.data),
            },
        )
    
    def _convert_superstep_started(self, event: WorkflowEvent) -> SSEEvent:
        """转换 superstep_started 事件"""
        iteration = event.iteration or 0
        
        return SSEEvent(
            event_type=SSEEventType.SUPERSTEP_STARTED,
            data={
                "iteration": iteration,
                "message": f"超步 {iteration} 开始",
            },
        )
    
    def _convert_superstep_completed(self, event: WorkflowEvent) -> SSEEvent:
        """转换 superstep_completed 事件"""
        iteration = event.iteration or 0
        
        return SSEEvent(
            event_type=SSEEventType.SUPERSTEP_COMPLETED,
            data={
                "iteration": iteration,
                "message": f"超步 {iteration} 完成",
            },
        )
    
    def _serialize_data(self, data: Any) -> Any:
        """序列化数据为 JSON 兼容格式"""
        if data is None:
            return None
        elif isinstance(data, (str, int, float, bool)):
            return data
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif hasattr(data, '__dict__'):
            # 对象，转换为字典
            return self._serialize_data(data.__dict__)
        else:
            # 其他类型，转为字符串
            return str(data)


# ============================================================================
# SSE 流生成器
# ============================================================================

class SSEStreamGenerator:
    """
    SSE 流生成器
    
    将 agent_framework 的原生事件流转换为 SSE 流。
    
    原生特性：
    - 直接消费 workflow.run(stream=True) 返回的事件流
    - 实时转换并推送，无缓冲
    - 支持心跳保活
    """
    
    def __init__(
        self,
        heartbeat_interval: float = 15.0,
    ):
        """
        初始化 SSE 流生成器
        
        Args:
            heartbeat_interval: 心跳间隔（秒）
        """
        self._converter = NativeEventToSSEConverter()
        self._heartbeat_interval = heartbeat_interval
    
    async def generate(
        self,
        event_stream: AsyncIterator[WorkflowEvent],
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        生成 SSE 流
        
        原生特性说明：
        - event_stream 是 workflow.run(stream=True) 返回的异步迭代器
        - 每个 WorkflowEvent 被实时转换为 SSE 事件
        - 心跳事件确保连接保活
        
        Args:
            event_stream: 原生事件流
            session_id: 会话 ID
        
        Yields:
            SSE 格式的事件字符串
        """
        last_heartbeat = datetime.now()
        
        async for event in event_stream:
            # 检查是否需要发送心跳
            now = datetime.now()
            if (now - last_heartbeat).total_seconds() >= self._heartbeat_interval:
                yield self._create_heartbeat()
                last_heartbeat = now
            
            # 转换事件
            sse_event = self._converter.convert(event)
            
            if sse_event:
                # 添加会话 ID
                sse_event.data["session_id"] = session_id
                yield sse_event.to_sse_format()
        
        # 发送最终心跳
        yield self._create_heartbeat()
    
    def _create_heartbeat(self) -> str:
        """创建心跳事件"""
        event = SSEEvent(
            event_type=SSEEventType.HEARTBEAT,
            data={"timestamp": datetime.now().isoformat()},
        )
        return event.to_sse_format()


# ============================================================================
# FastAPI SSE 路由
# ============================================================================

def create_sse_router() -> APIRouter:
    """
    创建 SSE 路由
    
    Returns:
        FastAPI 路由器
    """
    router = APIRouter(prefix="/stream", tags=["stream"])
    
    @router.get("/workflow/{session_id}")
    async def stream_workflow_events(
        session_id: str,
        heartbeat_interval: float = Query(default=15.0, description="心跳间隔（秒）"),
    ):
        """
        流式获取工作流事件
        
        原生特性说明：
        - 直接监听 agent_framework 的原生事件流
        - 所有事件实时透传，无手动组装
        - 前端"玻璃盒" UI 可完整展示 Agent 思考过程
        
        Args:
            session_id: 会话 ID
            heartbeat_interval: 心跳间隔
        
        Returns:
            StreamingResponse (SSE)
        """
        # 获取工作流事件流
        # 注意：这里需要从全局工作流管理器获取事件流
        # 实际实现中，应该有一个工作流注册表
        from agents.workflow_native import get_workflow_event_stream
        
        event_stream = await get_workflow_event_stream(session_id)
        
        # 创建 SSE 生成器
        generator = SSEStreamGenerator(heartbeat_interval=heartbeat_interval)
        
        # 返回 SSE 响应
        return StreamingResponse(
            generator.generate(event_stream, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            },
        )
    
    @router.get("/agent/{agent_id}")
    async def stream_agent_events(
        agent_id: str,
        session_id: str = Query(..., description="会话 ID"),
    ):
        """
        流式获取单个 Agent 的事件
        
        用于监控特定 Agent 的执行过程。
        
        Args:
            agent_id: Agent ID
            session_id: 会话 ID
        
        Returns:
            StreamingResponse (SSE)
        """
        # 实现类似 stream_workflow_events
        # 但只过滤特定 agent_id 的事件
        pass
    
    return router


# ============================================================================
# 全局工作流事件流管理器
# ============================================================================

class WorkflowEventStreamRegistry:
    """
    工作流事件流注册表
    
    管理活跃工作流的事件流，支持多客户端订阅。
    
    原生特性：
    - 每个工作流运行产生一个事件流
    - 支持多个客户端订阅同一事件流
    - 使用 asyncio.Queue 实现事件分发
    """
    
    def __init__(self):
        self._streams: Dict[str, AsyncIterator[WorkflowEvent]] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def register(
        self,
        session_id: str,
        event_stream: AsyncIterator[WorkflowEvent],
    ) -> None:
        """
        注册工作流事件流
        
        Args:
            session_id: 会话 ID
            event_stream: 事件流
        """
        async with self._lock:
            self._streams[session_id] = event_stream
            self._subscribers[session_id] = []
            
            # 启动事件分发任务
            asyncio.create_task(self._distribute_events(session_id))
    
    async def subscribe(
        self,
        session_id: str,
    ) -> asyncio.Queue:
        """
        订阅工作流事件
        
        Args:
            session_id: 会话 ID
        
        Returns:
            事件队列
        """
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = []
            
            queue: asyncio.Queue = asyncio.Queue()
            self._subscribers[session_id].append(queue)
            
            return queue
    
    async def unsubscribe(
        self,
        session_id: str,
        queue: asyncio.Queue,
    ) -> None:
        """
        取消订阅
        
        Args:
            session_id: 会话 ID
            queue: 事件队列
        """
        async with self._lock:
            if session_id in self._subscribers:
                try:
                    self._subscribers[session_id].remove(queue)
                except ValueError:
                    pass
    
    async def _distribute_events(self, session_id: str) -> None:
        """
        分发事件到所有订阅者
        
        Args:
            session_id: 会话 ID
        """
        event_stream = self._streams.get(session_id)
        if not event_stream:
            return
        
        try:
            async for event in event_stream:
                # 分发到所有订阅者
                subscribers = self._subscribers.get(session_id, [])
                for queue in subscribers:
                    try:
                        await queue.put(event)
                    except Exception:
                        # 队列已满或已关闭，忽略
                        pass
        except Exception:
            # 事件流结束或出错
            pass
        finally:
            # 清理
            async with self._lock:
                if session_id in self._streams:
                    del self._streams[session_id]
                if session_id in self._subscribers:
                    del self._subscribers[session_id]


# 全局注册表实例
_registry = WorkflowEventStreamRegistry()


async def get_workflow_event_stream(session_id: str) -> AsyncIterator[WorkflowEvent]:
    """
    获取工作流事件流
    
    高层 API，用于 SSE 路由。
    
    Args:
        session_id: 会话 ID
    
    Returns:
        事件流
    """
    queue = await _registry.subscribe(session_id)
    
    try:
        while True:
            event = await queue.get()
            yield event
    finally:
        await _registry.unsubscribe(session_id, queue)


async def register_workflow_event_stream(
    session_id: str,
    event_stream: AsyncIterator[WorkflowEvent],
) -> None:
    """
    注册工作流事件流
    
    在启动工作流时调用。
    
    Args:
        session_id: 会话 ID
        event_stream: 事件流
    """
    await _registry.register(session_id, event_stream)
