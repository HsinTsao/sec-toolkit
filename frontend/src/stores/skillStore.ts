import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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

// Skill 列表项
export interface SkillListItem {
  id: string
  name: string
  description: string
  icon: string
  category: string
  is_builtin: boolean
  enabled: boolean
  tools_count: number
}

// Skill 完整信息
export interface Skill extends SkillListItem {
  system_prompt: string
  tools: string[]
  welcome_message: string
  example_prompts: string[]
  max_tool_calls: number
  created_at?: string
  updated_at?: string
}

// Skill 列表响应
export interface SkillListResponse {
  builtin: SkillListItem[]
  custom: SkillListItem[]
}

interface SkillState {
  // Skill 列表
  builtinSkills: SkillListItem[]
  customSkills: SkillListItem[]
  loading: boolean
  error: string | null
  
  // 当前激活的 Skills（支持多个）
  activeSkillIds: string[]
  activeSkills: Skill[]
  
  // 加载 Skill 列表
  loadSkills: () => Promise<void>
  
  // 获取 Skill 详情
  getSkillDetail: (skillId: string) => Promise<Skill | null>
  
  // 切换 Skill 激活状态
  toggleSkill: (skillId: string) => Promise<void>
  
  // 检查 Skill 是否激活
  isSkillActive: (skillId: string) => boolean
  
  // 清除所有激活
  clearActiveSkills: () => void
  
  // 获取激活的 Skill IDs（给 API 用）
  getActiveSkillIds: () => string[]
  
  // CRUD 操作
  createSkill: (data: SkillCreateData) => Promise<Skill>
  updateSkill: (skillId: string, data: Partial<SkillCreateData>) => Promise<Skill>
  deleteSkill: (skillId: string) => Promise<void>
}

// 创建 Skill 的数据
export interface SkillCreateData {
  name: string
  description: string
  icon: string
  category: string
  system_prompt: string
  tools: string[]
  welcome_message: string
  example_prompts: string[]
  max_tool_calls: number
}

// API 请求函数
const skillApi = {
  async list(): Promise<SkillListResponse> {
    const token = getAuthToken()
    const response = await fetch('/api/skills', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      throw new Error('获取 Skill 列表失败')
    }
    return response.json()
  },
  
  async get(skillId: string): Promise<Skill> {
    const token = getAuthToken()
    const response = await fetch(`/api/skills/${skillId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      throw new Error('获取 Skill 详情失败')
    }
    return response.json()
  },
  
  async create(data: SkillCreateData): Promise<Skill> {
    const token = getAuthToken()
    const response = await fetch('/api/skills', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || '创建 Skill 失败')
    }
    return response.json()
  },
  
  async update(skillId: string, data: Partial<SkillCreateData>): Promise<Skill> {
    const token = getAuthToken()
    const response = await fetch(`/api/skills/${skillId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || '更新 Skill 失败')
    }
    return response.json()
  },
  
  async delete(skillId: string): Promise<void> {
    const token = getAuthToken()
    const response = await fetch(`/api/skills/${skillId}`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || '删除 Skill 失败')
    }
  },
}

export const useSkillStore = create<SkillState>()(
  persist(
    (set, get) => ({
      // 列表状态
      builtinSkills: [],
      customSkills: [],
      loading: false,
      error: null,
      
      // 激活状态（支持多个）
      activeSkillIds: [],
      activeSkills: [],
      
      // 加载 Skill 列表
      loadSkills: async () => {
        set({ loading: true, error: null })
        try {
          const data = await skillApi.list()
          set({
            builtinSkills: data.builtin,
            customSkills: data.custom,
            loading: false,
          })
        } catch (error) {
          set({
            error: (error as Error).message,
            loading: false,
          })
        }
      },
      
      // 获取 Skill 详情
      getSkillDetail: async (skillId: string) => {
        try {
          return await skillApi.get(skillId)
        } catch (error) {
          console.error('获取 Skill 详情失败:', error)
          return null
        }
      },
      
      // 切换 Skill 激活状态
      toggleSkill: async (skillId: string) => {
        const { activeSkillIds, activeSkills } = get()
        
        if (activeSkillIds.includes(skillId)) {
          // 取消激活
          set({
            activeSkillIds: activeSkillIds.filter(id => id !== skillId),
            activeSkills: activeSkills.filter(s => s.id !== skillId),
          })
        } else {
          // 激活
          try {
            const skill = await skillApi.get(skillId)
            set({
              activeSkillIds: [...activeSkillIds, skillId],
              activeSkills: [...activeSkills, skill],
            })
          } catch (error) {
            console.error('激活 Skill 失败:', error)
            throw error
          }
        }
      },
      
      // 检查 Skill 是否激活
      isSkillActive: (skillId: string) => get().activeSkillIds.includes(skillId),
      
      // 清除所有激活
      clearActiveSkills: () => {
        set({
          activeSkillIds: [],
          activeSkills: [],
        })
      },
      
      // 获取激活的 Skill IDs
      getActiveSkillIds: () => get().activeSkillIds,
      
      // 创建 Skill
      createSkill: async (data: SkillCreateData) => {
        const skill = await skillApi.create(data)
        await get().loadSkills()
        return skill
      },
      
      // 更新 Skill
      updateSkill: async (skillId: string, data: Partial<SkillCreateData>) => {
        const skill = await skillApi.update(skillId, data)
        await get().loadSkills()
        // 如果更新的是当前激活的 Skill，也更新 activeSkills
        const { activeSkillIds, activeSkills } = get()
        if (activeSkillIds.includes(skillId)) {
          set({
            activeSkills: activeSkills.map(s => s.id === skillId ? skill : s),
          })
        }
        return skill
      },
      
      // 删除 Skill
      deleteSkill: async (skillId: string) => {
        await skillApi.delete(skillId)
        // 如果删除的是当前激活的 Skill，取消激活
        const { activeSkillIds, activeSkills } = get()
        if (activeSkillIds.includes(skillId)) {
          set({
            activeSkillIds: activeSkillIds.filter(id => id !== skillId),
            activeSkills: activeSkills.filter(s => s.id !== skillId),
          })
        }
        await get().loadSkills()
      },
    }),
    {
      name: 'skill-storage',
      // 只持久化激活的 Skill IDs
      partialize: (state) => ({
        activeSkillIds: state.activeSkillIds,
      }),
    }
  )
)
