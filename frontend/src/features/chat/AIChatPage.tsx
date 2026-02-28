import { useState, useRef, useEffect, useCallback, memo } from 'react'
import { 
  Send, 
  Settings, 
  Plus, 
  Trash2, 
  MessageSquare, 
  Copy, 
  Check,
  Loader2,
  X,
  Bot,
  User,
  Sparkles,
  RefreshCw,
  Edit3,
  FileText,
  AlertCircle,
  BookOpen,
  Link2,
  FileUp,
  ExternalLink,
  PanelLeftOpen,
  Activity,
} from 'lucide-react'
import { useLLMStore, type ChatMessage } from '@/stores/llmStore'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import { notesApi, llmApi, toolsApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { TraceTimeline } from '@/components/trace'
import { useTraceStore, type TraceEvent } from '@/stores/traceStore'
import { AgentConfigPanel } from '@/components/agent'
import { SkillSelector, SkillWelcome } from '@/components/skill/SkillSelector'
import { useSkillStore } from '@/stores/skillStore'

// ==================== 性能优化：节流更新 ====================
/**
 * 创建节流函数，用于限制流式消息更新频率
 * 约 60fps (16ms) 更新一次，避免频繁渲染
 */
function createThrottledUpdater() {
  let pendingContent = ''
  let timer: number | null = null
  let lastUpdateTime = 0
  const THROTTLE_MS = 16 // ~60fps
  
  return {
    update: (
      sessionId: string,
      messageId: string,
      content: string,
      updateFn: (sessionId: string, messageId: string, content: string) => void
    ) => {
      pendingContent = content
      const now = Date.now()
      
      // 如果距离上次更新超过节流时间，立即更新
      if (now - lastUpdateTime >= THROTTLE_MS) {
        updateFn(sessionId, messageId, pendingContent)
        lastUpdateTime = now
        return
      }
      
      // 否则设置定时器延迟更新
      if (!timer) {
        timer = window.setTimeout(() => {
          updateFn(sessionId, messageId, pendingContent)
          lastUpdateTime = Date.now()
          timer = null
        }, THROTTLE_MS - (now - lastUpdateTime))
      }
    },
    // 强制刷新（流结束时调用）
    flush: (
      sessionId: string,
      messageId: string,
      content: string,
      updateFn: (sessionId: string, messageId: string, content: string) => void
    ) => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      updateFn(sessionId, messageId, content)
    }
  }
}

export default function AIChatPage() {
  const { token } = useAuthStore()
  const {
    loadProviders,
    config,
    configLoading,
    loadConfig,
    getCurrentProvider,
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    setCurrentSession,
    getCurrentSession,
    addMessage,
    updateMessage,
    getHistory,
  } = useLLMStore()
  
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [savingNoteId, setSavingNoteId] = useState<string | null>(null)
  const [useKnowledge, setUseKnowledge] = useState(true)
  const [knowledgeSources, setKnowledgeSources] = useState<string[]>(['note', 'bookmark', 'file'])
  const [lastSources, setLastSources] = useState<RAGSource[]>([])
  const [showChatSidebar, setShowChatSidebar] = useState(false) // 移动端会话列表
  const [useFastMode, setUseFastMode] = useState(true) // 快速模式（省 Token）
  const [lastTokensUsed, setLastTokensUsed] = useState<number | null>(null) // 上次 Token 消耗
  const [isMobileView, setIsMobileView] = useState(false)
  const [userLocation, setUserLocation] = useState<string | null>(null) // 用户位置
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null) // 当前流式输出的消息ID
  const [showTracePanel, setShowTracePanel] = useState(true) // 显示 Trace 面板
  const [showAgentConfig, setShowAgentConfig] = useState(false) // 显示 Agent 配置
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const throttledUpdater = useRef(createThrottledUpdater()) // 节流更新器
  
  // Trace Store
  const { 
    startSession: startTraceSession,
    endSession: endTraceSession, 
    addEvent: addTraceEvent,
    currentSession: traceCurrentSession,
  } = useTraceStore()
  
  // Skill Store
  const { activeSkillIds, activeSkills } = useSkillStore()
  
  // 监听窗口大小变化
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768 // md breakpoint
      setIsMobileView(mobile)
      if (!mobile) {
        setShowChatSidebar(false) // 桌面端关闭移动端抽屉
      }
    }
    
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

