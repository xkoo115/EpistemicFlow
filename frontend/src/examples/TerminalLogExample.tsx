/**
 * TerminalLog 组件使用示例
 *
 * 本示例展示如何在 WorkbenchLayout 中集成 TerminalLog 组件
 */

import React, { useState } from 'react'
import { WorkbenchLayout } from '@/layouts/WorkbenchLayout'
import { TerminalLog } from '@/components/workbench/TerminalLog'
import { AgentRoster } from '@/components/workbench/AgentRoster'
import { MainCanvas } from '@/components/workbench/MainCanvas'

/**
 * 示例 1: 基础集成
 */
export function BasicTerminalLogExample() {
  return (
    <WorkbenchLayout
      leftSidebar={<AgentRoster />}
      mainCanvas={<MainCanvas />}
      rightSidebar={<TerminalLog endpoint="/api/stream" />}
    />
  )
}

/**
 * 示例 2: 自定义配置
 */
export function CustomTerminalLogExample() {
  return (
    <WorkbenchLayout
      leftSidebar={<AgentRoster />}
      mainCanvas={<MainCanvas />}
      rightSidebar={
        <TerminalLog
          endpoint="/api/stream"
          className="h-full"
          maxLogEntries={2000}
          showToolbar={true}
        />
      }
    />
  )
}

/**
 * 示例 3: 动态端点切换
 */
export function DynamicEndpointExample() {
  const [endpoint, setEndpoint] = useState('/api/stream')

  return (
    <div className="h-screen flex flex-col p-4 gap-4">
      {/* 端点选择器 */}
      <div className="flex items-center gap-4 p-4 bg-dark-bg-secondary rounded-lg border border-dark-border">
        <label className="text-sm text-gray-300">选择 SSE 端点:</label>
        <select
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          className="px-3 py-2 bg-dark-bg-primary border border-dark-border rounded text-sm text-gray-300 focus:outline-none focus:border-accent-cyan-500"
        >
          <option value="/api/stream">默认流</option>
          <option value="/api/stream/agent-1">智能体 1</option>
          <option value="/api/stream/agent-2">智能体 2</option>
          <option value="/api/stream/sandbox">沙箱执行</option>
        </select>
      </div>

      {/* 终端日志组件 */}
      <div className="flex-1">
        <TerminalLog endpoint={endpoint} />
      </div>
    </div>
  )
}

/**
 * 示例 4: 带过滤器的集成
 */
export function FilteredTerminalLogExample() {
  return (
    <WorkbenchLayout
      leftSidebar={<AgentRoster />}
      mainCanvas={<MainCanvas />}
      rightSidebar={
        <div className="h-full flex flex-col p-4">
          <div className="mb-4 p-3 bg-dark-bg-secondary rounded-lg border border-dark-border">
            <h3 className="text-sm font-medium text-gray-300 mb-2">实时日志监控</h3>
            <p className="text-xs text-gray-500">
              显示所有智能体的实时活动日志
            </p>
          </div>
          <div className="flex-1">
            <TerminalLog endpoint="/api/stream" />
          </div>
        </div>
      }
    />
  )
}

/**
 * 示例 5: 使用 useSSEStream Hook 的自定义组件
 */
export function CustomLogViewerExample() {
  const { messages, isConnected, error, reconnect } = useSSEStream({
    url: '/api/stream',
    parseMessage: (data) => JSON.parse(data),
  })

  return (
    <div className="h-full flex flex-col p-4">
      {/* 状态栏 */}
      <div className="flex items-center justify-between mb-4 p-3 bg-dark-bg-secondary rounded-lg border border-dark-border">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-accent-green-500 animate-pulse' : 'bg-accent-red-500'
            }`}
          />
          <span className="text-sm text-gray-300">
            {isConnected ? '已连接' : '未连接'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{messages.length} 条消息</span>
          {!isConnected && (
            <button
              onClick={reconnect}
              className="px-3 py-1 bg-accent-cyan-500/20 text-accent-cyan-500 text-xs rounded hover:bg-accent-cyan-500/30 transition-colors"
            >
              重新连接
            </button>
          )}
        </div>
      </div>

      {/* 日志列表 */}
      <div className="flex-1 overflow-y-auto bg-dark-bg-primary rounded-lg border border-dark-border p-3">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-600">
            <p className="text-sm">等待日志数据...</p>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className="mb-2 text-sm text-gray-300">
              <pre className="whitespace-pre-wrap break-words">
                {JSON.stringify(msg.data, null, 2)}
              </pre>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

/**
 * 示例 6: 多端点监控
 */
export function MultiEndpointExample() {
  const [activeTab, setActiveTab] = useState<'all' | 'agent' | 'sandbox'>('all')

  return (
    <div className="h-full flex flex-col">
      {/* 标签页 */}
      <div className="flex items-center gap-2 mb-4">
        {[
          { id: 'all', label: '全部', endpoint: '/api/stream' },
          { id: 'agent', label: '智能体', endpoint: '/api/stream/agent' },
          { id: 'sandbox', label: '沙箱', endpoint: '/api/stream/sandbox' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-4 py-2 text-sm rounded transition-colors ${
              activeTab === tab.id
                ? 'bg-accent-cyan-500/20 text-accent-cyan-500 border border-accent-cyan-500/50'
                : 'bg-dark-bg-secondary text-gray-500 border border-dark-border'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 终端日志 */}
      <div className="flex-1">
        <TerminalLog
          endpoint={
            activeTab === 'all'
              ? '/api/stream'
              : activeTab === 'agent'
                ? '/api/stream/agent'
                : '/api/stream/sandbox'
          }
        />
      </div>
    </div>
  )
}

/**
 * 示例 7: 带日志统计的集成
 */
export function TerminalLogWithStatsExample() {
  const { messages, isConnected } = useSSEStream({
    url: '/api/stream',
  })

  // 统计不同级别的日志数量
  const stats = messages.reduce(
    (acc, msg) => {
      const level = (msg.data as any)?.level || 'UNKNOWN'
      acc[level] = (acc[level] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  return (
    <div className="h-full flex flex-col">
      {/* 统计面板 */}
      <div className="mb-4 p-4 bg-dark-bg-secondary rounded-lg border border-dark-border">
        <h3 className="text-sm font-medium text-gray-300 mb-3">日志统计</h3>
        <div className="grid grid-cols-5 gap-2">
          {[
            { label: 'DEBUG', color: 'text-gray-500' },
            { label: 'INFO', color: 'text-accent-cyan-500' },
            { label: 'SUCCESS', color: 'text-accent-green-500' },
            { label: 'WARN', color: 'text-accent-amber-500' },
            { label: 'ERROR', color: 'text-accent-red-500' },
          ].map((item) => (
            <div
              key={item.label}
              className="flex flex-col items-center p-2 bg-dark-bg-primary rounded"
            >
              <span className={`text-lg font-bold ${item.color}`}>
                {stats[item.label] || 0}
              </span>
              <span className="text-xs text-gray-500">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 终端日志 */}
      <div className="flex-1">
        <TerminalLog endpoint="/api/stream" />
      </div>
    </div>
  )
}

// 导入 useSSEStream Hook
import { useSSEStream } from '@/hooks/useSSEStream'

/**
 * 默认导出 - 基础示例
 */
export default BasicTerminalLogExample
