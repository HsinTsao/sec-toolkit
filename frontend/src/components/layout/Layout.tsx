import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import StatusBar from './StatusBar'
import { useSidebarStore } from '@/stores/sidebarStore'

export default function Layout() {
  const { isMobile } = useSidebarStore()
  
  return (
    <div className="min-h-screen bg-theme-bg flex">
      {/* 侧边栏 */}
      <Sidebar />
      
      {/* 主内容区 - 移动端无边距，桌面端有侧边栏宽度的边距 */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${isMobile ? 'ml-0' : 'ml-64'}`}>
        <Header />
        {/* 添加底部 padding 为状态栏留出空间 */}
        <main className="flex-1 p-4 lg:p-6 pb-12 overflow-auto">
          <Outlet />
        </main>
      </div>
      
      {/* IDE 风格状态栏 */}
      <StatusBar />
    </div>
  )
}
