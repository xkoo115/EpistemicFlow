# TerminalLog 组件使用文档

## 概述

TerminalLog 是一个用于实时显示 SSE (Server-Sent Events) 流式日志的 React 组件,专为 EpistemicFlow 平台设计。它提供了类似终端的日志查看体验,支持多种日志级别的颜色映射、自动滚动、过滤和导出功能。

## 功能特性

### 核心功能
- ✅ **SSE 实时连接**: 使用浏览器原生 EventSource API 连接后端 SSE 端点
- ✅ **自动重连机制**: 指数退避算法,支持断线重连
- ✅ **终端风格渲染**: 类似 tail -f 的日志查看体验
- ✅ **智能自动滚动**: 用户手动滚动时暂停,滚动到底部时恢复
- ✅ **日志级别映射**: 不同级别使用不同颜色 (DEBUG/灰, INFO/青, SUCCESS/绿, WARN/琥珀, ERROR/红)
- ✅ **日志来源标识**: 使用 emoji 图标区分不同来源 (系统/智能体/工具/沙箱/网络)
- ✅ **丰富的元数据**: 显示时间戳、智能体 ID、工具名称等
- ✅ **强大的过滤功能**: 支持按级别、来源、关键词过滤
- ✅ **日志导出**: 导出为纯文本文件
- ✅ **内存管理**: 限制最大日志条目数,防止内存溢出

### 安全特性
- ✅ **内存泄漏防护**: 组件卸载时自动清理所有资源
- ✅ **错误处理**: 完善的错误捕获和重试机制
- ✅ **类型安全**: 完整的 TypeScript 类型定义

## 安装依赖

项目已包含所有必需的依赖:

```json
{
  "react": "^19.2.4",
  "lucide-react": "^1.7.0",
  "clsx": "^2.1.1",
  "tailwind-merge": "^3.5.0"
}
```

## 快速开始

### 基础使用

```tsx
import { TerminalLog } from '@/components/workbench/TerminalLog'

function App() {
  return (
    <div className="h-screen">
      <TerminalLog endpoint="/api/stream" />
    </div>
  )
}
```

### 自定义配置

```tsx
import { TerminalLog } from '@/components/workbench/TerminalLog'

function App() {
  return (
    <div className="h-screen">
      <TerminalLog
        endpoint="/api/stream"
        className="custom-styles"
        maxLogEntries={2000}
        showToolbar={true}
      />
    </div>
  )
}
```

## 组件 API

### Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `endpoint` | `string` | `'/api/stream'` | SSE 端点 URL |
| `className` | `string` | `undefined` | 自定义类名 |
| `maxLogEntries` | `number` | `1000` | 最大日志条目数 |
| `showToolbar` | `boolean` | `true` | 是否显示工具栏 |

## SSE 数据格式

后端 SSE 端点应返回以下格式的 JSON 数据:

```json
{
  "level": "INFO",
  "source": "AGENT_THINKING",
  "message": "智能体正在分析问题...",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "agentId": "agent-1",
  "toolName": "math_calculator",
  "metadata": {
    "executionTime": 123.45,
    "success": true
  }
}
```

### 日志级别 (LogLevel)

- `DEBUG`: 调试信息 (灰色)
- `INFO`: 一般信息 (青色)
- `SUCCESS`: 成功状态 (绿色)
- `WARN`: 警告信息 (琥珀色)
- `ERROR`: 错误信息 (红色)

### 日志来源 (LogSource)

- `SYSTEM`: 系统提示 (⚙️)
- `AGENT_THINKING`: 智能体思考 (🤖)
- `TOOL_CALL`: 工具调用 (🔧)
- `SANDBOX_EXECUTION`: 沙箱执行 (📦)
- `NETWORK`: 网络请求 (🌐)

## 自定义 Hook: useSSEStream

如果需要更底层的控制,可以直接使用 `useSSEStream` Hook:

```tsx
import { useSSEStream } from '@/hooks/useSSEStream'

function MyComponent() {
  const { messages, isConnected, error, reconnect, disconnect } = useSSEStream({
    url: '/api/stream',
    parseMessage: (data) => JSON.parse(data),
    reconnectDelayBase: 1000,
    maxReconnectDelay: 30000,
    autoReconnect: true,
    onOpen: () => console.log('连接已建立'),
    onMessage: (msg) => console.log('收到消息:', msg),
    onError: (err) => console.error('连接错误:', err),
    onClose: () => console.log('连接已关闭'),
  })

  return (
    <div>
      <div>连接状态: {isConnected ? '已连接' : '未连接'}</div>
      <div>消息数量: {messages.length}</div>
      {error && <div>错误: {error.type}</div>}
    </div>
  )
}
```

