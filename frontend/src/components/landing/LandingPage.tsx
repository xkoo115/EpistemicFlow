/**
 * LandingPage 组件
 *
 * 系统的主入口页面，提供：
 * - 科技感的大输入框（用于输入科研 Idea）
 * - 论文类型选择（研究/综述）
 * - 模型配置选项
 * - "Start Discovery" 启动按钮
 *
 * 用户点击启动后，界面平滑过渡到 WorkbenchLayout，并开始 SSE 监听。
 */

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PaperType } from '@/types/workflow'

/**
 * 论文类型选项
 */
const PAPER_TYPE_OPTIONS = [
  {
    value: PaperType.RESEARCH_PAPER,
    label: '原创研究',
    description: '提出新方法、新理论或新实验',
    icon: '🔬',
  },
  {
    value: PaperType.SURVEY_PAPER,
    label: '综述论文',
    description: '系统梳理某一领域的研究现状',
    icon: '📚',
  },
] as const

/**
 * LandingPage 属性
 */
interface LandingPageProps {
  onStartWorkflow?: (data: WorkflowStartData) => void
}

/**
 * 工作流启动数据
 */
export interface WorkflowStartData {
  researchIdea: string
  paperType: PaperType
  keywords?: string[]
  modelConfig?: Record<string, unknown>
}

/**
 * LandingPage 组件
 */
const LandingPage: React.FC<LandingPageProps> = ({ onStartWorkflow }) => {
  const navigate = useNavigate()

  // 状态管理
  const [researchIdea, setResearchIdea] = useState('')
  const [paperType, setPaperType] = useState<PaperType>(PaperType.RESEARCH_PAPER)
  const [keywords, setKeywords] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /**
   * 处理启动工作流
   */
  const handleStart = async () => {
    // 验证输入
    if (!researchIdea.trim()) {
      setError('请输入您的研究方向或假设')
      return
    }

    if (researchIdea.trim().length < 10) {
      setError('研究方向描述至少需要 10 个字符')
      return
    }

    setError(null)
    setIsLoading(true)

    try {
      // 准备请求数据
      const requestData = {
        research_idea: researchIdea.trim(),
        paper_type: paperType,  // PaperType 枚举值已经是字符串
        keywords: keywords.trim() ? keywords.split(',').map(k => k.trim()).filter(Boolean) : undefined,
      }

      console.log('Sending request:', requestData)

      // 调用后端 API
      const response = await fetch('/api/v1/workflows/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      })

      console.log('Response status:', response.status)

      if (!response.ok) {
        // 尝试解析错误响应
        let errorMessage = '启动工作流失败'
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          // 如果无法解析 JSON，使用状态文本
          errorMessage = response.statusText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const data = await response.json()
      console.log('Response data:', data)

      // 回调
      if (onStartWorkflow) {
        onStartWorkflow({
          researchIdea: researchIdea.trim(),
          paperType,
          keywords: requestData.keywords,
        })
      }

      // 导航到工作台，传递 session_id
      navigate(`/workbench/${data.session_id}`)

    } catch (err) {
      console.error('Error:', err)
      setError(err instanceof Error ? err.message : '启动工作流失败')
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * 处理键盘事件
   */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleStart()
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      {/* 背景装饰 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
      </div>

      {/* 主内容 */}
      <div className="relative w-full max-w-4xl">
        {/* 标题区域 */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-white mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              EpistemicFlow
            </span>
          </h1>
          <p className="text-xl text-slate-400">
            AI 驱动的自动化科研平台
          </p>
          <p className="text-sm text-slate-500 mt-2">
            输入您的研究想法，让多智能体系统为您完成文献调研、方法设计和论文撰写
          </p>
        </div>

        {/* 输入卡片 */}
        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-8 shadow-2xl">
          {/* 科研 Idea 输入框 */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              研究方向 / 假设
            </label>
            <div className="relative">
              <textarea
                value={researchIdea}
                onChange={(e) => setResearchIdea(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述您想要探索的研究方向、问题或假设...&#10;&#10;例如：研究一种新的注意力机制，能够在保持计算效率的同时提升长序列建模能力"
                className="w-full h-40 px-4 py-3 bg-slate-900/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all resize-none"
                disabled={isLoading}
              />
              {/* 字数统计 */}
              <div className="absolute bottom-3 right-3 text-xs text-slate-500">
                {researchIdea.length} / 5000
              </div>
            </div>
          </div>

          {/* 论文类型选择 */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              论文类型
            </label>
            <div className="grid grid-cols-2 gap-4">
              {PAPER_TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setPaperType(option.value)}
                  disabled={isLoading}
                  className={`
                    p-4 rounded-xl border transition-all text-left
                    ${paperType === option.value
                      ? 'bg-blue-500/20 border-blue-500/50 ring-2 ring-blue-500/30'
                      : 'bg-slate-900/30 border-slate-600/50 hover:bg-slate-900/50 hover:border-slate-500/50'
                    }
                    ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                  `}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{option.icon}</span>
                    <div>
                      <div className="font-medium text-white">{option.label}</div>
                      <div className="text-sm text-slate-400 mt-1">{option.description}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 关键词输入（可选） */}
          <div className="mb-8">
            <label className="block text-sm font-medium text-slate-300 mb-3">
              关键词 <span className="text-slate-500">(可选，用逗号分隔)</span>
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="深度学习, 注意力机制, 图像分类"
              className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
              disabled={isLoading}
            />
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* 启动按钮 */}
          <button
            onClick={handleStart}
            disabled={isLoading || !researchIdea.trim()}
            className={`
              w-full py-4 rounded-xl font-semibold text-lg transition-all
              ${isLoading || !researchIdea.trim()
                ? 'bg-slate-700/50 text-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:from-blue-600 hover:to-purple-600 shadow-lg shadow-blue-500/25'
              }
            `}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-3">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                正在启动...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                Start Discovery
              </span>
            )}
          </button>

          {/* 提示信息 */}
          <p className="text-center text-xs text-slate-500 mt-4">
            按 <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-slate-400">Ctrl</kbd> + <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-slate-400">Enter</kbd> 快速启动
          </p>
        </div>

        {/* 功能说明 */}
        <div className="mt-12 grid grid-cols-3 gap-6">
          {[
            {
              icon: '🔍',
              title: '智能文献调研',
              description: '自动检索、分析和综述相关文献',
            },
            {
              icon: '🤖',
              title: '多智能体协作',
              description: '专业分工，高效协同完成研究',
            },
            {
              icon: '📝',
              title: 'LaTeX 导出',
              description: '生成符合学术规范的论文手稿',
            },
          ].map((feature, index) => (
            <div
              key={index}
              className="text-center p-4 rounded-xl bg-slate-800/30 border border-slate-700/30"
            >
              <div className="text-3xl mb-2">{feature.icon}</div>
              <div className="font-medium text-white mb-1">{feature.title}</div>
              <div className="text-sm text-slate-400">{feature.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default LandingPage
