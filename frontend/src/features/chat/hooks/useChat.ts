import { useState, useRef, useCallback } from 'react'
import { useLLMStore } from '@/stores/llmStore'
import { useAuthStore } from '@/stores/authStore'
import { useTraceStore, type TraceEvent } from '@/stores/traceStore'
import { useSkillStore } from '@/stores/skillStore'
import { notesApi, toolsApi } from '@/lib/api'
import toast from 'react-hot-toast'
import type { RAGSource } from '../components/ChatInput'

function createThrottledUpdater() {
  let pendingContent = ''
  let timer: number | null = null
  let lastUpdateTime = 0
  const THROTTLE_MS = 16

  return {
    update(
      sessionId: string,
      messageId: string,
      content: string,
      updateFn: (sid: string, mid: string, c: string) => void,
    ) {
      pendingContent = content
      const now = Date.now()
      if (now - lastUpdateTime >= THROTTLE_MS) {
        updateFn(sessionId, messageId, pendingContent)
        lastUpdateTime = now
        return
      }
      if (!timer) {
        timer = window.setTimeout(() => {
          updateFn(sessionId, messageId, pendingContent)
          lastUpdateTime = Date.now()
          timer = null
        }, THROTTLE_MS - (now - lastUpdateTime))
      }
    },
    flush(
      sessionId: string,
      messageId: string,
      content: string,
      updateFn: (sid: string, mid: string, c: string) => void,
    ) {
      if (timer) { clearTimeout(timer); timer = null }
      updateFn(sessionId, messageId, content)
    },
  }
}

