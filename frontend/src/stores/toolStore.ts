import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ToolHistory {
  id: string
  toolKey: string
  input: string
  output: string
  timestamp: number
}

interface ToolState {
  favorites: string[]
  recentTools: string[]
  history: ToolHistory[]
  
  addFavorite: (toolKey: string) => void
  removeFavorite: (toolKey: string) => void
  isFavorite: (toolKey: string) => boolean
  
  addRecentTool: (toolKey: string) => void
  
  addHistory: (toolKey: string, input: string, output: string) => void
  clearHistory: (toolKey?: string) => void
}

export const useToolStore = create<ToolState>()(
  persist(
    (set, get) => ({
      favorites: [],
      recentTools: [],
      history: [],
      
      addFavorite: (toolKey) =>
        set((state) => ({
          favorites: state.favorites.includes(toolKey)
            ? state.favorites
            : [...state.favorites, toolKey],
        })),
      
      removeFavorite: (toolKey) =>
        set((state) => ({
          favorites: state.favorites.filter((k) => k !== toolKey),
        })),
      
      isFavorite: (toolKey) => get().favorites.includes(toolKey),
      
      addRecentTool: (toolKey) =>
        set((state) => {
          const recent = state.recentTools.filter((k) => k !== toolKey)
          return { recentTools: [toolKey, ...recent].slice(0, 10) }
        }),
      
      addHistory: (toolKey, input, output) =>
        set((state) => ({
          history: [
            {
              id: Date.now().toString(),
              toolKey,
              input,
              output,
              timestamp: Date.now(),
            },
            ...state.history,
          ].slice(0, 100), // 只保留最近 100 条
        })),
      
      clearHistory: (toolKey) =>
        set((state) => ({
          history: toolKey
            ? state.history.filter((h) => h.toolKey !== toolKey)
            : [],
        })),
    }),
    {
      name: 'tool-storage',
    }
  )
)

