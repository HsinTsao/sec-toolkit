import { useState, useMemo } from 'react'
import { ToolCard, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'
import { 
  CheckCircle, XCircle, Clock, FileType, AlertCircle, Globe, Search, 
  ChevronDown, ChevronRight, AlertTriangle, CheckSquare, Square, 
  MinusSquare, Play, Download
} from 'lucide-react'

// 资源类型选项
const resourceTypeOptions = [
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'audio', label: '音频' },
  { value: 'script', label: '脚本' },
  { value: 'stylesheet', label: '样式表' },
  { value: 'font', label: '字体' },
  { value: 'document', label: '文档' },
  { value: 'other', label: '其他' },
]

// 资源项类型定义
interface ResourceItem {
  url: string
  resource_type: string
  tag?: string
  attr?: string
  source_url?: string
  size?: number
  size_formatted?: string
  size_error?: string
  content_type?: string
}

// 资源测试结果类型定义
interface ResourceResult {
  url: string
  resource_type: string
  status_code: number | null
  status_text: string
  content_type: string | null
  content_length: number | null
  response_time_ms: number | null
  error: string | null
  accessible: boolean
  matched_id?: string
  source_url?: string
  // 增强测试字段
  enhanced_test?: boolean
  content_valid?: boolean | null
  content_type_match?: boolean | null
  magic_bytes_match?: boolean | null
  detected_type?: string | null
  warnings?: string[]
}

interface ExtractResult {
  total_sites: number
  input_urls?: number  // 原始输入数量
  deduplicated?: number  // 去重数量
  success_sites: number
  failed_sites: number
  total_resources: number
  total_size?: number
  total_size_formatted?: string
  sites: Array<{
    target_url: string
    total_resources: number
    total_size?: number
    total_size_formatted?: string
    resources: ResourceItem[]
    summary_by_type: Record<string, number>
    error: string | null
  }>
  all_resources: ResourceItem[]
  summary_by_type: Record<string, number>
  error: string | null
}

interface TestResult {
  total: number
  accessible_count: number
  inaccessible_count: number
  warning_count: number
  enhanced_mode: boolean
  results: ResourceResult[]
  summary_by_type: Record<string, { total: number; accessible: number; inaccessible: number; with_warnings: number }>
  error: string | null
}

