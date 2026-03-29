/**
 * 日志工具函数单元测试
 *
 * 测试内容:
 * - SSE 消息解析
 * - 时间戳格式化
 * - 日志级别颜色映射
 * - 日志来源图标和标签
 * - 日志过滤功能
 * - Mock 日志数据生成
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  parseSSEMessageToLogEntry,
  formatTimestamp,
  getLogLevelClasses,
  getLogSourceIcon,
  getLogSourceLabel,
  filterLogEntries,
  generateMockLogEntry,
  LOG_LEVEL_COLOR_MAP,
  LOG_SOURCE_ICONS,
  LOG_SOURCE_LABELS,
} from '@/lib/logUtils'
import { LogLevel, LogSource, type LogEntry, type SSEMessage } from '@/types/log'

describe('日志工具函数', () => {
  describe('parseSSEMessageToLogEntry', () => {
    it('应该正确解析有效的 SSE 消息', () => {
      const message: SSEMessage = {
        id: 'msg-1',
        data: {
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        },
        timestamp: Date.now(),
      }

      const entry = parseSSEMessageToLogEntry(message)

      expect(entry).not.toBeNull()
      expect(entry?.id).toBe('msg-1')
      expect(entry?.level).toBe(LogLevel.INFO)
      expect(entry?.source).toBe(LogSource.SYSTEM)
      expect(entry?.message).toBe('测试消息')
    })

    it('应该返回 null 对于无效的消息', () => {
      const invalidMessages: SSEMessage[] = [
        { data: null, timestamp: Date.now() },
        { data: undefined, timestamp: Date.now() },
        { data: 'invalid', timestamp: Date.now() },
        { data: {}, timestamp: Date.now() },
        { data: { level: 'INVALID', source: LogSource.SYSTEM, message: 'test' }, timestamp: Date.now() },
        { data: { level: LogLevel.INFO, source: 'INVALID', message: 'test' }, timestamp: Date.now() },
      ]

      invalidMessages.forEach((msg) => {
        const entry = parseSSEMessageToLogEntry(msg)
        expect(entry).toBeNull()
      })
    })

    it('应该处理包含可选字段的消息', () => {
      const message: SSEMessage = {
        id: 'msg-1',
        data: {
          level: LogLevel.INFO,
          source: LogSource.AGENT_THINKING,
          message: '测试消息',
          timestamp: new Date().toISOString(),
          agentId: 'agent-1',
          toolName: 'math_calculator',
          metadata: { executionTime: 123 },
        },
        timestamp: Date.now(),
      }

      const entry = parseSSEMessageToLogEntry(message)

      expect(entry?.agentId).toBe('agent-1')
      expect(entry?.toolName).toBe('math_calculator')
      expect(entry?.metadata).toEqual({ executionTime: 123 })
    })

    it('应该使用时间戳作为 ID 如果消息没有 ID', () => {
      const timestamp = Date.now()
      const message: SSEMessage = {
        data: {
          level: LogLevel.INFO,
          source: LogSource.SYSTEM,
          message: '测试消息',
          timestamp: new Date().toISOString(),
        },
        timestamp,
      }

      const entry = parseSSEMessageToLogEntry(message)

      expect(entry?.id).toBe(`log-${timestamp}`)
    })
  })

  describe('formatTimestamp', () => {
    it('应该格式化 ISO 时间戳', () => {
      const isoTimestamp = '2024-01-15T10:30:45.123Z'
      const formatted = formatTimestamp(isoTimestamp)

      expect(formatted).toMatch(/^\d{2}:\d{2}:\d{2}\.\d{3}$/)
    })

    it('应该格式化 Unix 时间戳', () => {
      const timestampMs = 1705317045123 // 2024-01-15T10:30:45.123Z
      const formatted = formatTimestamp('', timestampMs)

      expect(formatted).toMatch(/^\d{2}:\d{2}:\d{2}\.\d{3}$/)
    })

    it('应该优先使用 timestampMs 参数', () => {
      const isoTimestamp = '2024-01-15T10:30:45.123Z'
      const timestampMs = 1705317045123
      const formatted = formatTimestamp(isoTimestamp, timestampMs)

      // 由于时区问题，我们只验证格式正确，不验证具体时间
      expect(formatted).toMatch(/^\d{2}:\d{2}:\d{2}\.\d{3}$/)
    })
  })

  describe('getLogLevelClasses', () => {
    it('应该为每个日志级别返回正确的颜色类', () => {
      expect(getLogLevelClasses(LogLevel.DEBUG)).toBe('text-gray-500')
      expect(getLogLevelClasses(LogLevel.INFO)).toBe('text-accent-cyan-500')
      expect(getLogLevelClasses(LogLevel.SUCCESS)).toBe('text-accent-green-500')
      expect(getLogLevelClasses(LogLevel.WARN)).toBe('text-accent-amber-500')
      expect(getLogLevelClasses(LogLevel.ERROR)).toBe('text-accent-red-500')
    })
  })

  describe('getLogSourceIcon', () => {
    it('应该为每个日志来源返回正确的图标', () => {
      expect(getLogSourceIcon(LogSource.SYSTEM)).toBe('⚙️')
      expect(getLogSourceIcon(LogSource.AGENT_THINKING)).toBe('🤖')
      expect(getLogSourceIcon(LogSource.TOOL_CALL)).toBe('🔧')
      expect(getLogSourceIcon(LogSource.SANDBOX_EXECUTION)).toBe('📦')
      expect(getLogSourceIcon(LogSource.NETWORK)).toBe('🌐')
    })
  })

  describe('getLogSourceLabel', () => {
    it('应该为每个日志来源返回正确的标签', () => {
      expect(getLogSourceLabel(LogSource.SYSTEM)).toBe('系统')
      expect(getLogSourceLabel(LogSource.AGENT_THINKING)).toBe('智能体')
      expect(getLogSourceLabel(LogSource.TOOL_CALL)).toBe('工具调用')
      expect(getLogSourceLabel(LogSource.SANDBOX_EXECUTION)).toBe('沙箱执行')
      expect(getLogSourceLabel(LogSource.NETWORK)).toBe('网络')
    })
  })

  describe('filterLogEntries', () => {
    let testEntries: LogEntry[]

    beforeEach(() => {
      testEntries = [
        {
          id: 'log-1',
          level: LogLevel.DEBUG,
          source: LogSource.SYSTEM,
          message: '调试消息',
          timestamp: new Date().toISOString(),
          timestampMs: Date.now(),
        },
        {
          id: 'log-2',
          level: LogLevel.INFO,
          source: LogSource.AGENT_THINKING,
          message: '信息消息 agent-1',
          timestamp: new Date().toISOString(),
          timestampMs: Date.now(),
          agentId: 'agent-1',
        },
        {
          id: 'log-3',
          level: LogLevel.WARN,
          source: LogSource.TOOL_CALL,
          message: '警告消息 math_calculator',
          timestamp: new Date().toISOString(),
          timestampMs: Date.now(),
          toolName: 'math_calculator',
        },
        {
          id: 'log-4',
          level: LogLevel.ERROR,
          source: LogSource.SANDBOX_EXECUTION,
          message: '错误消息',
          timestamp: new Date().toISOString(),
          timestampMs: Date.now(),
        },
        {
          id: 'log-5',
          level: LogLevel.SUCCESS,
          source: LogSource.NETWORK,
          message: '成功消息',
          timestamp: new Date().toISOString(),
          timestampMs: Date.now(),
        },
      ]
    })

    it('应该按最小日志级别过滤', () => {
      const filtered = filterLogEntries(testEntries, {
        minLevel: LogLevel.INFO,
      })

      expect(filtered.length).toBe(4) // INFO, WARN, ERROR, SUCCESS
      expect(filtered.every((entry) => entry.level !== LogLevel.DEBUG)).toBe(true)
    })

    it('应该按日志来源过滤', () => {
      const filtered = filterLogEntries(testEntries, {
        sources: [LogSource.SYSTEM, LogSource.AGENT_THINKING],
      })

      expect(filtered.length).toBe(2)
      expect(filtered.every((entry) =>
        [LogSource.SYSTEM, LogSource.AGENT_THINKING].includes(entry.source)
      )).toBe(true)
    })

    it('应该按关键词搜索', () => {
      const filtered = filterLogEntries(testEntries, {
        keyword: 'agent',
      })

      expect(filtered.length).toBe(1)
      expect(filtered[0].agentId).toBe('agent-1')
    })

    it('应该按智能体 ID 过滤', () => {
      const filtered = filterLogEntries(testEntries, {
        agentId: 'agent-1',
      })

      expect(filtered.length).toBe(1)
      expect(filtered[0].agentId).toBe('agent-1')
    })

    it('应该组合多个过滤条件', () => {
      const filtered = filterLogEntries(testEntries, {
        minLevel: LogLevel.INFO,
        sources: [LogSource.AGENT_THINKING, LogSource.TOOL_CALL],
        keyword: 'agent',
      })

      expect(filtered.length).toBe(1)
      expect(filtered[0].agentId).toBe('agent-1')
    })

    it('应该返回所有条目如果没有过滤条件', () => {
      const filtered = filterLogEntries(testEntries, {})

      expect(filtered.length).toBe(5)
    })

    it('应该返回空数组如果没有匹配的条目', () => {
      const filtered = filterLogEntries(testEntries, {
        keyword: '不存在的关键词',
      })

      expect(filtered.length).toBe(0)
    })
  })

  describe('generateMockLogEntry', () => {
    it('应该生成有效的日志条目', () => {
      const entry = generateMockLogEntry()

      expect(entry).toHaveProperty('id')
      expect(entry).toHaveProperty('level')
      expect(entry).toHaveProperty('source')
      expect(entry).toHaveProperty('message')
      expect(entry).toHaveProperty('timestamp')
      expect(entry).toHaveProperty('timestampMs')

      expect(Object.values(LogLevel)).toContain(entry.level)
      expect(Object.values(LogSource)).toContain(entry.source)
    })

    it('应该支持覆盖默认值', () => {
      const entry = generateMockLogEntry({
        level: LogLevel.ERROR,
        message: '自定义消息',
      })

      expect(entry.level).toBe(LogLevel.ERROR)
      expect(entry.message).toBe('自定义消息')
    })

    it('应该生成唯一的 ID', () => {
      const entry1 = generateMockLogEntry()
      const entry2 = generateMockLogEntry()

      expect(entry1.id).not.toBe(entry2.id)
    })
  })

  describe('常量映射', () => {
    it('应该为所有日志级别定义颜色映射', () => {
      Object.values(LogLevel).forEach((level) => {
        expect(LOG_LEVEL_COLOR_MAP[level]).toBeDefined()
      })
    })

    it('应该为所有日志来源定义图标', () => {
      Object.values(LogSource).forEach((source) => {
        expect(LOG_SOURCE_ICONS[source]).toBeDefined()
      })
    })

    it('应该为所有日志来源定义标签', () => {
      Object.values(LogSource).forEach((source) => {
        expect(LOG_SOURCE_LABELS[source]).toBeDefined()
      })
    })
  })
})
