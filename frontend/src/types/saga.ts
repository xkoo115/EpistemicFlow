/**
 * Saga 时间旅行相关类型定义
 * 
 * 用于管理状态机的检查点、回滚和时间旅行功能
 */

/**
 * 智能体状态枚举
 */
export enum AgentStatus {
  IDLE = 'IDLE',           // 闲置状态
  BUSY = 'BUSY',           // 忙碌状态(正在执行任务)
  SUSPENDED = 'SUSPENDED', // 挂起状态(等待人工干预)
  ERROR = 'ERROR',         // 错误状态
  SUCCESS = 'SUCCESS',     // 成功完成状态
}

/**
 * 智能体信息接口
 */
export interface Agent {
  id: string                    // 智能体唯一标识
  name: string                  // 智能体名称(如:首席研究员、新颖性审稿人)
  status: AgentStatus           // 当前状态
  description?: string          // 智能体描述
  lastActiveTime?: string       // 最后活跃时间
  taskCount?: number            // 已完成任务数
  icon?: string                 // 图标标识
}

/**
 * Saga 检查点节点接口
 * 用于表示状态机的一个历史状态
 */
export interface SagaCheckpoint {
  checkpoint_id: string         // 检查点唯一标识
  parent_id: string | null      // 父节点ID(null表示根节点)
  stage_name: string            // 阶段名称(如:"阶段一:文献检索")
  timestamp: string             // 创建时间戳
  status: 'completed' | 'running' | 'failed' | 'suspended'  // 节点状态
  is_fork?: boolean             // 是否为分叉节点(因人类干预产生)
  metadata?: Record<string, unknown>  // 额外元数据
}

/**
 * 回滚请求接口
 */
export interface RollbackRequest {
  session_id: string            // 会话ID
  checkpoint_id: string         // 目标检查点ID
  human_instruction: string     // 人类纠偏指令
  timestamp: string             // 请求时间戳
}

/**
 * 回滚响应接口
 */
export interface RollbackResponse {
  success: boolean              // 是否成功
  new_checkpoint_id?: string    // 新创建的检查点ID
  message?: string              // 响应消息
  error?: string                // 错误信息
}

/**
 * React Flow 节点数据接口
 * 用于在 React Flow 图表中显示 Saga 节点
 */
export interface SagaNodeData {
  label: string                 // 节点显示标签
  status: SagaCheckpoint['status']  // 节点状态
  isFork: boolean               // 是否为分叉节点
  checkpoint: SagaCheckpoint    // 原始检查点数据
}

/**
 * React Flow 边数据接口
 */
export interface SagaEdgeData {
  isFork: boolean               // 是否为分叉边
}
