# AgentSidebar 组件实现总结

## 任务完成情况

✅ **所有任务已完成**

1. ✅ 安装 @xyflow/react 依赖
2. ✅ 探索项目结构,了解现有组件和主题配置
3. ✅ 创建 AgentSidebar.tsx 主组件(智能体列表 + Saga 树)
4. ✅ 创建 RollbackModal.tsx 回滚模态框组件
5. ✅ 编写 AgentSidebar 的单元测试

## 实现内容

### 1. 类型定义文件 (`frontend/src/types/saga.ts`)

定义了以下核心类型:

- `AgentStatus`: 智能体状态枚举(IDLE, BUSY, SUSPENDED, ERROR, SUCCESS)
- `Agent`: 智能体信息接口
- `SagaCheckpoint`: Saga 检查点节点接口
- `RollbackRequest`: 回滚请求接口
- `RollbackResponse`: 回滚响应接口
- `SagaNodeData`: React Flow 节点数据接口
- `SagaEdgeData`: React Flow 边数据接口

### 2. AgentSidebar 主组件 (`frontend/src/components/workbench/AgentSidebar.tsx`)

**核心功能:**

#### 上半部分:智能体实时拓扑

- 展示当前活跃的智能体列表(首席研究员、新颖性审稿人等)
- 使用脉冲动画表现智能体状态:
  - `BUSY` → 青色脉冲动画(计算中)
  - `SUSPENDED` → 琥珀色(HITL 挂起)
  - `ERROR` → 红色(错误)
  - `SUCCESS` → 绿色(已完成)
  - `IDLE` → 灰色(闲置)

#### 下半部分:Saga 时间旅行可视化树

- 使用 @xyflow/react 渲染垂直方向的流程树
- 清晰展示主干线以及因人类干预产生的"分叉"路径
- 支持缩放、平移、小地图等交互功能

**核心算法:数据结构转换**

```typescript
/**
 * 将 Saga 检查点数据转换为 React Flow 节点和边
 * 
 * 转换逻辑:
 * 1. 遍历所有检查点,为每个检查点创建一个 React Flow 节点
 * 2. 节点的位置通过层级计算得出(垂直布局)
 * 3. 对于有相同 parent_id 的多个节点,识别为分叉,横向排列
 * 4. 为每个非根节点创建一条边,连接到其父节点
 */
const convertCheckpointsToFlowElements = (checkpoints: SagaCheckpoint[])
```

**关键特性:**

- 分叉节点识别:通过 `parent_id` 相同的多个节点识别分叉
- 分叉节点样式:使用琥珀色边框高亮显示
- 运行状态动画:运行中的节点边使用动画效果
- 响应式布局:自动计算节点位置,支持多级分叉

### 3. RollbackModal 组件 (`frontend/src/components/workbench/RollbackModal.tsx`)

**功能:**

- 当用户点击 Saga 树中的历史节点时弹出
- 显示目标检查点信息(ID、时间、状态)
- 提供纠偏指令输入框(支持验证)
- 提交回滚请求到后端 API

**交互流程:**

1. 用户点击历史节点 → 模态框打开
2. 用户输入纠偏指令 → 验证输入(至少 10 个字符)
3. 用户点击提交 → 调用 `POST /workflows/{session_id}/rollback`
4. 回滚成功 → 模态框关闭,刷新 Saga 树

**UI 特性:**

- 深色主题设计,与全局主题一致
- 玻璃态效果(backdrop-blur)
- 输入验证和错误提示
- 加载状态显示
- 键盘支持(ESC 关闭)

### 4. 单元测试 (`frontend/src/components/workbench/__tests__/AgentSidebar.test.tsx`)

**测试覆盖:**

- ✅ 组件正确挂载和渲染
- ✅ 智能体列表正确显示
- ✅ Saga 树容器正确渲染
- ✅ 状态指示器正确显示
- ✅ 分叉节点正确识别
- ✅ 数据转换函数正确工作
- ✅ 相同 parent_id 的多个节点正确处理(分叉)

