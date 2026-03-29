/**
 * WorkbenchLayout - EpistemicFlow 核心工作台布局
 *
 * 设计理念:
 * - 类似 VS Code 的三栏式布局,打造"玻璃盒"级别的透明度
 * - 全屏固定布局,不可随意滚动,确保工作区域稳定
 * - 响应式设计,支持不同屏幕尺寸
 *
 * 布局策略:
 * - 采用 Flexbox 而非 CSS Grid
 * - 原因: Flexbox 在处理动态宽度调整和拖拽调整时更灵活
 * - 左右栏固定宽度百分比,中栏自适应填充剩余空间
 * - 未来可扩展为可拖拽调整宽度的可变布局
 */

import React from 'react'
import { cn } from '@/lib/utils'

interface WorkbenchLayoutProps {
  /** 左侧栏 - 智能体拓扑树 */
  leftSidebar?: React.ReactNode
  /** 中间主工作区 - 主工作画布 */
  mainCanvas?: React.ReactNode
  /** 右侧栏 - 实时活动日志 */
  rightSidebar?: React.ReactNode
  /** 自定义类名 */
  className?: string
}

/**
 * WorkbenchLayout 组件
 * 实现三栏式全屏布局,类似高级 IDE 的工作台界面
 */
export const WorkbenchLayout: React.FC<WorkbenchLayoutProps> = ({
  leftSidebar,
  mainCanvas,
  rightSidebar,
  className,
}) => {
  return (
    <div
      className={cn(
        // 全屏容器 - 固定尺寸,禁止滚动
        'w-full h-screen overflow-hidden',
        // 深邃暗黑背景
        'bg-dark-bg-primary',
        // Flexbox 水平布局
        'flex flex-row',
        className
      )}
    >
      {/* 左栏 - 智能体拓扑树 (Agent Roster) */}
      {/* 占宽约 20%,最小宽度 240px,最大宽度 320px */}
      <aside
        className={cn(
          'w-[20%] min-w-[240px] max-w-[320px]',
          'h-full overflow-hidden',
          // 玻璃态效果
          'glass-panel border-r border-dark-border',
          // 内边距
          'p-4'
        )}
      >
        {leftSidebar}
      </aside>

      {/* 中栏 - 主工作画布 (Main Canvas) */}
      {/* 占宽约 60%,自适应填充剩余空间 */}
      <main
        className={cn(
          'flex-1', // 自动填充剩余宽度
          'h-full overflow-hidden',
          // 深色背景,略浅于主背景
          'bg-dark-bg-secondary',
          // 内边距
          'p-6'
        )}
      >
        {mainCanvas}
      </main>

      {/* 右栏 - 实时活动日志 (Activity Log) */}
      {/* 占宽约 20%,最小宽度 280px,最大宽度 400px */}
      <aside
        className={cn(
          'w-[20%] min-w-[280px] max-w-[400px]',
          'h-full overflow-hidden',
          // 玻璃态效果
          'glass-panel border-l border-dark-border',
          // 内边距
          'p-4'
        )}
      >
        {rightSidebar}
      </aside>
    </div>
  )
}

export default WorkbenchLayout
