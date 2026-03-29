/**
 * ActivityLog 组件测试
 * 测试目标:确保实时活动日志组件能够正确挂载和渲染
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ActivityLog from '@/components/workbench/ActivityLog'

describe('ActivityLog', () => {
  it('应该正确挂载并渲染组件', () => {
    render(<ActivityLog />)

    // 验证组件容器存在
    const component = screen.getByText('活动日志').parentElement?.parentElement
    expect(component).toBeInTheDocument()
  })

  it('应该显示面板标题', () => {
    render(<ActivityLog />)

    // 验证标题文本存在
    expect(screen.getByText('活动日志')).toBeInTheDocument()
  })

  it('应该显示示例日志条目', () => {
    render(<ActivityLog />)

    // 验证一些关键日志条目
    expect(screen.getByText('系统初始化完成')).toBeInTheDocument()
    expect(screen.getByText('连接到后端服务...')).toBeInTheDocument()
    expect(screen.getByText('WebSocket 连接已建立')).toBeInTheDocument()
  })

  it('应该显示日志级别标签', () => {
    render(<ActivityLog />)

    // 验证不同级别的日志标签(使用 getAllBy 处理多个匹配)
    const infoTags = screen.getAllByText('[INFO]')
    expect(infoTags.length).toBeGreaterThan(0)

    // 其他级别的日志标签也可能有多个匹配，使用 getAllBy
    const successTags = screen.getAllByText('[SUCCESS]')
    const warnTags = screen.getAllByText('[WARN]')
    const debugTags = screen.getAllByText('[DEBUG]')

    expect(successTags.length).toBeGreaterThan(0)
    expect(warnTags.length).toBeGreaterThan(0)
    expect(debugTags.length).toBeGreaterThan(0)
  })

  it('应该显示实时连接状态', () => {
    render(<ActivityLog />)

    // 验证底部状态栏
    expect(screen.getByText('实时连接')).toBeInTheDocument()
    expect(screen.getByText(/条日志/)).toBeInTheDocument()
  })

  it('应该应用正确的容器样式', () => {
    const { container } = render(<ActivityLog />)

    // 验证容器应用了 flex 布局
    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv).toHaveClass('h-full')
    expect(rootDiv).toHaveClass('flex')
    expect(rootDiv).toHaveClass('flex-col')
  })
})
