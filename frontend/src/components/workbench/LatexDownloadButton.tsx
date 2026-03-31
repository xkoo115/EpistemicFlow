/**
 * LaTeX 下载按钮组件
 *
 * 当工作流状态变为 COMPLETED 时，在主画布区渲染此按钮。
 * 点击后触发 LaTeX 源码下载。
 *
 * 使用示例：
 * <LatexDownloadButton sessionId={sessionId} workflowStatus={workflowStatus} />
 */

import React, { useState } from 'react'
import { WorkflowStatus } from '@/types/workflow'

/**
 * LatexDownloadButton 属性
 */
interface LatexDownloadButtonProps {
  sessionId: string
  workflowStatus: WorkflowStatus
  onDownloadComplete?: () => void
}

/**
 * LaTeX 导出响应
 */
interface LaTeXExportResponse {
  session_id: string
  filename: string
  content: string
  metadata: {
    char_count: number
    line_count: number
    section_count: number
    subsection_count: number
    equation_count: number
    figure_count: number
    table_count: number
    bibliography_count: number
  }
}

/**
 * LaTeX 下载按钮组件
 */
const LatexDownloadButton: React.FC<LatexDownloadButtonProps> = ({
  sessionId,
  workflowStatus,
  onDownloadComplete,
}) => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [metadata, setMetadata] = useState<LaTeXExportResponse['metadata'] | null>(null)

  /**
   * 处理下载
   */
  const handleDownload = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // 调用导出 API
      const response = await fetch(`/api/v1/workflows/${sessionId}/export/latex`)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '导出 LaTeX 失败')
      }

      const data: LaTeXExportResponse = await response.json()

      // 保存元数据
      setMetadata(data.metadata)

      // 创建 Blob 并触发下载
      const blob = new Blob([data.content], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = data.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      // 回调
      if (onDownloadComplete) {
        onDownloadComplete()
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败')
    } finally {
      setIsLoading(false)
    }
  }

  // 只有在 COMPLETED 状态下才显示
  if (workflowStatus !== WorkflowStatus.COMPLETED) {
    return null
  }

  return (
    <div className="bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border border-emerald-500/30 rounded-xl p-6">
      {/* 标题 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
          <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">论文手稿已生成</h3>
          <p className="text-sm text-slate-400">点击下载 LaTeX 源码</p>
        </div>
      </div>

      {/* 元数据统计 */}
      {metadata && (
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{metadata.section_count}</div>
            <div className="text-xs text-slate-400">章节</div>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{metadata.equation_count}</div>
            <div className="text-xs text-slate-400">公式</div>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{metadata.figure_count}</div>
            <div className="text-xs text-slate-400">图表</div>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{metadata.bibliography_count}</div>
            <div className="text-xs text-slate-400">引用</div>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* 下载按钮 */}
      <button
        onClick={handleDownload}
        disabled={isLoading}
        className={`
          w-full py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2
          ${isLoading
            ? 'bg-slate-700/50 text-slate-400 cursor-not-allowed'
            : 'bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-500/25'
          }
        `}
      >
        {isLoading ? (
          <>
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
            正在导出...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Download LaTeX Source
          </>
        )}
      </button>

      {/* 提示信息 */}
      <p className="text-center text-xs text-slate-500 mt-3">
        使用 pdflatex 或 xelatex 编译生成 PDF
      </p>
    </div>
  )
}

export default LatexDownloadButton
