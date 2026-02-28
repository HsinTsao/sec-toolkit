/**
 * TraceTimeline - AI Agent 执行追踪时间线组件
 * 
 * 显示 Agent 执行的每一步，包括：
 * - 规则匹配
 * - 意图识别
 * - 工具调用
 * - 摘要生成
 */
import { useState, useRef, useEffect, memo } from 'react'
import { 
  ChevronDown, 
  ChevronRight, 
  Clock, 
  Zap, 
  Wrench, 
  Brain,
  FileText,
  AlertCircle,
  CheckCircle,
  Loader2,
  Trash2,
  Search,
  Database,
  Globe,
  RefreshCw,
  Sparkles,
  BookOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTraceStore, type TraceSpan, type TraceType } from '@/stores/traceStore'

// 事件类型配置
const typeConfig: Record<TraceType, { icon: React.ElementType; color: string; label: string }> = {
  skill: { icon: Sparkles, color: 'text-theme-primary', label: 'Skill 激活' },
  skill_select: { icon: Search, color: 'text-emerald-500', label: 'Skill 选择' },
  memory_recall: { icon: BookOpen, color: 'text-amber-500', label: '长期记忆' },
  memory_save: { icon: BookOpen, color: 'text-lime-500', label: '记忆存储' },
  conversation_history: { icon: FileText, color: 'text-sky-500', label: '对话历史' },
  rule_match: { icon: Zap, color: 'text-yellow-500', label: '规则匹配' },
  intent: { icon: Brain, color: 'text-purple-500', label: '意图识别' },
  tool_call: { icon: Wrench, color: 'text-blue-500', label: '工具调用' },
  llm_call: { icon: Brain, color: 'text-green-500', label: 'LLM 调用' },
  rag_query: { icon: Database, color: 'text-orange-500', label: 'RAG 检索' },
  mcp_request: { icon: Globe, color: 'text-cyan-500', label: 'MCP 请求' },
  workflow_step: { icon: RefreshCw, color: 'text-indigo-500', label: '工作流步骤' },
  agent_loop: { icon: RefreshCw, color: 'text-pink-500', label: 'Agent 循环' },
  summary: { icon: FileText, color: 'text-teal-500', label: '摘要生成' },
  error: { icon: AlertCircle, color: 'text-red-500', label: '错误' },
}

// 格式化时间
function formatDuration(ms?: number): string {
  if (!ms) return '-'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

// 格式化时间戳为相对时间
function formatRelativeTime(timestamp: number, baseTime: number): string {
  const diff = timestamp - baseTime
  if (diff < 1000) return `${Math.round(diff)}ms`
  return `${(diff / 1000).toFixed(1)}s`
}

// Span 节点组件
interface SpanNodeProps {
  span: TraceSpan
  baseTime: number
  depth?: number
  onSelect: (span: TraceSpan) => void
  isSelected: boolean
}

const SpanNode = memo(function SpanNode({ 
  span, 
  baseTime, 
  depth = 0, 
  onSelect,
  isSelected,
}: SpanNodeProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const config = typeConfig[span.type] || typeConfig.error
  const Icon = config.icon
  const hasChildren = span.children.length > 0
  
  const statusIcon = span.status === 'running' ? (
    <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
  ) : span.status === 'error' ? (
    <AlertCircle className="w-3 h-3 text-red-500" />
  ) : (
    <CheckCircle className="w-3 h-3 text-green-500" />
  )
  
  return (
    <div className="select-none">
      <div
        className={cn(
          "flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer transition-colors",
          "hover:bg-theme-hover",
          isSelected && "bg-theme-active"
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(span)}
      >
        {/* 展开/折叠按钮 */}
        <button
          className="w-4 h-4 flex items-center justify-center"
          onClick={(e) => {
            e.stopPropagation()
            if (hasChildren) setIsExpanded(!isExpanded)
          }}
        >
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-theme-text-secondary" />
            ) : (
              <ChevronRight className="w-3 h-3 text-theme-text-secondary" />
            )
          ) : null}
        </button>
        
        {/* 状态图标 */}
        {statusIcon}
        
        {/* 类型图标 */}
        <Icon className={cn("w-4 h-4", config.color)} />
        
        {/* 名称 */}
        <span className="flex-1 text-sm text-theme-text truncate">
          {span.name}
        </span>
        
        {/* 相对时间 */}
        <span className="text-xs text-theme-text-secondary">
          [{formatRelativeTime(span.startTime, baseTime)}]
        </span>
        
        {/* 耗时 */}
        <span className={cn(
          "text-xs font-mono",
          span.duration_ms && span.duration_ms > 1000 
            ? "text-yellow-500" 
            : "text-theme-text-secondary"
        )}>
          {formatDuration(span.duration_ms)}
        </span>
      </div>
      
      {/* 子节点 */}
      {hasChildren && isExpanded && (
        <div>
          {span.children.map(child => (
            <SpanNode
              key={child.id}
              span={child}
              baseTime={baseTime}
              depth={depth + 1}
              onSelect={onSelect}
              isSelected={isSelected}
            />
          ))}
        </div>
      )}
    </div>
  )
})

