import { useState } from 'react'
import { toolsApi } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  Shield,
  Globe,
  FileText,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  Monitor,
  Server,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface Finding {
  directive: string | null
  severity: 'high' | 'medium' | 'low' | 'info'
  title: string
  description: string
  value: string
}

interface EvaluationResult {
  raw: string
  directives: Record<string, string[]>
  findings: Finding[]
  summary: {
    high: number
    medium: number
    low: number
    info: number
    score: number
    rating: string
  }
}

interface FetchResult {
  url: string
  status_code?: number
  csp: string
  csp_report_only?: string
  csp_source?: string
  fetch_method?: 'browser' | 'server'
  evaluation?: EvaluationResult
  report_only_evaluation?: EvaluationResult
  error?: string
}

type InputMode = 'url' | 'raw'

const SEVERITY_CONFIG = {
  high: { label: '高危', icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', badge: 'bg-red-500/20 text-red-400' },
  medium: { label: '中危', icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', badge: 'bg-yellow-500/20 text-yellow-400' },
  low: { label: '低危', icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30', badge: 'bg-blue-500/20 text-blue-400' },
  info: { label: '信息', icon: Info, color: 'text-gray-400', bg: 'bg-gray-500/10 border-gray-500/30', badge: 'bg-gray-500/20 text-gray-400' },
}

const RATING_COLORS: Record<string, string> = {
  A: 'text-green-400 border-green-500',
  B: 'text-lime-400 border-lime-500',
  C: 'text-yellow-400 border-yellow-500',
  D: 'text-orange-400 border-orange-500',
  F: 'text-red-400 border-red-500',
}

const CSP_VERSIONS = [
  { value: 3, label: 'CSP Level 3（推荐）' },
  { value: 2, label: 'CSP Level 2' },
  { value: 1, label: 'CSP Level 1' },
]

function normalizeUrl(url: string): string {
  url = url.trim()
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = `https://${url}`
  }
  return url
}

/**
 * 前端直接 fetch URL，尝试读取 CSP 响应头。
 * 受 CORS 限制，跨域站点可能无法读取 headers，此时返回 null 表示需要回退到后端。
 */
async function browserFetchCsp(rawUrl: string): Promise<{
  url: string
  status_code: number
  csp: string
  csp_report_only: string
  csp_source: string
} | null> {
  const url = normalizeUrl(rawUrl)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)

  try {
    const resp = await fetch(url, {
      method: 'GET',
      mode: 'cors',
      credentials: 'omit',
      redirect: 'follow',
      signal: controller.signal,
    })

    clearTimeout(timer)

    const csp = resp.headers.get('content-security-policy') || ''
    const cspRo = resp.headers.get('content-security-policy-report-only') || ''

    // CORS 下浏览器可能返回空 headers（opaque filtered response）
    // 如果连 content-type 都读不到，说明 headers 被浏览器屏蔽了
    const canReadHeaders = resp.headers.get('content-type') !== null

    if (!canReadHeaders) {
      return null
    }

    // 如果 header 中没有 CSP，尝试从 HTML meta 标签提取
    let metaCsp = ''
    let cspSource = 'none'
    if (csp) {
      cspSource = 'header'
    } else {
      try {
        const html = await resp.text()
        const match = html.match(/<meta\s+http-equiv=["']Content-Security-Policy["']\s+content=["']([^"']+)["']/i)
        if (match) {
          metaCsp = match[1]
          cspSource = 'meta'
        }
      } catch { /* 忽略 body 读取失败 */ }
    }

    return {
      url: resp.url,
      status_code: resp.status,
      csp: csp || metaCsp,
      csp_report_only: cspRo,
      csp_source: cspSource,
    }
  } catch {
    clearTimeout(timer)
    return null
  }
}

export default function CspEvaluator() {
  const [mode, setMode] = useState<InputMode>('url')
  const [urlInput, setUrlInput] = useState('')
  const [rawCsp, setRawCsp] = useState('')
  const [cspVersion, setCspVersion] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FetchResult | null>(null)
  const [directEval, setDirectEval] = useState<EvaluationResult | null>(null)
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set())

  const handleFetch = async () => {
    if (!urlInput.trim()) {
      toast.error('请输入 URL')
      return
    }
    setLoading(true)
    setResult(null)
    setDirectEval(null)

    // 1) 前端浏览器直接请求
    const browserResult = await browserFetchCsp(urlInput.trim())

    if (browserResult) {
      // 浏览器获取成功，把 CSP 发给后端做评估
      try {
        const evalPromises: Promise<any>[] = [
          toolsApi.cspEvaluate(browserResult.csp, cspVersion),
        ]
        if (browserResult.csp_report_only) {
          evalPromises.push(toolsApi.cspEvaluate(browserResult.csp_report_only, cspVersion))
        }
        const [evalRes, roRes] = await Promise.all(evalPromises)

        setResult({
          ...browserResult,
          fetch_method: 'browser',
          evaluation: evalRes.data,
          report_only_evaluation: roRes?.data || null,
        })
      } catch {
        // 评估接口失败，仍展示获取结果
        setResult({ ...browserResult, fetch_method: 'browser' })
        toast.error('CSP 评估请求失败')
      }
    } else {
      // 2) 浏览器受 CORS 限制，回退到后端代理
      try {
        const { data } = await toolsApi.cspFetchAndEvaluate(urlInput.trim(), cspVersion)
        setResult({ ...data, fetch_method: 'server' })
        if (data.error) {
          toast.error(data.error)
        }
      } catch (e: any) {
        toast.error(e.response?.data?.detail || '请求失败')
      }
    }

    setLoading(false)
  }

  const handleEvaluate = async () => {
    if (!rawCsp.trim()) {
      toast.error('请输入 CSP 策略')
      return
    }
    setLoading(true)
    setResult(null)
    setDirectEval(null)
    try {
      const { data } = await toolsApi.cspEvaluate(rawCsp.trim(), cspVersion)
      setDirectEval(data)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || '评估失败')
    } finally {
      setLoading(false)
    }
  }

  const toggleFinding = (index: number) => {
    setExpandedFindings(prev => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('已复制')
  }

  const evaluation = mode === 'url' ? result?.evaluation : directEval
  const reportOnlyEval = mode === 'url' ? result?.report_only_evaluation : null

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
          <Shield className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-theme-text">CSP 评估器</h1>
          <p className="text-sm text-theme-muted">分析 Content Security Policy 策略安全性</p>
        </div>
      </div>

      {/* 输入区域 */}
      <div className="bg-theme-card border border-theme-border rounded-xl p-5 space-y-4">
        {/* 模式切换 */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode('url')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              mode === 'url'
                ? 'bg-theme-primary/20 text-theme-primary'
                : 'text-theme-muted hover:text-theme-text hover:bg-theme-bg'
            )}
          >
            <Globe className="w-4 h-4" />
            从 URL 获取
          </button>
          <button
            onClick={() => setMode('raw')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              mode === 'raw'
                ? 'bg-theme-primary/20 text-theme-primary'
                : 'text-theme-muted hover:text-theme-text hover:bg-theme-bg'
            )}
          >
            <FileText className="w-4 h-4" />
            直接输入 CSP
          </button>
        </div>

        {/* URL 输入 */}
        {mode === 'url' && (
          <>
            <div className="flex gap-3">
              <input
                type="text"
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleFetch()}
                placeholder="输入 URL，例如 https://example.com"
                className="flex-1 bg-theme-bg border border-theme-border rounded-lg px-4 py-2.5 text-theme-text placeholder:text-theme-muted/50 focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
              />
              <button
                onClick={handleFetch}
                disabled={loading}
                className="px-6 py-2.5 bg-theme-primary text-white rounded-lg font-medium hover:bg-theme-primary/90 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {loading ? '获取中...' : '获取 & 评估'}
              </button>
            </div>
            <p className="text-xs text-theme-muted/60">
              优先通过浏览器直接访问目标 URL（使用你本地网络环境），CORS 受限时自动回退到服务端代理
            </p>
          </>
        )}

        {/* CSP 文本输入 */}
        {mode === 'raw' && (
          <div className="space-y-3">
            <textarea
              value={rawCsp}
              onChange={e => setRawCsp(e.target.value)}
              placeholder="粘贴 CSP 策略字符串，例如：default-src 'self'; script-src 'self' cdn.example.com"
              rows={4}
              className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 text-theme-text placeholder:text-theme-muted/50 focus:outline-none focus:ring-2 focus:ring-theme-primary/50 font-mono text-sm resize-y"
            />
            <button
              onClick={handleEvaluate}
              disabled={loading}
              className="px-6 py-2.5 bg-theme-primary text-white rounded-lg font-medium hover:bg-theme-primary/90 disabled:opacity-50 transition-colors"
            >
              {loading ? '评估中...' : '评估 CSP'}
            </button>
          </div>
        )}

        {/* CSP 版本选择 */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-theme-muted">CSP 版本:</span>
          {CSP_VERSIONS.map(v => (
            <button
              key={v.value}
              onClick={() => setCspVersion(v.value)}
              className={cn(
                'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                cspVersion === v.value
                  ? 'bg-theme-primary/20 text-theme-primary'
                  : 'text-theme-muted hover:text-theme-text hover:bg-theme-bg'
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* 获取信息摘要（URL 模式） */}
      {mode === 'url' && result && !result.error && (
        <div className="bg-theme-card border border-theme-border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-theme-text">获取结果</h2>
            <div className="flex items-center gap-2">
              {/* 获取方式标签 */}
              <span className={cn(
                'text-xs px-2 py-0.5 rounded flex items-center gap-1',
                result.fetch_method === 'browser'
                  ? 'bg-purple-500/20 text-purple-400'
                  : 'bg-cyan-500/20 text-cyan-400'
              )}>
                {result.fetch_method === 'browser'
                  ? <><Monitor className="w-3 h-3" /> 浏览器直连</>
                  : <><Server className="w-3 h-3" /> 服务端代理</>}
              </span>
              {/* CSP 来源标签 */}
              <span className={cn(
                'text-xs px-2 py-0.5 rounded',
                result.csp_source === 'header' ? 'bg-green-500/20 text-green-400'
                  : result.csp_source === 'meta' ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-red-500/20 text-red-400'
              )}>
                {result.csp_source === 'header' ? 'HTTP Header'
                  : result.csp_source === 'meta' ? 'Meta Tag'
                  : '未检测到 CSP'}
              </span>
            </div>
          </div>
          <div className="text-xs text-theme-muted space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-theme-muted/70">URL:</span>
              <a href={result.url} target="_blank" rel="noopener noreferrer" className="text-theme-primary hover:underline flex items-center gap-1">
                {result.url} <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            {result.status_code && (
              <div><span className="text-theme-muted/70">状态码:</span> {result.status_code}</div>
            )}
          </div>
          {result.csp && (
            <div className="relative group">
              <pre className="bg-theme-bg rounded-lg p-3 text-xs font-mono text-theme-text overflow-x-auto whitespace-pre-wrap break-all">
                {result.csp}
              </pre>
              <button
                onClick={() => copyToClipboard(result.csp)}
                className="absolute top-2 right-2 p-1.5 rounded-md bg-theme-card/80 text-theme-muted hover:text-theme-text opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
          {result.csp_report_only && (
            <div>
              <div className="text-xs text-theme-muted mb-1">Content-Security-Policy-Report-Only:</div>
              <pre className="bg-theme-bg rounded-lg p-3 text-xs font-mono text-yellow-400/80 overflow-x-auto whitespace-pre-wrap break-all">
                {result.csp_report_only}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* 评估结果 */}
      {evaluation && (
        <EvaluationPanel evaluation={evaluation} label="CSP 评估结果" expandedFindings={expandedFindings} toggleFinding={toggleFinding} />
      )}

      {/* Report-Only 评估 */}
      {reportOnlyEval && (
        <EvaluationPanel evaluation={reportOnlyEval} label="Report-Only CSP 评估" expandedFindings={expandedFindings} toggleFinding={toggleFinding} indexOffset={evaluation?.findings.length || 0} />
      )}

      {/* 无 CSP 提示 */}
      {mode === 'url' && result && !result.error && !result.csp && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-5 text-center">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-400 font-medium">该网站未设置 Content-Security-Policy</p>
          <p className="text-sm text-theme-muted mt-1">没有 CSP 保护，网站容易受到 XSS、数据注入等攻击</p>
        </div>
      )}
    </div>
  )
}

function EvaluationPanel({
  evaluation,
  label,
  expandedFindings,
  toggleFinding,
  indexOffset = 0,
}: {
  evaluation: EvaluationResult
  label: string
  expandedFindings: Set<number>
  toggleFinding: (i: number) => void
  indexOffset?: number
}) {
  const { summary, directives, findings } = evaluation

  return (
    <div className="space-y-4">
      {/* 评分概览 */}
      <div className="bg-theme-card border border-theme-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-theme-text mb-4">{label}</h2>
        <div className="flex items-center gap-6">
          {/* 评级 */}
          <div className={cn(
            'w-20 h-20 rounded-xl border-2 flex flex-col items-center justify-center',
            RATING_COLORS[summary.rating] || 'text-gray-400 border-gray-500'
          )}>
            <span className="text-3xl font-black">{summary.rating}</span>
            <span className="text-[10px] opacity-70">{summary.score}/100</span>
          </div>

          {/* 统计 */}
          <div className="flex-1 grid grid-cols-4 gap-3">
            {(['high', 'medium', 'low', 'info'] as const).map(sev => {
              const cfg = SEVERITY_CONFIG[sev]
              return (
                <div key={sev} className={cn('rounded-lg border p-3 text-center', cfg.bg)}>
                  <cfg.icon className={cn('w-4 h-4 mx-auto mb-1', cfg.color)} />
                  <div className={cn('text-xl font-bold', cfg.color)}>{summary[sev]}</div>
                  <div className="text-[10px] text-theme-muted">{cfg.label}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* 指令解析表 */}
      {Object.keys(directives).length > 0 && (
        <div className="bg-theme-card border border-theme-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-theme-text mb-3">指令解析</h3>
          <div className="space-y-2">
            {Object.entries(directives).map(([name, values]) => (
              <div key={name} className="flex gap-3 text-xs">
                <code className="text-theme-primary font-semibold whitespace-nowrap min-w-[140px]">{name}</code>
                <div className="flex flex-wrap gap-1.5">
                  {values.map((v, i) => (
                    <span
                      key={i}
                      className={cn(
                        'px-2 py-0.5 rounded font-mono',
                        v === "'unsafe-inline'" || v === "'unsafe-eval'" ? 'bg-red-500/15 text-red-400'
                          : v === "'none'" ? 'bg-green-500/15 text-green-400'
                          : v === "'self'" || v.startsWith("'nonce-") || v.startsWith("'sha") ? 'bg-blue-500/15 text-blue-400'
                          : v === "'strict-dynamic'" ? 'bg-purple-500/15 text-purple-400'
                          : v === 'data:' || v === 'blob:' ? 'bg-yellow-500/15 text-yellow-400'
                          : 'bg-theme-bg text-theme-text'
                      )}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 发现列表 */}
      {findings.length > 0 && (
        <div className="bg-theme-card border border-theme-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-theme-text mb-3">安全发现 ({findings.length})</h3>
          <div className="space-y-2">
            {findings.map((f, i) => {
              const idx = i + indexOffset
              const isExpanded = expandedFindings.has(idx)
              const cfg = SEVERITY_CONFIG[f.severity]
              return (
                <div key={idx} className={cn('rounded-lg border transition-colors', cfg.bg)}>
                  <button
                    onClick={() => toggleFinding(idx)}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left"
                  >
                    <cfg.icon className={cn('w-4 h-4 flex-shrink-0', cfg.color)} />
                    <span className={cn('text-xs px-2 py-0.5 rounded font-medium flex-shrink-0', cfg.badge)}>
                      {cfg.label}
                    </span>
                    {f.directive && (
                      <code className="text-xs text-theme-primary font-mono flex-shrink-0">{f.directive}</code>
                    )}
                    <span className="text-sm text-theme-text flex-1 truncate">{f.title}</span>
                    {f.value && (
                      <code className="text-xs text-theme-muted font-mono hidden sm:inline truncate max-w-[120px]">{f.value}</code>
                    )}
                    {isExpanded ? <ChevronDown className="w-4 h-4 text-theme-muted flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-theme-muted flex-shrink-0" />}
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-3 pt-0">
                      <p className="text-sm text-theme-muted leading-relaxed pl-7">{f.description}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 全部通过 */}
      {findings.length === 0 && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5 text-center">
          <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
          <p className="text-green-400 font-medium">CSP 策略看起来很安全</p>
        </div>
      )}
    </div>
  )
}
