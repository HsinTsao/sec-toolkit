import { memo } from 'react'
import { 
  Copy, 
  Check,
  Loader2,
  Bot,
  User,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'
import type { ChatMessage } from '@/stores/llmStore'

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

export default MessageBubble
