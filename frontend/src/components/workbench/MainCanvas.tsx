/**
 * MainCanvas - 主工作画布组件
 *
 * 功能说明:
 * - 用于渲染 Markdown 论文预览或图表
 * - 包含差异对比的结构化干预仪表板
 * - 支持多种视图模式切换(预览、编辑、对比等)
 *
 * 占位说明:
 * - 当前为基础占位组件,后续将实现完整的画布功能
 * - 将支持 Markdown 渲染、图表可视化、差异对比等
 */

import React, { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { FileText, Layers, Sparkles, Loader2, CheckCircle, Edit, XCircle } from 'lucide-react'
import { useSSEStream } from '@/hooks/useSSEStream'

/**
 * MainCanvas Props 接口
 */
export interface MainCanvasProps {
  /** 会话 ID */
  sessionId?: string
}

/**
 * MainCanvas 组件
 * 中间主工作区 - 主工作画布
 */
export const MainCanvas: React.FC<MainCanvasProps> = ({ sessionId }) => {
  // 工作流数据状态
  const [workflowData, setWorkflowData] = useState<any>(null)
  const [status, setStatus] = useState<string>('pending')
  const [hitlContext, setHitlContext] = useState<any>(null)

  // SSE 连接
  const { messages, isConnected } = useSSEStream({
    url: sessionId ? `/api/stream/events/${sessionId}` : '',
    parseMessage: (data) => {
      try {
        return JSON.parse(data)
      } catch {
        return { raw: data }
      }
    },
    onMessage: (message) => {
      console.log('[MainCanvas] 接收到消息:', message)
      console.log('[MainCanvas] 消息类型:', message.event)
      console.log('[MainCanvas] 消息数据:', message.data)

      // 根据事件类型更新工作流数据
      if (message.event === 'workflow_stage_change') {
        const stage = message.data?.data?.to_stage || message.data?.data?.stage
        if (stage) {
          console.log('[MainCanvas] 阶段变更:', stage)
          setStatus(stage)
        }
      }

      // 处理智能体思考事件
      if (message.event === 'agent_thought') {
        const thought = message.data?.data?.thought
        console.log('[MainCanvas] 智能体思考:', thought)
        // 更新工作流数据，显示智能体思考内容
        if (thought) {
          setWorkflowData({
            title: '智能体思考过程',
            content: thought,
            type: 'agent_thought',
          })
        }
      }

      // 处理智能体行动事件
      if (message.event === 'agent_action') {
        const action = message.data?.data?.action
        const params = message.data?.data?.params
        console.log('[MainCanvas] 智能体行动:', action, params)
        // 更新工作流数据，显示智能体行动
        if (action) {
          setWorkflowData({
            title: '智能体执行操作',
            content: `操作: ${action}\n参数: ${JSON.stringify(params, null, 2)}`,
            type: 'agent_action',
          })
        }
      }

      // 处理 HITL 中断事件（人工审核）
      if (message.event === 'hitl_interrupt') {
        const reason = message.data?.data?.reason
        const context = message.data?.data?.context
        console.log('[MainCanvas] HITL 中断:', reason, context)
        // 更新工作流数据，显示人工审核提示
        setWorkflowData({
          title: '⚠️ 需要人工审核',
          content: context?.message || '工作流已暂停，等待您的审核和确认',
          type: 'hitl_interrupt',
          context: context,
        })
        setHitlContext(context)
        setStatus('paused')
      }
    },
  })

  // 处理 HITL 操作
  const handleHitlAction = async (actionId: string) => {
    if (!sessionId || !hitlContext) return

    console.log('[MainCanvas] 执行 HITL 操作:', actionId)

    try {
      const response = await fetch(`/api/v1/workflows/${sessionId}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: actionId,
          feedback: hitlContext.research_result,
        }),
      })

      if (response.ok) {
        console.log('[MainCanvas] 工作流已恢复')
        setHitlContext(null)
        setStatus('running')
      } else {
        console.error('[MainCanvas] 恢复工作流失败:', await response.text())
      }
    } catch (error) {
      console.error('[MainCanvas] 恢复工作流失败:', error)
    }
  }

  // 获取初始工作流状态
  useEffect(() => {
    if (!sessionId) return

    const fetchWorkflowStatus = async () => {
      try {
        const response = await fetch(`/api/v1/workflows/${sessionId}/status`)
        if (response.ok) {
          const data = await response.json()
          setStatus(data.status || 'pending')
          console.log('[MainCanvas] 工作流状态:', data)
        }
      } catch (error) {
        console.error('[MainCanvas] 获取工作流状态失败:', error)
      }
    }

    fetchWorkflowStatus()
  }, [sessionId])

  return (
    <div className={cn('h-full flex flex-col')}>
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-dark-border">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-accent-cyan-500" />
          <h2 className="text-lg font-semibold text-gray-100">工作画布</h2>
        </div>

        {/* 视图模式切换按钮组 */}
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 text-xs font-medium rounded-md bg-dark-bg-tertiary text-gray-300 hover:bg-dark-surface transition-colors">
            预览
          </button>
          <button className="px-3 py-1.5 text-xs font-medium rounded-md bg-dark-bg-tertiary text-gray-300 hover:bg-dark-surface transition-colors">
            编辑
          </button>
          <button className="px-3 py-1.5 text-xs font-medium rounded-md bg-dark-bg-tertiary text-gray-300 hover:bg-dark-surface transition-colors">
            对比
          </button>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        {/* 连接状态指示 */}
        {!isConnected && sessionId && (
          <div className="mb-4 flex items-center gap-2 text-amber-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">正在连接工作流...</span>
          </div>
        )}

        {/* 工作流数据显示 */}
        {workflowData ? (
          <div className="w-full h-full overflow-auto">
            <div className="prose prose-invert max-w-none">
              <h3 className="text-xl font-semibold text-gray-100 mb-4">
                {workflowData.title || '工作流执行中'}
              </h3>
              <div className="text-sm text-gray-300 whitespace-pre-wrap mb-4">
                {workflowData.content || JSON.stringify(workflowData, null, 2)}
              </div>

              {/* HITL 审核界面 */}
              {workflowData.type === 'hitl_interrupt' && hitlContext && (
                <div className="mt-6 p-4 rounded-lg bg-dark-bg-tertiary border border-dark-border">
                  <h4 className="text-lg font-semibold text-gray-100 mb-3">
                    研究结果摘要
                  </h4>

                  {/* 研究结果 */}
                  {hitlContext.research_result && (
                    <div className="mb-4 text-left">
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="text-gray-400">论文数量:</div>
                        <div className="text-gray-200">{hitlContext.research_result.papers_found} 篇</div>

                        <div className="text-gray-400">研究主题:</div>
                        <div className="text-gray-200">{hitlContext.research_result.research_topic}</div>

                        <div className="text-gray-400">关键词:</div>
                        <div className="text-gray-200">{hitlContext.research_result.keywords?.join(', ')}</div>

                        {hitlContext.research_result.survey_title && (
                          <>
                            <div className="text-gray-400">综述标题:</div>
                            <div className="text-gray-200">{hitlContext.research_result.survey_title}</div>
                          </>
                        )}
                      </div>

                      {hitlContext.research_result.key_findings && (
                        <div className="mt-3">
                          <div className="text-gray-400 text-sm mb-1">主要发现:</div>
                          <div className="text-gray-200 text-sm whitespace-pre-wrap">
                            {hitlContext.research_result.key_findings.substring(0, 300)}...
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 操作按钮 */}
                  <div className="flex gap-3 mt-4">
                    {hitlContext.actions?.map((action: any) => (
                      <button
                        key={action.id}
                        onClick={() => handleHitlAction(action.id)}
                        className={cn(
                          'flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                          'flex items-center justify-center gap-2',
                          action.id === 'approve' && 'bg-accent-green-600 hover:bg-accent-green-700 text-white',
                          action.id === 'modify' && 'bg-accent-amber-600 hover:bg-accent-amber-700 text-white',
                          action.id === 'reject' && 'bg-accent-red-600 hover:bg-accent-red-700 text-white'
                        )}
                      >
                        {action.id === 'approve' && <CheckCircle className="w-4 h-4" />}
                        {action.id === 'modify' && <Edit className="w-4 h-4" />}
                        {action.id === 'reject' && <XCircle className="w-4 h-4" />}
                        {action.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* 装饰性图标 */}
            <div className="mb-6 relative">
              <div className="absolute inset-0 bg-accent-cyan-500/20 blur-3xl rounded-full" />
              <div className="relative p-6 rounded-2xl bg-dark-bg-tertiary border border-dark-border">
                {status === 'running' ? (
                  <Loader2 className="w-12 h-12 text-accent-cyan-500 animate-spin" />
                ) : (
                  <Sparkles className="w-12 h-12 text-accent-cyan-500" />
                )}
              </div>
            </div>

            {/* 标题和描述 */}
            <h3 className="text-xl font-semibold text-gray-100 mb-2">
              {status === 'running' ? '工作流执行中...' : 'EpistemicFlow 工作台'}
            </h3>
            <p className="text-sm text-gray-400 mb-6 max-w-md">
              {sessionId
                ? `会话 ID: ${sessionId.substring(0, 8)}...`
                : 'AI 驱动的自动化科研平台'}
              <br />
              在此预览论文、图表和进行结构化干预
            </p>

            {/* 功能卡片 */}
            <div className="grid grid-cols-3 gap-4 w-full max-w-2xl">
              <div className="p-4 rounded-lg bg-dark-bg-tertiary border border-dark-border hover:border-accent-cyan-500/50 transition-colors">
                <FileText className="w-6 h-6 text-accent-cyan-500 mb-2" />
                <p className="text-xs font-medium text-gray-300">Markdown 预览</p>
              </div>
              <div className="p-4 rounded-lg bg-dark-bg-tertiary border border-dark-border hover:border-accent-amber-500/50 transition-colors">
                <Layers className="w-6 h-6 text-accent-amber-500 mb-2" />
                <p className="text-xs font-medium text-gray-300">图表可视化</p>
              </div>
              <div className="p-4 rounded-lg bg-dark-bg-tertiary border border-dark-border hover:border-accent-green-500/50 transition-colors">
                <Sparkles className="w-6 h-6 text-accent-green-500 mb-2" />
                <p className="text-xs font-medium text-gray-300">差异对比</p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default MainCanvas
