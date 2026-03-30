/**
 * AgentSidebar - 智能体侧边栏组件
 * 
 * 功能说明:
 * 1. 上半部分:展示当前活跃的智能体列表,使用脉冲动画表现状态
 * 2. 下半部分:使用 React Flow 渲染 Saga 时间旅行分叉树
 * 3. 支持点击历史节点触发回滚操作
 * 
 * 核心特性:
 * - 智能体实时状态展示(脉冲动画/状态指示灯)
 * - Saga 状态机可视化(垂直流程树,支持分叉)
 * - 时间旅行回滚交互(点击节点弹出模态框)
 */

import React, { useState, useMemo, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Bot, Network, Clock, Activity } from 'lucide-react'
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

// 导入类型定义
import {
  Agent,
  AgentStatus,
  SagaCheckpoint,
  SagaNodeData,
} from '@/types/saga'

// 导入回滚模态框组件
import { RollbackModal } from './RollbackModal'

/**
 * ============================================================================
 * Mock 数据 - 用于开发和测试
 * ============================================================================
 */

// Mock 智能体数据
const MOCK_AGENTS: Agent[] = [
  {
    id: 'agent-1',
    name: '首席研究员',
    status: AgentStatus.BUSY,
    description: '负责整体研究规划和协调',
    lastActiveTime: '2024-03-30 10:30:00',
    taskCount: 15,
  },
  {
    id: 'agent-2',
    name: '新颖性审稿人',
    status: AgentStatus.IDLE,
    description: '评估研究新颖性和创新性',
    lastActiveTime: '2024-03-30 10:25:00',
    taskCount: 8,
  },
  {
    id: 'agent-3',
    name: '数据分析专家',
    status: AgentStatus.SUSPENDED,
    description: '执行数据分析和统计计算',
    lastActiveTime: '2024-03-30 10:20:00',
    taskCount: 12,
  },
  {
    id: 'agent-4',
    name: '文献检索员',
    status: AgentStatus.SUCCESS,
    description: '检索和整理相关文献',
    lastActiveTime: '2024-03-30 10:15:00',
    taskCount: 20,
  },
]

// Mock Saga 检查点数据(包含分叉结构)
const MOCK_SAGA_CHECKPOINTS: SagaCheckpoint[] = [
  {
    checkpoint_id: 'cp-1',
    parent_id: null,
    stage_name: '阶段一:文献检索',
    timestamp: '2024-03-30 09:00:00',
    status: 'completed',
  },
  {
    checkpoint_id: 'cp-2',
    parent_id: 'cp-1',
    stage_name: '阶段二:数据分析',
    timestamp: '2024-03-30 09:30:00',
    status: 'completed',
  },
  {
    checkpoint_id: 'cp-3',
    parent_id: 'cp-2',
    stage_name: '阶段三:自动执行前',
    timestamp: '2024-03-30 10:00:00',
    status: 'completed',
  },
  {
    checkpoint_id: 'cp-4',
    parent_id: 'cp-3',
    stage_name: '阶段四:结果生成',
    timestamp: '2024-03-30 10:30:00',
    status: 'running',
  },
  // 分叉节点1:从 cp-3 分叉(人类干预)
  {
    checkpoint_id: 'cp-5',
    parent_id: 'cp-3',
    stage_name: '阶段三:人工干预分支A',
    timestamp: '2024-03-30 10:05:00',
    status: 'completed',
    is_fork: true,
  },
  {
    checkpoint_id: 'cp-6',
    parent_id: 'cp-5',
    stage_name: '阶段四:分支A执行',
    timestamp: '2024-03-30 10:15:00',
    status: 'suspended',
    is_fork: true,
  },
  // 分叉节点2:从 cp-3 分叉(另一次人类干预)
  {
    checkpoint_id: 'cp-7',
    parent_id: 'cp-3',
    stage_name: '阶段三:人工干预分支B',
    timestamp: '2024-03-30 10:10:00',
    status: 'failed',
    is_fork: true,
  },
]

/**
 * ============================================================================
 * 工具函数
 * ============================================================================
 */

/**
 * 获取智能体状态对应的样式类名
 */
const getAgentStatusClass = (status: AgentStatus): string => {
  switch (status) {
    case AgentStatus.BUSY:
      return 'status-computing' // 青色脉冲动画
    case AgentStatus.SUSPENDED:
      return 'status-suspended' // 琥珀色
    case AgentStatus.ERROR:
      return 'status-error' // 红色
    case AgentStatus.SUCCESS:
      return 'status-success' // 绿色
    default:
      return 'status-idle' // 默认灰色
  }
}

/**
 * 获取智能体状态对应的文本
 */
