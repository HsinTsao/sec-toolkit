/**
 * 配置 openapi-ts 生成的客户端
 *
 * 在 main.tsx 中导入此文件即可：
 *   import '@/api/setup'
 *
 * 配置内容：
 *  - baseUrl 改为空字符串（走 vite proxy / nginx 代理）
 *  - 请求拦截器注入 Bearer token
 *  - 错误拦截器处理 401 自动刷新 token
 */
import { client } from './generated/client.gen'
import { useAuthStore } from '@/stores/authStore'

client.setConfig({ baseUrl: '' })

let isRefreshing = false
let refreshQueue: Array<() => void> = []

client.interceptors.request.use((request) => {
  const token = useAuthStore.getState().token
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`)
  }
  return request
})

client.interceptors.error.use(async (error) => {
  const response = (error as { response?: Response }).response
  if (!response || response.status !== 401) throw error

  const { refreshToken, setTokens, logout } = useAuthStore.getState()
  if (!refreshToken) {
    logout()
    window.location.href = '/login'
    throw error
  }

  if (isRefreshing) {
    return new Promise<void>((resolve) => {
      refreshQueue.push(resolve)
    }).then(() => { throw error })
  }

  isRefreshing = true
  try {
    const res = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) throw new Error('refresh failed')
    const data = await res.json()
    setTokens(data.access_token, data.refresh_token)
    refreshQueue.forEach((cb) => cb())
  } catch {
    logout()
    window.location.href = '/login'
  } finally {
    isRefreshing = false
    refreshQueue = []
  }
  throw error
})
