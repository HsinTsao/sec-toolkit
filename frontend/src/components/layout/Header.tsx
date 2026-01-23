import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, LogOut, Settings, Command } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import CommandPalette from './CommandPalette'

export default function Header() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const [showCommandPalette, setShowCommandPalette] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  
  const handleLogout = () => {
    logout()
    navigate('/login')
  }
  
  return (
    <>
      <header className="h-16 bg-theme-card border-b border-theme-border flex items-center justify-between px-6 transition-colors">
        {/* 搜索栏 */}
        <button
          onClick={() => setShowCommandPalette(true)}
          className="flex items-center gap-3 px-4 py-2 bg-theme-bg border border-theme-border rounded-lg text-theme-muted hover:border-theme-primary transition-colors w-96"
        >
          <Search className="w-4 h-4" />
          <span className="flex-1 text-left text-sm">搜索工具...</span>
          <kbd className="hidden sm:flex items-center gap-1 px-2 py-0.5 text-xs bg-theme-card rounded border border-theme-border">
            <Command className="w-3 h-3" />
            <span>K</span>
          </kbd>
        </button>
        
        {/* 用户菜单 */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-theme-bg transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-theme-primary/20 flex items-center justify-center">
              {user?.avatar ? (
                <img src={user.avatar} alt="" className="w-8 h-8 rounded-full" />
              ) : (
                <User className="w-4 h-4 text-theme-primary" />
              )}
            </div>
            <span className="text-sm font-medium text-theme-text">{user?.username}</span>
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
