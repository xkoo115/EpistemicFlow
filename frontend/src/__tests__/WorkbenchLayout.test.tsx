/**
 * WorkbenchLayout 组件测试
 * 测试目标:确保三栏式布局能够正确挂载和渲染
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import WorkbenchLayout from '@/layouts/WorkbenchLayout'

describe('WorkbenchLayout', () => {
  it('应该正确挂载并渲染布局容器', () => {
    render(<WorkbenchLayout />)

    // 验证布局容器存在
    const layout = screen.getByRole('main').parentElement
    expect(layout).toBeInTheDocument()
  })

  it('应该渲染三个栏位(左、中、右)', () => {
    render(<WorkbenchLayout />)

    // 验证主工作区存在
    const mainCanvas = screen.getByRole('main')
    expect(mainCanvas).toBeInTheDocument()

    // 验证左右两个侧栏存在
    const sidebars = screen.getAllByRole('complementary')
    expect(sidebars).toHaveLength(2) // 左右两个 aside
  })

  it('应该正确渲染传入的子组件', () => {
    render(
      <WorkbenchLayout
        leftSidebar={<div data-testid="left-content">左侧内容</div>}
        mainCanvas={<div data-testid="main-content">主内容</div>}
        rightSidebar={<div data-testid="right-content">右侧内容</div>}
      />
    )

    // 验证子组件都被渲染
    expect(screen.getByTestId('left-content')).toBeInTheDocument()
    expect(screen.getByTestId('main-content')).toBeInTheDocument()
    expect(screen.getByTestId('right-content')).toBeInTheDocument()
  })

  it('应该应用正确的暗黑主题背景色', () => {
    const { container } = render(<WorkbenchLayout />)

    // 验证根容器应用了暗黑背景色类
    const layout = container.firstChild as HTMLElement
    expect(layout).toHaveClass('bg-dark-bg-primary')
  })

  it('应该应用全屏固定布局样式', () => {
    const { container } = render(<WorkbenchLayout />)

    const layout = container.firstChild as HTMLElement
    // 验证全屏和禁止滚动
    expect(layout).toHaveClass('w-full')
    expect(layout).toHaveClass('h-screen')
    expect(layout).toHaveClass('overflow-hidden')
  })
})
