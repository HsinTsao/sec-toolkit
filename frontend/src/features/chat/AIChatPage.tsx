import { useState, useEffect, useRef, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import { TraceTimeline } from '@/components/trace'
import { AgentConfigPanel } from '@/components/agent'
import { SkillWelcome } from '@/components/skill/SkillSelector'
import { useSkillStore } from '@/stores/skillStore'
import useChat from './hooks/useChat'
import ChatSidebar from './components/ChatSidebar'
import ChatInput from './components/ChatInput'
import MessageBubble from './components/MessageBubble'
import SettingsModal from './components/SettingsModal'
import WelcomePage from './components/WelcomePage'

export default function AIChatPage() {
  const chat = useChat()
  const { activeSkills } = useSkillStore()

  const [showSettings, setShowSettings] = useState(false)
  const [showChatSidebar, setShowChatSidebar] = useState(false)
  const [showTracePanel, setShowTracePanel] = useState(true)
  const [showAgentConfig, setShowAgentConfig] = useState(false)
  const [isMobileView, setIsMobileView] = useState(false)

  // 监听窗口大小
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768
      setIsMobileView(mobile)
      if (!mobile) setShowChatSidebar(false)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // 加载提供商、配置、位置
  useEffect(() => {
    if (chat.token) {
      chat.loadProviders()
      chat.loadConfig()
    }
  }, [chat.token, chat.loadProviders, chat.loadConfig])

  useEffect(() => { chat.fetchLocation() }, [chat.fetchLocation])

  // 滚动控制
  const prevSessionId = useRef<string | null>(null)
  const prevMessageCount = useRef<number>(0)

  const scrollToBottom = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      chat.messagesEndRef.current?.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'end',
      })
    })
  }, [chat.messagesEndRef])

  useEffect(() => {
    if (chat.currentSessionId !== prevSessionId.current) {
      prevSessionId.current = chat.currentSessionId
      prevMessageCount.current = chat.currentSession?.messages.length || 0
      scrollToBottom(false)
    }
  }, [chat.currentSessionId, chat.currentSession?.messages.length, scrollToBottom])

  useEffect(() => {
    const count = chat.currentSession?.messages.length || 0
    if (count <= prevMessageCount.current) {
      prevMessageCount.current = count
      return
    }
    prevMessageCount.current = count
    const lastMsg = chat.currentSession?.messages[count - 1]
    const isStreaming = chat.isLoading && lastMsg?.role === 'assistant'
    scrollToBottom(!isStreaming)
  }, [chat.currentSession?.messages.length, chat.isLoading, scrollToBottom, chat.currentSession?.messages])

  // sendMessage 需要在配置未设置时打开设置弹窗
  const handleSend = useCallback(async () => {
    if (!chat.config) {
      setShowSettings(true)
      return
    }
    if (!chat.config.use_system_default && !chat.config.api_key_set && chat.config.provider_id !== 'ollama') {
      setShowSettings(true)
    }
    await chat.sendMessage()
  }, [chat])

  return (
    <div className="flex animate-fadeIn -m-4 lg:-m-6 -mb-12 overflow-hidden" style={{ height: 'calc(100vh - 56px - 24px)', minHeight: 0, maxWidth: '100vw' }}>
      {/* 移动端遮罩 */}
      {isMobileView && showChatSidebar && (
        <div
          className="fixed inset-0 bg-black/50 z-20"
          onClick={() => setShowChatSidebar(false)}
        />
      )}

      {/* 左侧会话列表 */}
      <ChatSidebar
        sessions={chat.sessions}
        currentSessionId={chat.currentSessionId}
        onCreateSession={chat.createSession}
        onDeleteSession={chat.deleteSession}
        onSelectSession={chat.setCurrentSession}
        onOpenSettings={() => setShowSettings(true)}
        onOpenAgentConfig={() => setShowAgentConfig(true)}
        isMobileView={isMobileView}
        showChatSidebar={showChatSidebar}
        onCloseSidebar={() => setShowChatSidebar(false)}
        config={chat.config}
        configLoading={chat.configLoading}
        currentProvider={chat.currentProvider}
      />

      {/* 中间聊天区域 */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {chat.currentSession ? (
          <>
            {/* 消息列表 */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4 scroll-smooth">
              {chat.useFastMode && chat.currentSession.messages.length === 0 && activeSkills.length > 0 && (
                <SkillWelcome />
              )}

              {chat.currentSession.messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  isStreaming={chat.streamingMessageId === message.id}
                  onCopy={() => chat.copyMessage(message.content, message.id)}
                  isCopied={chat.copiedId === message.id}
                  onSaveToNote={message.role === 'assistant' ? () => chat.saveToNote(message.content, message.id) : undefined}
                  isSaving={chat.savingNoteId === message.id}
                />
              ))}
              {chat.isLoading && chat.currentSession.messages[chat.currentSession.messages.length - 1]?.content === '' && (
                <div className="flex items-center gap-2 text-theme-muted">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">思考中...</span>
                </div>
              )}
              <div ref={chat.messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <ChatInput
              input={chat.input}
              onInputChange={chat.setInput}
              isLoading={chat.isLoading}
              onSend={handleSend}
              isMobileView={isMobileView}
              onOpenChatSidebar={() => setShowChatSidebar(true)}
              useKnowledge={chat.useKnowledge}
              onToggleKnowledge={() => chat.setUseKnowledge(!chat.useKnowledge)}
              knowledgeSources={chat.knowledgeSources}
              onSetKnowledgeSources={chat.setKnowledgeSources}
              useFastMode={chat.useFastMode}
              onToggleFastMode={() => chat.setUseFastMode(!chat.useFastMode)}
              showTracePanel={showTracePanel}
              onToggleTracePanel={() => setShowTracePanel(!showTracePanel)}
              onOpenAgentConfig={() => setShowAgentConfig(true)}
              lastTokensUsed={chat.lastTokensUsed}
              currentProvider={chat.currentProvider}
              config={chat.config}
              lastSources={chat.lastSources}
              inputRef={chat.inputRef}
            />
          </>
        ) : (
          <WelcomePage
            config={chat.config}
            onOpenSettings={() => setShowSettings(true)}
            onCreateSession={chat.createSession}
            onSetInput={chat.setInput}
            inputRef={chat.inputRef}
          />
        )}
      </div>

      {/* 右侧 Trace 面板 */}
      {showTracePanel && chat.useFastMode && !isMobileView && (
        <div className="w-80 flex-shrink-0">
          <TraceTimeline />
        </div>
      )}

      {/* 弹窗 */}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      <AgentConfigPanel isOpen={showAgentConfig} onClose={() => setShowAgentConfig(false)} />
    </div>
  )
}
