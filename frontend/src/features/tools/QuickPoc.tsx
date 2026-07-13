import { useState, useEffect } from 'react'
import {
  Zap,
  Copy,
  Check,
  ExternalLink,
  Globe,
  Loader2,
  RefreshCw,
  Clock,
  ChevronDown,
  ChevronUp,
  FileCode,
  Users,
} from 'lucide-react'
import { pocApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

interface PocItem {
  name: string
  description: string
  category: string
  content_type: string
  record: boolean
  usage: string | null
  hit_count: number
}

interface PocLogItem {
  id: string
  poc_name: string
  client_ip: string | null
  method: string | null
  path: string | null
  query_string: string | null
  headers: Record<string, string> | null
  body: string | null
  user_agent: string | null
  timestamp: string | null
}

interface PocPreviewResponse {
  name: string
  content_type: string
  status_code: number
  redirect_url: string | null
  body: string
}

const CATEGORY_LABELS: Record<string, string> = {
  xss: 'XSS',
  xxe: 'XXE',
  ssrf: 'SSRF',
  rce: 'RCE',
  shell: 'Shell',
  script: 'Script',
  custom: 'Custom',
  general: 'General',
}

export default function QuickPoc() {
  const [pocs, setPocs] = useState<PocItem[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPoc, setSelectedPoc] = useState<PocItem | null>(null)
  const [copiedName, setCopiedName] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState<string | null>(null)
  const [previewMeta, setPreviewMeta] = useState<PocPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [logs, setLogs] = useState<PocLogItem[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null)
  const [filterCat, setFilterCat] = useState<string | null>(null)

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

  const getPocUrl = (name: string) => `${getBaseUrl()}/p/${name}`

  const copyToClipboard = async (text: string): Promise<boolean> => {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true } catch { /* fall */ }
    }
    const ta = document.createElement('textarea')
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'
    document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy'); return true } catch { return false } finally { document.body.removeChild(ta) }
  }

  const copyUrl = async (name: string) => {
    const ok = await copyToClipboard(getPocUrl(name))
    if (ok) { setCopiedName(name); toast.success('URL copied'); setTimeout(() => setCopiedName(null), 2000) }
  }

  const copyUsage = async (poc: PocItem) => {
    if (!poc.usage) return
    const text = poc.usage.replace('{url}', getPocUrl(poc.name))
    const ok = await copyToClipboard(text)
    if (ok) toast.success('Payload copied')
  }

  const loadPocs = async () => {
    setLoading(true)
    try {
      const { data } = await pocApi.list()
      setPocs(data.pocs)
      setCategories(data.categories)
    } catch { toast.error('Load failed') }
    finally { setLoading(false) }
  }

  const loadPreview = async (name: string) => {
    setPreviewLoading(true)
    try {
      const { data } = await pocApi.preview(name)
      setPreviewMeta(data)
      setPreviewContent(data.body || '')
    } catch {
      setPreviewMeta(null)
      setPreviewContent('Preview failed')
    }
    finally { setPreviewLoading(false) }
  }

  const loadLogs = async (name: string) => {
    setLogsLoading(true)
    try {
      const { data } = await pocApi.getLogs(name, 100)
      setLogs(data.logs || [])
    } catch {
      setLogs([])
      toast.error('Load history failed')
    } finally {
      setLogsLoading(false)
    }
  }

  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return 'Unknown'
    return new Date(timestamp).toLocaleString()
  }

  const formatIp = (ip: string | null) => ip || 'Unknown'

  const formatPath = (log: PocLogItem) => {
    const path = log.path && log.path !== '/' ? `/${log.path.replace(/^\/+/, '')}` : ''
    const query = log.query_string ? `?${log.query_string}` : ''
    return `${getPocUrl(log.poc_name)}${path}${query}`
  }

  useEffect(() => { loadPocs() }, [])

  useEffect(() => {
    if (selectedPoc) {
      setExpandedLogId(null)
      loadPreview(selectedPoc.name)
      loadLogs(selectedPoc.name)
    } else {
      setPreviewMeta(null)
      setPreviewContent(null)
      setLogs([])
    }
  }, [selectedPoc])

  const filtered = filterCat ? pocs.filter(p => p.category === filterCat) : pocs

  return (
    <div className="h-[calc(100vh-8rem)] min-w-0 flex animate-fadeIn">
      {/* Left: PoC list */}
      <div className="w-80 bg-theme-card border-r border-theme-border p-4 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-theme-primary" />
            <h2 className="font-semibold text-theme-text">Quick PoC</h2>
          </div>
          <button onClick={loadPocs} className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary transition-colors">
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>

        {/* Category filter */}
        <div className="flex flex-wrap gap-1 mb-3">
          <button
            onClick={() => setFilterCat(null)}
            className={cn('px-2 py-0.5 text-xs rounded-full transition-colors',
              !filterCat ? 'bg-theme-primary/20 text-theme-primary' : 'bg-theme-bg text-theme-muted hover:text-theme-text'
            )}
          >All ({pocs.length})</button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setFilterCat(filterCat === cat ? null : cat)}
              className={cn('px-2 py-0.5 text-xs rounded-full transition-colors',
                filterCat === cat ? 'bg-theme-primary/20 text-theme-primary' : 'bg-theme-bg text-theme-muted hover:text-theme-text'
              )}
            >{(CATEGORY_LABELS[cat] || cat)} ({pocs.filter(p => p.category === cat).length})</button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-theme-primary" /></div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-8 text-theme-muted text-sm">No PoC found</div>
          ) : (
            filtered.map(poc => (
              <div
                key={poc.name}
                onClick={() => setSelectedPoc(poc)}
                className={cn(
                  'p-2.5 rounded-lg border cursor-pointer transition-all',
                  selectedPoc?.name === poc.name
                    ? 'bg-theme-primary/20 border-theme-primary'
                    : 'bg-theme-bg border-theme-border hover:border-theme-primary/50'
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-sm text-theme-text truncate">{poc.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-theme-primary/10 text-theme-primary rounded">{poc.category}</span>
                </div>
                <div className="text-xs text-theme-muted truncate">{poc.description}</div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-xs text-theme-muted">{poc.hit_count} hits</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); copyUrl(poc.name) }}
                    className="p-1 hover:text-theme-primary transition-colors text-theme-muted"
                  >
                    {copiedName === poc.name ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right: detail */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {selectedPoc ? (
          <>
            {/* Header */}
            <div className="p-4 border-b border-theme-border bg-theme-card">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-theme-text text-lg">{selectedPoc.name}</h3>
                  <p className="text-sm text-theme-muted mt-0.5">{selectedPoc.description}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 text-xs rounded bg-theme-primary/10 text-theme-primary">{selectedPoc.category}</span>
                  <span className="px-2 py-1 text-xs rounded bg-theme-bg text-theme-muted">{selectedPoc.content_type}</span>
                  <a
                    href={getPocUrl(selectedPoc.name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>

              {/* URL */}
              <div
                className="flex items-center gap-2 p-2 bg-theme-bg rounded-lg cursor-pointer hover:bg-theme-bg/80 group"
                onClick={() => copyUrl(selectedPoc.name)}
              >
                <Globe className="w-4 h-4 text-theme-muted flex-shrink-0" />
                <code className="text-sm font-mono text-theme-primary truncate flex-1">{getPocUrl(selectedPoc.name)}</code>
                <span className="text-xs text-theme-muted group-hover:text-theme-primary transition-colors">
                  {copiedName === selectedPoc.name ? 'Copied!' : 'Click to copy'}
                </span>
              </div>

              {/* Usage */}
              {selectedPoc.usage && (
                <div
                  className="mt-2 flex items-center gap-2 p-2 bg-blue-500/10 border border-blue-500/25 rounded-lg cursor-pointer hover:bg-blue-500/15 group"
                  onClick={() => copyUsage(selectedPoc)}
                >
                  <span className="text-blue-500 flex-shrink-0 font-semibold text-sm">$</span>
                  <code className="text-xs font-mono text-blue-300 truncate flex-1">
                    {selectedPoc.usage.replace('{url}', getPocUrl(selectedPoc.name))}
                  </code>
                  <span className="text-xs text-blue-400 flex-shrink-0">
                    <Copy className="w-3 h-3 inline mr-1" />Copy
                  </span>
                </div>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-h-0 overflow-auto p-4">
              <div className="grid h-full min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
                <section className="min-h-0 rounded-lg border border-theme-border bg-theme-card p-4 flex flex-col overflow-hidden">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-medium text-theme-muted">Response Preview</h4>
                      {previewMeta && (
                        <p className="mt-1 text-xs text-theme-muted">
                          {previewMeta.status_code} · {previewMeta.content_type}
                          {previewMeta.redirect_url ? ` · redirect ${previewMeta.redirect_url}` : ''}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => selectedPoc && loadPreview(selectedPoc.name)}
                      className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary transition-colors"
                    >
                      <RefreshCw className={cn('w-4 h-4', previewLoading && 'animate-spin')} />
                    </button>
                  </div>
                  {previewLoading ? (
                    <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-theme-primary" /></div>
                  ) : (
                    <pre className="flex-1 bg-theme-bg border border-theme-border rounded-lg p-4 text-xs font-mono text-theme-text whitespace-pre-wrap break-all min-h-[20rem] overflow-auto">
                      {previewContent || 'No preview'}
                    </pre>
                  )}
                </section>

                <section className="min-h-0 rounded-lg border border-theme-border bg-theme-card p-4 flex flex-col overflow-hidden">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-medium text-theme-muted">Access History</h4>
                      <p className="text-xs text-theme-muted mt-1">
                        {selectedPoc.record ? `${logs.length} recent requests` : 'This PoC does not record requests'}
                      </p>
                    </div>
                    <button
                      onClick={() => selectedPoc && loadLogs(selectedPoc.name)}
                      disabled={!selectedPoc.record}
                      className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <RefreshCw className={cn('w-4 h-4', logsLoading && 'animate-spin')} />
                    </button>
                  </div>

                  {!selectedPoc.record ? (
                    <div className="flex-1 rounded-lg border border-dashed border-theme-border bg-theme-bg/40 flex items-center justify-center text-sm text-theme-muted">
                      This PoC has record=false
                    </div>
                  ) : logsLoading ? (
                    <div className="flex flex-1 items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-theme-primary" /></div>
                  ) : logs.length === 0 ? (
                    <div className="flex-1 rounded-lg border border-dashed border-theme-border bg-theme-bg/40 flex items-center justify-center text-sm text-theme-muted">
                      No access history yet
                    </div>
                  ) : (
                    <div className="flex-1 space-y-2 overflow-y-auto pr-1">
                      {logs.map((log) => {
                        const expanded = expandedLogId === log.id
                        return (
                          <div key={log.id} className="rounded-lg border border-theme-border bg-theme-bg overflow-hidden">
                            <button
                              onClick={() => setExpandedLogId(expanded ? null : log.id)}
                              className="w-full p-3 text-left hover:bg-theme-bg/80 transition-colors"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <span className={cn(
                                      'px-2 py-0.5 rounded text-[11px] font-mono flex-shrink-0',
                                      log.method === 'GET' && 'bg-green-500/20 text-green-400',
                                      log.method === 'POST' && 'bg-blue-500/20 text-blue-400',
                                      log.method === 'PUT' && 'bg-yellow-500/20 text-yellow-400',
                                      log.method === 'DELETE' && 'bg-red-500/20 text-red-400',
                                      !['GET', 'POST', 'PUT', 'DELETE'].includes(log.method || '') && 'bg-gray-500/20 text-gray-400'
                                    )}>
                                      {log.method || 'REQ'}
                                    </span>
                                    <span className="font-mono text-xs text-theme-text truncate">
                                      {(log.path || '/')}
                                      {log.query_string ? `?${log.query_string}` : ''}
                                    </span>
                                  </div>
                                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-theme-muted">
                                    <span className="flex items-center gap-1">
                                      <Globe className="w-3 h-3" />
                                      {formatIp(log.client_ip)}
                                    </span>
                                    <span className="flex items-center gap-1">
                                      <Clock className="w-3 h-3" />
                                      {formatTime(log.timestamp)}
                                    </span>
                                  </div>
                                  {log.user_agent && (
                                    <div className="mt-2 truncate text-xs text-theme-muted">
                                      UA: {log.user_agent}
                                    </div>
                                  )}
                                </div>
                                {expanded ? <ChevronUp className="w-4 h-4 text-theme-muted" /> : <ChevronDown className="w-4 h-4 text-theme-muted" />}
                              </div>
                            </button>

                            {expanded && (
                              <div className="border-t border-theme-border bg-theme-card p-3 space-y-3">
                                <div>
                                  <div className="mb-1 text-xs font-medium text-theme-muted">Full URL</div>
                                  <div className="rounded-lg bg-theme-bg p-3 font-mono text-xs text-theme-text break-all">
                                    {formatPath(log)}
                                  </div>
                                </div>

                                {log.user_agent && (
                                  <div>
                                    <div className="mb-1 text-xs font-medium text-theme-muted flex items-center gap-1">
                                      <Users className="w-3.5 h-3.5" />
                                      User-Agent
                                    </div>
                                    <div className="rounded-lg bg-theme-bg p-3 font-mono text-xs text-theme-text break-all">
                                      {log.user_agent}
                                    </div>
                                  </div>
                                )}

                                {log.headers && Object.keys(log.headers).length > 0 && (
                                  <div>
                                    <div className="mb-1 text-xs font-medium text-theme-muted flex items-center gap-1">
                                      <FileCode className="w-3.5 h-3.5" />
                                      Headers
                                    </div>
                                    <div className="rounded-lg bg-theme-bg p-3 font-mono text-xs text-theme-text max-h-40 overflow-auto space-y-1">
                                      {Object.entries(log.headers).map(([key, value]) => (
                                        <div key={key} className="break-all">
                                          <span className="text-theme-primary">{key}:</span> {String(value)}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {log.body && (
                                  <div>
                                    <div className="mb-1 text-xs font-medium text-theme-muted">Body</div>
                                    <pre className="rounded-lg bg-theme-bg p-3 font-mono text-xs text-theme-text whitespace-pre-wrap break-all max-h-40 overflow-auto">
                                      {log.body}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </section>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-theme-muted">
            <div className="text-center">
              <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Select a PoC to view details</p>
              <p className="text-sm mt-2">PoCs can come from backend/app/poc/handlers/ or data/poc-files/</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
