import { useState } from 'react'
import { RefreshCw, Copy, Check } from 'lucide-react'
import { ToolCard, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import { cn, copyToClipboard } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function PasswordTools() {
  const { addRecentTool } = useToolStore()
  
  // 密码生成
  const [length, setLength] = useState(16)
  const [uppercase, setUppercase] = useState(true)
  const [lowercase, setLowercase] = useState(true)
  const [digits, setDigits] = useState(true)
  const [special, setSpecial] = useState(true)
  const [generatedPassword, setGeneratedPassword] = useState('')
  const [copied, setCopied] = useState(false)
  
  // 密码强度
  const [passwordToCheck, setPasswordToCheck] = useState('')
  const [strengthResult, setStrengthResult] = useState<{
    score: number
    max_score: number
    strength: string
    level: string
    feedback: string[]
  } | null>(null)
  
  const [loading, setLoading] = useState(false)
  
  // 生成密码
  const handleGenerate = async () => {
    setLoading(true)
    try {
      const { data } = await toolsApi.generatePassword({
        length,
        uppercase,
        lowercase,
        digits,
        special,
      })
      setGeneratedPassword(data.result)
      setCopied(false)
      addRecentTool('password')
    } catch {
      toast.error('生成失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 复制密码
  const handleCopy = async () => {
    if (!generatedPassword) return
    await copyToClipboard(generatedPassword)
    setCopied(true)
    toast.success('已复制')
    setTimeout(() => setCopied(false), 2000)
  }
  
  // 检查密码强度
  const handleCheckStrength = async () => {
    if (!passwordToCheck.trim()) {
      toast.error('请输入密码')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.checkPasswordStrength(passwordToCheck)
      setStrengthResult(data)
      addRecentTool('password')
    } catch {
      toast.error('检查失败')
    } finally {
      setLoading(false)
    }
  }
  
  const getStrengthColor = (level: string) => {
    switch (level) {
      case 'weak':
        return 'bg-red-500'
      case 'medium':
        return 'bg-yellow-500'
      case 'strong':
        return 'bg-green-500'
      case 'very_strong':
        return 'bg-theme-primary'
      default:
        return 'bg-gray-500'
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">密码工具</h1>
        <p className="text-theme-muted mt-1">
          安全密码生成、密码强度检测
        </p>
      </div>
      
      {/* 密码生成 */}
      <ToolCard title="密码生成器" toolKey="password-generate">
        <div className="space-y-6">
          {/* 长度滑块 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">密码长度</label>
              <span className="text-sm font-mono text-theme-primary">{length}</span>
            </div>
            <input
              type="range"
              min="8"
              max="64"
              value={length}
              onChange={(e) => setLength(parseInt(e.target.value))}
              className="w-full h-2 bg-theme-bg rounded-lg appearance-none cursor-pointer accent-theme-primary"
            />
            <div className="flex justify-between text-xs text-theme-muted mt-1">
              <span>8</span>
              <span>64</span>
            </div>
          </div>
          
          {/* 选项 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={uppercase}
                onChange={(e) => setUppercase(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm">大写字母 (A-Z)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={lowercase}
                onChange={(e) => setLowercase(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm">小写字母 (a-z)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={digits}
                onChange={(e) => setDigits(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm">数字 (0-9)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={special}
                onChange={(e) => setSpecial(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm">特殊字符 (!@#$)</span>
            </label>
          </div>
          
          {/* 生成按钮 */}
          <ToolButton onClick={handleGenerate} loading={loading}>
            <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
            生成密码
          </ToolButton>
          
          {/* 生成的密码 */}
          {generatedPassword && (
            <div className="relative">
              <div className="bg-theme-bg border border-theme-border rounded-lg p-4 font-mono text-lg break-all">
                {generatedPassword}
              </div>
              <button
                onClick={handleCopy}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 hover:bg-theme-card rounded-lg transition-colors"
              >
                {copied ? (
                  <Check className="w-5 h-5 text-theme-primary" />
                ) : (
                  <Copy className="w-5 h-5 text-theme-muted hover:text-theme-primary" />
                )}
              </button>
            </div>
          )}
        </div>
      </ToolCard>
      
      {/* 密码强度检测 */}
      <ToolCard title="密码强度检测" toolKey="password-strength">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">输入密码</label>
            <input
              type="text"
              value={passwordToCheck}
              onChange={(e) => setPasswordToCheck(e.target.value)}
              placeholder="输入要检测的密码..."
              className="w-full font-mono"
            />
          </div>
          
          <ToolButton onClick={handleCheckStrength} loading={loading}>
            检测强度
          </ToolButton>
          
          {strengthResult && (
            <div className="space-y-4">
              {/* 强度条 */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-theme-muted">强度</span>
                  <span className={cn(
                    'text-sm font-medium',
                    strengthResult.level === 'weak' && 'text-red-500',
                    strengthResult.level === 'medium' && 'text-yellow-500',
                    strengthResult.level === 'strong' && 'text-green-500',
                    strengthResult.level === 'very_strong' && 'text-theme-primary',
                  )}>
                    {strengthResult.strength}
                  </span>
                </div>
                <div className="h-2 bg-theme-bg rounded-full overflow-hidden">
                  <div
                    className={cn('h-full transition-all', getStrengthColor(strengthResult.level))}
                    style={{ width: `${(strengthResult.score / strengthResult.max_score) * 100}%` }}
                  />
                </div>
                <div className="text-xs text-theme-muted mt-1">
                  得分: {strengthResult.score} / {strengthResult.max_score}
                </div>
              </div>
              
              {/* 建议 */}
              {strengthResult.feedback.length > 0 && (
                <div>
                  <label className="text-sm text-theme-muted mb-2 block">改进建议</label>
                  <ul className="space-y-1">
                    {strengthResult.feedback.map((item, i) => (
                      <li key={i} className="text-sm text-theme-warning flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-theme-warning" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </ToolCard>
    </div>
  )
}

