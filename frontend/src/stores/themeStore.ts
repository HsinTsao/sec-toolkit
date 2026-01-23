import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

// 应用主题到 DOM
const applyTheme = (theme: Theme) => {
  const root = document.documentElement
  
  if (theme === 'dark') {
    root.classList.add('dark')
    root.classList.remove('light')
  } else {
    root.classList.add('light')
    root.classList.remove('dark')
  }
}

// 获取系统偏好的主题
const getSystemTheme = (): Theme => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'dark'
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'dark', // 默认暗色主题
      
      setTheme: (theme: Theme) => {
        applyTheme(theme)
        set({ theme })
      },
      
      toggleTheme: () => {
        const currentTheme = get().theme
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark'
        applyTheme(newTheme)
        set({ theme: newTheme })
      },
    }),
    {
      name: 'theme-storage',
      onRehydrateStorage: () => (state) => {
        // 当 store 从存储中恢复时，应用保存的主题
        if (state) {
          applyTheme(state.theme)
        }
      },
    }
  )
)

// 初始化主题（在应用启动时调用）
export const initTheme = () => {
  const stored = localStorage.getItem('theme-storage')
  if (stored) {
    try {
      const { state } = JSON.parse(stored)
      if (state?.theme) {
        applyTheme(state.theme)
        return
      }
    } catch {
      // 忽略解析错误
    }
  }
  // 如果没有存储的主题，使用系统偏好或默认暗色
  applyTheme(getSystemTheme())
}