// RAG 来源类型
interface RAGSource {
  source_type: string
  source_id: string
  title: string
  snippet: string
  url?: string
}
  
  const currentSession = getCurrentSession()
  const currentProvider = getCurrentProvider()
  
  // 获取用户位置（通过后端代理，避免 ipapi.co 的 CORS 和 429 限制）
  useEffect(() => {
    const fetchLocation = async () => {
      try {
        const { data } = await toolsApi.myLocation()
        if (data && !data.error) {
          const location = data.city || data.region || data.country
          if (location) {
            setUserLocation(location)
            console.log('[Location] 获取到用户位置:', location)
          }
        }
      } catch (error) {
        console.warn('[Location] 获取位置失败:', error)
      }
    }
    fetchLocation()
  }, [])
  
  // 加载提供商和配置
  useEffect(() => {
    if (token) {
      loadProviders()
      loadConfig()
    }
  }, [token, loadProviders, loadConfig])
  
  // 记录上一次的会话 ID 和消息数量，用于检测会话切换和新消息
  const prevSessionId = useRef<string | null>(null)
  const prevMessageCount = useRef<number>(0)
  
  // 滚动到底部（使用 requestAnimationFrame 避免抖动）
  const scrollToBottom = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ 
        behavior: smooth ? 'smooth' : 'auto',
        block: 'end'
      })
    })
  }, [])
  
  // 会话切换或首次加载时，直接跳到底部（无动画）
  useEffect(() => {
    if (currentSessionId !== prevSessionId.current) {
      prevSessionId.current = currentSessionId
      prevMessageCount.current = currentSession?.messages.length || 0
      // 会话切换或首次加载，直接跳到底部，无动画
      scrollToBottom(false)
    }
  }, [currentSessionId, currentSession?.messages.length, scrollToBottom])
  
  // 监听消息变化，新消息时滚动（流式输出用即时滚动）
  useEffect(() => {
    const messageCount = currentSession?.messages.length || 0
    // 只在有新消息时处理（排除会话切换）
    if (messageCount <= prevMessageCount.current) {
      prevMessageCount.current = messageCount
      return
    }
    prevMessageCount.current = messageCount
    
    const lastMessage = currentSession?.messages[messageCount - 1]
    // 如果最后一条是正在输出的 AI 消息，使用即时滚动
    const isStreaming = isLoading && lastMessage?.role === 'assistant'
    scrollToBottom(!isStreaming)
  }, [currentSession?.messages.length, isLoading, scrollToBottom, currentSession?.messages])
  
  // 自动调整输入框高度
  const adjustTextareaHeight = () => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }
  
  // 复制消息
  const copyMessage = async (content: string, id: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(id)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopiedId(null), 2000)
    } catch (error) {
      console.error('复制失败:', error)
      // 降级方案：使用 execCommand
      try {
        const textArea = document.createElement('textarea')
        textArea.value = content
        textArea.style.position = 'fixed'
        textArea.style.left = '-9999px'
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
        setCopiedId(id)
        toast.success('已复制到剪贴板')
        setTimeout(() => setCopiedId(null), 2000)
      } catch {
        toast.error('复制失败，请手动选择复制')
      }
    }
  }
  
  // 保存到笔记
  const saveToNote = async (content: string, messageId: string) => {
    if (!content.trim()) return
    
    setSavingNoteId(messageId)
    try {
      // 从内容中提取标题（第一行或前30个字符）
      const firstLine = content.split('\n')[0].replace(/^#+\s*/, '').trim()
      const title = firstLine.slice(0, 50) || 'AI 对话记录'
      
      // 添加元信息
      const noteContent = `> 来自 AI Chat (${currentProvider?.name || 'Unknown'} - ${config?.model})\n> 时间: ${new Date().toLocaleString('zh-CN')}\n\n---\n\n${content}`
      
      await notesApi.createNote({
        title: title + (firstLine.length > 50 ? '...' : ''),
        content: noteContent,
      })
      
      toast.success('已保存到笔记')
    } catch (error) {
      console.error('保存笔记失败:', error)
      toast.error('保存失败，请重试')
    } finally {
      setSavingNoteId(null)
    }
  }
  
  // 发送消息（调用后端 API）
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return
    
    // 检查是否已配置
    if (!config) {
      toast.error('请先配置 LLM API Key')
      setShowSettings(true)
      return
    }
    
    // 使用系统默认时不需要检查 api_key_set
    if (!config.use_system_default && !config.api_key_set && config.provider_id !== 'ollama') {
      toast.error('请先配置 API Key')
      setShowSettings(true)
      return
    }
    
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = createSession()
    }
    
    const userMessage = input.trim()
    setInput('')
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }
    
    // 在添加新消息之前，先获取对话历史（不包含当前消息）
    const chatHistory = (sessionId && getHistory) ? getHistory(sessionId, 10) : []
    
    // 添加用户消息
    addMessage(sessionId, { role: 'user', content: userMessage })
    
    // 添加助手消息占位
    addMessage(sessionId, { role: 'assistant', content: '' })
    
    // 获取刚添加的助手消息ID，用于标记流式输出状态
    const session = useLLMStore.getState().sessions.find(s => s.id === sessionId)
    const assistantMsgId = session?.messages[session.messages.length - 1]?.id || null
    setStreamingMessageId(assistantMsgId)
    
    setIsLoading(true)
    setLastTokensUsed(null)
    
    try {
      // 获取历史消息（只保留 user/assistant/system 类型，过滤掉可能存在的无效消息）
      const history = (getCurrentSession()?.messages.slice(0, -1) || [])
        .filter(m => ['user', 'assistant', 'system'].includes(m.role))
        .map(m => ({
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
        }))
      
      // ============ 快速模式：双 LLM 架构（省 Token）============
      // 快速模式可在任何时候使用，适合编码/解码/哈希等简单操作
      // 注意：快速模式是无状态的，不使用历史记录
      if (useFastMode) {
        // 如果有正在进行的会话，先结束它（保存到历史）
        if (traceCurrentSession) {
          endTraceSession()
        }
        
        // 使用流式 API 获取实时 trace 事件（chatHistory 已在前面获取）
        const fastResponse = await fetch('/api/llm/fast/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: userMessage,
            mode: 'auto',
            skip_summary: false,
            context: userLocation ? {
              location: userLocation,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            } : undefined,
            skill_ids: activeSkillIds.length > 0 ? activeSkillIds : undefined,
            history: chatHistory.length > 0 ? chatHistory : undefined,  // 传递对话历史
          }),
        })
        
        if (fastResponse.ok) {
          const reader = fastResponse.body?.getReader()
          if (!reader) {
            throw new Error('无法读取响应流')
          }
          
          const decoder = new TextDecoder()
          let fastContent = ''
          let fastBuffer = ''
          let fastResult: {
            fallback_needed?: boolean
            tokens_estimated?: number
            rule_matched?: boolean
            tool_used?: string | null
            trace_id?: string
          } = {}
          
          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) break
              
              fastBuffer += decoder.decode(value, { stream: true })
              const lines = fastBuffer.split('\n')
              fastBuffer = lines.pop() || ''
              
              for (const line of lines) {
                const trimmedLine = line.trim()
                if (!trimmedLine || !trimmedLine.startsWith('data: ')) continue
                
                const data = trimmedLine.slice(6)
                if (!data) continue
                
                try {
                  const json = JSON.parse(data)
                  
                  // 处理 trace 事件
                  if (json.stage === 'trace_start' && json.data?.trace_id) {
                    startTraceSession(json.data.trace_id)
                  } else if (json.stage === 'trace' && json.data) {
                    // 将 trace 事件添加到 store
                    addTraceEvent(json.data as TraceEvent)
                  }
                  
                  // 处理业务事件
                  if (json.stage === 'content') {
                    fastContent = json.data
                  } else if (json.stage === 'fallback') {
                    fastResult.fallback_needed = true
                    console.log('[FastMode] Fallback to full mode:', json.data?.reason)
                  } else if (json.stage === 'done') {
                    fastResult = { ...fastResult, ...json.data }
                  }
                } catch {
                  // 忽略 JSON 解析错误
                }
              }
            }
          } finally {
            reader.releaseLock()
          }
          
          // 如果不需要 fallback，直接返回结果
          if (!fastResult.fallback_needed && fastContent) {
            setLastTokensUsed(fastResult.tokens_estimated || 0)
            
            // 更新消息
            const session = useLLMStore.getState().sessions.find(s => s.id === sessionId)
            const lastMsg = session?.messages[session.messages.length - 1]
            if (lastMsg && lastMsg.role === 'assistant') {
              // 添加模式标记
              const modeTag = fastResult.rule_matched ? '⚡' : '🚀'
              const toolInfo = fastResult.tool_used ? ` (${fastResult.tool_used})` : ''
              const tokenInfo = fastResult.tokens_estimated === 0 ? '0 tokens (规则匹配)' : `~${fastResult.tokens_estimated} tokens`
              updateMessage(sessionId, lastMsg.id, `${fastContent}\n\n---\n_${modeTag} 快速模式${toolInfo} · ${tokenInfo}_`)
            }
            // 快速模式完成，结束 trace session
            endTraceSession()
            setIsLoading(false)
            setStreamingMessageId(null)
            return
          }
          // 需要 fallback（复杂问题），自动切换到完整模式
        }
      }
      
      // ============ 完整模式：流式 API（支持 RAG）============
      const response = await fetch('/api/llm/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: userMessage,
          history,
          use_knowledge: useKnowledge,
          knowledge_sources: knowledgeSources,
          max_results: 5,
        }),
      })
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(error.detail || '请求失败')
      }
      
      // 流式读取
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法读取响应流')
      }
      
      const decoder = new TextDecoder()
      let content = ''
      let buffer = ''
      
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // 保留最后一个不完整的行
          
          for (const line of lines) {
            const trimmedLine = line.trim()
            if (!trimmedLine || !trimmedLine.startsWith('data: ')) continue
            
            const data = trimmedLine.slice(6)
            if (!data) continue
            
            try {
              const json = JSON.parse(data)
              
              if (json.error) {
                throw new Error(json.error)
              }
              
              // 处理 trace 事件（完整模式也支持 trace）
              if (json.stage === 'trace_start' && json.data?.trace_id) {
                // 如果之前没有启动 trace session（非 fallback 场景），启动一个
                if (!useTraceStore.getState().currentSession) {
                  startTraceSession(json.data.trace_id)
                }
              } else if (json.stage === 'trace' && json.data) {
                addTraceEvent(json.data as TraceEvent)
              }
              
              // 处理来源信息
              if (json.sources) {
                setLastSources(json.sources)
              }
              
              if (json.done) {
                break
              }
              
              if (json.content) {
                content += json.content
                
                // 使用节流更新消息（减少渲染频率）
                const session = useLLMStore.getState().sessions.find(s => s.id === sessionId)
                const lastMsg = session?.messages[session.messages.length - 1]
                if (lastMsg && lastMsg.role === 'assistant') {
                  throttledUpdater.current.update(sessionId, lastMsg.id, content, updateMessage)
                }
              }
            } catch (e) {
              if (!(e instanceof SyntaxError)) {
                throw e
              }
              // 忽略 JSON 解析错误
            }
          }
        }
        
        // 流结束后，强制刷新最终内容
        const finalSession = useLLMStore.getState().sessions.find(s => s.id === sessionId)
        const finalMsg = finalSession?.messages[finalSession.messages.length - 1]
        if (finalMsg && finalMsg.role === 'assistant' && content) {
          throttledUpdater.current.flush(sessionId, finalMsg.id, content, updateMessage)
        }
        
        // 完整模式完成，结束 trace session
        endTraceSession()
      } finally {
        reader.releaseLock()
      }
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '发送失败'
      toast.error(errorMessage)
      
      // 更新最后一条消息为错误提示
      const session = useLLMStore.getState().sessions.find(s => s.id === sessionId)
      const lastMsg = session?.messages[session.messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        updateMessage(sessionId, lastMsg.id, `❌ 错误: ${errorMessage}`)
      }
    } finally {
      setIsLoading(false)
      setStreamingMessageId(null) // 清除流式输出标记
    }
  }
  
  // 计算高度：视口高度 - header(64px) - statusbar(24px) - padding(24px上 + 48px下)
  return (
    <div className="flex animate-fadeIn -m-4 lg:-m-6 -mb-12 overflow-hidden" style={{ height: 'calc(100vh - 56px - 24px)', minHeight: 0, maxWidth: '100vw' }}>
      {/* 移动端遮罩层 - z-index 低于系统侧边栏(z-50)，高于对话列表(z-30) */}
      {isMobileView && showChatSidebar && (
        <div 
          className="fixed inset-0 bg-black/50 z-20"
          onClick={() => setShowChatSidebar(false)}
        />
      )}
      
      {/* 左侧会话列表 - 移动端抽屉式，桌面端固定显示 */}
      <div className={cn(
        "bg-theme-card border-r border-theme-border flex flex-col flex-shrink-0 z-30",
        // 移动端样式
        isMobileView 
          ? "fixed inset-y-0 left-0 w-64 transition-transform duration-300"
          : "w-56 lg:w-64 relative",
        isMobileView && !showChatSidebar && "-translate-x-full"
      )}>
        <div className="p-3 lg:p-4 border-b border-theme-border flex items-center gap-2">
          <button
            onClick={() => createSession()}
            className="flex-1 btn btn-primary flex items-center justify-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            新对话
          </button>
          {/* 移动端关闭按钮 */}
          {isMobileView && (
            <button
              onClick={() => setShowChatSidebar(false)}
              className="p-2 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-text"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.length === 0 ? (
            <div className="text-center text-theme-muted text-sm py-8">
              暂无对话
            </div>
          ) : (
            sessions.map(session => (
              <div
                key={session.id}
                onClick={() => {
                  setCurrentSession(session.id)
                  if (isMobileView) setShowChatSidebar(false)
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors group cursor-pointer',
                  currentSessionId === session.id
                    ? 'bg-theme-primary/20 text-theme-primary'
                    : 'hover:bg-theme-bg text-theme-muted hover:text-theme-text'
                )}
              >
                <MessageSquare className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1 truncate">{session.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm('确定删除这个对话吗？')) {
                      deleteSession(session.id)
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-theme-danger transition-all"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
        
        {/* 设置按钮 */}
        <div className="p-3 lg:p-4 border-t border-theme-border">
          <button
            onClick={() => setShowSettings(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-theme-muted hover:text-theme-text hover:bg-theme-bg transition-colors"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm">API 设置</span>
            {configLoading ? (
              <Loader2 className="ml-auto w-4 h-4 animate-spin" />
            ) : config ? (
              <span className="ml-auto text-xs bg-theme-bg px-2 py-0.5 rounded hidden sm:block">
                {currentProvider?.icon} {currentProvider?.name}
              </span>
            ) : (
              <span className="ml-auto text-xs text-theme-warning flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                未配置
              </span>
            )}
          </button>
          
          {/* Agent 配置按钮 */}
          <button
            onClick={() => setShowAgentConfig(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-theme-muted hover:text-theme-text hover:bg-theme-bg transition-colors"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm">Agent 配置</span>
          </button>
        </div>
      </div>
      
      {/* 中间聊天区域 - 独立滚动 */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {currentSession ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4 scroll-smooth">
              {/* Skill 欢迎消息 */}
              {useFastMode && currentSession.messages.length === 0 && activeSkills.length > 0 && (
                <SkillWelcome />
              )}
              
              {currentSession.messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  isStreaming={streamingMessageId === message.id}
                  onCopy={() => copyMessage(message.content, message.id)}
                  isCopied={copiedId === message.id}
                  onSaveToNote={message.role === 'assistant' ? () => saveToNote(message.content, message.id) : undefined}
                  isSaving={savingNoteId === message.id}
                />
              ))}
              {isLoading && currentSession.messages[currentSession.messages.length - 1]?.content === '' && (
                <div className="flex items-center gap-2 text-theme-muted">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">思考中...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            
            {/* 输入区域 */}
            <div className="p-3 lg:p-4 border-t border-theme-border bg-theme-bg relative z-[60]">
              <div className="flex gap-2 max-w-4xl mx-auto">
                {/* 移动端显示会话列表切换按钮 */}
                {isMobileView && (
                  <button
                    onClick={() => setShowChatSidebar(true)}
                    className="btn btn-ghost p-2 self-end flex-shrink-0"
                    title="会话列表"
                  >
                    <PanelLeftOpen className="w-5 h-5" />
                  </button>
                )}
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value)
                    adjustTextareaHeight()
                  }}
                  onKeyDown={(e) => {
                    // 检测输入法状态，避免在选择候选词时误发送
                    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault()
                      sendMessage()
                    }
                  }}
                  placeholder={isMobileView ? "输入消息..." : "输入消息... (Enter 发送, Shift+Enter 换行)"}
                  className="flex-1 resize-none min-h-[44px] max-h-[200px] text-sm lg:text-base"
                  rows={1}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  className="btn btn-primary px-3 lg:px-4 self-end flex-shrink-0"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
              {/* 知识库设置和模型信息 */}
              <div className="flex items-center justify-between max-w-4xl mx-auto mt-2 text-xs flex-wrap gap-2">
                {/* 知识库开关 */}
                <div className="flex items-center gap-2 lg:gap-3 flex-wrap">
                  <button
                    onClick={() => setUseKnowledge(!useKnowledge)}
                    className={cn(
                      'flex items-center gap-1 lg:gap-1.5 px-2 py-1 rounded transition-colors',
                      useKnowledge 
                        ? 'bg-theme-primary/20 text-theme-primary' 
                        : 'text-theme-muted hover:text-theme-text'
                    )}
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">知识库</span> {useKnowledge ? 'ON' : 'OFF'}
                  </button>
                  
                  {useKnowledge && (
                    <div className="flex items-center gap-1">
                      {[
                        { id: 'note', icon: FileText, label: '笔记' },
                        { id: 'bookmark', icon: Link2, label: '书签' },
                        { id: 'file', icon: FileUp, label: '文件' },
                      ].map(source => {
                        const isActive = knowledgeSources.includes(source.id)
                        const isLastOne = knowledgeSources.length === 1 && isActive
                        return (
                          <button
                            key={source.id}
                            onClick={() => {
                              if (isActive) {
                                if (!isLastOne) {
                                  setKnowledgeSources(knowledgeSources.filter(s => s !== source.id))
                                }
                              } else {
                                setKnowledgeSources([...knowledgeSources, source.id])
                              }
                            }}
                            className={cn(
                              'flex items-center gap-1 px-1.5 py-0.5 rounded text-xs transition-all',
                              isActive
                                ? 'bg-theme-primary/20 text-theme-primary border border-theme-primary/30'
                                : 'text-theme-muted hover:text-theme-text hover:bg-theme-bg/50',
                              isLastOne && 'cursor-not-allowed opacity-60'
                            )}
                            title={isLastOne ? `${source.label}（至少选择一个）` : source.label}
                          >
                            <source.icon className="w-3 h-3" />
                          </button>
                        )
                      })}
                    </div>
                  )}
                  
                  {/* 快速模式开关 */}
                  <button
                    onClick={() => setUseFastMode(!useFastMode)}
                    className={cn(
                      'flex items-center gap-1 lg:gap-1.5 px-2 py-1 rounded transition-colors',
                      useFastMode 
                        ? 'bg-yellow-500/20 text-yellow-500' 
                        : 'text-theme-muted hover:text-theme-text'
                    )}
                    title={useFastMode 
                      ? '快速模式 ON：使用双 LLM 架构，Token 消耗降低 60-70%。适合编码/解码/哈希/网络查询' 
                      : '快速模式 OFF：使用完整 Tool Calling 模式'
                    }
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">快速</span> {useFastMode ? '⚡' : 'OFF'}
                  </button>
                  
                  {/* Skill 选择器（仅在快速模式下显示） */}
                  {useFastMode && (
                    <SkillSelector onManageClick={() => setShowAgentConfig(true)} />
                  )}
                  
                  {/* Trace 面板开关 */}
                  {useFastMode && !isMobileView && (
                    <button
                      onClick={() => setShowTracePanel(!showTracePanel)}
                      className={cn(
                        'flex items-center gap-1 lg:gap-1.5 px-2 py-1 rounded transition-colors',
                        showTracePanel 
                          ? 'bg-purple-500/20 text-purple-500' 
                          : 'text-theme-muted hover:text-theme-text'
                      )}
                      title="显示/隐藏执行追踪面板"
                    >
                      <Activity className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Trace</span>
                    </button>
                  )}
                </div>
                
                {/* 模型信息和 Token 消耗 */}
                <div className="flex items-center gap-2 text-theme-muted truncate">
                  {lastTokensUsed !== null && (
                    <span className="text-yellow-500 text-xs">~{lastTokensUsed} tokens</span>
                  )}
                  {currentProvider?.icon} <span className="hidden sm:inline">{config?.model || '未配置'}</span>
                </div>
              </div>
              
              {/* 引用来源显示 */}
              {lastSources.length > 0 && !isLoading && (
                <div className="max-w-4xl mx-auto mt-3 p-3 bg-theme-bg/50 rounded-lg border border-theme-border">
                  <div className="flex items-center gap-2 text-xs text-theme-muted mb-2">
                    <BookOpen className="w-3.5 h-3.5" />
                    上次回答引用了 {lastSources.length} 个知识来源
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {lastSources.map((source, i) => (
                      <a
                        key={i}
                        href={source.url || (source.source_type === 'note' ? `/knowledge/notes` : `/knowledge`)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 px-2 py-1 bg-theme-card rounded text-xs text-theme-text hover:text-theme-primary transition-colors"
                      >
                        {source.source_type === 'note' && <FileText className="w-3 h-3 text-blue-400" />}
                        {source.source_type === 'bookmark' && <Link2 className="w-3 h-3 text-green-400" />}
                        {source.source_type === 'file' && <FileUp className="w-3 h-3 text-orange-400" />}
                        <span className="truncate max-w-[150px]">{source.title}</span>
                        <ExternalLink className="w-2.5 h-2.5 opacity-50" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          // 空状态 - 欢迎页面
          <div className="flex-1 flex flex-col items-center justify-center p-4 lg:p-8 overflow-auto">
            <div className="w-16 h-16 lg:w-20 lg:h-20 rounded-2xl bg-gradient-to-br from-theme-primary to-theme-secondary flex items-center justify-center mb-4 lg:mb-6">
              <Sparkles className="w-8 h-8 lg:w-10 lg:h-10 text-theme-bg" />
            </div>
            <h1 className="text-2xl lg:text-3xl font-bold text-theme-text mb-2 text-center">AI 安全助手</h1>
            <p className="text-theme-muted mb-6 lg:mb-8 text-center max-w-md text-sm lg:text-base">
              专业的 Web 安全分析助手，可帮助分析请求、识别漏洞、生成测试 payload
            </p>
            
            {!config && (
              <div className="mb-4 lg:mb-6 p-3 lg:p-4 bg-theme-warning/10 border border-theme-warning/30 rounded-lg text-center">
                <p className="text-theme-warning text-sm flex items-center justify-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  请先配置 API Key
                </p>
                <button
                  onClick={() => setShowSettings(true)}
                  className="mt-2 btn btn-sm btn-outline"
                >
                  前往设置
                </button>
              </div>
            )}
            
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 lg:gap-3 max-w-2xl w-full">
              {[
                '帮我分析这段代码的安全问题',
                '生成 SQL 注入测试 payload',
                '解释 XSS 漏洞原理',
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => {
                    createSession()
                    setInput(prompt)
                    // 延迟聚焦，等待会话创建和输入框渲染
                    setTimeout(() => inputRef.current?.focus(), 100)
                  }}
                  className="p-2.5 lg:p-3 text-sm text-left rounded-lg bg-theme-card border border-theme-border hover:border-theme-primary/50 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
            <button
              onClick={() => createSession()}
              className="mt-6 lg:mt-8 btn btn-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              开始新对话
            </button>
            <p className="mt-4 lg:mt-6 text-xs text-theme-muted/60 text-center max-w-sm px-4">
              💡 对话记录仅存储在浏览器本地，登出后将清除。如需永久保存 AI 回复，可点击消息旁的 <FileText className="w-3 h-3 inline" /> 图标转存到笔记。
            </p>
          </div>
        )}
      </div>
      
      {/* 右侧 Trace 面板 */}
      {showTracePanel && useFastMode && !isMobileView && (
        <div className="w-80 flex-shrink-0">
          <TraceTimeline />
        </div>
      )}
      
      {/* 设置弹窗 */}
      {showSettings && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
        />
      )}
      
      {/* Agent 配置弹窗 */}
      <AgentConfigPanel
        isOpen={showAgentConfig}
        onClose={() => setShowAgentConfig(false)}
      />
    </div>
  )
}

// 代码块组件（带复制按钮）
function CodeBlock({ 
  language, 
  children 
}: { 
  language: string
  children: string 
}) {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(children)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div className="relative group/code my-3 overflow-hidden">
      {/* 语言标签和复制按钮 */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e1e] rounded-t-lg border-b border-gray-700">
        <span className="text-xs text-gray-400 font-mono">{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-green-400" />
              <span className="text-green-400">已复制</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>复制</span>
            </>
          )}
        </button>
      </div>
      <div className="overflow-x-auto">
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={language || 'text'}
          PreTag="div"
          customStyle={{
            margin: 0,
            borderRadius: '0 0 0.5rem 0.5rem',
            fontSize: '0.875rem',
            padding: '1rem',
            minWidth: 'min-content',
          }}
        >
          {children}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}

// 消息气泡组件（使用 memo 优化）
interface MessageBubbleProps {
  message: ChatMessage
  isStreaming?: boolean
  onCopy: () => void
  isCopied: boolean
  onSaveToNote?: () => void
  isSaving?: boolean
}

const MessageBubble = memo(function MessageBubble({ 
  message, 
  isStreaming = false,
  onCopy, 
  isCopied,
  onSaveToNote,
  isSaving
}: MessageBubbleProps) {
  const isUser = message.role === 'user'
  
  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div className={cn(
        'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
        isUser ? 'bg-theme-secondary/20' : 'bg-theme-primary/20'
      )}>
        {isUser ? (
          <User className="w-4 h-4 text-theme-secondary" />
        ) : (
          <Bot className="w-4 h-4 text-theme-primary" />
        )}
      </div>
      
      <div className={cn(
        'flex-1 max-w-3xl group min-w-0 overflow-hidden',
        isUser && 'flex flex-col items-end'
      )}>
        <div className={cn(
          'rounded-lg px-4 py-3 overflow-hidden max-w-full',
          isUser 
            ? 'bg-theme-secondary/20 border border-theme-secondary/30 text-theme-text' 
            : 'bg-theme-card border border-theme-border'
        )}>
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : isStreaming ? (
            // 流式输出时使用简化渲染
            <div className="prose prose-invert prose-sm max-w-none break-words prose-p:text-theme-text">
              <p className="whitespace-pre-wrap">{message.content || '...'}</p>
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words overflow-hidden
              prose-headings:text-theme-text prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
              prose-p:text-theme-text prose-p:leading-relaxed prose-p:my-2
              prose-a:text-theme-primary prose-a:no-underline hover:prose-a:underline
              prose-strong:text-theme-strong prose-strong:font-semibold
              prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-theme-text
              prose-blockquote:border-l-theme-primary prose-blockquote:bg-theme-bg/50 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r
              prose-table:border-collapse prose-th:bg-theme-bg prose-th:px-3 prose-th:py-2 prose-th:border prose-th:border-theme-border
              prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-theme-border
              prose-hr:border-theme-border
              prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:overflow-x-auto"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // 代码块
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '')
                    const codeContent = String(children).replace(/\n$/, '')
                    const isInline = !match && !codeContent.includes('\n')
                    
                    if (isInline) {
                      return (
                        <code 
                          className="px-1.5 py-0.5 bg-theme-border/50 rounded text-theme-text text-sm font-mono" 
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }
                    
                    return <CodeBlock language={match?.[1] || 'text'}>{codeContent}</CodeBlock>
                  },
                  // 链接 - 新窗口打开
                  a({ href, children, ...props }) {
                    return (
                      <a 
                        href={href} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-theme-primary hover:text-theme-secondary transition-colors"
                        {...props}
                      >
                        {children}
                      </a>
                    )
                  },
                  // 表格
                  table({ children }) {
                    return (
                      <div className="overflow-x-auto my-3 rounded-lg border border-theme-border">
                        <table className="min-w-full divide-y divide-theme-border">{children}</table>
                      </div>
                    )
                  },
                  thead({ children }) {
                    return <thead className="bg-theme-bg">{children}</thead>
                  },
                  th({ children }) {
                    return (
                      <th className="px-4 py-2 text-left text-sm font-semibold text-theme-text border-b border-theme-border">
                        {children}
                      </th>
                    )
                  },
                  td({ children }) {
                    return (
                      <td className="px-4 py-2 text-sm text-theme-text">
                        {children}
                      </td>
                    )
                  },
                }}
              >
                {message.content || '...'}
              </ReactMarkdown>
            </div>
          )}
        </div>
        
        {/* 消息操作按钮 */}
        {message.content && !isStreaming && (
          <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={onCopy}
              className="p-1 rounded text-theme-muted hover:text-theme-primary transition-colors"
              title="复制"
            >
              {isCopied ? (
                <Check className="w-3.5 h-3.5 text-theme-success" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
            
            {/* AI 消息显示保存到笔记按钮 */}
            {!isUser && onSaveToNote && (
              <button
                onClick={onSaveToNote}
                disabled={isSaving}
                className="p-1 rounded text-theme-muted hover:text-theme-primary transition-colors disabled:opacity-50"
                title="保存到笔记"
              >
                {isSaving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <FileText className="w-3.5 h-3.5" />
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  return (
    prevProps.message.id === nextProps.message.id &&
    prevProps.message.content === nextProps.message.content &&
    prevProps.isStreaming === nextProps.isStreaming &&
    prevProps.isCopied === nextProps.isCopied &&
    prevProps.isSaving === nextProps.isSaving
  )
})

// 设置弹窗组件
function SettingsModal({
  onClose,
}: {
  onClose: () => void
}) {
  const { providers, config, updateConfig } = useLLMStore()
  
  // 系统默认配置
  const [defaultConfig, setDefaultConfig] = useState<{
    available: boolean
    provider_id: string | null
    provider_name?: string
    model: string | null
    models: string[]
  } | null>(null)
  
  // 本地表单状态
  const [formData, setFormData] = useState({
    provider_id: config?.provider_id || 'qwen',
    api_key: '',
    base_url: config?.base_url || '',
    model: config?.model || '',
    use_system_default: config?.use_system_default || false,
  })
  const [showApiKey, setShowApiKey] = useState(false)
  const [useCustomModel, setUseCustomModel] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [fetchedModels, setFetchedModels] = useState<string[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelsFetchError, setModelsFetchError] = useState<string | null>(null)
  
  const currentProvider = providers.find(p => p.id === formData.provider_id)
  
  // 加载系统默认配置
  useEffect(() => {
    const loadDefaultConfig = async () => {
      try {
        const { data } = await llmApi.getDefaultConfig()
        setDefaultConfig(data)
      } catch {
        setDefaultConfig({ available: false, provider_id: null, model: null, models: [] })
      }
    }
    loadDefaultConfig()
  }, [])
  
  // 初始化表单
  useEffect(() => {
    if (config) {
      setFormData({
        provider_id: config.provider_id,
        api_key: '', // 不显示实际的 API Key
        base_url: config.base_url || '',
        model: config.model,
        use_system_default: config.use_system_default || false,
      })
    }
  }, [config])
  
  // 合并预定义模型和动态获取的模型
  // 如果使用系统默认，显示系统默认的模型列表
  const availableModels = formData.use_system_default && defaultConfig?.available
    ? defaultConfig.models
    : [
        ...(currentProvider?.models || []),
        ...fetchedModels.filter(m => !currentProvider?.models.includes(m))
      ]
  
  // 切换提供商
  const handleProviderChange = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId)
    if (provider) {
      setFormData({
        ...formData,
        provider_id: providerId,
        base_url: provider.base_url,
        model: provider.default_model,
      })
      setFetchedModels([])
      setModelsFetchError(null)
      setUseCustomModel(false)
    }
  }
  
  // 从 API 获取模型列表
  const fetchModels = useCallback(async () => {
    if (!formData.base_url) {
      toast.error('请先填写 API 地址')
      return
    }
    
    // Ollama 不需要 API Key，其他需要（如果没有保存过则需要填写）
    if (formData.provider_id !== 'ollama' && !formData.api_key && !config?.api_key_set) {
      toast.error('请先填写 API Key')
      return
    }
    
    setIsLoadingModels(true)
    setModelsFetchError(null)
    
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      
      // 使用新输入的 API Key 或已保存的
      const apiKey = formData.api_key || (config?.api_key_set ? 'SAVED' : '')
      if (apiKey && formData.provider_id !== 'ollama') {
        // 如果是已保存的 key，需要通过后端代理获取
        if (apiKey === 'SAVED') {
          // TODO: 添加后端代理接口
          toast.error('请输入新的 API Key 或使用后端代理')
          setIsLoadingModels(false)
          return
        }
        headers['Authorization'] = `Bearer ${apiKey}`
      }
      
      const response = await fetch(`${formData.base_url}/models`, { headers })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      // 处理不同格式的响应
      let models: string[] = []
      if (Array.isArray(data)) {
        // Ollama 格式: [{ name: "llama3" }, ...]
        models = data.map((m: { name?: string; id?: string }) => m.name || m.id || '').filter(Boolean)
      } else if (data.data && Array.isArray(data.data)) {
        // OpenAI 格式: { data: [{ id: "gpt-4" }, ...] }
        models = data.data.map((m: { id?: string; name?: string }) => m.id || m.name || '').filter(Boolean)
      } else if (data.models && Array.isArray(data.models)) {
        // 其他格式
        models = data.models.map((m: string | { id?: string; name?: string }) => 
          typeof m === 'string' ? m : (m.id || m.name || '')
        ).filter(Boolean)
      }
      
      if (models.length === 0) {
        setModelsFetchError('未获取到任何模型')
      } else {
        setFetchedModels(models)
        toast.success(`获取到 ${models.length} 个模型`)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取模型列表失败'
      setModelsFetchError(message)
      toast.error(message)
    } finally {
      setIsLoadingModels(false)
    }
  }, [formData.base_url, formData.api_key, formData.provider_id, config?.api_key_set])
  
  // 保存配置
  const handleSave = async () => {
    if (!formData.model) {
      toast.error('请选择模型')
      return
    }
    
    // 如果使用系统默认，不需要检查 API Key
    // 如果没有使用系统默认，且没有保存过 API Key 且不是 Ollama，需要填写
    if (!formData.use_system_default && !config?.api_key_set && !formData.api_key && formData.provider_id !== 'ollama') {
      toast.error('请填写 API Key')
      return
    }
    
    setIsSaving(true)
    try {
      await updateConfig({
        provider_id: formData.use_system_default && defaultConfig?.provider_id ? defaultConfig.provider_id : formData.provider_id,
        api_key: formData.use_system_default ? undefined : (formData.api_key || undefined),
        base_url: formData.use_system_default ? undefined : formData.base_url,
        model: formData.model,
        use_system_default: formData.use_system_default,
      })
      toast.success('配置已保存')
      onClose()
    } catch {
      // 错误已在 store 中处理
    } finally {
      setIsSaving(false)
    }
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[150] p-4">
      <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-lg p-6 animate-fadeIn max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">API 设置</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-theme-bg">
            <X className="w-5 h-5 text-theme-muted" />
          </button>
        </div>
        
        <div className="space-y-4">
          {/* 使用系统默认选项 */}
          {defaultConfig?.available && (
            <div className="p-4 rounded-lg border border-theme-border bg-theme-bg/50">
              <label className="flex items-center justify-between cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">使用系统默认配置</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-theme-primary/20 text-theme-primary">
                      {defaultConfig.provider_name}
                    </span>
                  </div>
                  <p className="text-xs text-theme-muted mt-1">
                    使用管理员预配置的 API Key，无需自行设置
                  </p>
                </div>
                <div 
                  onClick={() => {
                    const useDefault = !formData.use_system_default
                    setFormData({
                      ...formData,
                      use_system_default: useDefault,
                      // 如果切换到使用系统默认，自动选择系统默认的模型
                      model: useDefault && defaultConfig?.model ? defaultConfig.model : formData.model,
                    })
                  }}
                  className={cn(
                    'w-12 h-6 rounded-full transition-colors cursor-pointer relative',
                    formData.use_system_default ? 'bg-theme-primary' : 'bg-theme-border'
                  )}
                >
                  <div className={cn(
                    'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                    formData.use_system_default ? 'translate-x-7' : 'translate-x-1'
                  )} />
                </div>
              </label>
            </div>
          )}
          
          {/* 提供商选择 */}
          <div className={formData.use_system_default ? 'opacity-50 pointer-events-none' : ''}>
            <label className="block text-sm text-theme-muted mb-2">选择服务商</label>
            <div className="grid grid-cols-2 gap-2">
              {providers.map(provider => (
                <button
                  key={provider.id}
                  onClick={() => handleProviderChange(provider.id)}
                  className={cn(
                    'p-3 rounded-lg border text-left transition-all',
                    formData.provider_id === provider.id
                      ? 'border-theme-primary bg-theme-primary/10'
                      : 'border-theme-border hover:border-theme-primary/50'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{provider.icon}</span>
                    <span className="font-medium text-sm">{provider.name}</span>
                  </div>
                  <p className="text-xs text-theme-muted mt-1">{provider.description}</p>
                </button>
              ))}
            </div>
          </div>
          
          {/* API Key - 使用系统默认时隐藏 */}
          {!formData.use_system_default && (
          <div>
            <label className="block text-sm text-theme-muted mb-2">
              API Key 
              {formData.provider_id === 'ollama' && ' (本地无需填写)'}
              {config?.api_key_set && (
                <span className="ml-2 text-xs text-theme-success">✓ 已保存</span>
              )}
            </label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                placeholder={
                  config?.api_key_set 
                    ? '已保存，留空保持不变' 
                    : (formData.provider_id === 'ollama' ? '本地部署无需 API Key' : 'sk-...')
                }
                className="w-full pr-20"
              />
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-theme-muted hover:text-theme-text"
              >
                {showApiKey ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          )}
          
          {/* Base URL - 使用系统默认时隐藏 */}
          {!formData.use_system_default && (
          <div>
            <label className="block text-sm text-theme-muted mb-2">API 地址</label>
            <input
              type="text"
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              placeholder="https://api.example.com/v1"
              className="w-full"
            />
          </div>
          )}
          
          {/* 模型选择 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">模型</label>
              {/* 使用系统默认时不显示获取模型按钮 */}
              {!formData.use_system_default && (
              <div className="flex items-center gap-2">
                <button
                  onClick={fetchModels}
                  disabled={isLoadingModels}
                  className="flex items-center gap-1 text-xs text-theme-primary hover:text-theme-secondary transition-colors disabled:opacity-50"
                  title="从 API 获取可用模型列表"
                >
                  <RefreshCw className={cn('w-3 h-3', isLoadingModels && 'animate-spin')} />
                  获取模型
                </button>
                <span className="text-theme-border">|</span>
                <button
                  onClick={() => setUseCustomModel(!useCustomModel)}
                  className={cn(
                    'flex items-center gap-1 text-xs transition-colors',
                    useCustomModel ? 'text-theme-secondary' : 'text-theme-muted hover:text-theme-text'
                  )}
                  title="手动输入模型名称"
                >
                  <Edit3 className="w-3 h-3" />
                  手动输入
                </button>
              </div>
              )}
            </div>
            
            {useCustomModel ? (
              <input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="输入模型名称，如 gpt-4、llama3..."
                className="w-full"
              />
            ) : availableModels.length > 0 ? (
              <select
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                className="w-full"
              >
                {/* 使用系统默认时，直接显示系统默认的模型列表 */}
                {formData.use_system_default ? (
                  availableModels.map(model => (
                    <option key={model} value={model}>{model}</option>
                  ))
                ) : (
                  <>
                    {/* 预定义模型 */}
                    {currentProvider && currentProvider.models.length > 0 && (
                      <optgroup label="推荐模型">
                        {currentProvider.models.map(model => (
                          <option key={model} value={model}>{model}</option>
                        ))}
                      </optgroup>
                    )}
                    {/* 动态获取的模型 */}
                    {fetchedModels.length > 0 && (
                      <optgroup label="从 API 获取">
                        {fetchedModels
                          .filter(m => !currentProvider?.models.includes(m))
                          .map(model => (
                            <option key={model} value={model}>{model}</option>
                          ))
                        }
                      </optgroup>
                    )}
                  </>
                )}
              </select>
            ) : (
              <input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="输入模型名称"
                className="w-full"
              />
            )}
            
            {/* 提示信息 */}
            {modelsFetchError && (
              <p className="text-xs text-theme-danger mt-1">{modelsFetchError}</p>
            )}
            {fetchedModels.length > 0 && !useCustomModel && (
              <p className="text-xs text-theme-muted mt-1">
                已加载 {fetchedModels.length} 个模型
              </p>
            )}
          </div>
        </div>
        
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn btn-ghost">
            取消
          </button>
          <button 
            onClick={handleSave} 
            disabled={isSaving}
            className="btn btn-primary"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                保存中...
              </>
            ) : (
              '保存配置'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
