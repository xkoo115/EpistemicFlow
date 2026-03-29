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

import React from 'react'
import { cn } from '@/lib/utils'
import { FileText, Layers, Sparkles } from 'lucide-react'

/**
 * MainCanvas 组件
 * 中间主工作区 - 主工作画布
 */
export const MainCanvas: React.FC = () => {
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

      {/* 主内容区域 - 占位 */}
      <div className="flex-1 flex flex-col items-center justify-center text-center">
        {/* 装饰性图标 */}
        <div className="mb-6 relative">
          <div className="absolute inset-0 bg-accent-cyan-500/20 blur-3xl rounded-full" />
          <div className="relative p-6 rounded-2xl bg-dark-bg-tertiary border border-dark-border">
            <Sparkles className="w-12 h-12 text-accent-cyan-500" />
          </div>
        </div>

        {/* 标题和描述 */}
        <h3 className="text-xl font-semibold text-gray-100 mb-2">
          EpistemicFlow 工作台
        </h3>
        <p className="text-sm text-gray-400 mb-6 max-w-md">
          AI 驱动的自动化科研平台
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
      </div>
    </div>
  )
}

export default MainCanvas
