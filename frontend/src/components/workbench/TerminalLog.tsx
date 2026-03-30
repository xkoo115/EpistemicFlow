/**
 * TerminalLog - 实时 SSE 日志终端组件
 *
 * 功能说明:
 * - 连接 SSE 端点,实时接收智能体思考过程和沙箱执行日志
 * - 终端风格化渲染,支持不同日志级别的颜色映射
 * - 自动滚动到底部 (类似 tail -f),用户手动滚动时暂停
 * - 支持日志过滤、搜索、导出等功能
 * - "玻璃盒"级别的透明度,展示底层系统状态
 */

import React, { useRef, useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Terminal, Filter, Download, Trash2, Search, X, RefreshCw } from 'lucide-react'
import { useSSEStream } from '@/hooks/useSSEStream'
import type { SSEMessage } from '@/types/log'
import {
  parseSSEMessageToLogEntry,
  formatTimestamp,
  getLogLevelClasses,
  getLogSourceIcon,
  getLogSourceLabel,
  filterLogEntries,
  type LogEntry,
} from '@/lib/logUtils'
import { LogLevel, LogSource } from '@/types/log'

/**
 * 组件 Props 接口
 */
export interface TerminalLogProps {
  /** SSE 端点 URL */
  endpoint?: string
  /** 自定义类名 */
  className?: string
  /** 最大日志条目数 (防止内存溢出) */
  maxLogEntries?: number
  /** 是否显示工具栏 */
  showToolbar?: boolean
}

/**
 * TerminalLog 组件
 */
