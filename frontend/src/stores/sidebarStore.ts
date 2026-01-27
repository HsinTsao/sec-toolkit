import { create } from 'zustand'

interface SidebarState {
  isOpen: boolean
  isMobile: boolean
  open: () => void
  close: () => void
  toggle: () => void
  setIsMobile: (isMobile: boolean) => void
}

export const useSidebarStore = create<SidebarState>((set) => ({
  isOpen: false, // 移动端默认关闭
  isMobile: false,
  
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  setIsMobile: (isMobile: boolean) => set({ isMobile, isOpen: !isMobile }), // 桌面端默认打开
}))
