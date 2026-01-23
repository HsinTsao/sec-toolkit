import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { llmApi, type LLMProvider, type LLMConfig } from '@/lib/api'

// 聊天消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}

// 聊天会话
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

interface LLMState {
  // 提供商列表（从后端获取）
  providers: LLMProvider[]
  loadProviders: () => Promise<void>
  
  // 用户配置（从后端获取）
  config: LLMConfig | null
  configLoading: boolean
  configError: string | null
  loadConfig: () => Promise<void>
  updateConfig: (data: { provider_id: string; api_key?: string; base_url?: string; model: string }) => Promise<void>
  
  // 当前选择的提供商信息（辅助函数）
  getCurrentProvider: () => LLMProvider | null
  
  // 会话管理（保持本地存储）
  sessions: ChatSession[]
  currentSessionId: string | null
  createSession: () => string
  deleteSession: (id: string) => void
  setCurrentSession: (id: string | null) => void
  getCurrentSession: () => ChatSession | null
  
  // 消息管理
  addMessage: (sessionId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  updateMessage: (sessionId: string, messageId: string, content: string) => void
  clearMessages: (sessionId: string) => void
}

export const useLLMStore = create<LLMState>()(
  persist(
    (set, get) => ({
      // 提供商
      providers: [],
      loadProviders: async () => {
        try {
          const { data } = await llmApi.getProviders()
          set({ providers: data })
        } catch (error) {
          console.error('加载 LLM 提供商失败:', error)
        }
      },
      
      // 配置
      config: null,
      configLoading: false,
      configError: null,
      
      loadConfig: async () => {
        set({ configLoading: true, configError: null })
        try {
          const { data } = await llmApi.getConfig()
          set({ config: data, configLoading: false })
        } catch (error: unknown) {
          // 404 表示未配置，不算错误
          if ((error as { response?: { status: number } })?.response?.status === 404) {
            set({ config: null, configLoading: false })
          } else {
            set({ 
              configError: (error as Error)?.message || '加载配置失败', 
              configLoading: false 
            })
          }
        }
      },
      
      updateConfig: async (data) => {
        set({ configLoading: true, configError: null })
        try {
          const { data: newConfig } = await llmApi.updateConfig(data)
          set({ config: newConfig, configLoading: false })
        } catch (error: unknown) {
          const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '保存配置失败'
          set({ configError: message, configLoading: false })
          throw error
        }
      },
      
      getCurrentProvider: () => {
        const { config, providers } = get()
        if (!config) return null
        return providers.find(p => p.id === config.provider_id) || null
      },
      
      // 会话
      sessions: [],
      currentSessionId: null,
      
      createSession: () => {
        const id = crypto.randomUUID()
        const session: ChatSession = {
          id,
          title: '新对话',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: id,
        }))
        return id
      },
      
      deleteSession: (id) => set((state) => ({
        sessions: state.sessions.filter(s => s.id !== id),
        currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
      })),
      
      setCurrentSession: (id) => set({ currentSessionId: id }),
      
      getCurrentSession: () => {
        const state = get()
        return state.sessions.find(s => s.id === state.currentSessionId) || null
      },
      
      // 消息
      addMessage: (sessionId, message) => set((state) => ({
        sessions: state.sessions.map(session => 
          session.id === sessionId
            ? {
                ...session,
                messages: [...session.messages, {
                  ...message,
                  id: crypto.randomUUID(),
                  timestamp: Date.now(),
                }],
                updatedAt: Date.now(),
                // 如果是第一条用户消息，更新标题
                title: session.messages.length === 0 && message.role === 'user'
                  ? message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
                  : session.title,
              }
            : session
        ),
      })),
      
      updateMessage: (sessionId, messageId, content) => set((state) => ({
        sessions: state.sessions.map(session =>
          session.id === sessionId
            ? {
                ...session,
                messages: session.messages.map(msg =>
                  msg.id === messageId ? { ...msg, content } : msg
                ),
                updatedAt: Date.now(),
              }
            : session
        ),
      })),
      
      clearMessages: (sessionId) => set((state) => ({
        sessions: state.sessions.map(session =>
          session.id === sessionId
            ? { ...session, messages: [], updatedAt: Date.now() }
            : session
        ),
      })),
    }),
    {
      name: 'llm-storage',
      // 只持久化会话数据，配置从后端获取
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
      }),
    }
  )
)

// 导出类型（兼容）
export type { LLMProvider, LLMConfig }