export default function useChat() {
  const { token } = useAuthStore()
  const {
    loadProviders, config, configLoading, loadConfig, getCurrentProvider,
    sessions, currentSessionId, createSession, deleteSession,
    setCurrentSession, getCurrentSession, addMessage, updateMessage, getHistory,
  } = useLLMStore()

  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [savingNoteId, setSavingNoteId] = useState<string | null>(null)
  const [useKnowledge, setUseKnowledge] = useState(true)
  const [knowledgeSources, setKnowledgeSources] = useState<string[]>(['note', 'bookmark', 'file'])
  const [lastSources, setLastSources] = useState<RAGSource[]>([])
  const [useFastMode, setUseFastMode] = useState(true)
  const [lastTokensUsed, setLastTokensUsed] = useState<number | null>(null)
  const [userLocation, setUserLocation] = useState<string | null>(null)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const throttledUpdater = useRef(createThrottledUpdater())

  const {
    startSession: startTraceSession,
    endSession: endTraceSession,
    addEvent: addTraceEvent,
    currentSession: traceCurrentSession,
  } = useTraceStore()
  const { activeSkillIds } = useSkillStore()

  const currentSession = getCurrentSession()
  const currentProvider = getCurrentProvider()

  const fetchLocation = useCallback(async () => {
    try {
      const { data } = await toolsApi.myLocation()
      if (data && !data.error) {
        const loc = data.city || data.region || data.country
        if (loc) setUserLocation(loc)
      }
    } catch { /* ignore */ }
  }, [])

  const copyMessage = useCallback(async (content: string, id: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(id)
      toast.success('\u5DF2\u590D\u5236\u5230\u526A\u8D34\u677F')
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      try {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.style.position = 'fixed'
        ta.style.left = '-9999px'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        setCopiedId(id)
        toast.success('\u5DF2\u590D\u5236\u5230\u526A\u8D34\u677F')
        setTimeout(() => setCopiedId(null), 2000)
      } catch {
        toast.error('\u590D\u5236\u5931\u8D25\uFF0C\u8BF7\u624B\u52A8\u9009\u62E9\u590D\u5236')
      }
    }
  }, [])

  const saveToNote = useCallback(async (content: string, messageId: string) => {
    if (!content.trim()) return
    setSavingNoteId(messageId)
    try {
      const firstLine = content.split('\n')[0].replace(/^#+\s*/, '').trim()
      const title = firstLine.slice(0, 50) || 'AI \u5BF9\u8BDD\u8BB0\u5F55'
      const noteContent =
        `> \u6765\u81EA AI Chat (${currentProvider?.name || 'Unknown'} - ${config?.model})\n` +
        `> \u65F6\u95F4: ${new Date().toLocaleString('zh-CN')}\n\n---\n\n${content}`
      await notesApi.createNote({
        title: title + (firstLine.length > 50 ? '...' : ''),
        content: noteContent,
      })
      toast.success('\u5DF2\u4FDD\u5B58\u5230\u7B14\u8BB0')
    } catch {
      toast.error('\u4FDD\u5B58\u5931\u8D25\uFF0C\u8BF7\u91CD\u8BD5')
    } finally {
      setSavingNoteId(null)
    }
  }, [currentProvider?.name, config?.model])

  const sendMessage = useCallback(async (): Promise<boolean> => {
    if (!input.trim() || isLoading) return false
    if (!config) { toast.error('\u8BF7\u5148\u914D\u7F6E LLM API Key'); return false }
    if (!config.use_system_default && !config.api_key_set && config.provider_id !== 'ollama') {
      toast.error('\u8BF7\u5148\u914D\u7F6E API Key'); return false
    }

    let sessionId = currentSessionId
    if (!sessionId) sessionId = createSession()

    const userMessage = input.trim()
    setInput('')
    if (inputRef.current) inputRef.current.style.height = 'auto'

    const chatHistory = (sessionId && getHistory) ? getHistory(sessionId, 10) : []
    addMessage(sessionId, { role: 'user', content: userMessage })
    addMessage(sessionId, { role: 'assistant', content: '' })

    const sess = useLLMStore.getState().sessions.find(s => s.id === sessionId)
    const assistantMsgId = sess?.messages[sess.messages.length - 1]?.id || null
    setStreamingMessageId(assistantMsgId)
    setIsLoading(true)
    setLastTokensUsed(null)

    try {
      const history = (getCurrentSession()?.messages.slice(0, -1) || [])
        .filter(m => ['user', 'assistant', 'system'].includes(m.role))
        .map(m => ({ role: m.role as 'user' | 'assistant' | 'system', content: m.content }))

      // Fast mode
      if (useFastMode) {
        if (traceCurrentSession) endTraceSession()

        const fastResp = await fetch('/api/llm/fast/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({
            message: userMessage, mode: 'auto', skip_summary: false,
            context: userLocation
              ? { location: userLocation, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }
              : undefined,
            skill_ids: activeSkillIds.length > 0 ? activeSkillIds : undefined,
            history: chatHistory.length > 0 ? chatHistory : undefined,
          }),
        })

        if (fastResp.ok) {
          const reader = fastResp.body?.getReader()
          if (!reader) throw new Error('\u65E0\u6CD5\u8BFB\u53D6\u54CD\u5E9A\u6D41')
          const decoder = new TextDecoder()
          let fastContent = ''
          let fastBuffer = ''
          let fastResult: Record<string, unknown> = {}

          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) break
              fastBuffer += decoder.decode(value, { stream: true })
              const lines = fastBuffer.split('\n')
              fastBuffer = lines.pop() || ''
              for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed || !trimmed.startsWith('data: ')) continue
                const payload = trimmed.slice(6)
                if (!payload) continue
                try {
                  const json = JSON.parse(payload)
                  if (json.stage === 'trace_start' && json.data?.trace_id) startTraceSession(json.data.trace_id)
                  else if (json.stage === 'trace' && json.data) addTraceEvent(json.data as TraceEvent)
                  if (json.stage === 'content') fastContent = json.data
                  else if (json.stage === 'fallback') fastResult.fallback_needed = true
                  else if (json.stage === 'done') fastResult = { ...fastResult, ...json.data }
                } catch { /* JSON parse error */ }
              }
            }
          } finally { reader.releaseLock() }

          if (!fastResult.fallback_needed && fastContent) {
            const est = (fastResult.tokens_estimated as number) || 0
            setLastTokensUsed(est)
            const s2 = useLLMStore.getState().sessions.find(s => s.id === sessionId)
            const lastMsg = s2?.messages[s2.messages.length - 1]
            if (lastMsg && lastMsg.role === 'assistant') {
              const tag = fastResult.rule_matched ? '\u26A1' : '\uD83D\uDE80'
              const tool = fastResult.tool_used ? ` (${fastResult.tool_used})` : ''
              const tokenInfo = est === 0 ? '0 tokens (\u89C4\u5219\u5339\u914D)' : `~${est} tokens`
              updateMessage(sessionId, lastMsg.id,
                `${fastContent}\n\n---\n_${tag} \u5FEB\u901F\u6A21\u5F0F${tool} \u00B7 ${tokenInfo}_`)
            }
            endTraceSession()
            setIsLoading(false)
            setStreamingMessageId(null)
            return true
          }
        }
      }

      // Full mode
      const response = await fetch('/api/llm/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          message: userMessage, history,
          use_knowledge: useKnowledge, knowledge_sources: knowledgeSources, max_results: 5,
        }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(err.detail || '\u8BF7\u6C42\u5931\u8D25')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('\u65E0\u6CD5\u8BFB\u53D6\u54CD\u5E9A\u6D41')
      const decoder = new TextDecoder()
      let content = ''
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed || !trimmed.startsWith('data: ')) continue
            const payload = trimmed.slice(6)
            if (!payload) continue
            try {
              const json = JSON.parse(payload)
              if (json.error) throw new Error(json.error)
              if (json.stage === 'trace_start' && json.data?.trace_id) {
                if (!useTraceStore.getState().currentSession) startTraceSession(json.data.trace_id)
              } else if (json.stage === 'trace' && json.data) {
                addTraceEvent(json.data as TraceEvent)
              }
              if (json.sources) setLastSources(json.sources)
              if (json.done) break
              if (json.content) {
                content += json.content
                const s2 = useLLMStore.getState().sessions.find(s => s.id === sessionId)
                const lastMsg = s2?.messages[s2.messages.length - 1]
                if (lastMsg && lastMsg.role === 'assistant') {
                  throttledUpdater.current.update(sessionId, lastMsg.id, content, updateMessage)
                }
              }
            } catch (e) { if (!(e instanceof SyntaxError)) throw e }
          }
        }
        const fin = useLLMStore.getState().sessions.find(s => s.id === sessionId)
        const finMsg = fin?.messages[fin.messages.length - 1]
        if (finMsg && finMsg.role === 'assistant' && content) {
          throttledUpdater.current.flush(sessionId, finMsg.id, content, updateMessage)
        }
        endTraceSession()
      } finally { reader.releaseLock() }
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : '\u53D1\u9001\u5931\u8D25'
      toast.error(errMsg)
      const s2 = useLLMStore.getState().sessions.find(s => s.id === sessionId)
      const lastMsg = s2?.messages[s2.messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        updateMessage(sessionId, lastMsg.id, `\u274C \u9519\u8BEF: ${errMsg}`)
      }
    } finally {
      setIsLoading(false)
      setStreamingMessageId(null)
    }
    return true
  }, [
    input, isLoading, config, currentSessionId, createSession, getHistory,
    addMessage, getCurrentSession, updateMessage, useFastMode,
    traceCurrentSession, endTraceSession, startTraceSession, addTraceEvent,
    token, userLocation, activeSkillIds, useKnowledge, knowledgeSources,
  ])

  return {
    sessions, currentSessionId, currentSession, currentProvider,
    config, configLoading, loadProviders, loadConfig,
    createSession, deleteSession, setCurrentSession, token,
    input, setInput, isLoading,
    copiedId, copyMessage, savingNoteId, saveToNote,
    useKnowledge, setUseKnowledge,
    knowledgeSources, setKnowledgeSources, lastSources,
    useFastMode, setUseFastMode, lastTokensUsed,
    fetchLocation, streamingMessageId,
    messagesEndRef, inputRef, sendMessage,
  }
}
