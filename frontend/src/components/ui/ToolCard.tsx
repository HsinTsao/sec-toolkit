import { useState } from 'react'
import { Copy, Check, RotateCcw, Star } from 'lucide-react'
import { cn, copyToClipboard } from '@/lib/utils'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

interface ToolCardProps {
  title: string
  toolKey: string
  children: React.ReactNode
  className?: string
}

export function ToolCard({ title, toolKey, children, className }: ToolCardProps) {
  const { isFavorite, addFavorite, removeFavorite } = useToolStore()
  const favorite = isFavorite(toolKey)
  
  const toggleFavorite = () => {
    if (favorite) {
      removeFavorite(toolKey)
      toast.success('已取消收藏')
    } else {
      addFavorite(toolKey)
      toast.success('已添加收藏')
    }
  }
  
  return (
    <div className={cn('card', className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-theme-text">{title}</h3>
        <button
          onClick={toggleFavorite}
          className={cn(
            'p-2 rounded-lg transition-colors',
            favorite
              ? 'text-theme-warning bg-theme-warning/10'
              : 'text-theme-muted hover:text-theme-warning hover:bg-theme-warning/10'
          )}
        >
          <Star className={cn('w-4 h-4', favorite && 'fill-current')} />
        </button>
      </div>
      {children}
    </div>
  )
}

interface ToolInputProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
  className?: string
}

export function ToolInput({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  className,
}: ToolInputProps) {
  return (
    <div className={className}>
      <label className="block text-sm text-theme-muted mb-2">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm resize-none focus:outline-none focus:border-theme-primary"
      />
    </div>
  )
}

interface ToolOutputProps {
  label: string
  value: string
  className?: string
}

export function ToolOutput({ label, value, className }: ToolOutputProps) {
  const [copied, setCopied] = useState(false)
  
  const handleCopy = async () => {
    await copyToClipboard(value)
    setCopied(true)
    toast.success('已复制到剪贴板')
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm text-theme-muted">{label}</label>
        <button
          onClick={handleCopy}
          disabled={!value}
          className="flex items-center gap-1 px-2 py-1 text-xs text-theme-muted hover:text-theme-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3" />
              已复制
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              复制
            </>
          )}
        </button>
      </div>
      <div className="w-full min-h-[100px] bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm whitespace-pre-wrap break-all">
        {value || <span className="text-theme-muted">结果将显示在这里...</span>}
      </div>
    </div>
  )
}

interface ToolButtonProps {
  onClick: () => void
  loading?: boolean
  disabled?: boolean
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
  className?: string
}

export function ToolButton({
  onClick,
  loading,
  disabled,
  children,
  variant = 'primary',
  className,
}: ToolButtonProps) {
  const variants = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    ghost: 'btn-ghost',
  }
  
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={cn('btn', variants[variant], 'disabled:opacity-50', className)}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <RotateCcw className="w-4 h-4 animate-spin" />
          处理中...
        </span>
      ) : (
        children
      )}
    </button>
  )
}

interface ToolSelectProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
}

export function ToolSelect({
  label,
  value,
  onChange,
  options,
  className,
}: ToolSelectProps) {
  return (
    <div className={className}>
      <label className="block text-sm text-theme-muted mb-2">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-2 focus:outline-none focus:border-theme-primary"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}

