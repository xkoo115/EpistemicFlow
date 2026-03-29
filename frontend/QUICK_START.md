# TerminalLog 组件快速启动指南

## 🚀 5 分钟快速上手

### 步骤 1: 确认依赖

所有必需的依赖已在 `package.json` 中配置,无需额外安装。

```bash
# 已包含的依赖
- react: ^19.2.4
- lucide-react: ^1.7.0
- clsx: ^2.1.1
- tailwind-merge: ^3.5.0
```

### 步骤 2: 集成到 WorkbenchLayout

打开 `src/App.tsx` (或你的主布局文件),替换 ActivityLog 为 TerminalLog:

```tsx
import React from 'react'
import { WorkbenchLayout } from '@/layouts/WorkbenchLayout'
import { AgentRoster } from '@/components/workbench/AgentRoster'
import { MainCanvas } from '@/components/workbench/MainCanvas'
import { TerminalLog } from '@/components/workbench/TerminalLog'

function App() {
  return (
    <div className="h-screen bg-dark-bg-primary">
      <WorkbenchLayout
        leftSidebar={<AgentRoster />}
        mainCanvas={<MainCanvas />}
        rightSidebar={
          <TerminalLog
            endpoint="/api/stream"
            maxLogEntries={1000}
            showToolbar={true}
          />
        }
      />
    </div>
  )
}

export default App
```

### 步骤 3: 配置后端 SSE 端点

确保你的后端提供 SSE 端点。以下是 FastAPI 示例:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json
from datetime import datetime

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

### 步骤 4: 启动开发服务器

```bash
# 启动前端开发服务器
npm run dev

# 启动后端服务器 (根据你的后端框架)
# 例如: uvicorn main:app --reload
```

### 步骤 5: 测试功能

1. 打开浏览器访问 `http://localhost:5173`
2. 查看右侧栏的实时日志
3. 测试以下功能:
   - ✅ 自动滚动到底部
   - ✅ 手动向上滚动 (暂停自动滚动)
   - ✅ 点击滚动按钮恢复自动滚动
   - ✅ 使用过滤器按级别、来源、关键词过滤
   - ✅ 导出日志为文本文件
   - ✅ 清空日志

## 📦 文件清单

### 新增文件

```
src/
├── hooks/
│   └── useSSEStream.ts                 # SSE 连接 Hook
├── types/
│   └── log.ts                          # 日志类型定义
├── lib/
│   └── logUtils.ts                     # 日志工具函数
├── components/
│   └── workbench/
│       ├── TerminalLog.tsx             # 终端日志组件 (新)
│       └── TerminalLog.README.md       # 组件文档
├── __tests__/
│   ├── mocks/
│   │   └── mockSSEStream.ts            # Mock SSE 服务
│   ├── TerminalLog.test.tsx            # 组件测试
│   ├── useSSEStream.test.ts            # Hook 测试
│   └── logUtils.test.ts                # 工具函数测试
└── examples/
    └── TerminalLogExample.tsx          # 使用示例
```

### 修改文件

- `src/App.tsx` (可选): 集成 TerminalLog 组件

## 🔧 配置选项

### TerminalLog 组件 Props

```tsx
<TerminalLog
  endpoint="/api/stream"           // SSE 端点 URL (默认: /api/stream)
  className="custom-styles"        // 自定义类名 (可选)
  maxLogEntries={2000}             // 最大日志条目数 (默认: 1000)
  showToolbar={true}               // 是否显示工具栏 (默认: true)
/>
```

### useSSEStream Hook 选项

```tsx
const { messages, isConnected, reconnect } = useSSEStream({
  url: '/api/stream',
  parseMessage: (data) => JSON.parse(data),  // 消息解析器 (可选)
  reconnectDelayBase: 1000,                   // 重连延迟基数 (默认: 1000ms)
  maxReconnectDelay: 30000,                   // 最大重连延迟 (默认: 30000ms)
  autoReconnect: true,                        // 是否自动重连 (默认: true)
  onOpen: () => console.log('连接已建立'),     // 连接成功回调 (可选)
  onMessage: (msg) => console.log('收到消息'), // 消息接收回调 (可选)
  onError: (err) => console.error('错误'),    // 错误回调 (可选)
  onClose: () => console.log('连接已关闭'),   // 连接关闭回调 (可选)
})
```

## 🧪 运行测试

```bash
# 运行所有测试
npm test

# 运行测试并生成覆盖率报告
npm test:run -- --coverage

# 运行测试 UI (可视化测试界面)
npm test:ui
```

## 🎨 自定义样式

### 修改颜色映射

编辑 `src/lib/logUtils.ts`:

```typescript
export const LOG_LEVEL_COLOR_MAP: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: 'text-gray-500',
  [LogLevel.INFO]: 'text-accent-cyan-500',
  [LogLevel.SUCCESS]: 'text-accent-green-500',
  [LogLevel.WARN]: 'text-accent-amber-500',
  [LogLevel.ERROR]: 'text-accent-red-500',
}
```

### 修改 Tailwind 配置

编辑 `tailwind.config.js`:

```javascript
export default {
  theme: {
    extend: {
      colors: {
        'accent-cyan': {
          DEFAULT: '#00D9FF',
          500: '#00D9FF',
        },
        // 添加更多自定义颜色...
      },
    },
  },
}
```

## 🐛 常见问题

### Q: 无法连接到 SSE 端点

**A**: 检查以下几点:
1. 后端 SSE 端点是否正常运行
2. URL 路径是否正确
3. 是否存在 CORS 问题
4. 浏览器控制台是否有错误信息

### Q: 日志不会自动滚动

**A**: 这是因为你手动向上滚动过,导致自动滚动暂停。点击右下角的滚动按钮恢复自动滚动。

### Q: 内存占用过高

**A**: 减少 `maxLogEntries` 的值:

```tsx
<TerminalLog endpoint="/api/stream" maxLogEntries={500} />
```

### Q: 测试失败

**A**: 确保所有依赖已安装:

```bash
npm install
```

## 📚 更多资源

- [完整文档](./src/components/workbench/TerminalLog.README.md)
- [实现总结](./SSE_IMPLEMENTATION_SUMMARY.md)
- [使用示例](./src/examples/TerminalLogExample.tsx)
- [后端集成示例](./src/components/workbench/TerminalLog.README.md#后端集成示例)

## 🤝 获取帮助

如果遇到问题:
1. 查看 [完整文档](./src/components/workbench/TerminalLog.README.md)
2. 查看 [故障排除](./src/components/workbench/TerminalLog.README.md#故障排除)
3. 运行测试确认功能正常: `npm test`
4. 检查浏览器控制台和网络请求

## ✅ 验证清单

完成以下步骤确认集成成功:

- [ ] 组件正确渲染在右侧栏
- [ ] 显示"实时连接"状态
- [ ] 接收到后端发送的日志消息
- [ ] 日志正确显示级别颜色
- [ ] 日志正确显示来源图标
- [ ] 自动滚动功能正常
- [ ] 手动滚动时暂停自动滚动
- [ ] 过滤器功能正常
- [ ] 导出功能正常
- [ ] 清空功能正常
- [ ] 所有测试通过: `npm test`

## 🎉 完成!

你已经成功集成了 TerminalLog 组件!现在你可以在 EpistemicFlow 平台中实时监控智能体的思考过程和沙箱执行日志了。

享受"玻璃盒"级别的透明度吧! 🚀
