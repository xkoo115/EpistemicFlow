# WorkflowCanvas 组件使用指南

## 概述

WorkflowCanvas 是 EpistemicFlow 前端的核心画布组件，用于展示 AI 生成内容和处理 HITL（Human-in-the-Loop）干预。

## 安装依赖

```bash
npm install react-markdown remark-gfm react-diff-viewer-continued @radix-ui/react-slider @radix-ui/react-select @radix-ui/react-label
```

## 组件结构

```
src/components/workflow/
├── WorkflowCanvas.tsx          # 主画布组件
├── AutoGenerationView.tsx      # 自动生成视图（Markdown 渲染）
├── InterventionDashboard.tsx   # 结构化干预仪表板
├── DiffViewer.tsx              # 差异对比视图
├── StructuredForm.tsx          # 超参数调整表单
├── index.ts                    # 导出索引
└── WorkflowCanvas.test.tsx     # 单元测试
```

## 基本用法

### 1. 自动生成视图（RUNNING 状态）

```tsx
import { WorkflowCanvas } from '@/components/workflow';

function App() {
  return (
    <WorkflowCanvas
      status="RUNNING"
      sessionId="session-123"
      autoGenerationData={{
        content: '# 科研综述\n\n这是 AI 生成的内容...',
        contentType: 'markdown',
        title: '科研综述草稿',
        progress: 75,
      }}
    />
  );
}
```

### 2. 结构化干预仪表板（WAITING_FOR_HUMAN 状态）

```tsx
import { WorkflowCanvas } from '@/components/workflow';

function App() {
  const handleResume = async (payload) => {
    console.log('用户提交的干预数据:', payload);
    // 调用后端 API 恢复工作流
  };

  return (
    <WorkflowCanvas
      status="WAITING_FOR_HUMAN"
      sessionId="session-123"
      hitlData={{
        nodeId: 'node-456',
        originalProposal: '原始 AI 提案内容',
        currentHyperparameters: {
          temperature: 0.7,
          topP: 0.9,
          maxTokens: 2048,
          datasetPath: '/data/default.csv',
        },
        availableDatasets: ['/data/default.csv', '/data/alternative.csv'],
        reason: '需要人工审核',
      }}
      onResume={handleResume}
    />
  );
}
```

## 状态切换逻辑

| 状态 | 渲染视图 | 说明 |
|------|---------|------|
| RUNNING | AutoGenerationView | 正常执行中，显示 AI 生成内容 |
| COMPLETED | AutoGenerationView | 执行完成，显示最终结果 |
| ERROR | ErrorView | 执行出错，显示错误提示 |
| WAITING_FOR_HUMAN | InterventionDashboard | HITL 挂起，显示干预界面 |

## TypeScript 接口

### WorkflowCanvasProps

```typescript
interface WorkflowCanvasProps {
  status: WorkflowStatus;
  sessionId: string;
  autoGenerationData?: AutoGenerationData;
  hitlData?: HitlSuspensionData;
  onResume?: (payload: InterventionPayload) => Promise<void>;
  className?: string;
}
```

### InterventionPayload

```typescript
interface InterventionPayload {
  sessionId: string;
  modifiedContent: string;
  originalContent: string;
  hyperparameters: Hyperparameters;
  timestamp: string;
  userNote?: string;
}
```

## 深色模式

组件已完全适配深色模式，使用 Tailwind CSS 的 `dark:` 前缀和 CSS 变量：

- 背景色：`bg-background`, `bg-card`, `bg-secondary`
- 文本色：`text-foreground`, `text-muted-foreground`
- 边框色：`border-border`
- 强调色：`text-primary`, `bg-primary`

## 测试

运行单元测试：

```bash
npm test src/components/workflow/WorkflowCanvas.test.tsx
```

测试覆盖：

- ✅ 状态切换逻辑
- ✅ 视图正确渲染
- ✅ 表单提交数据结构
- ✅ Loading 状态
- ✅ API 调用验证

## API 集成

### 恢复工作流端点

```
POST /api/workflows/{session_id}/resume
```

请求体：

```json
{
  "sessionId": "session-123",
  "modifiedContent": "用户修改后的内容",
  "originalContent": "原始 AI 提案",
  "hyperparameters": {
    "temperature": 0.8,
    "topP": 0.95,
    "maxTokens": 3000,
    "datasetPath": "/data/alternative.csv"
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

## 注意事项

1. **性能优化**：Markdown 内容较大时，考虑使用虚拟滚动
2. **错误处理**：API 调用失败时，组件会捕获错误并记录到控制台
3. **防抖**：提交按钮已实现防抖，防止重复提交
4. **可访问性**：所有交互元素都包含 ARIA 标签

## 后续扩展

- [ ] 支持多人协作编辑
- [ ] 添加版本历史对比
- [ ] 集成代码语法高亮
- [ ] 支持图片和图表渲染
