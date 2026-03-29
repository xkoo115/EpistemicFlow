/**
 * AgentRoster 组件测试
 * 测试目标:确保智能体拓扑树组件能够正确挂载和渲染
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AgentRoster from '@/components/workbench/AgentRoster'

describe('AgentRoster', () => {
  it('应该正确挂载并渲染组件', () => {
    render(<AgentRoster />)

    // 验证组件容器存在
    const component = screen.getByText('智能体拓扑').parentElement?.parentElement
    expect(component).toBeInTheDocument()
  })

  it('应该显示面板标题', () => {
    render(<AgentRoster />)

    // 验证标题文本存在
    expect(screen.getByText('智能体拓扑')).toBeInTheDocument()
  })

  it('应该显示占位提示文本', () => {
    render(<AgentRoster />)

    // 验证占位提示
    expect(screen.getByText('智能体拓扑树')).toBeInTheDocument()
    expect(screen.getByText('展示多智能体结构和状态')).toBeInTheDocument()
  })

  it('应该显示所有状态指示器', () => {
    render(<AgentRoster />)

    // 验证四种状态都存在
    expect(screen.getByText('计算中')).toBeInTheDocument()
    expect(screen.getByText('HITL 挂起')).toBeInTheDocument()
    expect(screen.getByText('沙箱报错')).toBeInTheDocument()
    expect(screen.getByText('节点通过')).toBeInTheDocument()
  })

  it('应该应用正确的容器样式', () => {
    const { container } = render(<AgentRoster />)

    // 验证容器应用了 flex 布局
    const rootDiv = container.firstChild as HTMLElement
    expect(rootDiv).toHaveClass('h-full')
    expect(rootDiv).toHaveClass('flex')
    expect(rootDiv).toHaveClass('flex-col')
  })
})
