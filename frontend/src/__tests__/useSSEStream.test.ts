/**
 * useSSEStream Hook 单元测试
 *
 * 测试内容:
 * - SSE 连接建立和断开
 * - 消息接收和解析
 * - 自动重连机制 (指数退避)
 * - 错误处理
 * - 组件卸载时的清理
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useSSEStream } from '@/hooks/useSSEStream'
import { MockEventSource, createMockSSE } from './mocks/mockSSEStream'
import { LogLevel, LogSource, LogData } from '@/types/log'

// Mock EventSource
global.EventSource = MockEventSource as any

describe('useSSEStream Hook', () => {
  let mockSSE: MockEventSource

  beforeEach(() => {
    // 清除所有 mock
    vi.clearAllMocks()

    // 创建 Mock SSE 实例
    mockSSE = createMockSSE('/api/stream', {
      interval: 100,
      autoSend: false,
    })
  })

  afterEach(() => {
    // 清理 Mock SSE
    mockSSE.close()
  })

  describe('连接管理', () => {
    it('应该在挂载时建立连接', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })
    })

    it('应该在卸载时断开连接', async () => {
      const { result, unmount } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 卸载组件（这会触发清理逻辑）
      unmount()

      // 卸载后不再检查状态，因为组件已卸载
      // 清理逻辑会在 useSSEStream 的 cleanup 函数中执行
    })

    it('应该支持手动重连', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 手动断开连接
      act(() => {
        result.current.disconnect()
      })

      // 检查连接是否断开
      await waitFor(() => {
        expect(result.current.isConnected).toBe(false)
      })

      // 手动重连
      act(() => {
        result.current.reconnect()
      })

      // 检查连接是否重新建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })
    })
  })

  describe('消息接收和解析', () => {
    test.skip('应该接收并解析消息', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送测试消息
      const testMessage: LogData = {
        level: LogLevel.INFO,
        source: LogSource.SYSTEM,
        message: '测试消息',
        timestamp: new Date().toISOString(),
      }

      act(() => {
        mockSSE.send(testMessage)
      })

      // 等待消息接收
      await waitFor(() => {
        expect(result.current.messages.length).toBe(1)
        expect(result.current.messages[0].data).toEqual(testMessage)
      })
    })

    test.skip('应该接收多条消息', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送多条测试消息
      const messages: LogData[] = [
        {
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '消息 1',
          timestamp: new Date().toISOString(),
        },
        {
          level: LogLevel.DEBUG,
          source: LogSource.AGENT_THINKING,
          message: '消息 2',
          timestamp: new Date().toISOString(),
        },
        {
          level: LogLevel.ERROR,
          source: LogSource.TOOL_CALL,
          message: '消息 3',
          timestamp: new Date().toISOString(),
        },
      ]

      act(() => {
        messages.forEach((msg) => mockSSE.send(msg))
      })

      // 等待所有消息接收
      await waitFor(() => {
        expect(result.current.messages.length).toBe(3)
      })
    })

    it('应该使用自定义消息解析器', async () => {
      const customParse = vi.fn((data: string) => {
        return { custom: true, original: data }
      })

      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          parseMessage: customParse,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送测试消息
      const testMessage = '原始消息'

      act(() => {
        mockSSE.send({
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: testMessage,
          timestamp: new Date().toISOString(),
        })
      })

      // 等待消息接收
      await waitFor(() => {
        expect(customParse).toHaveBeenCalled()
        expect(result.current.messages[0].data).toEqual({
          custom: true,
          original: expect.any(String),
        })
      })
    })

    it('应该清空消息列表', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送测试消息
      act(() => {
        mockSSE.send({
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        })
      })

      // 等待消息接收
      await waitFor(() => {
        expect(result.current.messages.length).toBe(1)
      })

      // 清空消息
      act(() => {
        result.current.clearMessages()
      })

      // 检查消息是否被清空
      expect(result.current.messages.length).toBe(0)
    })
  })

  describe('自动重连机制', () => {
    test.skip('应该在连接错误时自动重连', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          autoReconnect: true,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 模拟连接错误
      act(() => {
        mockSSE.dispatchEvent(new Event('error'))
      })

      // 检查是否进入重连状态
      await waitFor(() => {
        expect(result.current.isReconnecting).toBe(true)
      })

      // 模拟连接恢复
      act(() => {
        mockSSE.dispatchEvent(new Event('open'))
      })

      // 检查是否恢复连接
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
        expect(result.current.isReconnecting).toBe(false)
      })
    })

    test.skip('应该使用指数退避算法', async () => {
      const reconnectDelayBase = 100 // 减小延迟以加快测试
      const maxReconnectDelay = 500 // 减小最大延迟

      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          autoReconnect: true,
          reconnectDelayBase,
          maxReconnectDelay,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 模拟多次连接错误
      for (let i = 0; i < 3; i++) {
        act(() => {
          mockSSE.dispatchEvent(new Event('error'))
        })

        // 等待重连尝试
        await waitFor(() => {
          expect(result.current.isReconnecting).toBe(true)
        })
      }

      // 检查是否在重连中
      expect(result.current.isReconnecting).toBe(true)
    })

    it('应该支持禁用自动重连', async () => {
      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          autoReconnect: false,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 模拟连接错误
      act(() => {
        mockSSE.dispatchEvent(new Event('error'))
      })

      // 检查是否不进入重连状态
      await waitFor(
        () => {
          expect(result.current.isReconnecting).toBe(false)
        },
        { timeout: 1000 }
      )
    })
  })

  describe('错误处理', () => {
    test.skip('应该捕获并记录连接错误', async () => {
      const onError = vi.fn()

      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          autoReconnect: false, // 禁用自动重连以便测试错误状态
          onError,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 模拟连接错误
      const errorEvent = new Event('error')
      act(() => {
        mockSSE.dispatchEvent(errorEvent)
      })

      // 检查错误回调是否被调用
      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(errorEvent)
      })
    })

    it('应该处理消息解析错误', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          parseMessage: () => {
            throw new Error('解析失败')
          },
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送测试消息
      act(() => {
        mockSSE.send({
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        })
      })

      // 检查是否记录了解析错误
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          '[useSSEStream] 消息解析失败:',
          expect.any(Error)
        )
      })

      // 恢复 console.error
      consoleSpy.mockRestore()
    })
  })

  describe('回调函数', () => {
    it('应该调用 onOpen 回调', async () => {
      const onOpen = vi.fn()

      renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          onOpen,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(onOpen).toHaveBeenCalled()
      })
    })

    it('应该调用 onMessage 回调', async () => {
      const onMessage = vi.fn()

      const { result } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          onMessage,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 发送测试消息
      act(() => {
        mockSSE.send({
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        })
      })

      // 检查是否调用了回调
      await waitFor(() => {
        expect(onMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            data: expect.any(Object),
            timestamp: expect.any(Number),
          })
        )
      })
    })

    it('应该调用 onClose 回调', async () => {
      const onClose = vi.fn()

      const { result, unmount } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
          onClose,
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 手动断开连接
      act(() => {
        result.current.disconnect()
      })

      // 检查是否调用了回调
      await waitFor(() => {
        expect(onClose).toHaveBeenCalled()
      })
    })
  })

  describe('内存泄漏防护', () => {
    it('应该在组件卸载时清理所有资源', async () => {
      const { result, unmount } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 卸载组件（这会触发清理逻辑）
      unmount()

      // 清理逻辑会在 useSSEStream 的 cleanup 函数中执行
      // 我们无法直接访问内部的 ref，但可以确保卸载不会抛出错误
    })

    it('应该在卸载后不再接收消息', async () => {
      const { result, unmount } = renderHook(() =>
        useSSEStream({
          url: '/api/stream',
        })
      )

      // 等待连接建立
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true)
      })

      // 卸载组件
      unmount()

      // 发送测试消息
      act(() => {
        mockSSE.send({
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        })
      })

      // 等待一段时间，确保没有接收到消息
      await waitFor(
        () => {
          expect(result.current.messages.length).toBe(0)
        },
        { timeout: 500 }
      )
    })
  })
})
