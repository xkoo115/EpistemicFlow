# EpistemicFlow API 交付文档

## 文档概述

本文档描述了 EpistemicFlow（AI驱动的自动化科研平台）的核心 API 接口，为前端开发和系统集成提供清晰的对接标准。

**文档版本**: 1.0.0
**最后更新**: 2024-01-01
**API 基础路径**: `http://localhost:8000/api`
**OpenAPI 规范**: `http://localhost:8000/openapi.json`
**交互式文档**: `http://localhost:8000/docs`

---

## 目录

1. [快速开始](#快速开始)
2. [认证与授权](#认证与授权)
3. [核心接口](#核心接口)
   - [提交流水线任务](#提交流水线任务)
   - [SSE 全局状态流式订阅](#sse-全局状态流式订阅)
   - [HITL 人工干预与状态机唤醒](#hitl-人工干预与状态机唤醒)
   - [Saga 确定性状态回滚](#saga-确定性状态回滚)
4. [辅助接口](#辅助接口)
5. [错误码定义](#错误码定义)
6. [最佳实践](#最佳实践)

---

## 快速开始

### 1. 启动服务

```bash
# 使用 Docker Compose 启动服务
make up

# 或使用 docker-compose 命令
docker-compose up -d
```

### 2. 验证服务状态

```bash
# 健康检查
curl http://localhost:8000/health

# 查看服务信息
curl http://localhost:8000/
```

### 3. 访问 API 文档

启动服务后，访问以下地址查看交互式 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## 认证与授权

**注意**: 当前版本暂未实现认证机制，所有接口均可直接访问。生产环境建议集成 JWT 或 OAuth2 认证。

### 认证方案（未来规划）

```http
Authorization: Bearer <access_token>
```

---

## 核心接口

### 提交流水线任务

创建并启动一个新的科研流水线任务。

**接口地址**: `POST /api/v1/workflows/`

**请求头**:
```http
Content-Type: application/json
```

**请求体**:
```json
{
  "session_id": "session_abc123",
  "workflow_name": "literature_review",
  "current_stage": "planning",
  "status": "pending",
  "agent_state": {
    "context": "研究机器学习在自然语言处理中的应用",
    "goals": ["文献检索", "方法设计", "实验验证"]
  },
  "metadata": {
    "user_id": "user_001",
    "priority": "high"
  }
}
```

**请求参数说明**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 会话 ID，用于标识唯一的科研任务 |
| workflow_name | string | 是 | 工作流名称，如 `literature_review`、`experiment_design` |
| current_stage | string | 是 | 当前阶段，枚举值见下方 |
| status | string | 否 | 初始状态，默认 `pending` |
| agent_state | object | 否 | 智能体初始状态数据 |
| metadata | object | 否 | 元数据，可存储任意键值对 |

**工作流阶段枚举** (`current_stage`):

- `planning` - 计划阶段
- `literature_search` - 文献检索
- `method_design` - 方法设计
- `experiment` - 实验执行
- `analysis` - 结果分析
- `report` - 报告生成

**工作流状态枚举** (`status`):

- `pending` - 待执行
- `running` - 执行中
- `paused` - 已暂停（HITL 中断）
- `completed` - 已完成
- `failed` - 已失败

**响应示例**:
```json
{
  "id": 1,
  "session_id": "session_abc123",
  "workflow_name": "literature_review",
  "current_stage": "planning",
  "status": "running",
  "agent_state": {
    "context": "研究机器学习在自然语言处理中的应用",
    "goals": ["文献检索", "方法设计", "实验验证"]
  },
  "human_feedback": null,
  "error_message": null,
  "metadata": {
    "user_id": "user_001",
    "priority": "high"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:01Z"
}
```

**错误响应**:
```json
{
  "detail": "创建工作流状态失败: 数据库连接错误"
}
```

**使用示例 (cURL)**:
```bash
curl -X POST http://localhost:8000/api/v1/workflows/ \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_abc123",
    "workflow_name": "literature_review",
    "current_stage": "planning",
    "status": "pending"
  }'
```

**使用示例 (JavaScript)**:
```javascript
const response = await fetch('http://localhost:8000/api/v1/workflows/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    session_id: 'session_abc123',
    workflow_name: 'literature_review',
    current_stage: 'planning',
    status: 'pending'
  })
});

const workflow = await response.json();
console.log('Workflow created:', workflow);
```

---

### SSE 全局状态流式订阅

通过 Server-Sent Events (SSE) 实时订阅工作流的全局状态变更，包括智能体思考、工具调用、沙箱日志等事件。

**接口地址**: `GET /api/stream/events/{session_id}`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 会话 ID，路径参数 |
| event_types | string | 否 | 订阅的事件类型，逗号分隔，如 `agent_thought,tool_call_start` |
| include_history | boolean | 否 | 是否包含历史事件，默认 `false` |

**事件类型枚举**:

#### 智能体事件
- `agent_thought` - 智能体思考
- `agent_action` - 智能体行动
- `agent_response` - 智能体响应

#### 工具调用事件
- `tool_call_start` - 工具调用开始
- `tool_call_result` - 工具调用结果
- `tool_call_error` - 工具调用错误

#### 沙箱事件
- `sandbox_start` - 沙箱启动
- `sandbox_stdout` - 沙箱标准输出
- `sandbox_stderr` - 沙箱标准错误
- `sandbox_complete` - 沙箱完成
- `sandbox_error` - 沙箱错误

#### 工作流事件
- `workflow_start` - 工作流启动
- `workflow_stage_change` - 工作流阶段变更
- `workflow_checkpoint` - 工作流检查点
- `workflow_complete` - 工作流完成
- `workflow_error` - 工作流错误

#### HITL 事件
- `hitl_interrupt` - HITL 中断
- `hitl_resume` - HITL 恢复
- `hitl_feedback` - HITL 反馈

#### 系统事件
- `heartbeat` - 心跳（每 15 秒发送一次）
- `error` - 错误

**SSE 事件格式**:
```
event: {event_type}
id: {event_id}
data: {json_data}

```

**事件数据结构**:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "priority": "normal",
  "session_id": "session_abc123",
  "agent_name": "researcher_agent",
  "data": {
    // 事件特定数据
  },
  "metadata": {}
}
```

**使用示例 (JavaScript)**:
```javascript
const eventSource = new EventSource(
  'http://localhost:8000/api/stream/events/session_abc123?event_types=agent_thought,tool_call_start'
);

// 监听智能体思考事件
eventSource.addEventListener('agent_thought', (event) => {
  const data = JSON.parse(event.data);
  console.log('Agent thought:', data.data.thought);
  console.log('Agent:', data.agent_name);
  console.log('Timestamp:', data.timestamp);
});

// 监听工具调用开始事件
eventSource.addEventListener('tool_call_start', (event) => {
  const data = JSON.parse(event.data);
  console.log('Tool called:', data.data.tool);
  console.log('Arguments:', data.data.arguments);
});

// 监听工作流阶段变更事件
eventSource.addEventListener('workflow_stage_change', (event) => {
  const data = JSON.parse(event.data);
  console.log('Stage changed:', data.data.from_stage, '->', data.data.to_stage);
});

// 监听错误事件
eventSource.addEventListener('error', (event) => {
  console.error('SSE error:', event);
});

// 监听连接关闭
eventSource.onerror = (error) => {
  console.error('SSE connection error:', error);
  eventSource.close();
};
```

**使用示例 (Python)**:
```python
import sseclient
import requests

# 创建 SSE 连接
response = requests.get(
    'http://localhost:8000/api/stream/events/session_abc123',
    stream=True
)

client = sseclient.SSEClient(response)

for event in client.events():
    if event.event == 'agent_thought':
        data = json.loads(event.data)
        print(f"Agent thought: {data['data']['thought']}")
    elif event.event == 'tool_call_start':
        data = json.loads(event.data)
        print(f"Tool called: {data['data']['tool']}")
```

**使用示例 (cURL)**:
```bash
curl -N http://localhost:8000/api/stream/events/session_abc123
```

**注意事项**:

1. **心跳机制**: 服务端每 15 秒发送一次心跳事件，用于保持连接活跃
2. **自动重连**: 浏览器的 EventSource 会自动重连，建议实现指数退避策略
3. **事件过滤**: 使用 `event_types` 参数过滤不需要的事件类型
4. **历史回放**: 设置 `include_history=true` 可获取最近 50 条历史事件
5. **连接管理**: 前端应实现连接状态监控和错误处理

---

### HITL 人工干预与状态机唤醒

当智能体执行到关键节点需要人工介入时，触发 HITL（Human-in-the-Loop）中断，等待人类反馈后恢复执行。

#### 1. 触发中断

**接口地址**: `POST /api/v1/workflows/{state_id}/interrupt`

**请求体**:
```json
{
  "reason": "human_approval_required",
  "message": "科研计划已生成，请审核并确认是否继续",
  "context": {
    "plan": "研究机器学习在自然语言处理中的应用",
    "steps": ["文献检索", "方法设计", "实验验证"]
  },
  "suggested_actions": [
    "批准并继续",
    "修改计划",
    "取消任务"
  ],
  "priority": "high"
}
```

**请求参数说明**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| reason | string | 是 | 中断原因，枚举值见下方 |
| message | string | 是 | 中断消息 |
| context | object | 否 | 上下文数据 |
| suggested_actions | array | 否 | 建议的操作列表 |
| priority | string | 否 | 优先级，默认 `normal` |

**中断原因枚举** (`reason`):

- `human_approval_required` - 需要人工审批
- `error_recovery` - 错误恢复
- `resource_constraint` - 资源限制
- `user_initiated` - 用户主动触发

**优先级枚举** (`priority`):

- `low` - 低优先级
- `normal` - 正常优先级
- `high` - 高优先级
- `critical` - 关键优先级

**响应示例**:
```json
{
  "reason": "human_approval_required",
  "message": "科研计划已生成，请审核并确认是否继续",
  "session_id": "session_abc123",
  "checkpoint_id": 1,
  "priority": "high",
  "context": {
    "plan": "研究机器学习在自然语言处理中的应用",
    "steps": ["文献检索", "方法设计", "实验验证"]
  },
  "suggested_actions": [
    "批准并继续",
    "修改计划",
    "取消任务"
  ],
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 2. 恢复执行

**接口地址**: `POST /api/v1/workflows/session/{session_id}/resume`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 会话 ID，路径参数 |
| checkpoint_id | integer | 否 | 检查点 ID（可选，默认使用最新检查点） |

**请求体**:
```json
{
  "feedback": "批准并继续，请专注于深度学习模型",
  "action": "approve",
  "additional_data": {
    "focus": "深度学习",
    "excluded_topics": ["传统机器学习"]
  }
}
```

**请求参数说明**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| feedback | string | 是 | 反馈内容 |
| action | string | 否 | 选择的操作 |
| additional_data | object | 否 | 额外的结构化数据 |

**响应示例**:
```json
{
  "checkpoint_id": 1,
  "session_id": "session_abc123",
  "status": "running",
  "message": "工作流已恢复，正在继续执行"
}
```

**使用示例**:
```javascript
// 1. 监听 HITL 中断事件
eventSource.addEventListener('hitl_interrupt', async (event) => {
  const interruptData = JSON.parse(event.data);

  console.log('Workflow interrupted:', interruptData.data.reason);
  console.log('Message:', interruptData.data.message);
  console.log('Suggested actions:', interruptData.data.suggested_actions);

  // 2. 显示用户界面，等待用户反馈
  const feedback = await showUserFeedbackDialog(interruptData);

  // 3. 恢复工作流
  const response = await fetch(
    `http://localhost:8000/api/v1/workflows/session/${interruptData.session_id}/resume`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        feedback: feedback.comment,
        action: feedback.action,
        additional_data: feedback.extraData
      })
    }
  );

  const result = await response.json();
  console.log('Workflow resumed:', result);
});
```

---

### Saga 确定性状态回滚

从历史检查点恢复状态，创建新的执行分支，用于探索不同的决策路径或修正错误。

#### 1. 获取检查点历史

**接口地址**: `GET /api/v1/workflows/session/{session_id}/history`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 会话 ID，路径参数 |
| limit | integer | 否 | 返回记录数限制，默认 50，最大 500 |

**响应示例**:
```json
{
  "session_id": "session_abc123",
  "checkpoints": [
    {
      "id": 1,
      "session_id": "session_abc123",
      "workflow_name": "literature_review",
      "current_stage": "planning",
      "status": "completed",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:01:00Z",
      "has_agent_state": true,
      "has_human_feedback": false,
      "has_error": false
    },
    {
      "id": 2,
      "session_id": "session_abc123",
      "workflow_name": "literature_review",
      "current_stage": "literature_search",
      "status": "paused",
      "created_at": "2024-01-01T00:01:00Z",
      "updated_at": "2024-01-01T00:02:00Z",
      "has_agent_state": true,
      "has_human_feedback": true,
      "has_error": false
    }
  ],
  "total_count": 2
}
```

#### 2. 执行回滚

**接口地址**: `POST /api/v1/workflows/session/{session_id}/rollback`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 当前会话 ID，路径参数 |

**请求体**:
```json
{
  "checkpoint_id": 1,
  "reason": "用户要求修改研究方向",
  "human_instruction": "请从深度学习模型转向传统机器学习方法",
  "additional_state": {
    "focus": "traditional_ml",
    "excluded_topics": ["深度学习", "神经网络"]
  }
}
```

**请求参数说明**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| checkpoint_id | integer | 是 | 目标检查点 ID |
| reason | string | 是 | 回滚原因 |
| human_instruction | string | 否 | 人类修改指令 |
| additional_state | object | 否 | 额外的状态更新 |

**响应示例**:
```json
{
  "original_checkpoint_id": 1,
  "new_checkpoint_id": 3,
  "new_session_id": "session_xyz789",
  "workflow_name": "literature_review",
  "current_stage": "planning",
  "message": "已从检查点 1 回滚并创建新的执行路径"
}
```

**使用示例**:
```javascript
// 1. 获取检查点历史
const response = await fetch(
  'http://localhost:8000/api/v1/workflows/session/session_abc123/history'
);

const history = await response.json();

console.log('Available checkpoints:', history.checkpoints);

// 2. 用户选择回滚到某个检查点
const selectedCheckpoint = history.checkpoints[0];

// 3. 执行回滚
const rollbackResponse = await fetch(
  'http://localhost:8000/api/v1/workflows/session/session_abc123/rollback',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      checkpoint_id: selectedCheckpoint.id,
      reason: '用户要求修改研究方向',
      human_instruction: '请从深度学习模型转向传统机器学习方法'
    })
  }
);

const rollbackResult = await rollbackResponse.json();

console.log('Rollback completed:', rollbackResult);
console.log('New session ID:', rollbackResult.new_session_id);

// 4. 订阅新会话的事件流
const newEventSource = new EventSource(
  `http://localhost:8000/api/stream/events/${rollbackResult.new_session_id}`
);
```

#### 3. 验证检查点状态

**接口地址**: `GET /api/v1/workflows/{state_id}/validate`

**响应示例**:
```json
{
  "checkpoint_id": 1,
  "is_valid": true,
  "state_hash": "a1b2c3d4e5f6...",
  "message": "状态验证通过"
}
```

---

## 辅助接口

### 获取工作流状态

**接口地址**: `GET /api/v1/workflows/{state_id}`

**响应示例**:
```json
{
  "id": 1,
  "session_id": "session_abc123",
  "workflow_name": "literature_review",
  "current_stage": "literature_search",
  "status": "running",
  "agent_state": {
    "context": "研究机器学习在自然语言处理中的应用",
    "goals": ["文献检索", "方法设计", "实验验证"],
    "progress": {
      "total": 100,
      "completed": 45
    }
  },
  "human_feedback": null,
  "error_message": null,
  "metadata": {
    "user_id": "user_001",
    "priority": "high"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z"
}
```

### 获取会话的所有工作流状态

**接口地址**: `GET /api/v1/workflows/session/{session_id}`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 是 | 会话 ID，路径参数 |
| limit | integer | 否 | 返回记录数限制，默认 100，最大 1000 |
| offset | integer | 否 | 偏移量，默认 0 |

### 添加反馈

**接口地址**: `POST /api/v1/workflows/{state_id}/feedback`

**请求体**:
```json
{
  "feedback": "建议增加更多实验对比"
}
```

### 获取统计信息

**接口地址**: `GET /api/v1/workflows/statistics/summary`

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| workflow_name | string | 否 | 工作流名称过滤 |
| days | integer | 否 | 统计天数，默认 30，范围 1-365 |

**响应示例**:
```json
{
  "total": 150,
  "status_stats": {
    "pending": 10,
    "running": 25,
    "paused": 5,
    "completed": 100,
    "failed": 10
  },
  "stage_stats": {
    "planning": 20,
    "literature_search": 40,
    "method_design": 30,
    "experiment": 35,
    "analysis": 20,
    "report": 5
  },
  "avg_duration_seconds": 3600.5
}
```

---

## 错误码定义

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 常见错误

| 错误信息 | 说明 | 解决方案 |
|----------|------|----------|
| `工作流状态不存在` | 指定的工作流状态 ID 不存在 | 检查 state_id 是否正确 |
| `检查点不存在` | 指定的检查点 ID 不存在 | 检查 checkpoint_id 是否正确 |
| `无效的事件类型` | SSE 订阅的事件类型无效 | 检查 event_types 参数 |
| `创建工作流状态失败` | 数据库操作失败 | 检查数据库连接和配置 |
| `触发中断失败` | 中断操作失败 | 检查工作流状态和中断参数 |
| `恢复工作流失败` | 恢复操作失败 | 检查检查点是否存在和状态是否正确 |
| `回滚工作流失败` | 回滚操作失败 | 检查检查点 ID 和状态数据 |

---

## 最佳实践

### 1. SSE 连接管理

```javascript
class SSEManager {
  constructor() {
    this.eventSources = new Map();
  }

  subscribe(sessionId, eventTypes = []) {
    // 如果已存在连接，先关闭
    this.unsubscribe(sessionId);

    const url = new URL(`http://localhost:8000/api/stream/events/${sessionId}`);
    if (eventTypes.length > 0) {
      url.searchParams.set('event_types', eventTypes.join(','));
    }

    const eventSource = new EventSource(url.toString());

    // 心跳检测（30秒无消息则重连）
    let heartbeatTimer = null;
    const resetHeartbeat = () => {
      clearTimeout(heartbeatTimer);
      heartbeatTimer = setTimeout(() => {
        console.warn('SSE heartbeat timeout, reconnecting...');
        this.subscribe(sessionId, eventTypes);
      }, 30000);
    };

    eventSource.addEventListener('heartbeat', resetHeartbeat);
    resetHeartbeat();

    // 错误处理
    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
      // 指数退避重连
      setTimeout(() => {
        this.subscribe(sessionId, eventTypes);
      }, 1000 * Math.pow(2, Math.random() * 5));
    };

    this.eventSources.set(sessionId, eventSource);
    return eventSource;
  }

  unsubscribe(sessionId) {
    const eventSource = this.eventSources.get(sessionId);
    if (eventSource) {
      eventSource.close();
      this.eventSources.delete(sessionId);
    }
  }

  unsubscribeAll() {
    this.eventSources.forEach((eventSource) => {
      eventSource.close();
    });
    this.eventSources.clear();
  }
}

// 使用示例
const sseManager = new SSEManager();
const eventSource = sseManager.subscribe('session_abc123', ['agent_thought', 'tool_call_start']);

// 页面卸载时关闭所有连接
window.addEventListener('beforeunload', () => {
  sseManager.unsubscribeAll();
});
```

### 2. HITL 工作流集成

```javascript
class HITLWorkflow {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.eventSource = null;
    this.pausedCheckpoints = new Map();
  }

  start() {
    this.eventSource = sseManager.subscribe(this.sessionId);

    this.eventSource.addEventListener('hitl_interrupt', async (event) => {
      const interruptData = JSON.parse(event.data);
      await this.handleInterrupt(interruptData);
    });
  }

  async handleInterrupt(interruptData) {
    // 显示中断对话框
    const feedback = await this.showInterruptDialog(interruptData);

    // 恢复工作流
    const response = await fetch(
      `http://localhost:8000/api/v1/workflows/session/${this.sessionId}/resume`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feedback: feedback.comment,
          action: feedback.action,
          additional_data: feedback.extraData
        })
      }
    );

    const result = await response.json();
    console.log('Workflow resumed:', result);
  }

  async showInterruptDialog(interruptData) {
    return new Promise((resolve) => {
      // 显示对话框 UI
      const dialog = document.createElement('div');
      dialog.innerHTML = `
        <h3>工作流需要人工介入</h3>
        <p>${interruptData.data.message}</p>
        <div>
          ${interruptData.data.suggested_actions.map(action =>
            `<button onclick="handleAction('${action}')">${action}</button>`
          ).join('')}
        </div>
        <input type="text" id="feedback-input" placeholder="请输入反馈">
      `;

      document.body.appendChild(dialog);

      window.handleAction = (action) => {
        const comment = document.getElementById('feedback-input').value;
        document.body.removeChild(dialog);
        resolve({ action, comment });
      };
    });
  }

  stop() {
    sseManager.unsubscribe(this.sessionId);
  }
}
```

### 3. Saga 回滚管理

```javascript
class RollbackManager {
  async getCheckpointHistory(sessionId) {
    const response = await fetch(
      `http://localhost:8000/api/v1/workflows/session/${sessionId}/history`
    );
    return await response.json();
  }

