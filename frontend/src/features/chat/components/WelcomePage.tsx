import { 
  Plus, 
  Sparkles,
  AlertCircle,
  FileText,
} from 'lucide-react'
import type { LLMConfig } from '@/lib/api'

interface WelcomePageProps {
  config: LLMConfig | null
  onOpenSettings: () => void
  onCreateSession: () => string
  onSetInput: (input: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement>
}

export default function WelcomePage({
  config,
  onOpenSettings,
  onCreateSession,
  onSetInput,
  inputRef,
}: WelcomePageProps) {
  return (
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
            onClick={onOpenSettings}
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
              onCreateSession()
              onSetInput(prompt)
              setTimeout(() => inputRef.current?.focus(), 100)
            }}
            className="p-2.5 lg:p-3 text-sm text-left rounded-lg bg-theme-card border border-theme-border hover:border-theme-primary/50 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>
      <button
        onClick={() => onCreateSession()}
        className="mt-6 lg:mt-8 btn btn-primary flex items-center gap-2"
      >
        <Plus className="w-4 h-4" />
        开始新对话
      </button>
      <p className="mt-4 lg:mt-6 text-xs text-theme-muted/60 text-center max-w-sm px-4">
        💡 对话记录仅存储在浏览器本地，登出后将清除。如需永久保存 AI 回复，可点击消息旁的 <FileText className="w-3 h-3 inline" /> 图标转存到笔记。
      </p>
    </div>
  )
}
