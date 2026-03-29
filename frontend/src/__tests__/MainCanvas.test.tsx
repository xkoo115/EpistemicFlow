/**
 * MainCanvas 组件测试
 * 测试目标:确保主工作画布组件能够正确挂载和渲染
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MainCanvas from '@/components/workbench/MainCanvas'

describe('MainCanvas', () => {
  it('应该正确挂载并渲染组件', () => {
    render(<MainCanvas />)

    // 验证组件容器存在
    const component = screen.getByText('工作画布').parentElement?.parentElement
    expect(component).toBeInTheDocument()
  })

  it('应该显示标题和描述', () => {
    render(<MainCanvas />)

    // 验证标题
    expect(screen.getByText('工作画布')).toBeInTheDocument()
    expect(screen.getByText('EpistemicFlow 工作台')).toBeInTheDocument()

    // 验证描述文本
    expect(screen.getByText(/AI 驱动的自动化科研平台/)).toBeInTheDocument()
  })

  it('应该显示视图模式切换按钮', () => {
    render(<MainCanvas />)

    // 验证三个视图模式按钮
    expect(screen.getByRole('button', { name: '预览' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '编辑' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '对比' })).toBeInTheDocument()
  })

  it('应该显示功能卡片', () => {
    render(<MainCanvas />)

    // 验证三个功能卡片
    expect(screen.getByText('Markdown 预览')).toBeInTheDocument()
    expect(screen.getByText('图表可视化')).toBeInTheDocument()
    expect(screen.getByText('差异对比')).toBeInTheDocument()
  })

  it('应该应用正确的容器样式', () => {
    const { container } = render(<MainCanvas />)

    // 验证容器应用了 flex 布局
    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv).toHaveClass('h-full')
    expect(rootDiv).toHaveClass('flex')
    expect(rootDiv).toHaveClass('flex-col')
  })
})
