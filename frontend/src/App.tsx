/**
 * EpistemicFlow 主应用入口
 * 
 * 路由配置：
 * - /: LandingPage（启动页）
 * - /workbench/:sessionId: WorkbenchLayout（工作台）
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from '@/components/landing/LandingPage'
import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AgentSidebar from '@/components/workbench/AgentSidebar'
import MainCanvas from '@/components/workbench/MainCanvas'
import TerminalLog from '@/components/workbench/TerminalLog'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 启动页 */}
        <Route path="/" element={<LandingPage />} />
        
        {/* 工作台（带 sessionId 参数） */}
        <Route
          path="/workbench/:sessionId"
          element={
            <WorkbenchLayout
              leftSidebar={<AgentSidebar />}
              mainCanvas={<MainCanvas />}
              rightSidebar={<TerminalLog />}
            />
          }
        />
        
        {/* 兼容旧路由：重定向到启动页 */}
        <Route path="/workbench" element={<Navigate to="/" replace />} />
        
        {/* 404：重定向到启动页 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
