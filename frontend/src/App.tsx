/**
 * EpistemicFlow 主应用入口
 * 集成三栏式工作台布局
 */

import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AgentRoster from '@/components/workbench/AgentRoster'
import MainCanvas from '@/components/workbench/MainCanvas'
import ActivityLog from '@/components/workbench/ActivityLog'

function App() {
  return (
    <WorkbenchLayout
      leftSidebar={<AgentRoster />}
      mainCanvas={<MainCanvas />}
      rightSidebar={<ActivityLog />}
    />
  )
}

export default App
