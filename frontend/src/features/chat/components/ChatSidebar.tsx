import { 
  Plus, 
  Trash2, 
  MessageSquare, 
  Loader2,
  X,
  Settings,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatSession } from '@/stores/llmStore'
import type { LLMProvider, LLMConfig } from '@/lib/api'

interface ChatSidebarProps {
  sessions: ChatSession[]
  currentSessionId: string | null
  onCreateSession: () => void
  onDeleteSession: (id: string) => void
  onSelectSession: (id: string) => void
  onOpenSettings: () => void
  onOpenAgentConfig: () => void
  isMobileView: boolean
  showChatSidebar: boolean
  onCloseSidebar: () => void
  config: LLMConfig | null
  configLoading: boolean
  currentProvider: LLMProvider | null
}

export default function ChatSidebar({
  sessions,
  currentSessionId,
  onCreateSession,
  onDeleteSession,
  onSelectSession,
  onOpenSettings,
  onOpenAgentConfig,
  isMobileView,
  showChatSidebar,
  onCloseSidebar,
  config,
  configLoading,
  currentProvider,
}: ChatSidebarProps) {
  return (
    <div className={cn(
      "bg-theme-card border-r border-theme-border flex flex-col flex-shrink-0 z-30",
      isMobileView 
        ? "fixed inset-y-0 left-0 w-64 transition-transform duration-300"
        : "w-56 lg:w-64 relative",
      isMobileView && !showChatSidebar && "-translate-x-full"
    )}>
      <div className="p-3 lg:p-4 border-b border-theme-border flex items-center gap-2">
        <button
          onClick={onCreateSession}
          className="flex-1 btn btn-primary flex items-center justify-center gap-2 text-sm"
        >
          <Plus className="w-4 h-4" />
          新对话
        </button>
        {isMobileView && (
          <button
            onClick={onCloseSidebar}
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
                onSelectSession(session.id)
                if (isMobileView) onCloseSidebar()
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
                    onDeleteSession(session.id)
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
      
      <div className="p-3 lg:p-4 border-t border-theme-border">
        <button
          onClick={onOpenSettings}
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
        
        <button
          onClick={onOpenAgentConfig}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-theme-muted hover:text-theme-text hover:bg-theme-bg transition-colors"
        >
          <Settings className="w-4 h-4" />
          <span className="text-sm">Agent 配置</span>
        </button>
      </div>
    </div>
  )
}