const getAgentStatusText = (status: AgentStatus): string => {
  switch (status) {
    case AgentStatus.BUSY:
      return '计算中'
    case AgentStatus.SUSPENDED:
      return 'HITL 挂起'
    case AgentStatus.ERROR:
      return '错误'
    case AgentStatus.SUCCESS:
      return '已完成'
    default:
      return '闲置'
  }
}

/**
 * ============================================================================
 * 核心函数:将 Saga 检查点数据转换为 React Flow 节点和边
 * ============================================================================
 * 
 * 数据结构转换逻辑:
 * 1. 遍历所有检查点,为每个检查点创建一个 React Flow 节点
 * 2. 节点的位置通过层级计算得出(垂直布局)
 * 3. 对于有相同 parent_id 的多个节点,识别为分叉,横向排列
 * 4. 为每个非根节点创建一条边,连接到其父节点
 * 
 * @param checkpoints Saga 检查点数组
 * @returns React Flow 的 nodes 和 edges
 */
const convertCheckpointsToFlowElements = (
  checkpoints: SagaCheckpoint[]
): { nodes: Node<SagaNodeData>[]; edges: Edge[] } => {
  // 节点基础配置
  const NODE_WIDTH = 180
  const NODE_HEIGHT = 60
  const VERTICAL_GAP = 80
  const HORIZONTAL_GAP = 200

  // 构建父子关系映射(用于识别分叉)
  const parentChildrenMap = new Map<string | null, SagaCheckpoint[]>()
  checkpoints.forEach((checkpoint) => {
    const children = parentChildrenMap.get(checkpoint.parent_id) || []
    children.push(checkpoint)
    parentChildrenMap.set(checkpoint.parent_id, children)
  })

  // 计算每个节点的层级(深度)
  const nodeDepthMap = new Map<string, number>()
  const calculateDepth = (checkpointId: string, depth: number): void => {
    nodeDepthMap.set(checkpointId, depth)
    const children = parentChildrenMap.get(checkpointId) || []
    children.forEach((child) => calculateDepth(child.checkpoint_id, depth + 1))
  }
  // 从根节点开始计算
  const rootCheckpoints = parentChildrenMap.get(null) || []
  rootCheckpoints.forEach((root) => calculateDepth(root.checkpoint_id, 0))

  // 创建节点
  const nodes: Node<SagaNodeData>[] = checkpoints.map((checkpoint, index) => {
    const depth = nodeDepthMap.get(checkpoint.checkpoint_id) || 0
    const siblings = parentChildrenMap.get(checkpoint.parent_id) || []
    const siblingIndex = siblings.findIndex(
      (s) => s.checkpoint_id === checkpoint.checkpoint_id
    )
    const hasMultipleSiblings = siblings.length > 1

    // 计算位置
    // Y 坐标:根据层级垂直排列
    const y = depth * (NODE_HEIGHT + VERTICAL_GAP)
    // X 坐标:如果有多个兄弟节点,横向排列;否则居中
    const x = hasMultipleSiblings
      ? (siblingIndex - (siblings.length - 1) / 2) * HORIZONTAL_GAP
      : 0

    return {
      id: checkpoint.checkpoint_id,
      type: 'default',
      position: { x, y },
      data: {
        label: checkpoint.stage_name,
        status: checkpoint.status,
        isFork: checkpoint.is_fork || false,
        checkpoint,
      },
      style: {
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        // 根据状态设置节点样式
        backgroundColor:
          checkpoint.status === 'completed'
            ? '#1F2937'
            : checkpoint.status === 'running'
            ? '#0A0E1A'
            : checkpoint.status === 'failed'
            ? '#2D1F1F'
            : '#1A1F2E',
        border: checkpoint.is_fork
          ? '2px solid #FFB800' // 分叉节点使用琥珀色边框
          : '1px solid #2D3748',
        borderRadius: '8px',
        fontSize: '12px',
        color: '#E5E7EB',
      },
    }
  })

  // 创建边
  const edges: Edge[] = checkpoints
    .filter((checkpoint) => checkpoint.parent_id !== null)
    .map((checkpoint) => ({
      id: `edge-${checkpoint.parent_id}-${checkpoint.checkpoint_id}`,
      source: checkpoint.parent_id!,
      target: checkpoint.checkpoint_id,
      type: 'smoothstep',
      animated: checkpoint.status === 'running', // 运行中的节点边使用动画
      style: {
        stroke: checkpoint.is_fork ? '#FFB800' : '#4A5568', // 分叉边使用琥珀色
        strokeWidth: checkpoint.is_fork ? 2 : 1,
      },
    }))

  return { nodes, edges }
}

/**
 * ============================================================================
 * AgentSidebar 主组件
 * ============================================================================
 */
