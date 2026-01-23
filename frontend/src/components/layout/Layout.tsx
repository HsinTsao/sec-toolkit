import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import StatusBar from './StatusBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-theme-bg flex">
      {/* 侧边栏 */}
      <Sidebar />
      
      {/* 主内容区 */}
      <div className="flex-1 flex flex-col ml-64">
        <Header />
        {/* 添加底部 padding 为状态栏留出空间 */}
        <main className="flex-1 p-6 pb-12 overflow-auto">
          <Outlet />
        </main>
      </div>
      
      {/* IDE 风格状态栏 */}
      <StatusBar />
    </div>
  )
}
