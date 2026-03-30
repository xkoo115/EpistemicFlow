/**
 * RollbackModal - Saga 回滚模态框组件
 * 
 * 功能说明:
 * - 当用户点击 Saga 树中的历史节点时弹出
 * - 允许用户输入纠偏指令
 * - 提交回滚请求到后端
 * 
 * 交互流程:
 * 1. 用户点击历史节点 -> 模态框打开,显示节点信息
 * 2. 用户输入纠偏指令 -> 验证输入
 * 3. 用户点击提交 -> 调用后端 API 进行回滚
 * 4. 回滚成功 -> 模态框关闭,刷新 Saga 树
 */

import React, { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { X, Clock, AlertCircle, CheckCircle2 } from 'lucide-react'
import { SagaCheckpoint } from '@/types/saga'

/**
 * RollbackModal 组件属性接口
 */
interface RollbackModalProps {
  isOpen: boolean                      // 模态框是否打开
  checkpoint: SagaCheckpoint           // 选中的检查点
  onClose: () => void                  // 关闭模态框回调
  onSubmit: (checkpointId: string, humanInstruction: string) => Promise<void>  // 提交回调
}

/**
 * RollbackModal 组件
 */
export const RollbackModal: React.FC<RollbackModalProps> = ({
  isOpen,
  checkpoint,
  onClose,
  onSubmit,
}) => {
  // 状态管理
  const [humanInstruction, setHumanInstruction] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 重置状态
  useEffect(() => {
    if (isOpen) {
      setHumanInstruction('')
      setIsSubmitting(false)
      setError(null)
    }
  }, [isOpen])

  /**
   * 处理提交
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // 验证输入
    if (!humanInstruction.trim()) {
      setError('请输入纠偏指令')
      return
    }

    if (humanInstruction.length < 10) {
      setError('纠偏指令至少需要 10 个字符')
      return
    }

    // 提交回滚请求
    setIsSubmitting(true)
    setError(null)

    try {
      await onSubmit(checkpoint.checkpoint_id, humanInstruction)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败,请重试')
      setIsSubmitting(false)
    }
  }

  /**
   * 处理键盘事件(ESC 关闭)
   */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && !isSubmitting) {
      onClose()
    }
  }

  // 如果模态框未打开,不渲染
  if (!isOpen) return null

  return (
    <>
      {/* 背景遮罩 */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 模态框主体 */}
      <div
        className={cn(
          'fixed z-50 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2',
          'w-full max-w-lg',
          'bg-dark-bg-secondary border border-dark-border rounded-lg shadow-2xl',
          'animate-in fade-in zoom-in-95 duration-200'
        )}
        onKeyDown={handleKeyDown}
        data-testid="rollback-modal"
      >
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-accent-amber-500" />
            <h2 className="text-lg font-semibold text-gray-100">
              Saga 时间旅行回滚
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className={cn(
              'p-1 rounded-lg transition-colors',
              'hover:bg-dark-bg-tertiary',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* 内容 */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* 检查点信息 */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              目标检查点
            </label>
            <div className="p-3 rounded-lg bg-dark-bg-tertiary border border-dark-border-light">
              <div className="flex items-center gap-2 mb-2">
                {checkpoint.status === 'completed' ? (
                  <CheckCircle2 className="w-4 h-4 text-accent-green-500" />
                ) : (
                  <Clock className="w-4 h-4 text-accent-amber-500" />
                )}
                <span className="text-sm font-medium text-gray-200">
                  {checkpoint.stage_name}
                </span>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>检查点 ID: {checkpoint.checkpoint_id}</div>
                <div>创建时间: {checkpoint.timestamp}</div>
                <div>状态: {checkpoint.status}</div>
                {checkpoint.is_fork && (
                  <div className="text-accent-amber-500">分叉节点</div>
                )}
              </div>
            </div>
          </div>

          {/* 纠偏指令输入 */}
          <div className="space-y-2">
            <label
              htmlFor="human-instruction"
              className="block text-sm font-medium text-gray-300"
            >
              纠偏指令 <span className="text-accent-red-500">*</span>
            </label>
            <textarea
              id="human-instruction"
              value={humanInstruction}
              onChange={(e) => {
                setHumanInstruction(e.target.value)
                setError(null)
              }}
              disabled={isSubmitting}
              placeholder="请输入您的纠偏指令,例如:增加针对某药物浓度的对照组..."
              rows={4}
              className={cn(
                'w-full px-3 py-2 rounded-lg',
                'bg-dark-bg-tertiary border border-dark-border-light',
                'text-gray-200 placeholder-gray-500',
                'focus:outline-none focus:ring-2 focus:ring-accent-cyan-500/50',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'resize-none',
                error && 'border-accent-red-500'
              )}
            />
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">
                {humanInstruction.length} / 500 字符
              </span>
              {error && (
                <span className="text-accent-red-500 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {error}
                </span>
              )}
            </div>
          </div>

          {/* 提示信息 */}
          <div className="p-3 rounded-lg bg-dark-bg-primary border border-dark-border">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-accent-amber-500 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-gray-400">
                <p className="font-medium mb-1">回滚说明:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  <li>回滚将创建新的分支,不会覆盖现有状态</li>
                  <li>纠偏指令将指导 AI 从该检查点重新执行</li>
                  <li>请确保指令清晰、具体、可执行</li>
                </ul>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className={cn(
                'px-4 py-2 rounded-lg',
                'bg-dark-bg-tertiary border border-dark-border-light',
                'text-gray-300 hover:text-gray-100',
                'hover:bg-dark-bg-surface',
                'transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !humanInstruction.trim()}
              className={cn(
                'px-4 py-2 rounded-lg',
                'bg-accent-cyan-600 hover:bg-accent-cyan-500',
                'text-white font-medium',
                'transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center gap-2'
              )}
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  提交中...
                </>
              ) : (
                <>
                  <Clock className="w-4 h-4" />
                  执行回滚
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </>
  )
}

export default RollbackModal
