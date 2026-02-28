/**
 * Trace Store - 管理 AI Agent 执行追踪状态
 */
import { create } from 'zustand'

// Trace 事件类型
export type TraceType = 
  | 'intent'
  | 'tool_call'
  | 'llm_call'
  | 'memory_recall'
  | 'memory_save'
  | 'conversation_history'
  | 'rag_query'
  | 'mcp_request'
  | 'workflow_step'
  | 'agent_loop'
  | 'rule_match'
  | 'summary'
  | 'skill'
  | 'skill_select'
  | 'error'

// 事件阶段
export type TraceStage = 'start' | 'end' | 'error'

// Trace 事件
export interface TraceEvent {
  id: string
  type: TraceType
  name: string
  stage: TraceStage
  timestamp: number
  parent_id?: string
  duration_ms?: number
  data: Record<string, unknown>
  metadata: Record<string, unknown>
}

// 合并后的 Trace Span（用于 UI 展示）
export interface TraceSpan {
  id: string
  type: TraceType
  name: string
  startTime: number
  endTime?: number
  duration_ms?: number
  data: Record<string, unknown>
  metadata: Record<string, unknown>
  status: 'running' | 'completed' | 'error'
  children: TraceSpan[]
}

// Trace 会话
export interface TraceSession {
  id: string
  traceId: string
  startTime: number
  endTime?: number
  events: TraceEvent[]
  spans: TraceSpan[]
  summary?: {
    totalTime_ms: number
    totalTokens: number
    eventCount: number
  }
}

interface TraceState {
  // 当前活跃的会话
  currentSession: TraceSession | null
  // 历史会话
  sessions: TraceSession[]
  // 是否显示追踪面板
  isPanelVisible: boolean
  // 选中的事件 ID
  selectedEventId: string | null
  
  // Actions
  startSession: (traceId: string) => void
  endSession: () => void
  addEvent: (event: TraceEvent) => void
  addEvents: (events: TraceEvent[]) => void
  togglePanel: () => void
  setSelectedEvent: (eventId: string | null) => void
  clearCurrentSession: () => void
  clearAllSessions: () => void
}

// 将事件列表转换为 Span 树
function eventsToSpans(events: TraceEvent[]): TraceSpan[] {
  const spanMap = new Map<string, TraceSpan>()
  const rootSpans: TraceSpan[] = []
  
  // 先处理所有 start 事件
  for (const event of events) {
    if (event.stage === 'start') {
      const span: TraceSpan = {
        id: event.id,
        type: event.type,
        name: event.name,
        startTime: event.timestamp,
        data: { ...event.data },
        metadata: { ...event.metadata },
        status: 'running',
        children: [],
      }
      spanMap.set(event.id, span)
      
      if (event.parent_id && spanMap.has(event.parent_id)) {
        spanMap.get(event.parent_id)!.children.push(span)
      } else {
        rootSpans.push(span)
      }
    }
  }
  
  // 再处理所有 end/error 事件
  for (const event of events) {
    if (event.stage === 'end' || event.stage === 'error') {
      const span = spanMap.get(event.id)
      if (span) {
        span.endTime = event.timestamp
        span.duration_ms = event.duration_ms
        span.status = event.stage === 'error' ? 'error' : 'completed'
        // 合并数据
        span.data = { ...span.data, ...event.data }
        span.metadata = { ...span.metadata, ...event.metadata }
      } else {
        // 没有对应的 start 事件，创建一个完整的 span
        const newSpan: TraceSpan = {
          id: event.id,
          type: event.type,
          name: event.name,
          startTime: event.timestamp - (event.duration_ms || 0),
          endTime: event.timestamp,
          duration_ms: event.duration_ms,
          data: { ...event.data },
          metadata: { ...event.metadata },
          status: event.stage === 'error' ? 'error' : 'completed',
          children: [],
        }
        rootSpans.push(newSpan)
      }
    }
  }
  
  // 按开始时间排序
  rootSpans.sort((a, b) => a.startTime - b.startTime)
  
  return rootSpans
}

export const useTraceStore = create<TraceState>((set, get) => ({
  currentSession: null,
  sessions: [],
  isPanelVisible: true,
  selectedEventId: null,
  
  startSession: (traceId: string) => {
    const session: TraceSession = {
      id: `session_${Date.now()}`,
      traceId,
      startTime: Date.now(),
      events: [],
      spans: [],
    }
    set({ currentSession: session })
  },
  
  endSession: () => {
    const { currentSession, sessions } = get()
    if (currentSession) {
      const endedSession: TraceSession = {
        ...currentSession,
        endTime: Date.now(),
        summary: {
          totalTime_ms: Date.now() - currentSession.startTime,
          totalTokens: currentSession.events.reduce((sum, e) => 
            sum + ((e.metadata?.tokens as number) || 0), 0),
          eventCount: currentSession.events.length,
        },
      }
      set({
        currentSession: null,
        sessions: [endedSession, ...sessions].slice(0, 50), // 保留最近50条
      })
    }
  },
  
  addEvent: (event: TraceEvent) => {
    const { currentSession } = get()
    if (!currentSession) return
    
    const newEvents = [...currentSession.events, event]
    const newSpans = eventsToSpans(newEvents)
    
    set({
      currentSession: {
        ...currentSession,
        events: newEvents,
        spans: newSpans,
      },
    })
  },
  
  addEvents: (events: TraceEvent[]) => {
    const { currentSession } = get()
    if (!currentSession) return
    
    const newEvents = [...currentSession.events, ...events]
    const newSpans = eventsToSpans(newEvents)
    
    set({
      currentSession: {
        ...currentSession,
        events: newEvents,
        spans: newSpans,
      },
    })
  },
  
  togglePanel: () => set(state => ({ isPanelVisible: !state.isPanelVisible })),
  
  setSelectedEvent: (eventId: string | null) => set({ selectedEventId: eventId }),
  
  clearCurrentSession: () => set({ currentSession: null }),
  
  clearAllSessions: () => set({ sessions: [], currentSession: null }),
}))
