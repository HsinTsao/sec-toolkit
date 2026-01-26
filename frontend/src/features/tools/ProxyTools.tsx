import { useState, useEffect, useCallback, useRef } from 'react'
import { ToolCard, ToolButton } from '@/components/ui/ToolCard'
import { proxyApi, toolsApi, ProxyConfig, ProxyLog } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'
import { Play, Square, Trash2, RefreshCw, Copy, ExternalLink, ChevronDown, ChevronUp, Plus, Frame, Code, Globe, Server, Shield, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

// iframe 代理配置类型
interface IframeProxyConfig {
  proxy_id: string
  target_url: string
  base_url: string
  fake_host: string
  rewrite_urls: boolean
}

export default function ProxyTools() {
  const { addRecentTool } = useToolStore()
  
  // 创建代理表单
  const [localPort, setLocalPort] = useState('8888')
  const [targetUrl, setTargetUrl] = useState('')
  const [fakeHost, setFakeHost] = useState('')
  const [preservePath, setPreservePath] = useState(true)
  const [sslVerify, setSslVerify] = useState(false)
  const [timeout, setTimeout] = useState('30')
  const [customHeaders, setCustomHeaders] = useState('')
  const [autoStart, setAutoStart] = useState(true)
  
  // 代理列表
  const [proxies, setProxies] = useState<ProxyConfig[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  
  // 日志
  const [selectedPort, setSelectedPort] = useState<number | null>(null)
  const [logs, setLogs] = useState<ProxyLog[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [expandedLog, setExpandedLog] = useState<number | null>(null)
  
  // iframe 同域代理
  const [iframeTargetUrl, setIframeTargetUrl] = useState('')
  const [iframeFakeHost, setIframeFakeHost] = useState('')
  const [iframeRewriteUrls, setIframeRewriteUrls] = useState(true)
  const [iframeInjectScript, setIframeInjectScript] = useState('')
  const [iframeCookies, setIframeCookies] = useState('')
  const [iframeProxies, setIframeProxies] = useState<IframeProxyConfig[]>([])
  const [iframeCreating, setIframeCreating] = useState(false)
  const [activeIframeId, setActiveIframeId] = useState<string | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  
  // hosts 文件修改助手
  const [hostsTargetDomain, setHostsTargetDomain] = useState('')
  const [hostsRealIP, setHostsRealIP] = useState('')
  const [hostsLookingUp, setHostsLookingUp] = useState(false)
  
  // 加载代理列表
  const loadProxies = useCallback(async () => {
    try {
      setLoading(true)
      const { data } = await proxyApi.listProxies()
      setProxies(data.proxies)
    } catch {
      // 静默处理
    } finally {
      setLoading(false)
    }
  }, [])
  
  // 加载 iframe 代理列表
  const loadIframeProxies = useCallback(async () => {
    try {
      const { data } = await proxyApi.listIframeProxies()
      setIframeProxies(data.configs)
    } catch {
      // 静默处理
    }
  }, [])
  
  // 初始加载
  useEffect(() => {
    loadProxies()
    loadIframeProxies()
    const interval = setInterval(loadProxies, 5000)
    return () => clearInterval(interval)
  }, [loadProxies, loadIframeProxies])
  
  // 监听 iframe 消息
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.from === 'iframe-proxy') {
        console.log('📨 收到 iframe 消息:', event.data)
        if (event.data.type === 'ready') {
          toast.success(`iframe 已加载: ${event.data.data?.title || '未知页面'}`)
        }
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])
  
  // 创建代理
  const handleCreateProxy = async () => {
    if (!targetUrl.trim()) {
      toast.error('请输入目标 URL')
      return
    }
    if (!fakeHost.trim()) {
      toast.error('请输入伪装的 Host')
      return
    }
    
    const port = parseInt(localPort)
    if (isNaN(port) || port < 1024 || port > 65535) {
      toast.error('端口范围：1024-65535')
      return
    }
    
    // 解析自定义头
    let headers: Record<string, string> = {}
    if (customHeaders.trim()) {
      try {
        customHeaders.split('\n').forEach(line => {
          const [key, ...valueParts] = line.split(':')
          if (key && valueParts.length > 0) {
            headers[key.trim()] = valueParts.join(':').trim()
          }
        })
      } catch {
        toast.error('自定义头格式错误')
        return
      }
    }
    
    setCreating(true)
    try {
      const { data } = await proxyApi.createProxy({
        local_port: port,
        target_url: targetUrl,
        fake_host: fakeHost,
        preserve_path: preservePath,
        ssl_verify: sslVerify,
        timeout: parseInt(timeout) || 30,
        custom_headers: headers,
        auto_start: autoStart
      })
      
      if (data.success) {
        toast.success(data.message)
        loadProxies()
        addRecentTool('proxy')
        setTargetUrl('')
        setFakeHost('')
        setCustomHeaders('')
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }
  
  // 启动代理
  const handleStartProxy = async (port: number) => {
    try {
      const { data } = await proxyApi.startProxy(port)
      toast.success(data.message)
      loadProxies()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '启动失败')
    }
  }
  
  // 停止代理
  const handleStopProxy = async (port: number) => {
    try {
      const { data } = await proxyApi.stopProxy(port)
      toast.success(data.message)
      loadProxies()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '停止失败')
    }
  }
  
  // 删除代理
  const handleDeleteProxy = async (port: number) => {
    if (!confirm(`确定要删除端口 ${port} 的代理吗？`)) return
    
    try {
      const { data } = await proxyApi.deleteProxy(port)
      toast.success(data.message)
      loadProxies()
      if (selectedPort === port) {
        setSelectedPort(null)
        setLogs([])
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '删除失败')
    }
  }
  
  // 加载日志
  const loadLogs = async (port: number) => {
    setSelectedPort(port)
    setLogsLoading(true)
    try {
      const { data } = await proxyApi.getProxyLogs(port, 50)
      setLogs(data.logs)
    } catch {
      toast.error('加载日志失败')
    } finally {
      setLogsLoading(false)
    }
  }
  
  // 创建 iframe 代理
  const handleCreateIframeProxy = async () => {
    if (!iframeTargetUrl.trim()) {
      toast.error('请输入目标 URL')
      return
    }
    
    setIframeCreating(true)
    try {
      const { data } = await proxyApi.createIframeProxy({
        target_url: iframeTargetUrl,
        fake_host: iframeFakeHost || undefined,
        rewrite_urls: iframeRewriteUrls,
        inject_script: iframeInjectScript || undefined,
        cookies: iframeCookies || undefined,
      })
      
      if (data.success) {
        toast.success('iframe 代理创建成功')
        loadIframeProxies()
        addRecentTool('proxy')
        setActiveIframeId(data.proxy_id)
        setIframeTargetUrl('')
        setIframeFakeHost('')
        setIframeInjectScript('')
        setIframeCookies('')
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      toast.error(error.response?.data?.detail || '创建失败')
    } finally {
      setIframeCreating(false)
    }
  }
  
  // 删除 iframe 代理
  const handleDeleteIframeProxy = async (proxyId: string) => {
    try {
      await proxyApi.deleteIframeProxy(proxyId)
      toast.success('已删除')
      loadIframeProxies()
      if (activeIframeId === proxyId) {
        setActiveIframeId(null)
      }
    } catch {
      toast.error('删除失败')
    }
  }
  
  // 获取 iframe DOM
  const getIframeDocument = () => {
    try {
      const iframe = iframeRef.current
      if (iframe?.contentDocument) return iframe.contentDocument
      if (iframe?.contentWindow?.document) return iframe.contentWindow.document
    } catch (e) {
      console.error('无法访问 iframe document:', e)
    }
    return null
  }
  
  // 在 iframe 中执行脚本
  const executeInIframe = (code: string) => {
    try {
      const iframe = iframeRef.current
      if (iframe?.contentWindow) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = (iframe.contentWindow as any).eval(code)
        console.log('执行结果:', result)
        toast.success('脚本执行成功，查看控制台')
        return result
      }
    } catch (e) {
      console.error('执行失败:', e)
      toast.error('执行失败: ' + (e as Error).message)
    }
  }
  
  // DNS 查询
  const lookupRealIP = async () => {
    if (!hostsTargetDomain.trim()) {
      toast.error('请输入目标域名')
      return
    }
    
    let domain = hostsTargetDomain.trim()
    if (domain.includes('://')) domain = domain.split('://')[1]
    domain = domain.split('/')[0].split(':')[0]
    setHostsTargetDomain(domain)
    
    setHostsLookingUp(true)
    try {
      const { data } = await toolsApi.dnsLookup(domain, 'A')
      if (data.error) {
        toast.error(data.error)
      } else if (data.records && data.records.length > 0) {
        setHostsRealIP(data.records[0])
        toast.success(`解析成功: ${data.records[0]}`)
      } else {
        toast.error('未找到 A 记录')
      }
    } catch {
      toast.error('DNS 查询失败')
    } finally {
      setHostsLookingUp(false)
    }
  }
  
  // 生成 hosts 条目
  const generateHostsEntry = () => `127.0.0.1\t${hostsTargetDomain}`
  
  // 获取操作系统
  const getOS = () => {
    const ua = navigator.userAgent.toLowerCase()
    if (ua.includes('mac')) return 'mac'
    if (ua.includes('win')) return 'windows'
    return 'linux'
  }
  
  // 复制到剪贴板
  const copyToClipboard = (text: string, label: string = '已复制') => {
    navigator.clipboard.writeText(text)
    toast.success(label)
  }
  
  // 获取状态码颜色
  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-emerald-400'
    if (status >= 300 && status < 400) return 'text-amber-400'
    if (status >= 400 && status < 500) return 'text-orange-400'
    return 'text-red-400'
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 页面标题和功能介绍 */}
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-theme-text flex items-center gap-3">
            <Globe className="w-7 h-7 text-theme-primary" />
            本地域名代理
          </h1>
          <p className="text-theme-text/70 mt-2 text-base">
            在本地启动代理服务器，转发请求并篡改 Host 头，用于安全测试和漏洞验证
          </p>
        </div>
        
        {/* 功能卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/20 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Server className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-theme-text">Host 伪造</h3>
            </div>
            <p className="text-sm text-theme-text/60">
              篡改请求的 Host 头，绕过基于域名的访问控制
            </p>
          </div>
          
          <div className="bg-gradient-to-br from-violet-500/10 to-violet-600/5 border border-violet-500/20 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center">
                <Frame className="w-5 h-5 text-violet-400" />
              </div>
              <h3 className="font-semibold text-theme-text">iframe 同域</h3>
            </div>
            <p className="text-sm text-theme-text/60">
              让外部页面与本站同域，可操作 iframe 内的 DOM
            </p>
          </div>
          
          <div className="bg-gradient-to-br from-amber-500/10 to-amber-600/5 border border-amber-500/20 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <Shield className="w-5 h-5 text-amber-400" />
              </div>
              <h3 className="font-semibold text-theme-text">CORS 绕过</h3>
            </div>
            <p className="text-sm text-theme-text/60">
              自动添加 CORS 头，绕过浏览器同源策略限制
            </p>
          </div>
        </div>
      </div>
      
      {/* 创建代理 */}
      <ToolCard title="创建代理" icon={<Plus className="w-5 h-5" />} toolKey="proxy-create">
        <div className="space-y-5">
          {/* 核心配置 */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-2">
              <label className="block text-sm font-medium text-theme-text/80 mb-2">本地端口</label>
              <input
                type="number"
                value={localPort}
                onChange={(e) => setLocalPort(e.target.value)}
                placeholder="8888"
                min={1024}
                max={65535}
                className="w-full"
              />
            </div>
            <div className="lg:col-span-5">
              <label className="block text-sm font-medium text-theme-text/80 mb-2">目标 URL</label>
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="https://api.target.com"
                className="w-full"
              />
            </div>
            <div className="lg:col-span-5">
              <label className="block text-sm font-medium text-theme-text/80 mb-2">伪装 Host</label>
              <input
                type="text"
                value={fakeHost}
                onChange={(e) => setFakeHost(e.target.value)}
                placeholder="trusted-origin.com"
                className="w-full"
              />
            </div>
          </div>
          
          {/* 选项 */}
          <div className="flex flex-wrap items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={preservePath}
                onChange={(e) => setPreservePath(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border bg-theme-bg text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm text-theme-text/80 group-hover:text-theme-text">保留路径</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={sslVerify}
                onChange={(e) => setSslVerify(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border bg-theme-bg text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm text-theme-text/80 group-hover:text-theme-text">验证 SSL 证书</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={autoStart}
                onChange={(e) => setAutoStart(e.target.checked)}
                className="w-4 h-4 rounded border-theme-border bg-theme-bg text-theme-primary focus:ring-theme-primary"
              />
              <span className="text-sm text-theme-text/80 group-hover:text-theme-text">自动启动</span>
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-theme-text/80">超时</span>
              <input
                type="number"
                value={timeout}
                onChange={(e) => setTimeout(e.target.value)}
                min={1}
                max={120}
                className="w-20 text-sm"
              />
              <span className="text-sm text-theme-text/60">秒</span>
            </div>
          </div>
          
          {/* 自定义头 */}
          <details className="group">
            <summary className="cursor-pointer text-sm text-theme-text/60 hover:text-theme-text flex items-center gap-2">
              <ChevronDown className="w-4 h-4 group-open:rotate-180 transition-transform" />
              自定义请求头（可选）
            </summary>
            <div className="mt-3">
              <textarea
                value={customHeaders}
                onChange={(e) => setCustomHeaders(e.target.value)}
                placeholder="Header-Name: Header-Value&#10;Another-Header: Value"
                rows={3}
                className="w-full font-mono text-sm"
              />
            </div>
          </details>
          
          <div className="flex items-center gap-4">
            <ToolButton onClick={handleCreateProxy} loading={creating}>
              <Zap className="w-4 h-4 mr-2" />
              创建代理
            </ToolButton>
            
            {targetUrl && fakeHost && (
              <div className="text-sm text-theme-text/60">
                <span className="text-theme-primary">http://127.0.0.1:{localPort}</span>
                <span className="mx-2">→</span>
                <span className="text-emerald-400">{targetUrl}</span>
                <span className="mx-2">（Host: {fakeHost}）</span>
              </div>
            )}
          </div>
        </div>
      </ToolCard>
      
      {/* 代理列表 */}
      <ToolCard 
        title={`运行中的代理 (${proxies.filter(p => p.running).length}/${proxies.length})`} 
        icon={<Server className="w-5 h-5" />}
        toolKey="proxy-list"
      >
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={loadProxies}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-theme-text/60 hover:text-theme-text transition-colors"
            >
              <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
              刷新
            </button>
          </div>
          
          {proxies.length === 0 ? (
            <div className="text-center text-theme-text/50 py-12">
              <Server className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>暂无代理配置</p>
              <p className="text-sm mt-1">在上方创建你的第一个代理</p>
            </div>
          ) : (
            <div className="space-y-3">
              {proxies.map((proxy) => (
                <div
                  key={proxy.local_port}
                  className={cn(
                    'bg-theme-bg rounded-xl p-4 border-2 transition-all',
                    proxy.running 
                      ? 'border-emerald-500/30 shadow-lg shadow-emerald-500/5' 
                      : 'border-theme-border/50'
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-3">
                        <span className={cn(
                          'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold',
                          proxy.running 
                            ? 'bg-emerald-500/20 text-emerald-400' 
                            : 'bg-zinc-500/20 text-zinc-400'
                        )}>
                          <span className={cn(
                            'w-1.5 h-1.5 rounded-full mr-1.5',
                            proxy.running ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-400'
                          )} />
                          {proxy.running ? '运行中' : '已停止'}
                        </span>
                        <span className="font-mono text-lg font-bold text-theme-primary">
                          :{proxy.local_port}
                        </span>
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-3">
                          <span className="text-theme-text/50 w-14">目标</span>
                          <code className="text-theme-text font-mono truncate flex-1">{proxy.target_url}</code>
                          <button
                            onClick={() => copyToClipboard(proxy.target_url)}
                            className="text-theme-text/40 hover:text-theme-text p-1"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-theme-text/50 w-14">Host</span>
                          <code className="text-violet-400 font-mono">{proxy.fake_host}</code>
                          <button
                            onClick={() => copyToClipboard(proxy.fake_host)}
                            className="text-theme-text/40 hover:text-theme-text p-1"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {proxy.running && (
                          <div className="flex items-center gap-3">
                            <span className="text-theme-text/50 w-14">访问</span>
                            <code className="text-emerald-400 font-mono">http://127.0.0.1:{proxy.local_port}</code>
                            <button
                              onClick={() => copyToClipboard(`http://127.0.0.1:${proxy.local_port}`)}
                              className="text-theme-text/40 hover:text-theme-text p-1"
                            >
                              <Copy className="w-3.5 h-3.5" />
                            </button>
                            <a
                              href={`http://127.0.0.1:${proxy.local_port}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-theme-text/40 hover:text-theme-text p-1"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => loadLogs(proxy.local_port)}
                        className="px-3 py-2 text-xs font-medium bg-theme-card hover:bg-theme-border rounded-lg transition-colors text-theme-text/70 hover:text-theme-text"
                      >
                        日志 ({proxy.log_count || 0})
                      </button>
                      {proxy.running ? (
                        <button
                          onClick={() => handleStopProxy(proxy.local_port)}
                          className="p-2.5 text-amber-400 hover:bg-amber-500/20 rounded-lg transition-colors"
                          title="停止"
                        >
                          <Square className="w-4 h-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleStartProxy(proxy.local_port)}
                          className="p-2.5 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors"
                          title="启动"
                        >
                          <Play className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleDeleteProxy(proxy.local_port)}
                        className="p-2.5 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ToolCard>
      
      {/* 请求日志 */}
      {selectedPort !== null && (
        <ToolCard title={`请求日志 - 端口 ${selectedPort}`} toolKey="proxy-logs">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-theme-text/60">
                显示最近 {logs.length} 条请求
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => loadLogs(selectedPort)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-theme-text/60 hover:text-theme-text transition-colors"
                >
                  <RefreshCw className={cn('w-4 h-4', logsLoading && 'animate-spin')} />
                  刷新
                </button>
                <button
                  onClick={() => { setSelectedPort(null); setLogs([]) }}
                  className="px-3 py-1.5 text-sm text-theme-text/60 hover:text-theme-text transition-colors"
                >
                  关闭
                </button>
              </div>
            </div>
            
            {logs.length === 0 ? (
              <div className="text-center text-theme-text/50 py-8">暂无请求记录</div>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {logs.map((log, index) => (
                  <div
                    key={index}
                    className="bg-theme-bg rounded-lg border border-theme-border overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedLog(expandedLog === index ? null : index)}
                      className="w-full flex items-center justify-between p-3 text-left hover:bg-theme-card/50 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={cn('font-mono text-sm font-bold', getStatusColor(log.status_code))}>
                          {log.status_code}
                        </span>
                        <span className="px-2 py-0.5 bg-theme-border rounded text-xs font-semibold text-theme-text">
                          {log.method}
                        </span>
                        <code className="text-sm text-theme-text/80 truncate">{log.path}</code>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-theme-text/50">{log.response_time}ms</span>
                        <span className="text-xs text-theme-text/50">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        {expandedLog === index ? (
                          <ChevronUp className="w-4 h-4 text-theme-text/40" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-theme-text/40" />
                        )}
                      </div>
                    </button>
                    
                    {expandedLog === index && (
                      <div className="border-t border-theme-border p-4 space-y-3 text-sm bg-theme-card/30">
                        <div className="flex gap-3">
                          <span className="text-theme-text/50 w-20">目标 URL</span>
                          <code className="text-theme-text">{log.target_url}</code>
                        </div>
                        <div className="flex gap-3">
                          <span className="text-theme-text/50 w-20">伪装 Host</span>
                          <code className="text-violet-400">{log.fake_host}</code>
                        </div>
                        {log.error && (
                          <div className="flex gap-3 text-red-400">
                            <span className="text-theme-text/50 w-20">错误</span>
                            <span>{log.error}</span>
                          </div>
                        )}
                        
                        <details className="group">
                          <summary className="cursor-pointer text-theme-text/50 hover:text-theme-text">请求头</summary>
                          <pre className="mt-2 p-3 bg-theme-bg rounded-lg text-xs overflow-x-auto text-theme-text/70">
                            {JSON.stringify(log.request_headers, null, 2)}
                          </pre>
                        </details>
                        
                        <details className="group">
                          <summary className="cursor-pointer text-theme-text/50 hover:text-theme-text">响应头</summary>
                          <pre className="mt-2 p-3 bg-theme-bg rounded-lg text-xs overflow-x-auto text-theme-text/70">
                            {JSON.stringify(log.response_headers, null, 2)}
                          </pre>
                        </details>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </ToolCard>
      )}
      
      {/* iframe 同域代理 */}
      <ToolCard title="iframe 同域代理" icon={<Frame className="w-5 h-5" />} toolKey="iframe-proxy">
        <div className="space-y-5">
          <div className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border border-violet-500/20 rounded-xl p-4">
            <h4 className="font-semibold text-theme-text mb-2 flex items-center gap-2">
              <Frame className="w-4 h-4 text-violet-400" />
              核心功能
            </h4>
            <p className="text-sm text-theme-text/70">
              通过后端代理加载外部页面，使 iframe 内容与本站同域。这样你可以：
            </p>
            <ul className="mt-2 space-y-1 text-sm text-theme-text/70">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                直接操作 iframe 内的 DOM 元素
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                在 iframe 中执行任意 JavaScript
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                实现无限制的 postMessage 通信
              </li>
            </ul>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-theme-text/80 mb-2">目标页面 URL</label>
              <input
                type="text"
                value={iframeTargetUrl}
                onChange={(e) => setIframeTargetUrl(e.target.value)}
                placeholder="https://example.com/page"
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-theme-text/80 mb-2">伪装 Host（可选）</label>
              <input
                type="text"
                value={iframeFakeHost}
                onChange={(e) => setIframeFakeHost(e.target.value)}
                placeholder="留空则使用目标域名"
                className="w-full"
              />
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-theme-text/80 mb-2">
              目标站点 Cookie（可选）
            </label>
            <textarea
              value={iframeCookies}
              onChange={(e) => setIframeCookies(e.target.value)}
              placeholder="session=abc123; token=xyz789"
              rows={2}
              className="w-full font-mono text-sm"
            />
            <p className="text-xs text-theme-text/50 mt-1">
              从浏览器开发者工具复制目标站点的 Cookie
            </p>
          </div>
          
          <details className="group">
            <summary className="cursor-pointer text-sm text-theme-text/60 hover:text-theme-text flex items-center gap-2">
              <ChevronDown className="w-4 h-4 group-open:rotate-180 transition-transform" />
              高级选项
            </summary>
            <div className="mt-3 space-y-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={iframeRewriteUrls}
                  onChange={(e) => setIframeRewriteUrls(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-theme-text/80">重写页面中的相对 URL</span>
              </label>
              <div>
                <label className="block text-sm text-theme-text/60 mb-2">注入脚本</label>
                <textarea
                  value={iframeInjectScript}
                  onChange={(e) => setIframeInjectScript(e.target.value)}
                  placeholder="console.log('Hello from injected script!');"
                  rows={3}
                  className="w-full font-mono text-sm"
                />
              </div>
            </div>
          </details>
          
          <ToolButton onClick={handleCreateIframeProxy} loading={iframeCreating}>
            <Frame className="w-4 h-4 mr-2" />
            创建 iframe 代理
          </ToolButton>
          
          {/* iframe 代理列表 */}
          {iframeProxies.length > 0 && (
            <div className="border-t border-theme-border pt-5 mt-5">
              <h4 className="text-sm font-medium text-theme-text mb-3">已创建的代理</h4>
              <div className="space-y-2">
                {iframeProxies.map((cfg) => (
                  <div
                    key={cfg.proxy_id}
                    className={cn(
                      'bg-theme-bg rounded-lg p-3 border-2 transition-all cursor-pointer',
                      activeIframeId === cfg.proxy_id 
                        ? 'border-violet-500/50' 
                        : 'border-theme-border/50 hover:border-violet-500/30'
                    )}
                    onClick={() => setActiveIframeId(cfg.proxy_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <code className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded font-semibold">
                            {cfg.proxy_id}
                          </code>
                          <span className="text-sm text-theme-text truncate">{cfg.target_url}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-theme-text/50">
                          <span>src:</span>
                          <code className="text-theme-primary">/api/proxy/iframe/{cfg.proxy_id}</code>
                          <button
                            onClick={(e) => { e.stopPropagation(); copyToClipboard(`/api/proxy/iframe/${cfg.proxy_id}`) }}
                            className="hover:text-theme-text"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteIframeProxy(cfg.proxy_id) }}
                        className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* iframe 预览 */}
          {activeIframeId && (
            <div className="border-t border-theme-border pt-5 mt-5">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-theme-text">iframe 预览</h4>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      const doc = getIframeDocument()
                      if (doc) {
                        console.log('iframe document:', doc)
                        console.log('iframe body:', doc.body?.innerHTML?.substring(0, 500))
                        toast.success('已输出到控制台')
                      } else {
                        toast.error('无法访问 iframe document')
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-theme-border hover:bg-violet-500/20 rounded-lg transition-colors text-theme-text/70 hover:text-theme-text"
                  >
                    <Code className="w-3.5 h-3.5" />
                    获取 DOM
                  </button>
                  <button
                    onClick={() => {
                      const code = prompt('输入要执行的 JavaScript:')
                      if (code) executeInIframe(code)
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-theme-border hover:bg-violet-500/20 rounded-lg transition-colors text-theme-text/70 hover:text-theme-text"
                  >
                    <Play className="w-3.5 h-3.5" />
                    执行脚本
                  </button>
                </div>
              </div>
              <div className="bg-white rounded-xl border border-theme-border overflow-hidden">
                <iframe
                  ref={iframeRef}
                  src={`/api/proxy/iframe/${activeIframeId}`}
                  className="w-full h-[400px]"
                  title="Proxy iframe"
                />
              </div>
              <p className="text-xs text-theme-text/50 mt-2">
                💡 打开浏览器控制台，可操作 <code className="text-theme-primary">document.querySelector('iframe').contentDocument</code>
              </p>
            </div>
          )}
        </div>
      </ToolCard>
      
      {/* Hosts 文件助手 */}
      <ToolCard title="Hosts 文件助手" icon={<Shield className="w-5 h-5" />} toolKey="hosts-helper">
        <div className="space-y-5">
          <div className="bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border border-emerald-500/20 rounded-xl p-4">
            <h4 className="font-semibold text-theme-text mb-2">最强方案：修改 Hosts 文件</h4>
            <p className="text-sm text-theme-text/70">
              让浏览器认为本地就是目标站点，<strong className="text-emerald-400">Cookie 自动携带，完全绕过 SameSite 限制</strong>
            </p>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-theme-text/80 mb-2">目标域名</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={hostsTargetDomain}
                  onChange={(e) => setHostsTargetDomain(e.target.value)}
                  placeholder="target.com"
                  className="flex-1"
                />
                <ToolButton onClick={lookupRealIP} loading={hostsLookingUp}>
                  查询 IP
                </ToolButton>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-theme-text/80 mb-2">真实 IP（备用）</label>
              <input
                type="text"
                value={hostsRealIP}
                onChange={(e) => setHostsRealIP(e.target.value)}
                placeholder="点击查询或手动输入"
                className="w-full"
              />
            </div>
          </div>
          
          {hostsTargetDomain && (
            <div className="space-y-5 border-t border-theme-border pt-5">
              <div>
                <label className="block text-sm font-medium text-theme-text/80 mb-2">添加到 hosts 文件</label>
                <div className="flex items-center gap-3">
                  <code className="flex-1 bg-theme-bg border border-theme-border p-3 rounded-lg font-mono text-emerald-400">
                    {generateHostsEntry()}
                  </code>
                  <button
                    onClick={() => copyToClipboard(generateHostsEntry(), 'hosts 条目已复制')}
                    className="p-3 bg-theme-border hover:bg-theme-primary/20 rounded-lg transition-colors"
                  >
                    <Copy className="w-5 h-5" />
                  </button>
                </div>
              </div>
              
              <div className="bg-theme-bg rounded-xl p-5 border border-theme-border">
                <h4 className="font-medium text-theme-text mb-4">操作步骤</h4>
                
                {getOS() === 'mac' && (
                  <div className="space-y-4 text-sm">
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">1</span>
                      <div className="flex-1">
                        <p className="text-theme-text mb-2">编辑 hosts 文件：</p>
                        <div className="flex items-center gap-2">
                          <code className="bg-black/30 px-3 py-2 rounded-lg text-emerald-400 font-mono text-xs">
                            sudo nano /etc/hosts
                          </code>
                          <button onClick={() => copyToClipboard('sudo nano /etc/hosts')} className="text-theme-text/40 hover:text-theme-text">
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">2</span>
                      <p className="text-theme-text">在文件末尾添加上面的 hosts 条目</p>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">3</span>
                      <div className="flex-1">
                        <p className="text-theme-text mb-2">刷新 DNS 缓存：</p>
                        <div className="flex items-center gap-2">
                          <code className="bg-black/30 px-3 py-2 rounded-lg text-emerald-400 font-mono text-xs">
                            sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
                          </code>
                          <button onClick={() => copyToClipboard('sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder')} className="text-theme-text/40 hover:text-theme-text">
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {getOS() === 'windows' && (
                  <div className="space-y-4 text-sm">
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">1</span>
                      <div className="flex-1">
                        <p className="text-theme-text mb-2">以管理员身份运行记事本，打开：</p>
                        <div className="flex items-center gap-2">
                          <code className="bg-black/30 px-3 py-2 rounded-lg text-emerald-400 font-mono text-xs">
                            C:\Windows\System32\drivers\etc\hosts
                          </code>
                          <button onClick={() => copyToClipboard('C:\\Windows\\System32\\drivers\\etc\\hosts')} className="text-theme-text/40 hover:text-theme-text">
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">2</span>
                      <p className="text-theme-text">添加 hosts 条目并保存</p>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">3</span>
                      <div className="flex-1">
                        <p className="text-theme-text mb-2">刷新 DNS（管理员 CMD）：</p>
                        <div className="flex items-center gap-2">
                          <code className="bg-black/30 px-3 py-2 rounded-lg text-emerald-400 font-mono text-xs">
                            ipconfig /flushdns
                          </code>
                          <button onClick={() => copyToClipboard('ipconfig /flushdns')} className="text-theme-text/40 hover:text-theme-text">
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {getOS() === 'linux' && (
                  <div className="space-y-4 text-sm">
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">1</span>
                      <div className="flex-1">
                        <p className="text-theme-text mb-2">编辑 hosts 文件：</p>
                        <div className="flex items-center gap-2">
                          <code className="bg-black/30 px-3 py-2 rounded-lg text-emerald-400 font-mono text-xs">
                            sudo nano /etc/hosts
                          </code>
                          <button onClick={() => copyToClipboard('sudo nano /etc/hosts')} className="text-theme-text/40 hover:text-theme-text">
                            <Copy className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="w-6 h-6 rounded-full bg-theme-primary text-theme-bg flex items-center justify-center text-xs font-bold flex-shrink-0">2</span>
                      <p className="text-theme-text">添加 hosts 条目并保存</p>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
                <h4 className="font-medium text-amber-400 mb-2">⚠️ 配置本地代理</h4>
                <p className="text-sm text-theme-text/70 mb-3">
                  修改 hosts 后，需要启动代理接收请求并转发到真实目标：
                </p>
                <ul className="text-sm text-theme-text/70 space-y-1">
                  <li>• 本地端口：<code className="text-theme-primary">80</code>（HTTP）或 <code className="text-theme-primary">443</code>（HTTPS）</li>
                  <li>• 目标 URL：<code className="text-theme-primary">http://{hostsRealIP || '真实IP'}</code></li>
                  <li>• 伪装 Host：<code className="text-theme-primary">{hostsTargetDomain}</code></li>
                </ul>
                <p className="text-xs text-amber-400/70 mt-2">💡 监听 80/443 端口需要管理员权限运行后端</p>
              </div>
              
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                <p className="text-sm text-red-400 font-medium">
                  🔄 测试完成后记得删除 hosts 条目！否则会影响正常访问该网站。
                </p>
              </div>
            </div>
          )}
        </div>
      </ToolCard>
    </div>
  )
}
