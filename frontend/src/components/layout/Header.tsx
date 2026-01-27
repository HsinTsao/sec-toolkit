import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, LogOut, Settings, Command, Menu } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useSidebarStore } from '@/stores/sidebarStore'
import CommandPalette from './CommandPalette'

export default function Header() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { isMobile, toggle } = useSidebarStore()
  const [showCommandPalette, setShowCommandPalette] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  
  const handleLogout = () => {
    logout()
    navigate('/login')
  }
  
  return (
    <>
      <header className="h-14 lg:h-16 bg-theme-card border-b border-theme-border flex items-center justify-between px-4 lg:px-6 transition-colors">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* 移动端汉堡菜单 */}
          {isMobile && (
            <button
              onClick={toggle}
              className="p-2 -ml-2 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-text transition-colors flex-shrink-0"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          
          {/* 搜索栏 - 响应式宽度 */}
          <button
            onClick={() => setShowCommandPalette(true)}
            className="flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2 bg-theme-bg border border-theme-border rounded-lg text-theme-muted hover:border-theme-primary transition-colors flex-1 max-w-[400px] min-w-0"
          >
            <Search className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1 text-left text-sm truncate">搜索工具...</span>
            <kbd className="hidden md:flex items-center gap-1 px-2 py-0.5 text-xs bg-theme-card rounded border border-theme-border flex-shrink-0">
              <Command className="w-3 h-3" />
              <span>K</span>
            </kbd>
          </button>
        </div>
        
        {/* 用户菜单 */}
        <div className="relative flex-shrink-0 ml-2">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 lg:gap-3 px-2 lg:px-3 py-2 rounded-lg hover:bg-theme-bg transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-theme-primary/20 flex items-center justify-center">
              {user?.avatar ? (
                <img src={user.avatar} alt="" className="w-8 h-8 rounded-full" />
              ) : (
                <User className="w-4 h-4 text-theme-primary" />
              )}
            </div>
            <span className="hidden sm:block text-sm font-medium text-theme-text">{user?.username}</span>
          </button>
          
          {/* 下拉菜单 */}
          {showUserMenu && (
            <div className="absolute right-0 top-full mt-2 w-48 bg-theme-card border border-theme-border rounded-lg shadow-xl z-50">
              <div className="p-2">
                <button
                  onClick={() => {
                    setShowUserMenu(false)
                    // TODO: 打开设置
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-theme-bg text-sm text-theme-text"
                >
                  <Settings className="w-4 h-4" />
                  设置
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-theme-bg text-sm text-theme-danger"
                >
                  <LogOut className="w-4 h-4" />
                  退出登录
                </button>
              </div>
            </div>
          )}
        </div>
      </header>
      
      {/* 命令面板 */}
      <CommandPalette
        isOpen={showCommandPalette}
        onClose={() => setShowCommandPalette(false)}
      />
    </>
  )
}
