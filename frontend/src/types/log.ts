/**
 * 日志相关类型定义
 */

/**
 * 日志级别枚举
 */
export enum LogLevel {
  /** 调试信息 */
  DEBUG = 'DEBUG',
  /** 一般信息 */
  INFO = 'INFO',
  /** 成功状态 */
  SUCCESS = 'SUCCESS',
  /** 警告信息 */
  WARN = 'WARN',
  /** 错误信息 */
  ERROR = 'ERROR',
}

/**
 * 日志来源类型
 */
export enum LogSource {
  /** 系统提示 */
  SYSTEM = 'SYSTEM',
  /** 智能体思考 */
  AGENT_THINKING = 'AGENT_THINKING',
  /** 工具调用 */
  TOOL_CALL = 'TOOL_CALL',
  /** 沙箱执行 */
  SANDBOX_EXECUTION = 'SANDBOX_EXECUTION',
  /** 网络请求 */
  NETWORK = 'NETWORK',
}

/**
 * 日志数据接口
 */
export interface LogData {
  /** 日志级别 */
  level: LogLevel
  /** 日志来源 */
  source: LogSource
  /** 日志消息 */
  message: string
  /** 时间戳 (ISO 8601 格式) */
  timestamp: string
  /** 智能体 ID (可选) */
  agentId?: string
  /** 工具名称 (可选) */
  toolName?: string
  /** 额外元数据 (可选) */
  metadata?: Record<string, unknown>
}

/**
 * 日志条目接口 (用于渲染)
 */
export interface LogEntry extends LogData {
  /** 唯一标识符 */
  id: string
  /** Unix 时间戳 */
  timestampMs: number
}

/**
 * 日志过滤器配置
 */
export interface LogFilter {
  /** 最小日志级别 */
  minLevel?: LogLevel
  /** 日志来源白名单 */
  sources?: LogSource[]
  /** 搜索关键词 */
  keyword?: string
  /** 智能体 ID 过滤 */
  agentId?: string
}

/**
 * SSE 消息类型
 */
export interface SSEMessage {
  /** 消息 ID */
  id?: string
  /** 消息事件类型 */
  event?: string
  /** 消息数据 */
  data: unknown
  /** 原始数据字符串 */
  rawData?: string
  /** 时间戳 */
  timestamp: number
}
