/**
 * Mock SSE 流式数据源服务
 *
 * 功能说明:
 * - 模拟后端 SSE 端点,用于前端测试
 * - 生成各种类型的日志数据
 * - 支持自定义消息生成策略
 * - 可以手动触发特定类型的日志
 */

import { LogLevel, LogSource, LogData } from '@/types/log'

/**
 * Mock SSE 配置选项
 */
export interface MockSSEOptions {
  /** 消息发送间隔 (毫秒) */
  interval?: number
  /** 是否自动发送消息 */
  autoSend?: boolean
  /** 自定义消息生成器 */
  messageGenerator?: () => LogData | null
  /** 最大消息数量 (0 表示无限制) */
  maxMessages?: number
}

/**
 * Mock SSE 事件类型
 */
export type MockSSEEventType = 'message' | 'open' | 'error' | 'close'

/**
 * Mock SSE 监听器类型
 */
export type MockSSEListener = (event: Event) => void

/**
 * Mock SSE 类
 * 模拟浏览器 EventSource API 的行为
 */
export class MockEventSource {
  private url: string
  private options: MockSSEOptions
  private intervalId: number | null = null
  private messageCount = 0
  private listeners: Map<string, Set<MockSSEListener>> = new Map()
  private readyState: number = 0 // 0: connecting, 1: open, 2: closed

  // 静态常量,与原生 EventSource 保持一致
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2

  constructor(url: string, options: MockSSEOptions = {}) {
    this.url = url
    this.options = {
      interval: 500,
      autoSend: true,
      maxMessages: 0,
      ...options,
    }

    // 初始化事件监听器集合
    this.listeners.set('message', new Set())
    this.listeners.set('open', new Set())
    this.listeners.set('error', new Set())
    this.listeners.set('close', new Set())

    // 模拟连接过程
    this.simulateConnection()
  }

  /**
   * 获取连接状态
   */
  get CONNECTING() {
    return MockEventSource.CONNECTING
  }

  get OPEN() {
    return MockEventSource.OPEN
  }

  get CLOSED() {
    return MockEventSource.CLOSED
  }

  /**
   * 模拟连接过程
   */
  private simulateConnection() {
    this.readyState = MockEventSource.CONNECTING

    // 模拟网络延迟后连接成功
    setTimeout(() => {
      this.readyState = MockEventSource.OPEN
      this.dispatchEvent(new Event('open'))

      // 如果启用自动发送,开始发送消息
      if (this.options.autoSend) {
        this.startSending()
      }
    }, 100)
  }

  /**
   * 开始发送消息
   */
  private startSending() {
    if (this.intervalId !== null) {
      return
    }

    this.intervalId = window.setInterval(() => {
      // 检查是否达到最大消息数量
      if (this.options.maxMessages && this.messageCount >= this.options.maxMessages) {
        this.stopSending()
        return
      }

      // 检查连接状态
      if (this.readyState !== MockEventSource.OPEN) {
        return
      }

      // 生成并发送消息
      const message = this.generateMessage()
      if (message) {
        this.sendMessage(message)
        this.messageCount++
      }
    }, this.options.interval)
  }

  /**
   * 停止发送消息
   */
  private stopSending() {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
  }

  /**
   * 生成随机日志消息
   */
  private generateMessage(): LogData | null {
    // 如果有自定义生成器,使用自定义生成器
    if (this.options.messageGenerator) {
      return this.options.messageGenerator()
    }

    // 默认生成器
    return generateRandomLogData()
  }

  /**
   * 发送消息
   */
  private sendMessage(data: LogData) {
    const messageEvent = new MessageEvent('message', {
      data: JSON.stringify(data),
      lastEventId: `msg-${this.messageCount}`,
      origin: this.url,
    })

    this.dispatchEvent(messageEvent)
  }

  /**
   * 分发事件
   */
  private dispatchEvent(event: Event) {
    const listeners = this.listeners.get(event.type)
    if (listeners) {
      listeners.forEach((listener) => {
        try {
          listener(event)
        } catch (err) {
          console.error('[MockEventSource] 事件监听器错误:', err)
        }
      })
    }
  }

  /**
   * 添加事件监听器
   */
  addEventListener(type: MockSSEEventType, listener: MockSSEListener) {
    const listeners = this.listeners.get(type)
    if (listeners) {
      listeners.add(listener)
    }
  }