**测试结果:**

```
✓ src/components/workbench/__tests__/AgentSidebar.test.tsx (7 tests) 169ms

Test Files  1 passed (1)
     Tests  7 passed (7)
```

## Mock 数据说明

为了便于开发和测试,提供了以下 Mock 数据:

### Mock 智能体数据

```typescript
const MOCK_AGENTS: Agent[] = [
  { id: 'agent-1', name: '首席研究员', status: AgentStatus.BUSY, ... },
  { id: 'agent-2', name: '新颖性审稿人', status: AgentStatus.IDLE, ... },
  { id: 'agent-3', name: '数据分析专家', status: AgentStatus.SUSPENDED, ... },
  { id: 'agent-4', name: '文献检索员', status: AgentStatus.SUCCESS, ... },
]
```

### Mock Saga 检查点数据(包含分叉结构)

```typescript
const MOCK_SAGA_CHECKPOINTS: SagaCheckpoint[] = [
  { checkpoint_id: 'cp-1', parent_id: null, stage_name: '阶段一:文献检索', ... },
  { checkpoint_id: 'cp-2', parent_id: 'cp-1', stage_name: '阶段二:数据分析', ... },
  { checkpoint_id: 'cp-3', parent_id: 'cp-2', stage_name: '阶段三:自动执行前', ... },
  { checkpoint_id: 'cp-4', parent_id: 'cp-3', stage_name: '阶段四:结果生成', ... },
  // 分叉节点1:从 cp-3 分叉
  { checkpoint_id: 'cp-5', parent_id: 'cp-3', stage_name: '阶段三:人工干预分支A', is_fork: true, ... },
  { checkpoint_id: 'cp-6', parent_id: 'cp-5', stage_name: '阶段四:分支A执行', is_fork: true, ... },
  // 分叉节点2:从 cp-3 分叉
  { checkpoint_id: 'cp-7', parent_id: 'cp-3', stage_name: '阶段三:人工干预分支B', is_fork: true, ... },
]
```

## 技术栈

- **React 19.2.4** - 前端框架
- **TypeScript 5.9.3** - 类型安全
- **@xyflow/react** - 流程图可视化库
- **Tailwind CSS 3.4.19** - 样式框架
- **Lucide React** - 图标库
- **Vitest 4.1.2** - 测试框架
- **Testing Library** - React 组件测试

## 文件结构

```
frontend/src/
├── types/
│   └── saga.ts                          # Saga 相关类型定义
├── components/
│   └── workbench/
│       ├── AgentSidebar.tsx             # 主组件
│       ├── RollbackModal.tsx            # 回滚模态框
│       └── __tests__/
│           └── AgentSidebar.test.tsx    # 单元测试
```

## 后续工作建议

1. **API 集成**:将 Mock 数据替换为真实的后端 API 调用
   - `GET /api/workflows/{session_id}/checkpoints` - 获取检查点列表
   - `POST /api/workflows/{session_id}/rollback` - 执行回滚

2. **实时更新**:使用 SSE 实现智能体状态和 Saga 树的实时更新

3. **性能优化**:
   - 大量节点时的虚拟化渲染
   - 节点展开/折叠功能
   - 搜索和过滤功能

4. **增强功能**:
   - 节点详情面板
   - 回滚历史记录
   - 节点比较功能
   - 导出流程图

## 使用示例

```tsx
import { AgentSidebar } from '@/components/workbench/AgentSidebar'

// 在布局中使用
<div className="left-panel">
  <AgentSidebar />
</div>
```

## 注意事项

1. 确保已安装 `@xyflow/react` 依赖
2. 组件依赖全局的深色主题配置
3. Mock 数据仅用于开发,生产环境需要替换为真实 API
4. 测试使用了 Mock,实际集成测试需要真实数据

---

**实现完成时间**: 2024-03-30
**实现者**: CodeArts Agent
**版本**: 1.0.0