// 事件详情面板
interface EventDetailsProps {
  span: TraceSpan | null
}

function EventDetails({ span }: EventDetailsProps) {
  if (!span) {
    return (
      <div className="h-full flex items-center justify-center text-theme-text-secondary text-sm">
        <Search className="w-4 h-4 mr-2" />
        选择一个事件查看详情
      </div>
    )
  }
  
  const config = typeConfig[span.type] || typeConfig.error
  
  // 类型安全地提取 span 字段
  const d = span.data as Record<string, unknown>
  const meta = span.metadata as Record<string, unknown>
  const apiInfo = {
    tool: d.tool as string | undefined,
    display_name: d.display_name as string | undefined,
    model: meta.model as string | undefined,
    category: d.category as string | undefined,
    confidence: d.confidence as number | undefined,
    params: d.params as Record<string, unknown> | undefined,
  }
  const input = d.input as string | Record<string, unknown> | undefined
  const output = d.output as string | Record<string, unknown> | undefined
  const tokens = meta.tokens as number | undefined
  
  return (
    <div className="p-3 space-y-3 overflow-auto h-full">
      {/* 标题 */}
      <div className="flex items-center gap-2">
        <config.icon className={cn("w-5 h-5", config.color)} />
        <span className="font-medium text-theme-text">{span.name}</span>
      </div>
      
      {/* API 信息（关键信息高亮显示）*/}
      {Boolean(apiInfo.tool || apiInfo.model || apiInfo.category) && (
        <div className="bg-theme-bg rounded p-2 space-y-1">
          {apiInfo.tool && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-theme-text-secondary">🔧 工具：</span>
              <code className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs font-mono">
                {apiInfo.tool}
              </code>
              {apiInfo.display_name && apiInfo.display_name !== apiInfo.tool && (
                <span className="text-theme-text-secondary text-xs">({apiInfo.display_name})</span>
              )}
            </div>
          )}
          {apiInfo.model && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-theme-text-secondary">🤖 模型：</span>
              <code className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs font-mono">
                {apiInfo.model}
              </code>
            </div>
          )}
          {apiInfo.category && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-theme-text-secondary">📂 类别：</span>
              <code className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs font-mono">
                {apiInfo.category}
              </code>
              {apiInfo.confidence !== undefined && (
                <span className="text-theme-text-secondary text-xs">
                  (置信度: {(apiInfo.confidence * 100).toFixed(0)}%)
                </span>
              )}
            </div>
          )}
          {apiInfo.params && Object.keys(apiInfo.params).length > 0 && (
            <div className="text-sm">
              <span className="text-theme-text-secondary">📋 参数：</span>
              <pre className="mt-1 text-xs bg-theme-card p-1.5 rounded overflow-auto max-h-20 text-theme-text">
                {JSON.stringify(apiInfo.params, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
      
      {/* 基本信息 */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-theme-text-secondary">类型：</span>
          <span className="text-theme-text">{config.label}</span>
        </div>
        <div>
          <span className="text-theme-text-secondary">状态：</span>
          <span className={cn(
            span.status === 'completed' && "text-green-500",
            span.status === 'running' && "text-blue-500",
            span.status === 'error' && "text-red-500",
          )}>
            {span.status === 'completed' ? '完成' : span.status === 'running' ? '运行中' : '错误'}
          </span>
        </div>
        <div>
          <span className="text-theme-text-secondary">耗时：</span>
          <span className="text-theme-text font-mono">{formatDuration(span.duration_ms)}</span>
        </div>
        {tokens !== undefined && (
          <div>
            <span className="text-theme-text-secondary">Tokens：</span>
            <span className="text-theme-text">{String(tokens)}</span>
          </div>
        )}
      </div>
      
      {/* 输入 */}
      {input && (
        <div>
          <div className="text-sm text-theme-text-secondary mb-1">📥 输入：</div>
          <pre className="text-xs bg-theme-bg p-2 rounded overflow-auto max-h-40 text-theme-text whitespace-pre-wrap break-all">
            {typeof input === 'string' ? input : JSON.stringify(input, null, 2)}
          </pre>
        </div>
      )}
      
      {/* 输出 */}
      {output && (
        <div>
          <div className="text-sm text-theme-text-secondary mb-1">📤 输出：</div>
          <pre className="text-xs bg-theme-bg p-2 rounded overflow-auto max-h-40 text-theme-text whitespace-pre-wrap break-all">
            {typeof output === 'string' ? output : JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
      
      {/* 其他数据（排除已显示的字段）*/}
      {(() => {
        const excludeKeys = ['input', 'output', 'tool', 'display_name', 'category', 'confidence', 'params']
        const otherData = Object.fromEntries(
          Object.entries(d).filter(([k]) => !excludeKeys.includes(k))
        )
        return Object.keys(otherData).length > 0 && (
          <div>
            <div className="text-sm text-theme-text-secondary mb-1">📋 其他数据：</div>
            <pre className="text-xs bg-theme-bg p-2 rounded overflow-auto max-h-32 text-theme-text">
              {JSON.stringify(otherData, null, 2)}
            </pre>
          </div>
        )
      })()}
    </div>
  )
}

// 主组件
export function TraceTimeline() {
  const { 
    currentSession, 
    sessions,
    isPanelVisible, 
    selectedEventId,
    setSelectedEvent,
    clearCurrentSession,
    clearAllSessions,
  } = useTraceStore()
  
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null)
  const [viewingHistoryIndex, setViewingHistoryIndex] = useState<number | null>(null)
  
  // 可拖动调整大小
  const [detailsHeight, setDetailsHeight] = useState(200)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // 处理拖动
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }
  
  useEffect(() => {
    if (!isDragging) return
    
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const containerRect = containerRef.current.getBoundingClientRect()
      const newHeight = containerRect.bottom - e.clientY
      // 限制最小和最大高度
      setDetailsHeight(Math.max(80, Math.min(400, newHeight)))
    }
    
    const handleMouseUp = () => {
      setIsDragging(false)
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])
  
  if (!isPanelVisible) return null
  
  // 确定当前查看的会话（当前或历史）
  // 优先级：用户选择的历史 > 当前会话（有内容时）> 最新历史会话 > 空
  const activeSession = (() => {
    // 如果用户明确选择了历史记录，显示历史
    if (viewingHistoryIndex !== null) {
      return sessions[viewingHistoryIndex]
    }
    // 如果当前会话有内容，显示当前会话
    if (currentSession && currentSession.spans.length > 0) {
      return currentSession
    }
    // 如果当前会话为空但有历史记录，显示最新的历史记录
    if (sessions.length > 0) {
      return sessions[0]
    }
    // 没有任何会话
    return null
  })()
  
  // 判断是否正在显示历史（用于 UI 提示）
  const isShowingLatestHistory = !currentSession?.spans?.length && sessions.length > 0 && viewingHistoryIndex === null
  
  const spans = activeSession?.spans || []
  const baseTime = activeSession?.startTime || Date.now()
  
  const handleSelectSpan = (span: TraceSpan) => {
    setSelectedSpan(span)
    setSelectedEvent(span.id)
  }
  
  // 计算总 tokens
  const totalTokens = spans.reduce((sum, span) => {
    const tokens = span.metadata?.tokens
    return sum + (typeof tokens === 'number' ? tokens : 0)
  }, 0)
  
  // 切换到当前会话
  const viewCurrent = () => {
    setViewingHistoryIndex(null)
    setSelectedSpan(null)
  }
  
  // 切换到上一条历史
  const viewPrevious = () => {
    if (viewingHistoryIndex === null) {
      if (sessions.length > 0) {
        setViewingHistoryIndex(0)
        setSelectedSpan(null)
      }
    } else if (viewingHistoryIndex < sessions.length - 1) {
      setViewingHistoryIndex(viewingHistoryIndex + 1)
      setSelectedSpan(null)
    }
  }
  
  // 切换到下一条历史
  const viewNext = () => {
    if (viewingHistoryIndex !== null) {
      if (viewingHistoryIndex > 0) {
        setViewingHistoryIndex(viewingHistoryIndex - 1)
        setSelectedSpan(null)
      } else {
        setViewingHistoryIndex(null)
        setSelectedSpan(null)
      }
    }
  }
  
  const hasHistory = sessions.length > 0
  const canGoPrevious = viewingHistoryIndex === null ? hasHistory : viewingHistoryIndex < sessions.length - 1
  const canGoNext = viewingHistoryIndex !== null && viewingHistoryIndex >= 0
  const isViewingHistory = viewingHistoryIndex !== null
  
  return (
    <div ref={containerRef} className="h-full flex flex-col bg-theme-card border-l border-theme-border">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-theme-border">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-theme-text-secondary" />
          <span className="text-sm font-medium text-theme-text">Trace</span>
          {activeSession && (
            <span className="text-xs text-theme-text-secondary">
              ({spans.length} 步, {totalTokens} tok)
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* 历史导航 */}
          {hasHistory && (
            <>
              <button
                onClick={viewPrevious}
                disabled={!canGoPrevious}
                className={cn(
                  "p-1 rounded text-xs",
                  canGoPrevious ? "hover:bg-theme-hover text-theme-text-secondary" : "text-theme-text-secondary/30 cursor-not-allowed"
                )}
                title="上一条"
              >
                ◀
              </button>
              <span className="text-xs text-theme-text-secondary min-w-[40px] text-center">
                {isViewingHistory ? `#${viewingHistoryIndex + 1}` : isShowingLatestHistory ? '上次' : '当前'}
              </span>
              <button
                onClick={viewNext}
                disabled={!canGoNext}
                className={cn(
                  "p-1 rounded text-xs",
                  canGoNext ? "hover:bg-theme-hover text-theme-text-secondary" : "text-theme-text-secondary/30 cursor-not-allowed"
                )}
                title="下一条"
              >
                ▶
              </button>
            </>
          )}
          {isViewingHistory && (
            <button
              onClick={viewCurrent}
              className="ml-1 px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30"
              title="返回当前"
            >
              当前
            </button>
          )}
          <button
            onClick={() => {
              if (isViewingHistory) {
                clearAllSessions()
                setViewingHistoryIndex(null)
              } else {
                clearCurrentSession()
              }
            }}
            className="p-1 hover:bg-theme-hover rounded ml-1"
            title={isViewingHistory ? "清空所有历史" : "清空当前"}
          >
            <Trash2 className="w-4 h-4 text-theme-text-secondary" />
          </button>
        </div>
      </div>
      
      {/* 历史提示 */}
      {(isViewingHistory || isShowingLatestHistory) && (
        <div className="px-3 py-1.5 bg-amber-500/10 border-b border-amber-500/20 text-xs text-amber-400">
          {isShowingLatestHistory ? (
            <>
              📜 上次对话记录
              {activeSession?.summary && (
                <span className="ml-2 text-amber-400/70">
                  · 耗时 {(activeSession.summary.totalTime_ms / 1000).toFixed(2)}s
                </span>
              )}
            </>
          ) : (
            <>
              📜 正在查看历史记录 #{viewingHistoryIndex! + 1}/{sessions.length}
              {activeSession?.summary && (
                <span className="ml-2 text-amber-400/70">
                  · 耗时 {(activeSession.summary.totalTime_ms / 1000).toFixed(2)}s
                </span>
              )}
            </>
          )}
        </div>
      )}
      
      {/* 内容区域 */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* 时间线 */}
        <div className="flex-1 overflow-auto">
          {spans.length === 0 ? (
            <div className="h-full flex items-center justify-center text-theme-text-secondary text-sm">
              {isViewingHistory ? '该记录为空' : sessions.length === 0 ? '等待执行...' : '该记录为空'}
            </div>
          ) : (
            <div className="py-1">
              {spans.map(span => (
                <SpanNode
                  key={span.id}
                  span={span}
                  baseTime={baseTime}
                  onSelect={handleSelectSpan}
                  isSelected={selectedEventId === span.id}
                />
              ))}
            </div>
          )}
        </div>
        
        {/* 可拖动的分隔条 */}
        <div
          onMouseDown={handleMouseDown}
          className={cn(
            "h-1.5 cursor-ns-resize flex items-center justify-center border-y border-theme-border",
            "hover:bg-theme-hover transition-colors",
            isDragging && "bg-blue-500/20"
          )}
        >
          <div className="w-8 h-0.5 bg-theme-text-secondary/30 rounded-full" />
        </div>
        
        {/* 详情面板（可调整高度）*/}
        <div 
          className="overflow-hidden"
          style={{ height: detailsHeight }}
        >
          <EventDetails span={selectedSpan} />
        </div>
      </div>
    </div>
  )
}

export default TraceTimeline
