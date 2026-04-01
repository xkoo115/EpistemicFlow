"""
原生 SSE 流路由（Native Event Streaming）

本模块使用 agent_framework 的原生事件流，替代手动组装的 SSE 日志。

核心变更：
- 直接监听 WorkflowEvent
- 实时透传到前端
- 支持事件类型过滤
"""

from typing import Optional, List, AsyncIterator
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
import asyncio

from agents.event_stream_native import (
    SSEStreamGenerator,
    get_workflow_event_stream,
    SSEEventType,
)


# ============================================================================
# 路由器定义
# ============================================================================

router = APIRouter(prefix="/stream", tags=["stream"])


# ============================================================================
# SSE 流接口
# ============================================================================

@router.get("/workflow/{session_id}")
async def stream_workflow_events(
    session_id: str,
    heartbeat_interval: float = Query(
        default=15.0,
        description="心跳间隔（秒）",
    ),
    event_types: Optional[str] = Query(
        default=None,
        description="订阅的事件类型（逗号分隔）",
    ),
):
    """
    流式获取工作流事件（原生架构）
    
    原生特性说明：
    - 直接监听 agent_framework 的 WorkflowEvent 流
    - 所有事件实时透传，无手动组装
    - 前端"玻璃盒" UI 可完整展示 Agent 思考过程
    
    事件类型：
    - workflow_start: 工作流启动
    - workflow_status: 状态变更
    - executor_invoked: 执行器被调用
    - agent_thought: Agent 思考
    - agent_response: Agent 响应
    - tool_call_start: 工具调用开始
    - tool_call_result: 工具调用结果
    - data: 中间数据
    - output: 最终输出
    - workflow_complete: 工作流完成
    - workflow_error: 工作流错误
    - heartbeat: 心跳
    
    前端使用示例：
        const eventSource = new EventSource(`/api/stream/workflow/${sessionId}`);
        
        eventSource.addEventListener('agent_thought', (e) => {
            const data = JSON.parse(e.data);
            console.log('Agent思考:', data.thought);
        });
        
        eventSource.addEventListener('tool_call_start', (e) => {
            const data = JSON.parse(e.data);
            console.log('工具调用:', data.tool_name);
        });
    
    Args:
        session_id: 会话 ID
        heartbeat_interval: 心跳间隔
        event_types: 订阅的事件类型（可选）
    
    Returns:
        StreamingResponse (SSE)
    """
    try:
        # 获取原生事件流
        event_stream = get_workflow_event_stream(session_id)
        
        # 创建 SSE 生成器
        generator = SSEStreamGenerator(
            heartbeat_interval=heartbeat_interval,
        )
        
        # 返回 SSE 响应
        return StreamingResponse(
            generator.generate(event_stream, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
                "X-Session-Id": session_id,
            },
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取事件流失败: {str(e)}",
        )


@router.get("/agent/{agent_id}")
async def stream_agent_events(
    agent_id: str,
    session_id: str = Query(..., description="会话 ID"),
    heartbeat_interval: float = Query(default=15.0),
):
    """
    流式获取单个 Agent 的事件
    
    用于监控特定 Agent 的执行过程。
    
    Args:
        agent_id: Agent ID
        session_id: 会话 ID
        heartbeat_interval: 心跳间隔
    
    Returns:
        StreamingResponse (SSE)
    """
    try:
        # 获取完整事件流
        full_stream = get_workflow_event_stream(session_id)
        
        # 过滤特定 agent 的事件
        async def filtered_stream():
            async for event in full_stream:
                # 检查事件是否来自目标 agent
                if hasattr(event, 'executor_id') and event.executor_id == agent_id:
                    yield event
                elif hasattr(event, 'data') and isinstance(event.data, dict):
                    if event.data.get('agent_id') == agent_id:
                        yield event
        
        generator = SSEStreamGenerator(heartbeat_interval=heartbeat_interval)
        
        return StreamingResponse(
            generator.generate(filtered_stream(), session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取 Agent 事件流失败: {str(e)}",
        )


# ============================================================================
# 事件历史查询接口
# ============================================================================

@router.get("/workflow/{session_id}/history")
async def get_event_history(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    event_type: Optional[str] = Query(default=None),
):
    """
    获取事件历史（用于断线重连）
    
    当客户端断线重连时，可以获取历史事件进行回放。
    
    Args:
        session_id: 会话 ID
        limit: 最大返回数量
        event_type: 过滤的事件类型
    
    Returns:
        事件历史列表
    """
    # 注意：这需要事件流注册表支持历史存储
    # 当前实现中，事件流是实时的，不存储历史
    # 如果需要历史功能，可以在 WorkflowEventStreamRegistry 中添加
    
    return {
        "session_id": session_id,
        "events": [],
        "message": "历史事件功能尚未实现，请使用实时 SSE 流",
    }


# ============================================================================
# 连接状态接口
# ============================================================================

@router.get("/workflow/{session_id}/status")
async def get_stream_status(
    session_id: str,
):
    """
    获取流连接状态
    
    Args:
        session_id: 会话 ID
    
    Returns:
        连接状态信息
    """
    from agents.event_stream_native import _registry
    
    is_active = session_id in _registry._streams
    subscriber_count = len(_registry._subscribers.get(session_id, []))
    
    return {
        "session_id": session_id,
        "is_active": is_active,
        "subscriber_count": subscriber_count,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# 兼容旧 API 的适配器
# ============================================================================

# 为了保持与现有前端的兼容性，提供旧的事件类型映射
LEGACY_EVENT_TYPE_MAP = {
    "workflow_start": "WORKFLOW_START",
    "workflow_status": "WORKFLOW_STAGE_CHANGE",
    "agent_thought": "AGENT_THOUGHT",
    "agent_response": "AGENT_RESPONSE",
    "tool_call_start": "TOOL_CALL_START",
    "tool_call_result": "TOOL_CALL_RESULT",
    "workflow_complete": "WORKFLOW_COMPLETE",
    "workflow_error": "WORKFLOW_ERROR",
    "heartbeat": "HEARTBEAT",
}


@router.get("/legacy/{session_id}")
async def stream_workflow_events_legacy(
    session_id: str,
):
    """
    流式获取工作流事件（兼容旧 API）
    
    为现有前端提供兼容的事件格式。
    
    Args:
        session_id: 会话 ID
    
    Returns:
        StreamingResponse (SSE)
    """
    try:
        event_stream = get_workflow_event_stream(session_id)
        generator = SSEStreamGenerator()
        
        # 包装生成器，转换事件类型
        async def legacy_generator():
            async for sse_str in generator.generate(event_stream, session_id):
                # 转换事件类型为旧格式
                for new_type, old_type in LEGACY_EVENT_TYPE_MAP.items():
                    sse_str = sse_str.replace(
                        f"event: {new_type}",
                        f"event: {old_type}",
                    )
                yield sse_str
        
        return StreamingResponse(
            legacy_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取事件流失败: {str(e)}",
        )