## 测试

### 运行测试

```bash
# 运行所有测试
npm test

# 运行测试并生成覆盖率报告
npm test:run -- --coverage

# 运行测试 UI
npm test:ui
```

### 测试文件

- `TerminalLog.test.tsx`: 组件集成测试
- `useSSEStream.test.ts`: Hook 单元测试
- `logUtils.test.ts`: 工具函数单元测试

### Mock 数据

使用内置的 Mock SSE 服务进行测试:

```tsx
import { createMockSSE } from '@/__tests__/mocks/mockSSEStream'

// 创建 Mock SSE 实例
const mockSSE = createMockSSE('/api/stream', {
  interval: 500,
  autoSend: true,
  maxMessages: 10,
})

// 手动发送消息
mockSSE.send({
  level: 'INFO',
  source: 'SYSTEM',
  message: '测试消息',
  timestamp: new Date().toISOString(),
})

// 关闭连接
mockSSE.close()
```

## 样式定制

组件使用 Tailwind CSS,可以通过以下方式定制样式:

### 全局样式 (index.css)

```css
/* 玻璃态面板 */
.glass-panel {
  @apply bg-dark-bg-primary/80 backdrop-blur-sm border border-dark-border;
}

/* 终端文本 */
.terminal-text {
  @apply font-mono text-sm leading-relaxed;
}

/* 面板标题 */
.panel-title {
  @apply text-sm font-medium text-gray-300;
}

/* 状态指示器 */
.status-computing {
  @apply text-accent-cyan-500;
}

.status-suspended {
  @apply text-accent-amber-500;
}

.status-error {
  @apply text-accent-red-500;
}

.status-success {
  @apply text-accent-green-500;
}
```

### Tailwind 配置 (tailwind.config.js)

```javascript
export default {
  theme: {
    extend: {
      colors: {
        'accent-cyan': {
          DEFAULT: '#00D9FF',
          500: '#00D9FF',
        },
        'accent-amber': {
          DEFAULT: '#FFB800',
          500: '#FFB800',
        },
        'accent-red': {
          DEFAULT: '#FF3B3B',
          500: '#FF3B3B',
        },
        'accent-green': {
          DEFAULT: '#00FF88',
          500: '#00FF88',
        },
        'dark-bg': {
          primary: '#0A0E1A',
          secondary: '#111827',
          tertiary: '#1F2937',
        },
        'dark-border': {
          DEFAULT: '#2D3748',
        },
      },
    },
  },
}
```

## 性能优化

### 内存管理

- 默认限制最大日志条目数为 1000
- 可通过 `maxLogEntries` prop 调整
- 组件卸载时自动清理所有资源

### 渲染优化

- 使用 `useCallback` 和 `useMemo` 优化重渲染
- 虚拟滚动支持 (计划中)
- 消息批量更新 (计划中)

## 故障排除

### 连接问题

**问题**: 无法连接到 SSE 端点

**解决方案**:
1. 检查后端 SSE 端点是否正常运行
2. 确认 URL 路径正确
3. 检查浏览器控制台是否有 CORS 错误
4. 查看网络请求是否成功

### 自动滚动问题

**问题**: 日志不会自动滚动到底部

**解决方案**:
1. 检查是否手动向上滚动过 (会暂停自动滚动)
2. 点击右下角的滚动按钮恢复自动滚动
3. 确认容器高度设置正确

### 内存问题

**问题**: 页面内存占用过高

**解决方案**:
1. 减少 `maxLogEntries` 的值
2. 使用过滤器减少显示的日志数量
3. 定期清空日志

## 后端集成示例

### FastAPI 示例

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()

@app.get("/api/stream")
async def stream_logs():
    async def generate_logs():
        while True:
            log_data = {
                "level": "INFO",
                "source": "SYSTEM",
                "message": "系统运行中...",
                "timestamp": datetime.now().isoformat(),
            }
            yield f"data: {json.dumps(log_data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

### Node.js 示例

```javascript
const express = require('express');
const app = express();

app.get('/api/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const sendLog = () => {
    const logData = {
      level: 'INFO',
      source: 'SYSTEM',
      message: '系统运行中...',
      timestamp: new Date().toISOString(),
    };
    res.write(`data: ${JSON.stringify(logData)}\n\n`);
  };

  const interval = setInterval(sendLog, 1000);

  req.on('close', () => {
    clearInterval(interval);
  });
});

app.listen(3000);
```

## 贡献指南

欢迎提交 Issue 和 Pull Request!

## 许可证

MIT License
