import { NavLink, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import {
  Bot,
  Binary,
  Hash,
  Lock,
  Key,
  FileCode,
  Globe,
  KeyRound,
  FileText,
  Compass,
  Star,
  Bookmark,
  Shield,
  Radio,
  BookOpen,
  Network,
  X,
  Bug,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useToolStore } from '@/stores/toolStore'
import { useSidebarStore } from '@/stores/sidebarStore'

const navItems = [
  { name: 'AI 助手', path: '/', icon: Bot },
  {
    name: '知识库',
    children: [
      { name: 'AI 知识库', path: '/knowledge', icon: BookOpen },
      { name: '笔记', path: '/knowledge/notes', icon: FileText },
      { name: '网址收藏', path: '/knowledge/bookmarks', icon: Bookmark },
      { name: '资源导航', path: '/knowledge/navigation', icon: Compass },
    ],
  },
  {
    name: '安全工具',
    children: [
      { name: '编码/解码', path: '/tools/encoding', icon: Binary },
      { name: '哈希计算', path: '/tools/hash', icon: Hash },
      { name: '加密/解密', path: '/tools/crypto', icon: Lock },
      { name: 'JWT 工具', path: '/tools/jwt', icon: Key },
      { name: '格式处理', path: '/tools/format', icon: FileCode },
      { name: '网络工具', path: '/tools/network', icon: Globe },
      { name: '密码工具', path: '/tools/password', icon: KeyRound },
      { name: 'WAF 绕过', path: '/tools/bypass', icon: Shield },
      { name: 'OOB 探测', path: '/tools/callback', icon: Radio },
      { name: '域名代理', path: '/tools/proxy', icon: Network },
      { name: '资源测试', path: '/tools/crawler', icon: Bug },
    ],
  },
]

export default function Sidebar() {
  const { favorites } = useToolStore()
  const { isOpen, isMobile, close, setIsMobile } = useSidebarStore()
  const location = useLocation()
  
  // 监听窗口大小变化
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 1024 // lg breakpoint
      setIsMobile(mobile)
    }
    
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [setIsMobile])
  
  // 移动端路由切换时关闭侧边栏
  useEffect(() => {
    if (isMobile) {
      close()
    }
  }, [location.pathname, isMobile, close])
  
  return (
    <>
      {/* 移动端遮罩层 */}
      {isMobile && isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={close}
        />
      )}
      
      <aside className={cn(
        "fixed left-0 top-0 h-full w-64 bg-theme-card border-r border-theme-border flex flex-col z-50",
        "transition-transform duration-300 ease-in-out",
        // 移动端: 根据 isOpen 状态控制显示
        isMobile && !isOpen && "-translate-x-full",
        // 桌面端: 始终显示
        !isMobile && "translate-x-0"
      )}>
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-theme-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-theme-primary to-theme-secondary flex items-center justify-center">
              <Lock className="w-4 h-4 text-theme-bg" />
            </div>
            <span className="text-lg font-bold text-theme-primary">SecToolkit</span>
          </div>
          {/* 移动端关闭按钮 */}
          {isMobile && (
            <button 
              onClick={close}
              className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-text transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
        
        {/* 导航 */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {/* 收藏的工具 */}
          {favorites.length > 0 && (
            <div className="px-4 mb-4">
              <div className="flex items-center gap-2 px-2 py-1 text-xs text-theme-muted uppercase tracking-wider">
                <Star className="w-3 h-3" />
                收藏
              </div>
              <div className="mt-2 space-y-1">
                {favorites.map((toolKey) => (
                  <NavLink
                    key={toolKey}
                    to={`/tools/${toolKey}`}
                    className={({ isActive }) =>
                      cn('nav-item text-sm', isActive && 'active')
                    }
                  >
                    {toolKey}
                  </NavLink>
                ))}
              </div>
            </div>
          )}
          
          {/* 主导航 */}
          <div className="space-y-1">
            {navItems.map((item) => {
              if ('children' in item && item.children) {
                return (
                  <div key={item.name} className="px-4">
                    <div className="px-2 py-2 text-xs text-theme-muted uppercase tracking-wider">
                      {item.name}
                    </div>
                    <div className="space-y-1">
                      {item.children.map((child) => (
                        <NavLink
                          key={child.path}
                          to={child.path}
                          className={({ isActive }) =>
                            cn('nav-item', isActive && 'active')
                          }
                        >
                          <child.icon className="w-4 h-4" />
                          <span>{child.name}</span>
                        </NavLink>
                      ))}
                    </div>
                  </div>
                )
              }
              
              return (
                <div key={item.path} className="px-4">
                  <NavLink
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) =>
                      cn('nav-item', isActive && 'active')
                    }
                  >
                    <item.icon className="w-4 h-4" />
                    <span>{item.name}</span>
                  </NavLink>
                </div>
              )
            })}
          </div>
        </nav>
      
        {/* 底部信息 */}
        <div className="p-4 border-t border-theme-border">
          <div className="text-xs text-theme-muted text-center">
            Security Toolkit v1.0
          </div>
        </div>
      </aside>
    </>
  )
}

