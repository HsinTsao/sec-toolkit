/**
 * 长期记忆状态管理
 */
import { create } from 'zustand'

// 从 auth-storage 获取 token 的辅助函数
function getAuthToken(): string | null {
  try {
    const authStorage = localStorage.getItem('auth-storage')
    if (authStorage) {
      const parsed = JSON.parse(authStorage)
      return parsed?.state?.token || null
    }
  } catch {
    // ignore parse error
  }
  return null
}

export interface Memory {
  id: string
  content: string
  category: string
  source: string | null
  importance: number
  created_at: string
  last_accessed_at: string
}

export interface MemoryStats {
  total: number
  by_category: Record<string, number>
}

interface MemoryState {
  memories: Memory[]
  stats: MemoryStats | null
  loading: boolean
  error: string | null
  
  // Actions
  loadMemories: (category?: string, search?: string) => Promise<void>
  loadStats: () => Promise<void>
  deleteMemory: (id: string) => Promise<void>
  clearMemories: (category?: string) => Promise<void>
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  stats: null,
  loading: false,
  error: null,
  
  loadMemories: async (category?: string, search?: string) => {
    set({ loading: true, error: null })
    try {
      const params = new URLSearchParams()
      if (category) params.append('category', category)
      if (search) params.append('search', search)
      params.append('limit', '100')
      
      const token = getAuthToken()
      const response = await fetch(`/api/memories?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (!response.ok) throw new Error('加载失败')
      
      const data = await response.json()
      set({ memories: data.memories, loading: false })
    } catch (error) {
      set({ error: (error as Error).message, loading: false })
    }
  },
  
  loadStats: async () => {
    try {
      const token = getAuthToken()
      const response = await fetch('/api/memories/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (!response.ok) throw new Error('加载统计失败')
      
      const data = await response.json()
      set({ stats: data })
    } catch (error) {
      console.error('Load memory stats error:', error)
    }
  },
  
  deleteMemory: async (id: string) => {
    const token = getAuthToken()
    const response = await fetch(`/api/memories/${id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    
    if (!response.ok) throw new Error('删除失败')
    
    // 更新本地状态
    set(state => ({
      memories: state.memories.filter(m => m.id !== id),
    }))
    
    // 刷新统计
    get().loadStats()
  },
  
  clearMemories: async (category?: string) => {
    const token = getAuthToken()
    const params = category ? `?category=${category}` : ''
    
    const response = await fetch(`/api/memories${params}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    
    if (!response.ok) throw new Error('清空失败')
    
    // 刷新列表和统计
    get().loadMemories()
    get().loadStats()
  },
}))

// 分类配置
export const MEMORY_CATEGORIES = [
  { id: 'all', name: '全部', icon: '📋' },
  { id: 'preference', name: '偏好', icon: '❤️' },
  { id: 'fact', name: '事实', icon: '📌' },
  { id: 'instruction', name: '指令', icon: '📝' },
  { id: 'general', name: '通用', icon: '💭' },
]
