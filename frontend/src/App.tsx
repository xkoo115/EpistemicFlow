/**
 * EpistemicFlow 主应用入口
 * 集成三栏式工作台布局
 */

import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AgentRoster from '@/components/workbench/AgentRoster'
import MainCanvas from '@/components/workbench/MainCanvas'
import ActivityLog from '@/components/workbench/ActivityLog'
import WorkflowCanvasDemo from '@/examples/WorkflowCanvasDemo'

function App() {
  // 切换到演示模式
  const DEMO_MODE = true

  if (DEMO_MODE) {
    return <WorkflowCanvasDemo />
  }

  return (
    <WorkbenchLayout
      leftSidebar={<AgentRoster />}
      mainCanvas={<MainCanvas />}
      rightSidebar={<ActivityLog />}
    />
  )
}

export default App