export const AgentSidebar: React.FC = () => {
  // 状态管理
  const [agents] = useState<Agent[]>(MOCK_AGENTS)
  const [checkpoints] = useState<SagaCheckpoint[]>(MOCK_SAGA_CHECKPOINTS)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<SagaCheckpoint | null>(null)

  // 将检查点转换为 React Flow 元素
  const { initialNodes, initialEdges } = useMemo(() => {
    return convertCheckpointsToFlowElements(checkpoints)
  }, [checkpoints])

  // React Flow 状态管理
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  /**
   * 处理节点点击事件
   * 当用户点击历史节点时,弹出回滚模态框
   */
  const onNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      const nodeData = node.data as SagaNodeData
      // 只有已完成或挂起的节点才能回滚
      if (
        nodeData.status === 'completed' ||
        nodeData.status === 'suspended'
      ) {
        setSelectedCheckpoint(nodeData.checkpoint)
        setIsModalOpen(true)
      }
    },
    []
  )

  /**
   * 处理回滚提交
   */
  const handleRollbackSubmit = async (
    checkpointId: string,
    humanInstruction: string
  ) => {
    // TODO: 调用后端 API 进行回滚
    console.log('回滚请求:', {
      checkpoint_id: checkpointId,
      human_instruction: humanInstruction,
    })

    // 模拟 API 调用
    // const response = await fetch(`/api/workflows/${sessionId}/rollback`, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({
    //     checkpoint_id: checkpointId,
    //     human_instruction: humanInstruction,
    //   }),
    // })

    setIsModalOpen(false)
    setSelectedCheckpoint(null)
  }

  return (
    <div className={cn('h-full flex flex-col bg-dark-bg-primary')} data-testid="agent-sidebar">
      {/* ================================================================== */}
      {/* 上半部分:智能体列表 */}
      {/* ================================================================== */}
      <div className="flex-none border-b border-dark-border">
        {/* 面板标题 */}
        <div className="panel-title flex items-center gap-2">
          <Network className="w-4 h-4 text-accent-cyan-500" />
          <span>智能体拓扑</span>
        </div>

        {/* 智能体列表 */}
        <div className="p-3 space-y-2 max-h-[240px] overflow-y-auto">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className={cn(
                'flex items-center gap-3 p-2 rounded-lg',
                'bg-dark-bg-secondary hover:bg-dark-bg-tertiary',
                'transition-colors duration-200 cursor-pointer'
              )}
            >
              {/* 状态指示器 */}
              <div className="flex-shrink-0">
                <div
                  className={cn(
                    'status-indicator',
                    getAgentStatusClass(agent.status)
                  )}
                />
              </div>

              {/* 智能体信息 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Bot className="w-3 h-3 text-gray-400" />
                  <span className="text-sm font-medium text-gray-200 truncate">
                    {agent.name}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {getAgentStatusText(agent.status)}
                  {agent.taskCount && ` · ${agent.taskCount} 任务`}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ================================================================== */}
      {/* 下半部分:Saga 时间旅行树 */}
      {/* ================================================================== */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* 面板标题 */}
        <div className="panel-title flex items-center gap-2 border-b border-dark-border">
          <Clock className="w-4 h-4 text-accent-amber-500" />
          <span>Saga 时间旅行</span>
        </div>

        {/* React Flow 图表 */}
        <div className="flex-1 min-h-0" data-testid="saga-tree">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.5}
            maxZoom={1.5}
            proOptions={{ hideAttribution: true }}
            style={{ background: '#0A0E1A' }}
          >
            {/* 背景网格 */}
            <Background color="#1F2937" gap={20} size={1} />
            
            {/* 控制按钮 */}
            <Controls
              style={{
                button: {
                  backgroundColor: '#1F2937',
                  border: '1px solid #2D3748',
                  color: '#9CA3AF',
                },
              }}
            />
            
            {/* 小地图 */}
            <MiniMap
              nodeColor={(node) => {
                const data = node.data as SagaNodeData
                return data.isFork ? '#FFB800' : '#4A5568'
              }}
              style={{
                backgroundColor: '#111827',
              }}
            />
          </ReactFlow>
        </div>

        {/* 图例说明 */}
        <div className="flex-none p-2 border-t border-dark-border">
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-accent-cyan-500" />
              <span>运行中</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-accent-green-500" />
              <span>已完成</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-accent-amber-500" />
              <span>分叉节点</span>
            </div>
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* 回滚模态框 */}
      {/* ================================================================== */}
      {selectedCheckpoint && (
        <RollbackModal
          isOpen={isModalOpen}
          checkpoint={selectedCheckpoint}
          onClose={() => {
            setIsModalOpen(false)
            setSelectedCheckpoint(null)
          }}
          onSubmit={handleRollbackSubmit}
        />
      )}
    </div>
  )
}

export default AgentSidebar
