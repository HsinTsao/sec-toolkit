import { Sun, Moon, Wifi, Clock } from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import { useState, useEffect } from 'react'

export default function StatusBar() {
  const { theme, toggleTheme } = useThemeStore()
  const [currentTime, setCurrentTime] = useState(new Date())
  const [isOnline, setIsOnline] = useState(navigator.onLine)

  // 更新时间
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // 监听网络状态
  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)
    
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const handleThemeToggle = () => {
    document.documentElement.classList.add('transitioning')
    toggleTheme()
    setTimeout(() => {
      document.documentElement.classList.remove('transitioning')
    }, 300)
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <footer className="status-bar">
      {/* 左侧信息 */}
      <div className="flex items-center gap-1">
        {/* 网络状态 */}
        <div className={`status-bar-item ${isOnline ? 'text-theme-success' : 'text-theme-danger'}`}>
          <Wifi className="w-3.5 h-3.5" />
          <span>{isOnline ? '在线' : '离线'}</span>
        </div>
      </div>

      {/* 右侧信息 */}
      <div className="flex items-center gap-1">
        {/* 时间 */}
        <div className="status-bar-item">
          <Clock className="w-3.5 h-3.5" />
          <span className="font-mono">{formatTime(currentTime)}</span>
        </div>
        
        <div className="status-bar-divider" />
        
        {/* 主题切换 */}
        <button
          onClick={handleThemeToggle}
          className="status-bar-item status-bar-button"
          title={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
        >
          {theme === 'dark' ? (
            <>
              <Moon className="w-3.5 h-3.5" />
              <span>暗色</span>
            </>
          ) : (
            <>
              <Sun className="w-3.5 h-3.5" />
              <span>亮色</span>
            </>
          )}
        </button>
      </div>
    </footer>
  )
}