export const TerminalLog: React.FC<TerminalLogProps> = ({
  endpoint = '/api/stream/events/default',
  className,
  maxLogEntries = 1000,
  showToolbar = true,
}) => {
  // SSE 连接状态
  const { messages, isConnected, isReconnecting, error, reconnect, disconnect, clearMessages } =
    useSSEStream({
      url: endpoint,
      parseMessage: (data) => {
        try {
          return JSON.parse(data)
        } catch {
          return { raw: data }
        }
      },
      onMessage: (message) => {
        console.log('[TerminalLog] 接收到消息:', message)
      },
      onError: (err) => {
        console.error('[TerminalLog] 连接错误:', err)
      },
    })

  // 日志条目状态
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [filteredEntries, setFilteredEntries] = useState<LogEntry[]>([])

  // 滚动控制状态
  const logContainerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const isUserScrollingRef = useRef(false)

  // 过滤器状态
  const [showFilter, setShowFilter] = useState(false)
  const [minLevel, setMinLevel] = useState<LogLevel>(LogLevel.DEBUG)
  const [selectedSources, setSelectedSources] = useState<LogSource[]>(Object.values(LogSource))
  const [keyword, setKeyword] = useState('')

  /**
   * 将 SSE 消息转换为日志条目
   */
  useEffect(() => {
    const newEntries = messages
      .map((message) => parseSSEMessageToLogEntry(message))
      .filter((entry): entry is LogEntry => entry !== null)

    if (newEntries.length === 0) return

    setLogEntries((prev) => {
      const updated = [...prev, ...newEntries]

      // 限制最大日志条目数,防止内存溢出
      if (updated.length > maxLogEntries) {
        return updated.slice(-maxLogEntries)
      }

      return updated
    })
  }, [messages, maxLogEntries])

  /**
   * 应用过滤器
   */
  useEffect(() => {
    const filtered = filterLogEntries(logEntries, {
      minLevel,
      sources: selectedSources,
      keyword,
    })
    setFilteredEntries(filtered)
  }, [logEntries, minLevel, selectedSources, keyword])

  /**
   * 自动滚动到底部
   */
  useEffect(() => {
    if (autoScroll && logContainerRef.current && filteredEntries.length > 0) {
      // 使用 requestAnimationFrame 确保在渲染完成后滚动
      requestAnimationFrame(() => {
        const container = logContainerRef.current
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    }
  }, [filteredEntries, autoScroll])

  /**
   * 处理滚动事件
   * 当用户手动向上滚动时,暂停自动滚动
   */
  const handleScroll = useCallback(() => {
    if (!logContainerRef.current) return

    const container = logContainerRef.current
    const { scrollTop, scrollHeight, clientHeight } = container

    // 计算是否滚动到底部 (允许 50px 的误差)
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50

    if (!isAtBottom) {
      // 用户正在向上滚动,暂停自动滚动
      if (autoScroll) {
        setAutoScroll(false)
        isUserScrollingRef.current = true
      }
    } else {
      // 用户滚动到底部,恢复自动滚动
      if (!autoScroll) {
        setAutoScroll(true)
        isUserScrollingRef.current = false
      }
    }
  }, [autoScroll])

  /**
   * 手动触发滚动到底部
   */
  const scrollToBottom = useCallback(() => {
    setAutoScroll(true)
    isUserScrollingRef.current = false

    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [])

  /**
   * 切换日志来源选择
   */
  const toggleSource = useCallback((source: LogSource) => {
    setSelectedSources((prev) => {
      if (prev.includes(source)) {
        // 如果只剩一个来源,不允许取消选择
        if (prev.length === 1) {
          return prev
        }
        return prev.filter((s) => s !== source)
      } else {
        return [...prev, source]
      }
    })
  }, [])

  /**
   * 清空日志
   */
  const handleClearLogs = useCallback(() => {
    clearMessages()
    setLogEntries([])
    setFilteredEntries([])
  }, [clearMessages])

  /**
   * 导出日志
   */
  const handleExportLogs = useCallback(() => {
    const logText = filteredEntries
      .map(
        (entry) =>
          `[${entry.level}] [${entry.source}] ${formatTimestamp(entry.timestamp, entry.timestampMs)} - ${entry.message}`
      )
      .join('\n')

    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs_${Date.now()}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [filteredEntries])

  return (
    <div className={cn('h-full flex flex-col', className)} data-testid="terminal-log">
      {/* 面板标题和工具栏 */}
      {showToolbar && (
        <div className="flex items-center justify-between mb-3">
          <div className="panel-title flex items-center gap-2 mb-0">
            <Terminal className="w-4 h-4 text-accent-cyan-500" />
            <span>活动日志</span>
          </div>

          {/* 工具按钮 */}
          <div className="flex items-center gap-1">
            <button
              className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors"
              onClick={reconnect}
              title="重新连接"
            >
              <RefreshCw
                className={cn(
                  'w-3.5 h-3.5 text-gray-500',
                  isReconnecting && 'animate-spin'
                )}
              />
            </button>
            <button
              className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors"
              onClick={() => setShowFilter(!showFilter)}
              title="过滤日志"
            >
              <Filter className="w-3.5 h-3.5 text-gray-500" />
            </button>
            <button
              className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors"
              onClick={handleExportLogs}
              title="导出日志"
            >
              <Download className="w-3.5 h-3.5 text-gray-500" />
            </button>
            <button
              className="p-1 rounded hover:bg-dark-bg-tertiary transition-colors"
              onClick={handleClearLogs}
              title="清空日志"
            >
              <Trash2 className="w-3.5 h-3.5 text-gray-500" />
            </button>
          </div>
        </div>
      )}

      {/* 过滤器面板 */}
      {showFilter && (
        <div className="mb-3 p-3 rounded-lg bg-dark-bg-secondary border border-dark-border">
          {/* 关键词搜索 */}
          <div className="flex items-center gap-2 mb-3">
            <Search className="w-3.5 h-3.5 text-gray-500" />
            <input
              type="text"
              placeholder="搜索日志..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="flex-1 bg-dark-bg-primary border border-dark-border rounded px-2 py-1 text-sm text-gray-300 focus:outline-none focus:border-accent-cyan-500"
            />
            {keyword && (
              <button
                className="p-1 rounded hover:bg-dark-bg-tertiary"
                onClick={() => setKeyword('')}
              >
                <X className="w-3 h-3 text-gray-500" />
              </button>
            )}
          </div>

          {/* 日志级别过滤 */}
          <div className="mb-2">
            <label className="text-xs text-gray-500 mb-1 block">最小日志级别:</label>
            <select
              value={minLevel}
              onChange={(e) => setMinLevel(e.target.value as LogLevel)}
              className="w-full bg-dark-bg-primary border border-dark-border rounded px-2 py-1 text-sm text-gray-300 focus:outline-none focus:border-accent-cyan-500"
            >
              {Object.values(LogLevel).map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>

          {/* 日志来源过滤 */}
          <div>
            <label className="text-xs text-gray-500 mb-1 block">日志来源:</label>
            <div className="flex flex-wrap gap-2">
              {Object.values(LogSource).map((source) => (
                <button
                  key={source}
                  onClick={() => toggleSource(source)}
                  className={cn(
                    'px-2 py-1 rounded text-xs transition-colors',
                    selectedSources.includes(source)
                      ? 'bg-accent-cyan-500/20 text-accent-cyan-500 border border-accent-cyan-500/50'
                      : 'bg-dark-bg-primary text-gray-500 border border-dark-border'
                  )}
                >
                  {getLogSourceIcon(source)} {getLogSourceLabel(source)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 终端日志区域 */}
      <div className="flex-1 overflow-hidden rounded-lg bg-dark-bg-primary border border-dark-border p-3">
        <div
          ref={logContainerRef}
          className="terminal-text space-y-1.5 h-full overflow-y-auto scrollbar-hide"
          onScroll={handleScroll}
        >
          {filteredEntries.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-600">
              <Terminal className="w-8 h-8 mb-2 opacity-50" />
              <p className="text-sm">等待日志数据...</p>
              {!isConnected && (
                <button
                  onClick={reconnect}
                  className="mt-2 px-3 py-1 rounded bg-accent-cyan-500/20 text-accent-cyan-500 text-xs hover:bg-accent-cyan-500/30 transition-colors"
                >
                  重新连接
                </button>
              )}
            </div>
          ) : (
            filteredEntries.map((entry) => (
              <div key={entry.id} className="flex items-start gap-2">
                {/* 日志级别标签 */}
                <span className={cn('select-none', getLogLevelClasses(entry.level))}>
                  [{entry.level}]
                </span>

                {/* 日志来源图标 */}
                <span className="select-none text-gray-500">
                  {getLogSourceIcon(entry.source)}
                </span>

                {/* 日志内容 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {/* 时间戳 */}
                    <span className="text-xs text-gray-600 select-none">
                      {formatTimestamp(entry.timestamp, entry.timestampMs)}
                    </span>

                    {/* 智能体 ID (如果有) */}
                    {entry.agentId && (
                      <span className="text-xs text-accent-cyan-500/70 select-none">
                        @{entry.agentId}
                      </span>
                    )}

                    {/* 工具名称 (如果有) */}
                    {entry.toolName && (
                      <span className="text-xs text-blue-400/70 select-none">
                        /{entry.toolName}
                      </span>
                    )}
                  </div>

                  {/* 日志消息 */}
                  <div className="text-sm text-gray-300 break-words whitespace-pre-wrap">
                    {entry.message}
                  </div>

                  {/* 元数据 (如果有) */}
                  {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                    <div className="mt-1 text-xs text-gray-600">
                      {JSON.stringify(entry.metadata, null, 2)}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 自动滚动按钮 (当暂停自动滚动时显示) */}
      {!autoScroll && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-16 right-4 p-2 rounded-full bg-accent-cyan-500 text-dark-bg-primary shadow-lg hover:bg-accent-cyan-400 transition-colors"
          title="滚动到底部"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      )}

      {/* 底部状态栏 */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-2" data-testid="terminal-log-status">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isConnected
                ? 'bg-accent-green-500 animate-pulse'
                : isReconnecting
                  ? 'bg-accent-amber-500 animate-pulse'
                  : 'bg-accent-red-500'
            )}
          />
          <span>
            {isConnected
              ? '实时连接'
              : isReconnecting
                ? '重连中...'
                : '连接断开'}
          </span>
          {error && <span className="text-accent-red-500">连接错误</span>}
        </div>
        <div className="flex items-center gap-2">
          <span>{filteredEntries.length} 条日志</span>
          {logEntries.length !== filteredEntries.length && (
            <span className="text-gray-600">
              (共 {logEntries.length} 条)
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default TerminalLog
