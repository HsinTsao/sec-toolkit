import { useState, useRef, useEffect, useCallback } from 'react'
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
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { useLLMStore, type ChatMessage } from '@/stores/llmStore'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import { notesApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

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
  const [isMobileView, setIsMobileView] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
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
    await navigator.clipboard.writeText(content)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
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
    
    if (!config.api_key_set && config.provider_id !== 'ollama') {
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
    
    // 添加用户消息
    addMessage(sessionId, { role: 'user', content: userMessage })
    
    // 添加助手消息占位
    addMessage(sessionId, { role: 'assistant', content: '' })
    
    setIsLoading(true)
    
    try {
      // 获取历史消息（只保留 user/assistant/system 类型，过滤掉可能存在的无效消息）
      const history = (getCurrentSession()?.messages.slice(0, -1) || [])
        .filter(m => ['user', 'assistant', 'system'].includes(m.role))
        .map(m => ({
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
        }))
      
      // 使用流式 API（支持 RAG）
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
      const decoder = new TextDecoder()
      let content = ''
      
      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(line => line.trim() !== '')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            
            try {
              const json = JSON.parse(data)
              
              if (json.error) {
                throw new Error(json.error)
              }
              
              // 处理来源信息
              if (json.sources) {
                setLastSources(json.sources)
              }
              
              if (json.done) {
                continue
              }
              
              if (json.content) {
                content += json.content
                
                // 更新消息
                const session = useLLMStore.getState().sessions.find(s => s.id === sessionId)
                const lastMsg = session?.messages[session.messages.length - 1]
                if (lastMsg && lastMsg.role === 'assistant') {
                  updateMessage(sessionId, lastMsg.id, content)
                }
              }
            } catch (e) {
              if (e instanceof SyntaxError) {
                // 忽略 JSON 解析错误
              } else {
                throw e
              }
            }
          }
        }
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
    }
  }
  
  // 计算高度：视口高度 - header(64px) - statusbar(24px) - padding(24px上 + 48px下)
  return (
    <div className="flex animate-fadeIn -m-4 lg:-m-6 -mb-12" style={{ height: 'calc(100vh - 56px - 24px)', minHeight: 0 }}>
      {/* 移动端遮罩层 */}
      {isMobileView && showChatSidebar && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setShowChatSidebar(false)}
        />
      )}
      
      {/* 左侧会话列表 - 移动端抽屉式，桌面端固定显示 */}
      <div className={cn(
        "bg-theme-card border-r border-theme-border flex flex-col flex-shrink-0 z-50",
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
              <button
                key={session.id}
                onClick={() => {
                  setCurrentSession(session.id)
                  if (isMobileView) setShowChatSidebar(false)
                }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors group',
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
              </button>
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
        </div>
      </div>
      
      {/* 右侧聊天区域 - 独立滚动 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {currentSession ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4">
              {currentSession.messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
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
            <div className="p-3 lg:p-4 border-t border-theme-border">
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
                </div>
                
                {/* 模型信息 */}
                <div className="text-theme-muted truncate">
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
                '分析这个 HTTP 请求',
                '帮我理解这个漏洞',
                '生成 CSRF PoC',
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => {
                    setInput(prompt)
                    inputRef.current?.focus()
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
      
      {/* 设置弹窗 */}
      {showSettings && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
        />
      )}
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
    <div className="relative group/code my-3">
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
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language || 'text'}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0 0 0.5rem 0.5rem',
          fontSize: '0.875rem',
          padding: '1rem',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  )
}

// 消息气泡组件
function MessageBubble({ 
  message, 
  onCopy, 
  isCopied,
  onSaveToNote,
  isSaving
}: { 
  message: ChatMessage
  onCopy: () => void
  isCopied: boolean
  onSaveToNote?: () => void
  isSaving?: boolean
}) {
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
        'flex-1 max-w-3xl group min-w-0',
        isUser && 'flex flex-col items-end'
      )}>
        <div className={cn(
          'rounded-lg px-4 py-3 overflow-hidden',
          isUser 
            ? 'bg-theme-secondary/20 border border-theme-secondary/30 text-theme-text' 
            : 'bg-theme-card border border-theme-border'
        )}>
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words 
              prose-headings:text-theme-text prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
              prose-p:text-theme-text prose-p:leading-relaxed prose-p:my-2
              prose-a:text-theme-primary prose-a:no-underline hover:prose-a:underline
              prose-strong:text-theme-strong prose-strong:font-semibold
              prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-li:text-theme-text
              prose-blockquote:border-l-theme-primary prose-blockquote:bg-theme-bg/50 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r
              prose-table:border-collapse prose-th:bg-theme-bg prose-th:px-3 prose-th:py-2 prose-th:border prose-th:border-theme-border
              prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-theme-border
              prose-hr:border-theme-border
              prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0"
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
        {message.content && (
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
}

// 设置弹窗组件
function SettingsModal({
  onClose,
}: {
  onClose: () => void
}) {
  const { providers, config, updateConfig } = useLLMStore()
  
  // 本地表单状态
  const [formData, setFormData] = useState({
    provider_id: config?.provider_id || 'deepseek',
    api_key: '',
    base_url: config?.base_url || '',
    model: config?.model || '',
  })
  const [showApiKey, setShowApiKey] = useState(false)
  const [useCustomModel, setUseCustomModel] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [fetchedModels, setFetchedModels] = useState<string[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelsFetchError, setModelsFetchError] = useState<string | null>(null)
  
  const currentProvider = providers.find(p => p.id === formData.provider_id)
  
  // 初始化表单
  useEffect(() => {
    if (config) {
      setFormData({
        provider_id: config.provider_id,
        api_key: '', // 不显示实际的 API Key
        base_url: config.base_url || '',
        model: config.model,
      })
    }
  }, [config])
  
  // 合并预定义模型和动态获取的模型
  const availableModels = [
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
    
    // 如果没有保存过 API Key 且不是 Ollama，需要填写
    if (!config?.api_key_set && !formData.api_key && formData.provider_id !== 'ollama') {
      toast.error('请填写 API Key')
      return
    }
    
    setIsSaving(true)
    try {
      await updateConfig({
        provider_id: formData.provider_id,
        api_key: formData.api_key || undefined, // 只有填写了才更新
        base_url: formData.base_url,
        model: formData.model,
      })
      toast.success('配置已保存')
      onClose()
    } catch (error) {
      // 错误已在 store 中处理
    } finally {
      setIsSaving(false)
    }
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-lg p-6 animate-fadeIn max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">API 设置</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-theme-bg">
            <X className="w-5 h-5 text-theme-muted" />
          </button>
        </div>
        
        <div className="space-y-4">
          {/* 提供商选择 */}
          <div>
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
          
          {/* API Key */}
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
          
          {/* Base URL */}
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
          
          {/* 模型选择 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">模型</label>
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
