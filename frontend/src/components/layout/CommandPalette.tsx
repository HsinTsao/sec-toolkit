import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Binary, Hash, Lock, Key, FileCode, Globe, KeyRound } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Command {
  id: string
  name: string
  path: string
  icon: React.ElementType
  keywords: string[]
}

const commands: Command[] = [
  { id: 'encoding', name: '编码/解码', path: '/tools/encoding', icon: Binary, keywords: ['base64', 'url', 'html', 'hex', 'unicode'] },
  { id: 'hash', name: '哈希计算', path: '/tools/hash', icon: Hash, keywords: ['md5', 'sha1', 'sha256', 'sha512'] },
  { id: 'crypto', name: '加密/解密', path: '/tools/crypto', icon: Lock, keywords: ['aes', 'rsa', 'des', 'encrypt', 'decrypt'] },
  { id: 'jwt', name: 'JWT 工具', path: '/tools/jwt', icon: Key, keywords: ['token', 'json web token', 'decode', 'encode'] },
  { id: 'format', name: '格式处理', path: '/tools/format', icon: FileCode, keywords: ['json', 'xml', 'yaml', 'regex', 'diff'] },
  { id: 'network', name: '网络工具', path: '/tools/network', icon: Globe, keywords: ['dns', 'whois', 'ip', 'lookup'] },
  { id: 'password', name: '密码工具', path: '/tools/password', icon: KeyRound, keywords: ['generate', 'strength', 'random'] },
]

interface Props {
  isOpen: boolean
  onClose: () => void
}

export default function CommandPalette({ isOpen, onClose }: Props) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  
  const filteredCommands = commands.filter((cmd) => {
    const searchLower = search.toLowerCase()
    return (
      cmd.name.toLowerCase().includes(searchLower) ||
      cmd.keywords.some((k) => k.includes(searchLower))
    )
  })
  
  const handleSelect = useCallback((command: Command) => {
    navigate(command.path)
    onClose()
    setSearch('')
  }, [navigate, onClose])
  
  // 键盘导航
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) {
        // Cmd+K 打开
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault()
        }
        return
      }
      
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setSelectedIndex((i) => Math.min(i + 1, filteredCommands.length - 1))
          break
        case 'ArrowUp':
          e.preventDefault()
          setSelectedIndex((i) => Math.max(i - 1, 0))
          break
        case 'Enter':
          e.preventDefault()
          if (filteredCommands[selectedIndex]) {
            handleSelect(filteredCommands[selectedIndex])
          }
          break
        case 'Escape':
          e.preventDefault()
          onClose()
          break
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, filteredCommands, selectedIndex, handleSelect, onClose])
  
  // 重置选中项
  useEffect(() => {
    setSelectedIndex(0)
  }, [search])
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* 面板 */}
      <div className="relative w-full max-w-lg bg-theme-card border border-theme-border rounded-xl shadow-2xl overflow-hidden animate-fadeIn">
        {/* 搜索输入 */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-theme-border">
          <Search className="w-5 h-5 text-theme-muted" />
          <input
            type="text"
            placeholder="搜索工具..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 bg-transparent border-none outline-none text-theme-text placeholder:text-theme-muted"
            autoFocus
          />
          <kbd className="px-2 py-0.5 text-xs bg-theme-bg rounded text-theme-muted">
            ESC
          </kbd>
        </div>
        
        {/* 结果列表 */}
        <div className="max-h-80 overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="px-4 py-8 text-center text-theme-muted">
              没有找到匹配的工具
            </div>
          ) : (
            filteredCommands.map((cmd, index) => (
              <button
                key={cmd.id}
                onClick={() => handleSelect(cmd)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors',
                  index === selectedIndex
                    ? 'bg-theme-primary/20 text-theme-primary'
                    : 'hover:bg-theme-bg'
                )}
              >
                <cmd.icon className="w-5 h-5" />
                <div>
                  <div className="font-medium">{cmd.name}</div>
                  <div className="text-xs text-theme-muted">
                    {cmd.keywords.join(', ')}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

