/**
 * EpistemicFlow 主应用入口
 * 集成三栏式工作台布局
 */

import React from 'react'
import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AgentSidebar from '@/components/workbench/AgentSidebar'
import MainCanvas from '@/components/workbench/MainCanvas'
import TerminalLog from '@/components/workbench/TerminalLog'

function App() {
  // 生产模式：显示完整的三栏式工作台界面
  return (
    <WorkbenchLayout
      leftSidebar={<AgentSidebar />}
      mainCanvas={<MainCanvas />}
      rightSidebar={<TerminalLog />}
    />
  )
}

export default App