  /**
   * 移除事件监听器
   */
  removeEventListener(type: MockSSEEventType, listener: MockSSEListener) {
    const listeners = this.listeners.get(type)
    if (listeners) {
      listeners.delete(listener)
    }
  }

  /**
   * 设置 onmessage 回调
   */
  set onmessage(listener: ((ev: MessageEvent) => unknown) | null) {
    this.addEventListener('message', listener as MockSSEListener)
  }

  /**
   * 设置 onopen 回调
   */
  set onopen(listener: ((ev: Event) => unknown) | null) {
    this.addEventListener('open', listener as MockSSEListener)
  }

  /**
   * 设置 onerror 回调
   */
  set onerror(listener: ((ev: Event) => unknown) | null) {
    this.addEventListener('error', listener as MockSSEListener)
  }

  /**
   * 手动发送单条消息
   */
  public send(message: LogData) {
    if (this.readyState !== MockEventSource.OPEN) {
      console.warn('[MockEventSource] 连接未打开,无法发送消息')
      return
    }

    this.sendMessage(message)
    this.messageCount++
  }

  /**
   * 关闭连接
   */
  public close() {
    this.readyState = MockEventSource.CLOSED
    this.stopSending()
    this.dispatchEvent(new Event('close'))
  }
}

/**
 * 生成随机日志数据
 */
export function generateRandomLogData(): LogData {
  const levels = Object.values(LogLevel)
  const sources = Object.values(LogSource)

  // 根据来源生成不同的消息内容
  const source = sources[Math.floor(Math.random() * sources.length)]
  const level = levels[Math.floor(Math.random() * levels.length)]

  let message = ''
  let metadata: Record<string, unknown> = {}

  switch (source) {
    case LogSource.SYSTEM:
      message = getRandomSystemMessage(level)
      break

    case LogSource.AGENT_THINKING:
      message = getRandomAgentThinkingMessage(level)
      metadata = {
        agentId: `agent-${Math.floor(Math.random() * 5) + 1}`,
        thoughtDepth: Math.floor(Math.random() * 10) + 1,
      }
      break

    case LogSource.TOOL_CALL:
      message = getRandomToolCallMessage(level)
      metadata = {
        toolName: getRandomToolName(),
        executionTime: Math.random() * 1000,
      }
      break

    case LogSource.SANDBOX_EXECUTION:
      message = getRandomSandboxMessage(level)
      metadata = {
        sandboxId: `sandbox-${Math.floor(Math.random() * 3) + 1}`,
        memoryUsage: Math.random() * 512,
      }
      break

    case LogSource.NETWORK:
      message = getRandomNetworkMessage(level)
      metadata = {
        endpoint: '/api/v1/execute',
        statusCode: level === LogLevel.ERROR ? 500 : 200,
        responseTime: Math.random() * 200,
      }
      break
  }

  return {
    level,
    source,
    message,
    timestamp: new Date().toISOString(),
    metadata,
  }
}

/**
 * 获取随机系统消息
 */
function getRandomSystemMessage(level: LogLevel): string {
  const messages = {
    [LogLevel.DEBUG]: [
      '调试信息: 正在加载配置文件',
      '调试信息: 初始化内存池',
      '调试信息: 检查依赖项版本',
    ],
    [LogLevel.INFO]: [
      '系统初始化完成',
      '连接到后端服务...',
      '开始执行任务流程',
      '加载配置文件: config.yaml',
      '初始化智能体拓扑...',
    ],
    [LogLevel.SUCCESS]: [
      'WebSocket 连接已建立',
      '智能体拓扑构建完成',
      '系统启动成功',
    ],
    [LogLevel.WARN]: [
      '等待智能体响应...',
      '检测到高延迟,建议优化网络',
      '内存使用率超过 80%',
    ],
    [LogLevel.ERROR]: [
      '连接超时',
      '初始化失败',
      '系统错误: 无法加载配置',
    ],
  }

  const levelMessages = messages[level] || messages[LogLevel.INFO]
  return levelMessages[Math.floor(Math.random() * levelMessages.length)]
}

/**
 * 获取随机智能体思考消息
 */
