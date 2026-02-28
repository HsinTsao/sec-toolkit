import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import {
  Play,
  Square,
  Trash2,
  Copy,
  Check,
  Radio,
  Terminal as TerminalIcon,
  Code,
  ArrowUpCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Monitor,
  X,
} from 'lucide-react'
import { cn, copyToClipboard } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'
import api from '@/lib/api'

// ==================== 类型定义 ====================

interface ListenerInfo {
  port: number
  started_at: string | null
  session_count: number
  active_sessions: number
}

interface SessionInfo {
  id: string
  client_ip: string
  client_port: number
  listener_port: number
  connected_at: string
  ws_clients: number
  is_alive: boolean
}

interface PayloadTemplate {
  id: string
  name: string
  platform: string
  command_template: string
}

interface UpgradeCommand {
  name: string
  command?: string
  steps?: string[]
  description: string
}

// ==================== 复制按钮 ====================

function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await copyToClipboard(text)
    setCopied(true)
    toast.success('已复制')
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      className={cn('p-1 rounded hover:bg-theme-bg/50 text-theme-muted hover:text-theme-primary transition-colors', className)}
      title="复制"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  )
}

// ==================== 终端组件 ====================

function ShellTerminal({
  sessionId,
  onClose,
}: {
  sessionId: string
  onClose: () => void
}) {
  const termRef = useRef<HTMLDivElement>(null)
  const termInstance = useRef<Terminal | null>(null)
  const fitAddon = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const { token } = useAuthStore()

  useEffect(() => {
    if (!termRef.current) return

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1a1b26',
        foreground: '#a9b1d6',
        cursor: '#c0caf5',
        selectionBackground: '#33467c',
        black: '#32344a',
        red: '#f7768e',
        green: '#9ece6a',
        yellow: '#e0af68',
        blue: '#7aa2f7',
        magenta: '#ad8ee6',
        cyan: '#449dab',
        white: '#787c99',
        brightBlack: '#444b6a',
        brightRed: '#ff7a93',
        brightGreen: '#b9f27c',
        brightYellow: '#ff9e64',
        brightBlue: '#7da6ff',
        brightMagenta: '#bb9af7',
        brightCyan: '#0db9d7',
        brightWhite: '#acb0d0',
      },
      scrollback: 5000,
      convertEol: true,
    })

    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(termRef.current)
    fit.fit()

    termInstance.current = term
    fitAddon.current = fit

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/revshell/sessions/${sessionId}/terminal?token=${token}`
    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      term.writeln('\x1b[32m[已连接到会话 ' + sessionId + ']\x1b[0m')
    }

    ws.onmessage = (event) => {
      const data = event.data instanceof ArrayBuffer
        ? new TextDecoder().decode(event.data)
        : event.data
      term.write(data)
    }

    ws.onclose = (event) => {
      term.writeln('')
      term.writeln(`\x1b[31m[连接已断开: ${event.reason || 'closed'}]\x1b[0m`)
    }

    ws.onerror = () => {
      term.writeln('\x1b[31m[WebSocket 连接错误]\x1b[0m')
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data))
      }
    })

    term.onBinary((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        const buffer = new Uint8Array(data.length)
        for (let i = 0; i < data.length; i++) {
          buffer[i] = data.charCodeAt(i)
        }
        ws.send(buffer)
      }
    })

    const handleResize = () => fit.fit()
    window.addEventListener('resize', handleResize)

    term.focus()

    return () => {
      window.removeEventListener('resize', handleResize)
      ws.close()
      term.dispose()
    }
  }, [sessionId, token])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-[#1a1b26] border-b border-gray-700 rounded-t-lg">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <TerminalIcon className="w-4 h-4" />
          <span>会话 {sessionId}</span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-700 rounded transition-colors text-gray-400 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div ref={termRef} className="flex-1 min-h-[400px] rounded-b-lg overflow-hidden" />
    </div>
  )
}

// ==================== 主页面 ====================

export default function RevShellTools() {
  const [activeTab, setActiveTab] = useState<'listener' | 'payload' | 'upgrade'>('listener')
  const [listeners, setListeners] = useState<ListenerInfo[]>([])
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [newPort, setNewPort] = useState('4444')
  const [loading, setLoading] = useState(false)

  // Payload 相关
  const [payloadIp, setPayloadIp] = useState('')
  const [payloadPort, setPayloadPort] = useState('4444')
  const [payloadTemplates, setPayloadTemplates] = useState<PayloadTemplate[]>([])
  const [generatedPayloads, setGeneratedPayloads] = useState<Array<{ template_id: string; name: string; platform: string; command: string }>>([])
  const [filterPlatform, setFilterPlatform] = useState<string>('all')

  // Upgrade 相关
  const [upgradeCommands, setUpgradeCommands] = useState<UpgradeCommand[]>([])

  // 折叠状态
  const [expandedPayload, setExpandedPayload] = useState<string | null>(null)

  const pollRef = useRef<number | null>(null)

  const fetchListeners = useCallback(async () => {
    try {
      const { data } = await api.get('/revshell/listeners')
      setListeners(data.listeners)
    } catch {
      // 静默失败
    }
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      const { data } = await api.get('/revshell/sessions')
      setSessions(data.sessions)
    } catch {
      // 静默失败
    }
  }, [])

  const fetchData = useCallback(async () => {
    await Promise.all([fetchListeners(), fetchSessions()])
  }, [fetchListeners, fetchSessions])

  // 轮询监听和会话状态
  useEffect(() => {
    fetchData()
    pollRef.current = window.setInterval(fetchData, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchData])

  // 加载 Payload 模板和 Upgrade 命令
  useEffect(() => {
    const load = async () => {
      try {
        const [templatesRes, upgradeRes] = await Promise.all([
          api.get('/revshell/payloads'),
          api.get('/revshell/payloads/upgrade-commands'),
        ])
        setPayloadTemplates(templatesRes.data.templates)
        setUpgradeCommands(upgradeRes.data.commands)
      } catch {
        // 静默失败
      }
    }
    load()
  }, [])

  const handleStartListener = async () => {
    const port = parseInt(newPort)
    if (isNaN(port) || port < 1024 || port > 65535) {
      toast.error('端口必须在 1024-65535 之间')
      return
    }
    setLoading(true)
    try {
      await api.post('/revshell/listeners', { port })
      toast.success(`监听已启动: 端口 ${port}`)
      await fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '启动监听失败')
    } finally {
      setLoading(false)
    }
  }

  const handleStopListener = async (port: number) => {
    try {
      await api.delete(`/revshell/listeners/${port}`)
      toast.success(`监听已停止: 端口 ${port}`)
      await fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '停止监听失败')
    }
  }

  const handleKillSession = async (sessionId: string) => {
    try {
      await api.delete(`/revshell/sessions/${sessionId}`)
      toast.success(`会话 ${sessionId} 已断开`)
      if (activeSessionId === sessionId) setActiveSessionId(null)
      await fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '断开会话失败')
    }
  }

  const handleGeneratePayloads = async () => {
    if (!payloadIp.trim()) {
      toast.error('请输入 IP 地址')
      return
    }
    const port = parseInt(payloadPort)
    if (isNaN(port) || port < 1 || port > 65535) {
      toast.error('端口不合法')
      return
    }
    try {
      const { data } = await api.post('/revshell/payloads/generate-all', { ip: payloadIp.trim(), port })
      setGeneratedPayloads(data.payloads)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '生成失败')
    }
  }

  const platforms = ['all', ...new Set(payloadTemplates.map(t => t.platform))]
  const filteredPayloads = filterPlatform === 'all'
    ? generatedPayloads
    : generatedPayloads.filter(p => p.platform === filterPlatform)

  const tabs = [
    { id: 'listener' as const, name: '监听管理', icon: Radio },
    { id: 'payload' as const, name: 'Payload 生成', icon: Code },
    { id: 'upgrade' as const, name: 'Shell 升级', icon: ArrowUpCircle },
  ]

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 顶部标题 */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
          <Monitor className="w-5 h-5 text-red-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-theme-text">反弹 Shell</h2>
          <p className="text-sm text-theme-muted">监听端口接收反弹 Shell 连接，在浏览器中交互</p>
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-1 p-1 bg-theme-bg rounded-lg w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              activeTab === tab.id
                ? 'bg-theme-card text-theme-primary shadow-sm'
                : 'text-theme-muted hover:text-theme-text'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.name}
          </button>
        ))}
      </div>

      {/* ==================== 监听管理 ==================== */}
      {activeTab === 'listener' && (
        <div className="space-y-4">
          {/* 启动监听 */}
          <div className="card">
            <h3 className="text-lg font-semibold text-theme-text mb-4">启动监听</h3>
            <div className="flex items-end gap-3">
              <div className="flex-1 max-w-xs">
                <label className="block text-sm text-theme-muted mb-2">监听端口</label>
                <input
                  type="number"
                  value={newPort}
                  onChange={e => setNewPort(e.target.value)}
                  placeholder="4444"
                  min={1024}
                  max={65535}
                  className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-2 focus:outline-none focus:border-theme-primary font-mono"
                />
              </div>
              <button
                onClick={handleStartListener}
                disabled={loading}
                className="btn btn-primary flex items-center gap-2"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                启动监听
              </button>
            </div>
          </div>

          {/* 活跃监听列表 */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-theme-text">活跃监听</h3>
              <button onClick={fetchData} className="p-2 hover:bg-theme-bg rounded-lg text-theme-muted hover:text-theme-text transition-colors">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            {listeners.length === 0 ? (
              <p className="text-theme-muted text-sm py-8 text-center">暂无活跃的监听</p>
            ) : (
              <div className="space-y-2">
                {listeners.map(l => (
                  <div key={l.port} className="flex items-center justify-between p-3 bg-theme-bg rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      <span className="font-mono text-sm text-theme-text">0.0.0.0:{l.port}</span>
                      <span className="text-xs text-theme-muted">
                        {l.active_sessions} 个活跃会话 / 共 {l.session_count} 个连接
                      </span>
                    </div>
                    <button
                      onClick={() => handleStopListener(l.port)}
                      className="flex items-center gap-1 px-3 py-1 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                    >
                      <Square className="w-3 h-3" />
                      停止
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 会话列表 */}
          <div className="card">
            <h3 className="text-lg font-semibold text-theme-text mb-4">反弹 Shell 会话</h3>
            {sessions.length === 0 ? (
              <p className="text-theme-muted text-sm py-8 text-center">等待连接中...</p>
            ) : (
              <div className="space-y-2">
                {sessions.map(s => (
                  <div
                    key={s.id}
                    className={cn(
                      'flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer',
                      activeSessionId === s.id
                        ? 'bg-theme-primary/5 border-theme-primary/30'
                        : 'bg-theme-bg border-transparent hover:border-theme-border'
                    )}
                    onClick={() => setActiveSessionId(s.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn('w-2 h-2 rounded-full', s.is_alive ? 'bg-green-400' : 'bg-gray-500')} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-medium text-theme-text">{s.client_ip}:{s.client_port}</span>
                          <span className="text-xs px-1.5 py-0.5 bg-theme-primary/10 text-theme-primary rounded">
                            {s.id}
                          </span>
                        </div>
                        <div className="text-xs text-theme-muted mt-0.5">
                          端口 {s.listener_port} · {new Date(s.connected_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={e => { e.stopPropagation(); setActiveSessionId(s.id) }}
                        className="flex items-center gap-1 px-3 py-1 text-sm text-theme-primary hover:bg-theme-primary/10 rounded-lg transition-colors"
                      >
                        <TerminalIcon className="w-3 h-3" />
                        终端
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleKillSession(s.id) }}
                        className="flex items-center gap-1 px-3 py-1 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                        断开
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 终端 */}
          {activeSessionId && (
            <div className="card p-0 overflow-hidden">
              <ShellTerminal
                key={activeSessionId}
                sessionId={activeSessionId}
                onClose={() => setActiveSessionId(null)}
              />
            </div>
          )}
        </div>
      )}

      {/* ==================== Payload 生成 ==================== */}
      {activeTab === 'payload' && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-lg font-semibold text-theme-text mb-4">生成反弹 Shell Payload</h3>
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm text-theme-muted mb-2">目标回连 IP</label>
                <input
                  type="text"
                  value={payloadIp}
                  onChange={e => setPayloadIp(e.target.value)}
                  placeholder="例如: 10.0.0.1"
                  className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-2 focus:outline-none focus:border-theme-primary font-mono"
                />
              </div>
              <div className="w-32">
                <label className="block text-sm text-theme-muted mb-2">端口</label>
                <input
                  type="number"
                  value={payloadPort}
                  onChange={e => setPayloadPort(e.target.value)}
                  placeholder="4444"
                  className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-2 focus:outline-none focus:border-theme-primary font-mono"
                />
              </div>
              <button onClick={handleGeneratePayloads} className="btn btn-primary">
                生成全部
              </button>
            </div>
          </div>

          {generatedPayloads.length > 0 && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-theme-text">
                  Payload 列表
                  <span className="ml-2 text-sm font-normal text-theme-muted">({filteredPayloads.length})</span>
                </h3>
                <div className="flex items-center gap-2">
                  {platforms.map(p => (
                    <button
                      key={p}
                      onClick={() => setFilterPlatform(p)}
                      className={cn(
                        'px-3 py-1 text-xs rounded-full transition-colors',
                        filterPlatform === p
                          ? 'bg-theme-primary text-white'
                          : 'bg-theme-bg text-theme-muted hover:text-theme-text'
                      )}
                    >
                      {p === 'all' ? '全部' : p}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                {filteredPayloads.map(p => (
                  <div key={p.template_id} className="bg-theme-bg rounded-lg overflow-hidden">
                    <div
                      className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-theme-bg/80"
                      onClick={() => setExpandedPayload(expandedPayload === p.template_id ? null : p.template_id)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-theme-text">{p.name}</span>
                        <span className="text-xs px-1.5 py-0.5 bg-theme-primary/10 text-theme-primary rounded">
                          {p.platform}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <CopyButton text={p.command} />
                        {expandedPayload === p.template_id
                          ? <ChevronUp className="w-4 h-4 text-theme-muted" />
                          : <ChevronDown className="w-4 h-4 text-theme-muted" />}
                      </div>
                    </div>
                    {expandedPayload === p.template_id && (
                      <div className="px-3 pb-3">
                        <pre className="text-xs font-mono text-green-400 bg-gray-900/50 rounded p-3 overflow-x-auto whitespace-pre-wrap break-all">
                          {p.command}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== Shell 升级 ==================== */}
      {activeTab === 'upgrade' && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="text-lg font-semibold text-theme-text mb-2">Shell 升级指南</h3>
            <p className="text-sm text-theme-muted mb-4">
              获取反弹 Shell 后，通常是一个简单的非交互式 Shell。以下命令可以帮助升级到完整的交互式 TTY。
            </p>
            <div className="space-y-4">
              {upgradeCommands.map((cmd, idx) => (
                <div key={idx} className="bg-theme-bg rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h4 className="text-sm font-semibold text-theme-text">{cmd.name}</h4>
                      <p className="text-xs text-theme-muted">{cmd.description}</p>
                    </div>
                    {cmd.command && <CopyButton text={cmd.command} />}
                  </div>
                  {cmd.command && (
                    <pre className="text-xs font-mono text-green-400 bg-gray-900/50 rounded p-3 mt-2">
                      {cmd.command}
                    </pre>
                  )}
                  {cmd.steps && (
                    <div className="mt-2 space-y-1">
                      {cmd.steps.map((step, stepIdx) => (
                        <div key={stepIdx} className="flex items-start gap-2">
                          <span className="text-xs text-theme-muted font-mono mt-0.5 w-4 shrink-0">{stepIdx + 1}.</span>
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <pre className="text-xs font-mono text-green-400 bg-gray-900/50 rounded px-2 py-1 flex-1 overflow-x-auto">
                              {step}
                            </pre>
                            {!step.startsWith('#') && <CopyButton text={step} />}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
