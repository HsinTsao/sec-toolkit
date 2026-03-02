import { 
  Send, 
  Loader2,
  BookOpen,
  FileText,
  Link2,
  FileUp,
  ExternalLink,
  PanelLeftOpen,
  Sparkles,
  Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { SkillSelector } from '@/components/skill/SkillSelector'
import type { LLMConfig, LLMProvider } from '@/lib/api'

export interface RAGSource {
  source_type: string
  source_id: string
  title: string
  snippet: string
  url?: string
}

interface ChatInputProps {
  input: string
  onInputChange: (value: string) => void
  isLoading: boolean
  onSend: () => void
  isMobileView: boolean
  onOpenChatSidebar: () => void
  useKnowledge: boolean
  onToggleKnowledge: () => void
  knowledgeSources: string[]
  onSetKnowledgeSources: (sources: string[]) => void
  useFastMode: boolean
  onToggleFastMode: () => void
  showTracePanel: boolean
  onToggleTracePanel: () => void
  onOpenAgentConfig: () => void
  lastTokensUsed: number | null
  currentProvider: LLMProvider | null
  config: LLMConfig | null
  lastSources: RAGSource[]
  inputRef: React.RefObject<HTMLTextAreaElement | null>
}

export default function ChatInput({
  input,
  onInputChange,
  isLoading,
  onSend,
  isMobileView,
  onOpenChatSidebar,
  useKnowledge,
  onToggleKnowledge,
  knowledgeSources,
  onSetKnowledgeSources,
  useFastMode,
  onToggleFastMode,
  showTracePanel,
  onToggleTracePanel,
  onOpenAgentConfig,
  lastTokensUsed,
  currentProvider,
  config,
  lastSources,
  inputRef,
}: ChatInputProps) {
  const adjustTextareaHeight = () => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px'
    }
  }

  return (
    <div className="p-3 lg:p-4 border-t border-theme-border bg-theme-bg relative z-[60]">
      <div className="flex gap-2 max-w-4xl mx-auto">
        {isMobileView && (
          <button
            onClick={onOpenChatSidebar}
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
            onInputChange(e.target.value)
            adjustTextareaHeight()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              onSend()
            }
          }}
          placeholder={isMobileView ? "输入消息..." : "输入消息... (Enter 发送, Shift+Enter 换行)"}
          className="flex-1 resize-none min-h-[44px] max-h-[200px] text-sm lg:text-base"
          rows={1}
        />
        <button
          onClick={onSend}
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

      <div className="flex items-center justify-between max-w-4xl mx-auto mt-2 text-xs flex-wrap gap-2">
        <div className="flex items-center gap-2 lg:gap-3 flex-wrap">
          <button
            onClick={onToggleKnowledge}
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
                          onSetKnowledgeSources(knowledgeSources.filter(s => s !== source.id))
                        }
                      } else {
                        onSetKnowledgeSources([...knowledgeSources, source.id])
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
          
          <button
            onClick={onToggleFastMode}
            className={cn(
              'flex items-center gap-1 lg:gap-1.5 px-2 py-1 rounded transition-colors',
              useFastMode 
                ? 'bg-yellow-500/20 text-yellow-500' 
                : 'text-theme-muted hover:text-theme-text'
            )}
            title={useFastMode 
              ? '快速模式 ON：使用双 LLM 架构，Token 消耗降低 60-70%' 
              : '快速模式 OFF：使用完整 Tool Calling 模式'
            }
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">快速</span> {useFastMode ? '\u26A1' : 'OFF'}
          </button>
          
          {useFastMode && (
            <SkillSelector onManageClick={onOpenAgentConfig} />
          )}
          
          {useFastMode && !isMobileView && (
            <button
              onClick={onToggleTracePanel}
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
        
        <div className="flex items-center gap-2 text-theme-muted truncate">
          {lastTokensUsed !== null && (
            <span className="text-yellow-500 text-xs">~{lastTokensUsed} tokens</span>
          )}
          {currentProvider?.icon} <span className="hidden sm:inline">{config?.model || '未配置'}</span>
        </div>
      </div>
      
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
  )
}