function getRandomAgentThinkingMessage(level: LogLevel): string {
  const messages = {
    [LogLevel.DEBUG]: [
      '分析问题结构...',
      '评估可能的解决方案...',
      '检查约束条件...',
    ],
    [LogLevel.INFO]: [
      '正在分析用户请求',
      '开始规划任务执行路径',
      '评估工具调用必要性',
      '思考步骤 1: 理解问题',
      '思考步骤 2: 分解任务',
    ],
    [LogLevel.SUCCESS]: [
      '成功理解用户意图',
      '任务规划完成',
      '找到最优解决方案',
    ],
    [LogLevel.WARN]: [
      '检测到潜在冲突',
      '需要更多信息才能做出决策',
      '建议用户提供更多上下文',
    ],
    [LogLevel.ERROR]: [
      '无法理解用户请求',
      '任务规划失败',
      '推理过程中断',
    ],
  }

  const levelMessages = messages[level] || messages[LogLevel.INFO]
  return levelMessages[Math.floor(Math.random() * levelMessages.length)]
}

/**
 * 获取随机工具调用消息
 */
function getRandomToolCallMessage(level: LogLevel): string {
  const messages = {
    [LogLevel.DEBUG]: [
      '准备工具参数...',
      '验证工具输入...',
    ],
    [LogLevel.INFO]: [
      '调用数学计算工具',
      '执行代码解释器',
      '访问外部 API',
      '读取文件内容',
    ],
    [LogLevel.SUCCESS]: [
      '工具调用成功',
      '获得计算结果',
      'API 响应已接收',
    ],
    [LogLevel.WARN]: [
      '工具执行时间较长',
      '部分参数缺失,使用默认值',
      '工具返回了部分结果',
    ],
    [LogLevel.ERROR]: [
      '工具调用失败',
      'API 返回错误',
      '工具不可用',
    ],
  }

  const levelMessages = messages[level] || messages[LogLevel.INFO]
  return levelMessages[Math.floor(Math.random() * levelMessages.length)]
}

/**
 * 获取随机沙箱执行消息
 */
function getRandomSandboxMessage(level: LogLevel): string {
  const messages = {
    [LogLevel.DEBUG]: [
      '初始化沙箱环境...',
      '设置资源限制...',
    ],
    [LogLevel.INFO]: [
      '在沙箱中执行 Python 代码',
      '启动隔离环境',
      '执行用户代码',
      '清理沙箱资源',
    ],
    [LogLevel.SUCCESS]: [
      '代码执行成功',
      '沙箱任务完成',
      '获得执行结果',
    ],
    [LogLevel.WARN]: [
      '代码执行时间接近限制',
      '内存使用率较高',
      '检测到潜在的安全风险',
    ],
    [LogLevel.ERROR]: [
      '代码执行错误',
      '沙箱资源耗尽',
      '执行超时',
      '检测到危险操作',
    ],
  }

  const levelMessages = messages[level] || messages[LogLevel.INFO]
  return levelMessages[Math.floor(Math.random() * levelMessages.length)]
}

/**
 * 获取随机网络消息
 */
function getRandomNetworkMessage(level: LogLevel): string {
  const messages = {
    [LogLevel.DEBUG]: [
      '准备 HTTP 请求...',
      '设置请求头...',
    ],
    [LogLevel.INFO]: [
      '发送 HTTP GET 请求',
      '接收服务器响应',
      '上传数据到服务器',
      '建立 WebSocket 连接',
    ],
    [LogLevel.SUCCESS]: [
      '请求成功',
      '数据传输完成',
      '连接建立成功',
    ],
    [LogLevel.WARN]: [
      '响应时间较长',
      '检测到网络不稳定',
      '请求被重试',
    ],
    [LogLevel.ERROR]: [
      '网络错误',
      '服务器返回 500 错误',
      '连接超时',
      '请求被拒绝',
    ],
  }

  const levelMessages = messages[level] || messages[LogLevel.INFO]
  return levelMessages[Math.floor(Math.random() * levelMessages.length)]
}

/**
 * 获取随机工具名称
 */
function getRandomToolName(): string {
  const tools = [
    'math_calculator',
    'code_interpreter',
    'web_search',
    'file_reader',
    'text_analyzer',
    'data_visualizer',
    'api_client',
    'database_query',
  ]

  return tools[Math.floor(Math.random() * tools.length)]
}

/**
 * 创建 Mock SSE 实例的工厂函数
 */
export function createMockSSE(url: string, options?: MockSSEOptions): MockEventSource {
  return new MockEventSource(url, options)
}
