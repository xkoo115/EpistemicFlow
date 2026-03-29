/**
 * AgentRoster - 智能体拓扑树组件
 *
 * 功能说明:
 * - 展示系统中的多智能体结构和当前状态
 * - 使用树形结构显示智能体层级关系
 * - 实时显示智能体的运行状态(计算中、挂起、错误、完成)
 *
 * 占位说明:
 * - 当前为基础占位组件,后续将实现完整的树形结构
 * - 将支持拖拽、展开/折叠、状态过滤等交互功能
 */

import React from 'react'
import { cn } from '@/lib/utils'
import { Bot, Network } from 'lucide-react'

/**
 * AgentRoster 组件
 * 左侧栏 - 智能体拓扑树
 */
export const AgentRoster: React.FC = () => {
  return (
    <div className={cn('h-full flex flex-col')}>
      {/* 面板标题 */}
      <div className="panel-title flex items-center gap-2">
        <Network className="w-4 h-4 text-accent-cyan-500" />
        <span>智能体拓扑</span>
      </div>

      {/* 占位内容 - 未来将实现树形结构 */}
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        {/* 图标 */}
        <div className="mb-4 p-4 rounded-full bg-dark-bg-tertiary">
          <Bot className="w-8 h-8 text-gray-500" />
        </div>

        {/* 提示文本 */}
        <p className="text-sm text-gray-500 mb-2">
          智能体拓扑树
        </p>
        <p className="text-xs text-gray-600">
          展示多智能体结构和状态
        </p>

        {/* 状态指示器示例 */}
        <div className="mt-6 space-y-2">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="status-indicator status-computing" />
            <span>计算中</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="status-indicator status-suspended" />
            <span>HITL 挂起</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="status-indicator status-error" />
            <span>沙箱报错</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="status-indicator status-success" />
            <span>节点通过</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AgentRoster
