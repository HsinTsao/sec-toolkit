import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Lock, Mail, User, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/lib/api'
import toast from 'react-hot-toast'

export default function RegisterPage() {
  const navigate = useNavigate()
  
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!email || !username || !password) {
      toast.error('请填写所有必填字段')
      return
    }
    
    if (password !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }
    
    if (password.length < 6) {
      toast.error('密码长度至少 6 位')
      return
    }
    
    setLoading(true)
    try {
      await authApi.register(email, username, password)
      toast.success('注册成功，请登录')
      navigate('/login')
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      toast.error(err.response?.data?.detail || '注册失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-theme-bg flex items-center justify-center p-4">
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
        
        {/* 注册表单 */}
        <div className="card">
          <h2 className="text-xl font-semibold text-center mb-6">注册</h2>
          
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
              <label className="block text-sm text-theme-muted mb-2">用户名</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-theme-muted" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="你的用户名"
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
                  placeholder="至少 6 位"
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
            
            <div>
              <label className="block text-sm text-theme-muted mb-2">确认密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-theme-muted" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入密码"
                  className="w-full pl-10"
                />
              </div>
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="w-full btn btn-primary"
            >
              {loading ? '注册中...' : '注册'}
            </button>
          </form>
          
          <div className="mt-6 text-center text-sm text-theme-muted">
            已有账号？
            <Link to="/login" className="text-theme-primary hover:underline ml-1">
              立即登录
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

