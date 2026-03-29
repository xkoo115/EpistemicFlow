/**
 * ActivityLog - 实时活动日志组件
 *
 * 功能说明:
 * - 模拟终端滚动的日志区域
 * - 接收 SSE 流式日志,实现"玻璃盒"级别的透明度
 * - 支持日志过滤、搜索、导出等功能
 *
 * 占位说明:
 * - 当前为基础占位组件,后续将实现完整的日志功能
 * - 将支持 SSE 连接、实时更新、日志级别过滤等
 */

import React from 'react'
import { cn } from '@/lib/utils'
import { Terminal, Filter, Download } from 'lucide-react'

/**
 * ActivityLog 组件
 * 右侧栏 - 实时活动日志
 */
export const ActivityLog: React.FC = () => {
  return (
    <div className={cn('h-full flex flex-col')}>
      {/* 面板标题和工具栏 */}
      <div className="flex items-center justify-between mb-3">
        <div className="panel-title flex items-center gap-2 mb-0">
          <Terminal className="w-4 h-4 text-accent-cyan-500" />
          <span>活动日志</span>
        </div>

        {/* 工具按钮 */}
        <div className="flex items-center gap-1">
          <button className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors">
            <Filter className="w-3.5 h-3.5 text-gray-500" />
          </button>
          <button className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors">
            <Download className="w-3.5 h-3.5 text-gray-500" />
          </button>
        </div>
      </div>

      {/* 终端日志区域 */}
      <div className="flex-1 overflow-hidden rounded-lg bg-dark-bg-primary border border-dark-border p-3">
        {/* 模拟终端输出 */}
        <div className="terminal-text space-y-1.5 h-full overflow-y-auto scrollbar-hide">
          {/* 示例日志条目 */}
          <div className="flex items-start gap-2">
            <span className="text-accent-cyan-500 select-none">[INFO]</span>
            <span>系统初始化完成</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-cyan-500 select-none">[INFO]</span>
            <span>连接到后端服务...</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-green-500 select-none">[SUCCESS]</span>
            <span>WebSocket 连接已建立</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-amber-500 select-none">[WARN]</span>
            <span>等待智能体响应...</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-cyan-500 select-none">[INFO]</span>
            <span>开始执行任务流程</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-gray-500 select-none">[DEBUG]</span>
            <span>加载配置文件: config.yaml</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-cyan-500 select-none">[INFO]</span>
            <span>初始化智能体拓扑...</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-accent-green-500 select-none">[SUCCESS]</span>
            <span>智能体拓扑构建完成</span>
          </div>

          {/* 占位提示 */}
          <div className="mt-4 pt-4 border-t border-dark-border">
            <p className="text-xs text-gray-600 italic">
              实时日志将在此处流式显示...
            </p>
          </div>
        </div>
      </div>

      {/* 底部状态栏 */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent-green-500 animate-pulse" />
          <span>实时连接</span>
        </div>
        <span>8 条日志</span>
      </div>
    </div>
  )
}

export default ActivityLog
