import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Lock, Mail, Eye, EyeOff } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { authApi, userApi } from '@/lib/api'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth, setTokens } = useAuthStore()
  
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!email || !password) {
      toast.error('请填写邮箱和密码')
      return
    }
    
    setLoading(true)
    try {
      // 登录
      const { data: tokens } = await authApi.login(email, password)
      
      // 先保存 token，这样后续请求才能带上 Authorization header
      setTokens(tokens.access_token, tokens.refresh_token)
      
      // 获取用户信息
      const { data: user } = await userApi.getMe()
      
      // 保存完整状态
      setAuth(user, tokens.access_token, tokens.refresh_token)
      
      toast.success('登录成功')
      navigate('/')
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      toast.error(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-theme-bg flex items-center justify-center p-4">
      {/* 背景效果 */}
      <div className="absolute inset-0 matrix-bg" />
      
      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-theme-primary to-theme-secondary mb-4">
            <Lock className="w-8 h-8 text-theme-bg" />
          </div>
          <h1 className="text-3xl font-bold text-theme-primary neon-glow">
            Security Toolkit
          </h1>
          <p className="text-theme-muted mt-2">安全工具库</p>
        </div>
        
        {/* 登录表单 */}
        <div className="card">
          <h2 className="text-xl font-semibold text-center mb-6">登录</h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-theme-muted mb-2">邮箱</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-theme-muted" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full pl-10"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm text-theme-muted mb-2">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-theme-muted" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-theme-muted hover:text-theme-text"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="w-full btn btn-primary"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>
          
          <div className="mt-6 text-center text-sm text-theme-muted">
            还没有账号？
            <Link to="/register" className="text-theme-primary hover:underline ml-1">
              立即注册
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

