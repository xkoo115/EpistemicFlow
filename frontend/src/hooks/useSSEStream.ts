/**
 * useSSEStream - SSE 流式数据连接 Hook
 *
 * 功能说明:
 * - 使用浏览器原生 EventSource API 连接 SSE 端点
 * - 实现指数退避重连机制 (Exponential Backoff)
 * - 自动清理连接,防止内存泄漏
 * - 支持自定义消息解析器
 *
 * 使用示例:
 * ```tsx
 * const { messages, isConnected, error, reconnect } = useSSEStream({
 *   url: '/api/stream',
 *   parseMessage: (data) => JSON.parse(data)
 * })
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import type { SSEMessage } from '@/types/log'

/**
 * Hook 配置选项
 */
export interface UseSSEStreamOptions {
  /** SSE 端点 URL */
  url: string
  /** 消息解析器,默认为 JSON.parse */
  parseMessage?: (data: string) => unknown
  /** 重连延迟基数 (毫秒),默认 1000ms */
  reconnectDelayBase?: number
  /** 最大重连延迟 (毫秒),默认 30000ms */
  maxReconnectDelay?: number
  /** 是否启用自动重连,默认 true */
  autoReconnect?: boolean
  /** 连接成功回调 */
  onOpen?: () => void
  /** 消息接收回调 */
  onMessage?: (message: SSEMessage) => void
  /** 错误回调 */
  onError?: (error: Event) => void
  /** 连接关闭回调 */
  onClose?: () => void
}

/**
 * Hook 返回值
 */
export interface UseSSEStreamReturn {
  /** 消息列表 */
  messages: SSEMessage[]
  /** 是否已连接 */
  isConnected: boolean
  /** 是否正在重连 */
  isReconnecting: boolean
  /** 错误对象 */
  error: Event | null
  /** 手动重连方法 */
  reconnect: () => void
  /** 手动断开连接方法 */
  disconnect: () => void
  /** 清空消息列表 */
  clearMessages: () => void
}

/**
 * SSE 流式数据连接 Hook
 */
export function useSSEStream(options: UseSSEStreamOptions): UseSSEStreamReturn {
  const {
    url,
    parseMessage = (data) => JSON.parse(data),
    reconnectDelayBase = 1000,
    maxReconnectDelay = 30000,
    autoReconnect = true,
    onOpen,
    onMessage,
    onError,
    onClose,
  } = options

  // 状态管理
  const [messages, setMessages] = useState<SSEMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const [error, setError] = useState<Event | null>(null)

  // Refs 用于存储可变值,避免闭包问题
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const mountedRef = useRef(true)

  /**
   * 计算下一次重连延迟时间 (指数退避算法)
   */
  const calculateReconnectDelay = useCallback(() => {
    const delay = Math.min(
      reconnectDelayBase * Math.pow(2, reconnectAttemptsRef.current),
      maxReconnectDelay
    )
    // 添加随机抖动 (±25%),避免多个客户端同时重连
    const jitter = delay * 0.25 * (Math.random() * 2 - 1)
    return Math.max(delay + jitter, reconnectDelayBase)
  }, [reconnectDelayBase, maxReconnectDelay])

  /**
   * 清理连接和定时器
   */
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  /**
   * 处理消息接收
   */
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      if (!mountedRef.current) return

      try {
        const parsedData = parseMessage(event.data)
        const message: SSEMessage = {
          id: event.lastEventId || undefined,
          event: event.type || undefined,
          data: parsedData,
          rawData: event.data,
          timestamp: Date.now(),
        }

        setMessages((prev) => [...prev, message])
        onMessage?.(message)
      } catch (err) {
        console.error('[useSSEStream] 消息解析失败:', err)
      }
    },
    [parseMessage, onMessage]
  )

  /**
   * 处理连接打开
   */
  const handleOpen = useCallback(() => {
    if (!mountedRef.current) return

    console.log('[useSSEStream] SSE 连接已建立')
    setIsConnected(true)
    setIsReconnecting(false)
    setError(null)
    reconnectAttemptsRef.current = 0
    onOpen?.()
  }, [onOpen])

  /**
   * 处理连接错误
   */
  const handleError = useCallback(
    (event: Event) => {
      if (!mountedRef.current) return

      console.error('[useSSEStream] SSE 连接错误:', event)
      setIsConnected(false)
      setError(event)
      onError?.(event)

      // 自动重连逻辑
      if (autoReconnect && mountedRef.current) {
        const delay = calculateReconnectDelay()
        console.log(`[useSSEStream] 将在 ${Math.round(delay)}ms 后重连...`)

        setIsReconnecting(true)
        reconnectAttemptsRef.current++

        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (mountedRef.current) {
            connect()
          }
        }, delay)
      }
    },
    [autoReconnect, calculateReconnectDelay, onError]
  )

  /**
   * 建立 SSE 连接
   */
  const connect = useCallback(() => {
    if (!mountedRef.current) return

    // 清理现有连接
    cleanup()

    try {
      console.log('[useSSEStream] 正在连接 SSE 端点:', url)

      const eventSource = new EventSource(url)
      eventSourceRef.current = eventSource

      // 绑定事件处理器
      eventSource.onopen = handleOpen
      eventSource.onmessage = handleMessage
      eventSource.onerror = handleError

      // 监听特定类型的事件 (如果后端发送了自定义事件类型)
      // eventSource.addEventListener('custom-event', handleMessage)
    } catch (err) {
      console.error('[useSSEStream] 连接失败:', err)
      handleError(new Event('connection-failed'))
    }
  }, [url, cleanup, handleOpen, handleMessage, handleError])

  /**
   * 手动重连
   */
  const reconnect = useCallback(() => {
    console.log('[useSSEStream] 手动触发重连')
    reconnectAttemptsRef.current = 0
    connect()
  }, [connect])

  /**
   * 手动断开连接
   */
  const disconnect = useCallback(() => {
    console.log('[useSSEStream] 手动断开连接')
    cleanup()
    setIsConnected(false)
    setIsReconnecting(false)
    onClose?.()
  }, [cleanup, onClose])

  /**
   * 清空消息列表
   */
  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  /**
   * 组件挂载时建立连接
   */
  useEffect(() => {
    mountedRef.current = true

    // 建立初始连接
    connect()

    /**
     * 组件卸载时的清理函数
     * 这是防止内存泄漏的关键步骤
     */
    return () => {
      console.log('[useSSEStream] 组件卸载,清理资源')
      mountedRef.current = false
      cleanup()
      setIsConnected(false)
      setIsReconnecting(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]) // 仅在 URL 变化时重新连接

  return {
    messages,
    isConnected,
    isReconnecting,
    error,
    reconnect,
    disconnect,
    clearMessages,
  }
}
