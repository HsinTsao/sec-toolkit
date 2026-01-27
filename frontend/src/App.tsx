import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { userApi } from '@/lib/api'
import Layout from '@/components/layout/Layout'
import LoginPage from '@/features/auth/LoginPage'
import RegisterPage from '@/features/auth/RegisterPage'
import AIChatPage from '@/features/chat/AIChatPage'
import EncodingTools from '@/features/tools/EncodingTools'
import HashTools from '@/features/tools/HashTools'
import CryptoTools from '@/features/tools/CryptoTools'
import JwtTools from '@/features/tools/JwtTools'
import FormatTools from '@/features/tools/FormatTools'
import NetworkTools from '@/features/tools/NetworkTools'
import PasswordTools from '@/features/tools/PasswordTools'
import BypassTools from '@/features/tools/BypassTools'
import CallbackServer from '@/features/tools/CallbackServer'
import ProxyTools from '@/features/tools/ProxyTools'
import CrawlerTools from '@/features/tools/CrawlerTools'
import NotesPage from '@/features/notes/NotesPage'
import NavigationPage from '@/features/navigation/NavigationPage'
import BookmarksPage from '@/features/knowledge/BookmarksPage'
import KnowledgeBasePage from '@/features/knowledge/KnowledgeBasePage'

// 应用初始化 Hook
function useAppInit() {
  const [isInitialized, setIsInitialized] = useState(false)
  const { token, setAuth, logout } = useAuthStore()
  
  useEffect(() => {
    const initAuth = async () => {
      // 如果有保存的 token，尝试验证
      if (token) {
        try {
          const { data: user } = await userApi.getMe()
          // token 有效，更新用户信息
          const refreshToken = useAuthStore.getState().refreshToken
          if (refreshToken) {
            setAuth(user, token, refreshToken)
          }
        } catch {
          // token 无效或过期，会自动尝试刷新
          // 如果刷新也失败，会被拦截器处理并登出
        }
      }
      setIsInitialized(true)
    }
    
    initAuth()
  }, [])
  
  return isInitialized
}

// 受保护的路由
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

// 公开路由 (已登录时跳转到首页)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  
  return <>{children}</>
}

export default function App() {
  const isInitialized = useAppInit()
  
  // 显示加载状态
  if (!isInitialized) {
    return (
      <div className="min-h-screen bg-theme-bg flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-theme-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-theme-muted">正在加载...</p>
        </div>
      </div>
    )
  }
  
  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      } />
      <Route path="/register" element={
        <PublicRoute>
          <RegisterPage />
        </PublicRoute>
      } />
      
      {/* 受保护的路由 */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<AIChatPage />} />
        
        {/* 知识库路由 */}
        <Route path="knowledge">
          <Route index element={<KnowledgeBasePage />} />
          <Route path="notes" element={<NotesPage />} />
          <Route path="bookmarks" element={<BookmarksPage />} />
          <Route path="navigation" element={<NavigationPage />} />
        </Route>
        
        {/* 工具路由 */}
        <Route path="tools">
          <Route path="encoding" element={<EncodingTools />} />
          <Route path="hash" element={<HashTools />} />
          <Route path="crypto" element={<CryptoTools />} />
          <Route path="jwt" element={<JwtTools />} />
          <Route path="format" element={<FormatTools />} />
          <Route path="network" element={<NetworkTools />} />
          <Route path="password" element={<PasswordTools />} />
          <Route path="bypass" element={<BypassTools />} />
          <Route path="callback" element={<CallbackServer />} />
          <Route path="proxy" element={<ProxyTools />} />
          <Route path="crawler" element={<CrawlerTools />} />
        </Route>
        
        {/* 旧路由重定向（兼容性） */}
        <Route path="notes" element={<Navigate to="/knowledge/notes" replace />} />
        <Route path="navigation" element={<Navigate to="/knowledge/navigation" replace />} />
      </Route>
      
      {/* 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