  async rollback(sessionId, checkpointId, reason, humanInstruction) {
    const response = await fetch(
      `http://localhost:8000/api/v1/workflows/session/${sessionId}/rollback`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          checkpoint_id: checkpointId,
          reason,
          human_instruction: humanInstruction
        })
      }
    );
    return await response.json();
  }

  async validateCheckpoint(stateId) {
    const response = await fetch(
      `http://localhost:8000/api/v1/workflows/${stateId}/validate`
    );
    return await response.json();
  }

  async performRollback(sessionId) {
    // 1. 获取检查点历史
    const history = await this.getCheckpointHistory(sessionId);

    // 2. 显示检查点选择界面
    const selectedCheckpoint = await this.showCheckpointSelector(history);

    // 3. 验证检查点状态
    const validation = await this.validateCheckpoint(selectedCheckpoint.id);
    if (!validation.is_valid) {
      throw new Error('检查点状态无效，无法回滚');
    }

    // 4. 获取回滚原因和指令
    const { reason, instruction } = await this.showRollbackDialog();

    // 5. 执行回滚
    const result = await this.rollback(
      sessionId,
      selectedCheckpoint.id,
      reason,
      instruction
    );

    return result;
  }

  async showCheckpointSelector(history) {
    return new Promise((resolve) => {
      // 显示检查点选择界面
      const selector = document.createElement('div');
      selector.innerHTML = `
        <h3>选择回滚检查点</h3>
        <select id="checkpoint-select">
          ${history.checkpoints.map(cp =>
            `<option value="${cp.id}">
              ${cp.current_stage} - ${cp.status} (${new Date(cp.created_at).toLocaleString()})
            </option>`
          ).join('')}
        </select>
        <button id="confirm-btn">确认</button>
      `;

      document.body.appendChild(selector);

      document.getElementById('confirm-btn').addEventListener('click', () => {
        const selectedId = parseInt(document.getElementById('checkpoint-select').value);
        const checkpoint = history.checkpoints.find(cp => cp.id === selectedId);
        document.body.removeChild(selector);
        resolve(checkpoint);
      });
    });
  }

  async showRollbackDialog() {
    return new Promise((resolve) => {
      const dialog = document.createElement('div');
      dialog.innerHTML = `
        <h3>回滚原因</h3>
        <input type="text" id="reason-input" placeholder="请输入回滚原因">
        <h3>修改指令</h3>
        <input type="text" id="instruction-input" placeholder="请输入修改指令">
        <button id="confirm-btn">确认回滚</button>
      `;

      document.body.appendChild(dialog);

      document.getElementById('confirm-btn').addEventListener('click', () => {
        const reason = document.getElementById('reason-input').value;
        const instruction = document.getElementById('instruction-input').value;
        document.body.removeChild(dialog);
        resolve({ reason, instruction });
      });
    });
  }
}
```

### 4. 错误处理和重试

```javascript
class APIClient {
  constructor(baseURL = 'http://localhost:8000/api') {
    this.baseURL = baseURL;
    this.maxRetries = 3;
    this.retryDelay = 1000;
  }