export default function CrawlerTools() {
  const { addRecentTool } = useToolStore()
  
  // 步骤状态: 'input' | 'select' | 'result'
  const [step, setStep] = useState<'input' | 'select' | 'result'>('input')
  
  // 输入状态
  const [crawlUrls, setCrawlUrls] = useState('')
  const [filterIds, setFilterIds] = useState('')
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [timeout, setTimeout] = useState(10)
  const [concurrency, setConcurrency] = useState(10)
  const [enhancedTest, setEnhancedTest] = useState(false)
  const [useBrowser, setUseBrowser] = useState(false)  // 浏览器渲染模式
  const [browserWaitTime, setBrowserWaitTime] = useState(3)  // 浏览器等待时间
  const [fetchSize, setFetchSize] = useState(false)  // 是否获取文件大小
  
  // 提取结果
  const [extractResult, setExtractResult] = useState<ExtractResult | null>(null)
  const [extractLoading, setExtractLoading] = useState(false)
  
  // 选择状态
  const [selectedResources, setSelectedResources] = useState<Set<string>>(new Set())
  
  // 测试结果
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [testLoading, setTestLoading] = useState(false)
  
  // 显示模式
  const [displayMode, setDisplayMode] = useState<'all' | 'filtered' | 'inaccessible' | 'warnings'>('all')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  
  // 解析过滤 ID
  const filterIdList = useMemo(() => {
    return filterIds.trim() 
      ? filterIds.split(/[\n,;]+/).map(id => id.trim()).filter(Boolean)
      : []
  }, [filterIds])
  
  // 根据 ID 过滤的资源
  const filteredByIds = useMemo(() => {
    if (!extractResult || filterIdList.length === 0) return []
    return extractResult.all_resources.filter(r => 
      filterIdList.some(id => r.url.includes(id))
    )
  }, [extractResult, filterIdList])
  
  // ID 匹配统计
  const idMatchSummary = useMemo(() => {
    if (!extractResult || filterIdList.length === 0) return {}
    const summary: Record<string, { found: boolean; count: number; resources: ResourceItem[] }> = {}
    for (const id of filterIdList) {
      const matched = extractResult.all_resources.filter(r => r.url.includes(id))
      summary[id] = {
        found: matched.length > 0,
        count: matched.length,
        resources: matched
      }
    }
    return summary
  }, [extractResult, filterIdList])
  
  // 格式化文件大小
  const formatSize = (bytes: number | null) => {
    if (bytes === null) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }
  
  // 提取资源
  const handleExtract = async () => {
    const urls = crawlUrls.split('\n').map(u => u.trim()).filter(Boolean)
    if (urls.length === 0) {
      toast.error('请输入至少一个目标网页 URL')
      return
    }
    
    setExtractLoading(true)
    setExtractResult(null)
    setSelectedResources(new Set())
    setTestResult(null)
    
    try {
      const { data } = await toolsApi.extractResources({
        urls,
        include_types: selectedTypes.length > 0 ? selectedTypes : undefined,
        use_browser: useBrowser,
        browser_wait_time: browserWaitTime,
        fetch_size: fetchSize
      })
      
      setExtractResult(data)
      addRecentTool('crawler')
      
      if (data.error) {
        toast.error(data.error)
      } else if (data.total_resources === 0) {
        toast.error('未找到任何资源，请检查目标网页是否正确')
        // 不切换步骤，保持在输入页面
      } else {
        toast.success(`提取完成：${data.success_sites}/${data.total_sites} 个网站，共 ${data.total_resources} 个资源`)
        setStep('select')
      }
    } catch {
      toast.error('提取失败')
    } finally {
      setExtractLoading(false)
    }
  }
  
  // 全选/取消全选
  const handleSelectAll = () => {
    if (!extractResult) return
    
    const resources = filterIdList.length > 0 ? filteredByIds : extractResult.all_resources
    if (selectedResources.size === resources.length) {
      setSelectedResources(new Set())
    } else {
      setSelectedResources(new Set(resources.map(r => r.url)))
    }
  }
  
  // 按类型选择
  const handleSelectByType = (type: string) => {
    if (!extractResult) return
    
    const resources = filterIdList.length > 0 ? filteredByIds : extractResult.all_resources
    const typeResources = resources.filter(r => r.resource_type === type)
    const allSelected = typeResources.every(r => selectedResources.has(r.url))
    
    const newSelected = new Set(selectedResources)
    if (allSelected) {
      typeResources.forEach(r => newSelected.delete(r.url))
    } else {
      typeResources.forEach(r => newSelected.add(r.url))
    }
    setSelectedResources(newSelected)
  }
  
  // 切换单个资源选择
  const toggleResourceSelect = (url: string) => {
    const newSelected = new Set(selectedResources)
    if (newSelected.has(url)) {
      newSelected.delete(url)
    } else {
      newSelected.add(url)
    }
    setSelectedResources(newSelected)
  }
  
  // 测试选定资源
  const handleTest = async () => {
    if (selectedResources.size === 0) {
      toast.error('请先选择要测试的资源')
      return
    }
    
    const resources = (filterIdList.length > 0 ? filteredByIds : extractResult?.all_resources || [])
      .filter(r => selectedResources.has(r.url))
    
    setTestLoading(true)
    setTestResult(null)
    
    try {
      const { data } = await toolsApi.testSelectedResources({
        resources,
        timeout,
        concurrency,
        enhanced: enhancedTest
      })
      
      setTestResult(data)
      setStep('result')
      
      if (data.error) {
        toast.error(data.error)
      } else {
        const warningMsg = data.warning_count > 0 ? `，${data.warning_count} 有警告` : ''
        toast.success(`测试完成：${data.accessible_count} 可访问，${data.inaccessible_count} 不可访问${warningMsg}`)
      }
    } catch {
      toast.error('测试失败')
    } finally {
      setTestLoading(false)
    }
  }
  
  // 重新开始
  const handleReset = () => {
    setStep('input')
    setExtractResult(null)
    setSelectedResources(new Set())
    setTestResult(null)
  }
  
  // 返回选择
  const handleBackToSelect = () => {
    setStep('select')
    setTestResult(null)
  }
  
  // 切换 ID 展开
  const toggleIdExpand = (id: string) => {
    const newExpanded = new Set(expandedIds)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedIds(newExpanded)
  }
  
  // 获取显示的测试结果
  const getDisplayResults = (): ResourceResult[] => {
    if (!testResult) return []
    
    if (displayMode === 'inaccessible') {
      return testResult.results.filter(r => !r.accessible)
    }
    
    if (displayMode === 'warnings') {
      return testResult.results.filter(r => r.warnings && r.warnings.length > 0)
    }
    
    if (displayMode === 'filtered' && filterIdList.length > 0) {
      return testResult.results.filter(r => 
        filterIdList.some(id => r.url.includes(id))
      )
    }
    
    return testResult.results
  }
  
  // 资源类型复选框
  const TypeCheckbox = ({ value, label }: { value: string; label: string }) => (
    <label className="inline-flex items-center gap-1.5 cursor-pointer">
      <input
        type="checkbox"
        checked={selectedTypes.includes(value)}
        onChange={(e) => {
          if (e.target.checked) {
            setSelectedTypes([...selectedTypes, value])
          } else {
            setSelectedTypes(selectedTypes.filter(t => t !== value))
          }
        }}
        className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
      />
      <span className="text-sm text-theme-text">{label}</span>
    </label>
  )
  
  // 资源选择行
  const ResourceSelectRow = ({ resource, showSource = false }: { resource: ResourceItem, showSource?: boolean }) => {
    const isSelected = selectedResources.has(resource.url)
    
    return (
      <div 
        className={`p-3 rounded-lg border cursor-pointer transition-colors ${
          isSelected 
            ? 'border-theme-primary bg-theme-primary/10' 
            : 'border-theme-border hover:border-theme-primary/50'
        }`}
        onClick={() => toggleResourceSelect(resource.url)}
      >
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            {isSelected ? (
              <CheckSquare className="w-5 h-5 text-theme-primary" />
            ) : (
              <Square className="w-5 h-5 text-theme-muted" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-0.5 text-xs rounded bg-theme-bg text-theme-muted">
                {resource.resource_type}
              </span>
              {resource.size_formatted && (
                <span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">
                  {resource.size_formatted}
                </span>
              )}
              {resource.size_error && (
                <span className="px-2 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-400">
                  大小获取失败
                </span>
              )}
            </div>
            <p className="text-sm text-theme-text mt-1 break-all">{resource.url}</p>
            {showSource && resource.source_url && (
              <p className="text-xs text-theme-muted mt-1 flex items-center gap-1">
                <Globe className="w-3 h-3" />
                来源: {resource.source_url}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }
  
  // 资源结果行组件
  const ResourceResultRow = ({ resource }: { resource: ResourceResult }) => {
    const hasWarnings = resource.warnings && resource.warnings.length > 0
    
    return (
      <div className={`p-3 rounded-lg border ${
        !resource.accessible 
          ? 'border-red-500/30 bg-red-500/5' 
          : hasWarnings 
            ? 'border-yellow-500/30 bg-yellow-500/5'
            : 'border-green-500/30 bg-green-500/5'
      }`}>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            {!resource.accessible ? (
              <XCircle className="w-5 h-5 text-red-500" />
            ) : hasWarnings ? (
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
            ) : (
              <CheckCircle className="w-5 h-5 text-green-500" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`px-2 py-0.5 text-xs rounded ${
                !resource.accessible 
                  ? 'bg-red-500/20 text-red-400' 
                  : hasWarnings
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-green-500/20 text-green-400'
              }`}>
                {resource.status_code || 'ERR'}
              </span>
              <span className="px-2 py-0.5 text-xs rounded bg-theme-bg text-theme-muted">
                {resource.resource_type}
              </span>
              {resource.enhanced_test && (
                <span className="px-2 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400">
                  增强测试
                </span>
              )}
              {resource.response_time_ms !== null && (
                <span className="flex items-center gap-1 text-xs text-theme-muted">
                  <Clock className="w-3 h-3" />
                  {resource.response_time_ms}ms
                </span>
              )}
              {resource.content_length !== null && (
                <span className="flex items-center gap-1 text-xs text-theme-muted">
                  <FileType className="w-3 h-3" />
                  {formatSize(resource.content_length)}
                </span>
              )}
            </div>
            <p className="text-sm text-theme-text mt-1 break-all">{resource.url}</p>
            {resource.source_url && (
              <p className="text-xs text-theme-muted mt-1 flex items-center gap-1">
                <Globe className="w-3 h-3" />
                来源: {resource.source_url}
              </p>
            )}
            {resource.error && (
              <p className="text-xs text-red-400 mt-1 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {resource.error}
              </p>
            )}
            {hasWarnings && (
              <div className="mt-2 space-y-1">
                {resource.warnings!.map((warning, idx) => (
                  <p key={idx} className="text-xs text-yellow-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                    {warning}
                  </p>
                ))}
              </div>
            )}
            {resource.detected_type && (
              <p className="text-xs text-theme-muted mt-1">
                检测到文件类型: {resource.detected_type}
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }
  
  // ID 匹配卡片（选择阶段）
  const IdMatchCard = ({ id, data }: { id: string; data: { found: boolean; count: number; resources: ResourceItem[] } }) => {
    const isExpanded = expandedIds.has(id)
    const allSelected = data.resources.every(r => selectedResources.has(r.url))
    const someSelected = data.resources.some(r => selectedResources.has(r.url))
    
    const handleSelectAll = (e: React.MouseEvent) => {
      e.stopPropagation()
      const newSelected = new Set(selectedResources)
      if (allSelected) {
        data.resources.forEach(r => newSelected.delete(r.url))
      } else {
        data.resources.forEach(r => newSelected.add(r.url))
      }
      setSelectedResources(newSelected)
    }
    
    return (
      <div className={`rounded-lg border ${data.found ? 'border-theme-border' : 'border-yellow-500/30 bg-yellow-500/5'}`}>
        <div
          className="p-3 cursor-pointer hover:bg-theme-bg/50 transition-colors"
          onClick={() => toggleIdExpand(id)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-theme-muted" />
              ) : (
                <ChevronRight className="w-4 h-4 text-theme-muted" />
              )}
              <Search className="w-4 h-4 text-theme-muted" />
              <span className="font-medium text-theme-text">{id}</span>
            </div>
            <div className="flex items-center gap-3">
              {data.found ? (
                <>
                  <span className="text-sm text-theme-muted">找到 {data.count} 个</span>
                  <button
                    onClick={handleSelectAll}
                    className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-theme-bg hover:bg-theme-card transition-colors"
                  >
                    {allSelected ? (
                      <CheckSquare className="w-3 h-3 text-theme-primary" />
                    ) : someSelected ? (
                      <MinusSquare className="w-3 h-3 text-theme-primary" />
                    ) : (
                      <Square className="w-3 h-3 text-theme-muted" />
                    )}
                    {allSelected ? '取消全选' : '全选'}
                  </button>
                </>
              ) : (
                <span className="text-sm text-yellow-500 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" />
                  未找到匹配资源
                </span>
              )}
            </div>
          </div>
        </div>
        
        {isExpanded && data.found && (
          <div className="px-3 pb-3 space-y-2 border-t border-theme-border pt-3 max-h-[300px] overflow-y-auto">
            {data.resources.map((resource, idx) => (
              <ResourceSelectRow key={idx} resource={resource} />
            ))}
          </div>
        )}
      </div>
    )
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">资源连通性测试</h1>
        <p className="text-theme-muted mt-1">
          爬取网站资源，手动选择后测试可访问性，支持增强测试模式
        </p>
      </div>
      
      {/* 步骤指示器 - 可点击切换 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setStep('input')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
            step === 'input' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
          }`}
        >
          <span className="w-5 h-5 rounded-full bg-current/20 flex items-center justify-center text-xs">1</span>
          <span className="text-sm">输入网址</span>
        </button>
        <ChevronRight className="w-4 h-4 text-theme-muted" />
        <button
          onClick={() => extractResult && setStep('select')}
          disabled={!extractResult}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
            step === 'select' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
          } ${!extractResult ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <span className="w-5 h-5 rounded-full bg-current/20 flex items-center justify-center text-xs">2</span>
          <span className="text-sm">选择资源</span>
        </button>
        <ChevronRight className="w-4 h-4 text-theme-muted" />
        <button
          onClick={() => testResult && setStep('result')}
          disabled={!testResult}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors ${
            step === 'result' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
          } ${!testResult ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <span className="w-5 h-5 rounded-full bg-current/20 flex items-center justify-center text-xs">3</span>
          <span className="text-sm">测试结果</span>
        </button>
      </div>
      
      {/* 步骤 1: 输入 */}
      {step === 'input' && (
        <ToolCard title="第一步：输入目标网址" toolKey="crawler-input">
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-theme-muted mb-2">
                目标网页 URL（每行一个）
              </label>
              <textarea
                value={crawlUrls}
                onChange={(e) => setCrawlUrls(e.target.value)}
                placeholder="https://example.com/page1&#10;https://example.com/page2"
                className="w-full h-28 resize-none font-mono text-sm"
              />
            </div>
            
            <div>
              <label className="block text-sm text-theme-muted mb-2">
                过滤 ID（可选，每行一个或用逗号分隔）
              </label>
              <textarea
                value={filterIds}
                onChange={(e) => setFilterIds(e.target.value)}
                placeholder="输入资源路径中包含的 ID，用于筛选资源&#10;例如: abc123, def456"
                className="w-full h-20 resize-none"
              />
            </div>
            
            <div>
              <label className="block text-sm text-theme-muted mb-2">
                资源类型过滤（可选）
              </label>
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {resourceTypeOptions.map(opt => (
                  <TypeCheckbox key={opt.value} value={opt.value} label={opt.label} />
                ))}
              </div>
            </div>
            
            {/* 浏览器渲染模式 */}
            <div className="p-4 rounded-lg bg-theme-bg border border-theme-border space-y-3">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useBrowser}
                  onChange={(e) => setUseBrowser(e.target.checked)}
                  className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
                />
                <span className="text-sm font-medium text-theme-text">浏览器渲染模式</span>
                <span className="text-xs text-theme-muted">（用于 JavaScript 动态加载的页面）</span>
              </label>
              {useBrowser && (
                <div className="mt-3 pl-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-theme-muted">等待时间:</label>
                    <input
                      type="number"
                      value={browserWaitTime}
                      onChange={(e) => setBrowserWaitTime(parseInt(e.target.value) || 3)}
                      min={1}
                      max={30}
                      className="w-16 text-sm"
                    />
                    <span className="text-xs text-theme-muted">秒（等待 JS 执行完成）</span>
                  </div>
                  <p className="text-xs text-yellow-500 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    浏览器模式较慢，首次使用需要下载 Chromium（约 150MB）
                  </p>
                </div>
              )}
              
              {/* 获取文件大小 */}
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={fetchSize}
                  onChange={(e) => setFetchSize(e.target.checked)}
                  className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
                />
                <span className="text-sm font-medium text-theme-text">获取文件大小</span>
                <span className="text-xs text-theme-muted">（会增加请求时间）</span>
              </label>
            </div>
            
            <ToolButton onClick={handleExtract} loading={extractLoading}>
              <Download className="w-4 h-4 mr-2" />
              {useBrowser ? '使用浏览器提取资源' : '提取资源列表'}
            </ToolButton>
            
            {/* 提取结果/错误信息 */}
            {extractResult && (
              <div className={`p-4 rounded-lg border ${
                extractResult.error || extractResult.total_resources === 0
                  ? 'border-red-500/30 bg-red-500/5'
                  : 'border-green-500/30 bg-green-500/5'
              }`}>
                {extractResult.error ? (
                  <div className="flex items-start gap-2 text-red-400">
                    <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">提取失败</p>
                      <p className="text-sm mt-1">{extractResult.error}</p>
                    </div>
                  </div>
                ) : extractResult.total_resources === 0 ? (
                  <div className="flex items-start gap-2 text-red-400">
                    <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">未找到任何资源</p>
                      <p className="text-sm mt-1">
                        成功访问了 {extractResult.success_sites}/{extractResult.total_sites} 个网站，但未发现任何资源。
                      </p>
                      {!useBrowser ? (
                        <div className="mt-3 p-3 rounded bg-yellow-500/10 border border-yellow-500/30">
                          <p className="text-sm text-yellow-400 font-medium">建议：尝试开启「浏览器渲染模式」</p>
                          <p className="text-xs text-yellow-400/80 mt-1">
                            该页面可能是 SPA（单页应用），内容由 JavaScript 动态加载。
                            浏览器渲染模式可以执行 JavaScript 获取完整内容。
                          </p>
                        </div>
                      ) : (
                        <ul className="text-sm mt-2 list-disc list-inside space-y-1">
                          <li>页面需要登录才能访问完整内容</li>
                          <li>资源在 iframe 中加载</li>
                          <li>尝试增加等待时间</li>
                          <li>输入的 URL 不正确</li>
                        </ul>
                      )}
                      {extractResult.sites.map((site, idx) => (
                        site.error && (
                          <p key={idx} className="text-sm mt-2">
                            <span className="text-theme-muted">{site.target_url}:</span> {site.error}
                          </p>
                        )
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-2 text-green-400">
                    <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">提取成功</p>
                      <p className="text-sm mt-1">
                        成功访问了 {extractResult.success_sites}/{extractResult.total_sites} 个网站
                        {extractResult.deduplicated && extractResult.deduplicated > 0 && (
                          <span className="text-yellow-400">（已去重 {extractResult.deduplicated} 个重复 URL）</span>
                        )}，
                        共发现 {extractResult.total_resources} 个资源
                        {extractResult.total_size_formatted && (
                          <span className="text-blue-400">，总大小约 {extractResult.total_size_formatted}</span>
                        )}。
                        点击上方"选择资源"步骤继续。
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </ToolCard>
      )}
      
      {/* 步骤 2: 选择资源 */}
      {step === 'select' && extractResult && (
        <ToolCard title="第二步：选择要测试的资源" toolKey="crawler-select">
          <div className="space-y-4">
            {/* 统计信息 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-xl font-bold text-theme-text">{extractResult.total_sites}</div>
                <div className="text-xs text-theme-muted">网站数</div>
              </div>
              <div className="p-3 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-xl font-bold text-theme-text">{extractResult.total_resources}</div>
                <div className="text-xs text-theme-muted">资源总数</div>
              </div>
              <div className="p-3 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-xl font-bold text-theme-text">
                  {filterIdList.length > 0 ? filteredByIds.length : extractResult.total_resources}
                </div>
                <div className="text-xs text-theme-muted">{filterIdList.length > 0 ? 'ID 匹配数' : '可选资源'}</div>
              </div>
              <div className="p-3 rounded-lg bg-theme-primary/10 border border-theme-primary/30">
                <div className="text-xl font-bold text-theme-primary">{selectedResources.size}</div>
                <div className="text-xs text-theme-primary">已选择</div>
              </div>
            </div>
            
            {/* 测试选项 */}
            <div className="p-4 rounded-lg bg-theme-bg border border-theme-border">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-theme-muted">超时:</label>
                    <input
                      type="number"
                      value={timeout}
                      onChange={(e) => setTimeout(parseInt(e.target.value) || 10)}
                      min={1}
                      max={60}
                      className="w-16 text-sm"
                    />
                    <span className="text-xs text-theme-muted">秒</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-theme-muted">并发:</label>
                    <input
                      type="number"
                      value={concurrency}
                      onChange={(e) => setConcurrency(parseInt(e.target.value) || 10)}
                      min={1}
                      max={50}
                      className="w-16 text-sm"
                    />
                  </div>
                </div>
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enhancedTest}
                    onChange={(e) => setEnhancedTest(e.target.checked)}
                    className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
                  />
                  <span className="text-sm text-theme-text">增强测试</span>
                  <span className="text-xs text-theme-muted">（验证文件内容真实性）</span>
                </label>
              </div>
              {enhancedTest && (
                <p className="text-xs text-yellow-500 mt-2 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  增强测试会下载部分内容，可能增加目标服务器负载
                </p>
              )}
            </div>
            
            {/* ID 匹配结果 */}
            {filterIdList.length > 0 && Object.keys(idMatchSummary).length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium text-theme-text">ID 匹配结果</div>
                {Object.entries(idMatchSummary).map(([id, data]) => (
                  <IdMatchCard key={id} id={id} data={data} />
                ))}
              </div>
            )}
            
            {/* 按类型快速选择 */}
            {Object.keys(extractResult.summary_by_type).length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-theme-muted">按类型选择:</span>
                {Object.entries(extractResult.summary_by_type).map(([type, count]) => {
                  const resources = filterIdList.length > 0 ? filteredByIds : extractResult.all_resources
                  const typeResources = resources.filter(r => r.resource_type === type)
                  const allSelected = typeResources.every(r => selectedResources.has(r.url))
                  
                  return (
                    <button
                      key={type}
                      onClick={() => handleSelectByType(type)}
                      className={`px-3 py-1 text-sm rounded transition-colors ${
                        allSelected 
                          ? 'bg-theme-primary text-white' 
                          : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
                      }`}
                    >
                      {type} ({count})
                    </button>
                  )
                })}
              </div>
            )}
            
            {/* 全选按钮 */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleSelectAll}
                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded bg-theme-bg hover:bg-theme-card transition-colors"
              >
                {selectedResources.size === (filterIdList.length > 0 ? filteredByIds : extractResult.all_resources).length ? (
                  <>
                    <CheckSquare className="w-4 h-4 text-theme-primary" />
                    取消全选
                  </>
                ) : (
                  <>
                    <Square className="w-4 h-4 text-theme-muted" />
                    全选 ({(filterIdList.length > 0 ? filteredByIds : extractResult.all_resources).length})
                  </>
                )}
              </button>
            </div>
            
            {/* 资源列表 - 始终按目标 URL 分组显示 */}
            {filterIdList.length === 0 && (
              <div className="space-y-4 max-h-[500px] overflow-y-auto">
                {extractResult.sites.map((site, siteIdx) => {
                  // 计算该站点的资源选中状态
                  const siteResources = site.resources
                  const selectedCount = siteResources.filter(r => selectedResources.has(r.url)).length
                  const allSelected = selectedCount === siteResources.length && siteResources.length > 0
                  const someSelected = selectedCount > 0 && selectedCount < siteResources.length
                  
                  // 切换该站点所有资源的选中状态
                  const toggleSiteSelection = (e: React.MouseEvent) => {
                    e.stopPropagation()
                    const newSelected = new Set(selectedResources)
                    if (allSelected) {
                      siteResources.forEach(r => newSelected.delete(r.url))
                    } else {
                      siteResources.forEach(r => newSelected.add(r.url))
                    }
                    setSelectedResources(newSelected)
                  }
                  
                  return (
                    <div key={siteIdx} className="rounded-lg border border-theme-border overflow-hidden">
                      {/* 站点标题栏 */}
                      <div className="bg-theme-bg px-4 py-3 border-b border-theme-border">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <Globe className="w-4 h-4 text-theme-primary flex-shrink-0" />
                            <span className="text-sm font-medium text-theme-text truncate" title={site.target_url}>
                              {site.target_url}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 flex-shrink-0">
                            <span className="text-xs text-theme-muted">
                              {site.total_resources} 个资源
                              {site.total_size_formatted && ` · ${site.total_size_formatted}`}
                            </span>
                            {site.total_resources > 0 && (
                              <button
                                onClick={toggleSiteSelection}
                                className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-theme-card hover:bg-theme-border transition-colors"
                              >
                                {allSelected ? (
                                  <CheckSquare className="w-3 h-3 text-theme-primary" />
                                ) : someSelected ? (
                                  <MinusSquare className="w-3 h-3 text-theme-primary" />
                                ) : (
                                  <Square className="w-3 h-3 text-theme-muted" />
                                )}
                                {allSelected ? '取消' : '全选'}
                              </button>
                            )}
                          </div>
                        </div>
                        {site.error && (
                          <p className="text-xs text-red-400 mt-2 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            {site.error}
                          </p>
                        )}
                      </div>
                      {/* 资源列表 */}
                      {site.total_resources > 0 ? (
                        <div className="p-2 space-y-2 max-h-[300px] overflow-y-auto">
                          {site.resources.map((resource, idx) => (
                            <ResourceSelectRow key={idx} resource={{...resource, source_url: site.target_url}} />
                          ))}
                        </div>
                      ) : (
                        <div className="p-4 text-center text-sm text-theme-muted">
                          未发现资源
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            
            {/* 操作按钮 */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm rounded bg-theme-bg hover:bg-theme-card transition-colors"
              >
                重新开始
              </button>
              <ToolButton 
                onClick={handleTest} 
                loading={testLoading}
                disabled={selectedResources.size === 0}
              >
                <Play className="w-4 h-4 mr-2" />
                测试选中的 {selectedResources.size} 个资源
              </ToolButton>
            </div>
          </div>
        </ToolCard>
      )}
      
      {/* 步骤 3: 测试结果 */}
      {step === 'result' && testResult && (
        <ToolCard title="第三步：测试结果" toolKey="crawler-result">
          <div className="space-y-4">
            {/* 统计摘要 */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="p-3 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-xl font-bold text-theme-text">{testResult.total}</div>
                <div className="text-xs text-theme-muted">测试总数</div>
              </div>
              <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30">
                <div className="text-xl font-bold text-green-500">{testResult.accessible_count}</div>
                <div className="text-xs text-green-400">可访问</div>
              </div>
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                <div className="text-xl font-bold text-red-500">{testResult.inaccessible_count}</div>
                <div className="text-xs text-red-400">不可访问</div>
              </div>
              {testResult.enhanced_mode && (
                <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                  <div className="text-xl font-bold text-yellow-500">{testResult.warning_count}</div>
                  <div className="text-xs text-yellow-400">有警告</div>
                </div>
              )}
              <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30">
                <div className="text-xl font-bold text-purple-500">{testResult.enhanced_mode ? '开启' : '关闭'}</div>
                <div className="text-xs text-purple-400">增强测试</div>
              </div>
            </div>
            
            {/* ID 过滤结果 */}
            {filterIdList.length > 0 && (
              <div className="p-4 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-sm font-medium text-theme-text mb-3">ID 过滤结果</div>
                <div className="flex flex-wrap gap-2">
                  {filterIdList.map(id => {
                    const matchedResults = testResult.results.filter(r => r.url.includes(id))
                    const found = matchedResults.length > 0
                    const accessible = matchedResults.filter(r => r.accessible).length
                    return (
                      <div 
                        key={id} 
                        className={`px-3 py-1.5 rounded text-sm ${
                          found 
                            ? 'bg-theme-card border border-theme-border' 
                            : 'bg-yellow-500/10 border border-yellow-500/30'
                        }`}
                      >
                        <span className="font-mono">{id}</span>
                        {found ? (
                          <span className="ml-2 text-xs">
                            <span className="text-green-400">{accessible}</span>
                            <span className="text-theme-muted">/</span>
                            <span className="text-theme-text">{matchedResults.length}</span>
                          </span>
                        ) : (
                          <span className="ml-2 text-xs text-yellow-500">未找到</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            
            {/* 按类型统计 */}
            {Object.keys(testResult.summary_by_type).length > 0 && (
              <div className="p-4 rounded-lg bg-theme-bg border border-theme-border">
                <div className="text-sm font-medium text-theme-text mb-3">按类型统计</div>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(testResult.summary_by_type).map(([type, stats]) => (
                    <div key={type} className="flex items-center gap-2 px-3 py-1.5 rounded bg-theme-card">
                      <span className="text-sm text-theme-text">{type}</span>
                      <span className="text-xs text-green-400">{stats.accessible}</span>
                      <span className="text-xs text-theme-muted">/</span>
                      <span className="text-xs text-red-400">{stats.inaccessible}</span>
                      {stats.with_warnings > 0 && (
                        <>
                          <span className="text-xs text-theme-muted">/</span>
                          <span className="text-xs text-yellow-400">{stats.with_warnings} 警告</span>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* 显示模式切换 */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-theme-muted">显示：</span>
              <div className="flex rounded-lg overflow-hidden border border-theme-border">
                <button
                  onClick={() => setDisplayMode('all')}
                  className={`px-3 py-1.5 text-sm transition-colors ${
                    displayMode === 'all' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
                  }`}
                >
                  全部 ({testResult.total})
                </button>
                <button
                  onClick={() => setDisplayMode('inaccessible')}
                  className={`px-3 py-1.5 text-sm transition-colors border-l border-theme-border ${
                    displayMode === 'inaccessible' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
                  }`}
                >
                  不可访问 ({testResult.inaccessible_count})
                </button>
                {testResult.enhanced_mode && (
                  <button
                    onClick={() => setDisplayMode('warnings')}
                    className={`px-3 py-1.5 text-sm transition-colors border-l border-theme-border ${
                      displayMode === 'warnings' ? 'bg-theme-primary text-white' : 'bg-theme-bg text-theme-muted hover:bg-theme-card'
                    }`}
                  >
                    有警告 ({testResult.warning_count})
                  </button>
                )}
              </div>
            </div>
            
            {/* 结果列表 */}
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {getDisplayResults().length === 0 ? (
                <div className="text-center py-8 text-theme-muted">
                  没有匹配的结果
                </div>
              ) : (
                getDisplayResults().map((resource, idx) => (
                  <ResourceResultRow key={idx} resource={resource} />
                ))
              )}
            </div>
            
            {/* 操作按钮 */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm rounded bg-theme-bg hover:bg-theme-card transition-colors"
              >
                重新开始
              </button>
              <button
                onClick={handleBackToSelect}
                className="px-4 py-2 text-sm rounded bg-theme-bg hover:bg-theme-card transition-colors"
              >
                返回选择资源
              </button>
            </div>
          </div>
        </ToolCard>
      )}
    </div>
  )
}