  async request(url, options = {}) {
    let lastError = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const response = await fetch(`${this.baseURL}${url}`, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...options.headers,
          },
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        lastError = error;
        console.warn(`Request failed (attempt ${attempt + 1}/${this.maxRetries}):`, error);

        // 最后一次尝试失败，抛出错误
        if (attempt === this.maxRetries - 1) {
          throw error;
        }

        // 指数退避
        await new Promise(resolve =>
          setTimeout(resolve, this.retryDelay * Math.pow(2, attempt))
        );
      }
    }

    throw lastError;
  }

  async createWorkflow(data) {
    return this.request('/v1/workflows/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getWorkflow(stateId) {
    return this.request(`/v1/workflows/${stateId}`);
  }

  async resumeWorkflow(sessionId, feedbackData) {
    return this.request(`/v1/workflows/session/${sessionId}/resume`, {
      method: 'POST',
      body: JSON.stringify(feedbackData),
    });
  }

  async rollbackWorkflow(sessionId, rollbackData) {
    return this.request(`/v1/workflows/session/${sessionId}/rollback`, {
      method: 'POST',
      body: JSON.stringify(rollbackData),
    });
  }
}

// 使用示例
const apiClient = new APIClient();

try {
  const workflow = await apiClient.createWorkflow({
    session_id: 'session_abc123',
    workflow_name: 'literature_review',
    current_stage: 'planning',
  });

  console.log('Workflow created:', workflow);
} catch (error) {
  console.error('Failed to create workflow:', error);
  // 显示错误提示
  alert(`操作失败: ${error.message}`);
}
```

---

## 附录

### A. 完整的事件类型列表

| 事件类型 | 说明 | 数据字段 |
|----------|------|----------|
| `agent_thought` | 智能体思考 | `thought: string` |
| `agent_action` | 智能体行动 | `action: string`, `params: object` |
| `agent_response` | 智能体响应 | `response: string` |
| `tool_call_start` | 工具调用开始 | `tool: string`, `arguments: object` |
| `tool_call_result` | 工具调用结果 | `tool: string`, `arguments: object`, `result: any` |
| `tool_call_error` | 工具调用错误 | `tool: string`, `arguments: object`, `error: string` |
| `sandbox_start` | 沙箱启动 | `execution_id: string`, `image: string` |
| `sandbox_stdout` | 沙箱标准输出 | `content: string`, `execution_id: string` |
| `sandbox_stderr` | 沙箱标准错误 | `content: string`, `execution_id: string` |
| `sandbox_complete` | 沙箱完成 | `execution_id: string`, `exit_code: number` |
| `sandbox_error` | 沙箱错误 | `execution_id: string`, `error: string` |
| `workflow_start` | 工作流启动 | `workflow_name: string` |
| `workflow_stage_change` | 工作流阶段变更 | `from_stage: string`, `to_stage: string`, `reason: string` |
| `workflow_checkpoint` | 工作流检查点 | `checkpoint_id: number`, `stage: string` |
| `workflow_complete` | 工作流完成 | `result: object` |
| `workflow_error` | 工作流错误 | `error: string` |
| `hitl_interrupt` | HITL 中断 | `reason: string`, `message: string`, `context: object` |
| `hitl_resume` | HITL 恢复 | `checkpoint_id: number` |
| `hitl_feedback` | HITL 反馈 | `feedback: string` |
| `heartbeat` | 心跳 | `timestamp: string` |
| `error` | 错误 | `error: string` |

### B. 数据库连接配置

**开发环境** (SQLite):
```
DB_URL=sqlite+aiosqlite:///./epistemicflow.db
```

**生产环境** (PostgreSQL):
```
DB_URL=postgresql+asyncpg://epistemicflow:password@db:5432/epistemicflow
```

### C. 环境变量配置

创建 `.env` 文件：

```bash
# 应用配置
APP_ENVIRONMENT=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
APP_CORS_ORIGINS=["http://localhost:3000"]

# 数据库配置
DB_PASSWORD=your_secure_password
DB_URL=postgresql+asyncpg://epistemicflow:${DB_PASSWORD}@db:5432/epistemicflow

# 大模型配置
LLM_GPT4__PROVIDER=openai
LLM_GPT4__API_KEY=your-openai-api-key
LLM_GPT4__MODEL_NAME=gpt-4

DEFAULT_LLM=gpt4
```

---

## 联系方式

如有问题或建议，请联系：

- **项目仓库**: https://github.com/yourusername/epistemicflow
- **问题反馈**: https://github.com/yourusername/epistemicflow/issues
- **邮箱**: team@epistemicflow.ai

---

**文档结束**
