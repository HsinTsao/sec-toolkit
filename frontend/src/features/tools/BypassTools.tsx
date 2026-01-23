import { useState, useEffect } from 'react'
import { 
  Shield, Copy, Check, ChevronDown, Zap, 
  Code, Hash, Type, Database, Wand2,
  FileCode, RefreshCw, Loader2, Info
} from 'lucide-react'
import { bypassApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

// 编码类型配置
const ENCODING_TYPES = [
  {
    id: 'url',
    name: 'URL 编码',
    icon: Code,
    description: '单次/多次 URL 编码',
    options: [
      { label: '单次编码', level: 1 },
      { label: '双重编码', level: 2 },
      { label: '三重编码', level: 3 },
    ],
  },
  {
    id: 'html',
    name: 'HTML 实体',
    icon: FileCode,
    description: '十进制/十六进制/命名实体',
    options: [
      { label: '十进制', mode: 'decimal' },
      { label: '十六进制', mode: 'hex' },
      { label: '命名实体', mode: 'named' },
      { label: '十进制(补零)', mode: 'decimal', padding: 7 },
    ],
  },
  {
    id: 'js',
    name: 'JavaScript 编码',
    icon: Hash,
    description: '八进制/十六进制/Unicode',
    options: [
      { label: '十六进制 (\\x)', mode: 'hex' },
      { label: '八进制 (\\)', mode: 'octal' },
      { label: 'Unicode (\\u)', mode: 'unicode' },
    ],
  },
  {
    id: 'case',
    name: '大小写变形',
    icon: Type,
    description: '随机/交替大小写',
    options: [
      { label: '随机大小写', mode: 'random' },
      { label: '交替大小写', mode: 'alternate' },
      { label: '全大写', mode: 'upper' },
      { label: '全小写', mode: 'lower' },
    ],
  },
  {
    id: 'sql',
    name: 'SQL 绕过',
    icon: Database,
    description: '注释/十六进制/CHAR函数',
    options: [
      { label: '注释绕过 (/**/)', technique: 'comment' },
      { label: '十六进制 (0x)', technique: 'hex' },
      { label: 'CHAR() MySQL', technique: 'char', dbType: 'mysql' },
      { label: 'CHAR() MSSQL', technique: 'char', dbType: 'mssql' },
      { label: 'CHR() Oracle', technique: 'char', dbType: 'oracle' },
    ],
  },
  {
    id: 'space',
    name: '空格绕过',
    icon: Wand2,
    description: '注释/Tab/换行替代',
    options: [
      { label: '注释 (/**/)', mode: 'comment' },
      { label: 'Tab', mode: 'tab' },
      { label: '换行', mode: 'newline' },
      { label: '加号 (+)', mode: 'plus' },
    ],
  },
]

// Payload 模板分类
const PAYLOAD_CATEGORIES = {
  XSS: ['xss_basic', 'xss_img', 'xss_svg', 'xss_body'],
  SQLi: ['sqli_union', 'sqli_or', 'sqli_comment'],
  LFI: ['lfi_basic', 'lfi_null'],
  CMD: ['cmd_basic', 'cmd_pipe'],
}

export default function BypassTools() {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [selectedType, setSelectedType] = useState(ENCODING_TYPES[0])
  const [selectedOption, setSelectedOption] = useState(ENCODING_TYPES[0].options[0])
  const [encodeAll, setEncodeAll] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [templates, setTemplates] = useState<Record<string, string>>({})
  const [allEncodings, setAllEncodings] = useState<Record<string, string> | null>(null)
  const [showAllEncodings, setShowAllEncodings] = useState(false)

  // 获取 Payload 模板
  useEffect(() => {
    bypassApi.getTemplates().then(({ data }) => {
      setTemplates(data.templates)
    }).catch(() => {})
  }, [])

  // 执行编码
  const handleEncode = async () => {
    if (!input.trim()) {
      toast.error('请输入要编码的内容')
      return
    }

    setLoading(true)
    try {
      let result = ''
      
      switch (selectedType.id) {
        case 'url': {
          const opt = selectedOption as { level: number }
          const { data } = await bypassApi.urlEncode(input, opt.level, encodeAll)
          result = data.result
          break
        }
        case 'html': {
          const opt = selectedOption as { mode: string; padding?: number }
          const { data } = await bypassApi.htmlEncode(input, opt.mode as 'decimal' | 'hex' | 'named', opt.padding || 0)
          result = data.result
          break
        }
        case 'js': {
          const opt = selectedOption as { mode: string }
          const { data } = await bypassApi.jsEncode(input, opt.mode as 'octal' | 'hex' | 'unicode')
          result = data.result
          break
        }
        case 'case': {
          const opt = selectedOption as { mode: string }
          const { data } = await bypassApi.caseTransform(input, opt.mode as 'upper' | 'lower' | 'random' | 'alternate')
          result = data.result
          break
        }
        case 'sql': {
          const opt = selectedOption as { technique: string; dbType?: string }
          const { data } = await bypassApi.sqlBypass(
            input, 
            opt.technique as 'comment' | 'hex' | 'char',
            (opt.dbType || 'mysql') as 'mysql' | 'mssql' | 'oracle'
          )
          result = data.result
          break
        }
        case 'space': {
          const opt = selectedOption as { mode: string }
          const { data } = await bypassApi.spaceBypass(input, opt.mode as 'comment' | 'tab' | 'newline' | 'plus' | 'parenthesis')
          result = data.result
          break
        }
      }
      
      setOutput(result)
      setAllEncodings(null)
      setShowAllEncodings(false)
    } catch {
      toast.error('编码失败')
    } finally {
      setLoading(false)
    }
  }

  // 解码
  const handleDecode = async () => {
    if (!input.trim()) {
      toast.error('请输入要解码的内容')
      return
    }

    setLoading(true)
    try {
      let result = ''
      
      switch (selectedType.id) {
        case 'url': {
          const opt = selectedOption as { level: number }
          const { data } = await bypassApi.urlDecode(input, opt.level)
          result = data.result
          break
        }
        case 'html': {
          const { data } = await bypassApi.htmlDecode(input)
          result = data.result
          break
        }
        case 'js': {
          const { data } = await bypassApi.jsDecode(input)
          result = data.result
          break
        }
        default:
          toast.error('该类型不支持解码')
          setLoading(false)
          return
      }
      
      setOutput(result)
      setAllEncodings(null)
      setShowAllEncodings(false)
    } catch {
      toast.error('解码失败')
    } finally {
      setLoading(false)
    }
  }

  // 一键生成所有编码
  const handleGenerateAll = async () => {
    if (!input.trim()) {
      toast.error('请输入要编码的内容')
      return
    }

    setLoading(true)
    try {
      const { data } = await bypassApi.generateAll(input)
      setAllEncodings(data.results)
      setShowAllEncodings(true)
      setOutput('')
      toast.success('已生成所有编码形式')
    } catch {
      toast.error('生成失败')
    } finally {
      setLoading(false)
    }
  }

  // 复制输出
  const handleCopy = async (text?: string) => {
    const textToCopy = text || output
    if (!textToCopy) return
    
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      toast.success('已复制')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('复制失败')
    }
  }

  // 使用模板
  const useTemplate = (key: string) => {
    const payload = templates[key]
    if (payload) {
      setInput(payload)
      setShowTemplates(false)
      toast.success('已加载模板')
    }
  }

  // 支持解码的类型
  const canDecode = ['url', 'html', 'js'].includes(selectedType.id)

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500/20 to-orange-500/20 flex items-center justify-center">
            <Shield className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-theme-text">WAF/编码绕过</h1>
            <p className="text-sm text-theme-muted">多种编码方式助力安全测试</p>
          </div>
        </div>
        
        {/* Payload 模板按钮 */}
        <div className="relative">
          <button
            onClick={() => setShowTemplates(!showTemplates)}
            className="btn btn-secondary flex items-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Payload 模板
            <ChevronDown className={cn('w-4 h-4 transition-transform', showTemplates && 'rotate-180')} />
          </button>
          
          {showTemplates && (
            <div className="absolute right-0 top-full mt-2 w-72 bg-theme-card border border-theme-border rounded-lg shadow-xl z-50 overflow-hidden">
              <div className="p-3 border-b border-theme-border bg-theme-bg/50">
                <span className="text-sm font-medium text-theme-text">常用 Payload</span>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {Object.entries(PAYLOAD_CATEGORIES).map(([category, keys]) => (
                  <div key={category} className="border-b border-theme-border/50 last:border-0">
                    <div className="px-3 py-2 bg-theme-bg/30">
                      <span className="text-xs font-medium text-theme-primary uppercase">{category}</span>
                    </div>
                    {keys.map((key) => (
                      <button
                        key={key}
                        onClick={() => useTemplate(key)}
                        className="w-full px-3 py-2 text-left hover:bg-theme-bg/50 transition-colors"
                      >
                        <div className="text-sm text-theme-text font-mono truncate">
                          {templates[key] || key}
                        </div>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 知识点卡片 */}
      <div className="card bg-gradient-to-br from-blue-500/10 to-purple-500/10 border-blue-500/30">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-2 text-sm">
            <h3 className="font-semibold text-theme-text">WAF 绕过技巧</h3>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-theme-muted">
              <li>• <strong>多层编码</strong>: 双重/三重 URL 编码绕过单次解码的 WAF</li>
              <li>• <strong>HTML 实体</strong>: 十进制/十六进制实体绕过 XSS 过滤</li>
              <li>• <strong>大小写混淆</strong>: &lt;ScRiPt&gt; 绕过大小写敏感的规则</li>
              <li>• <strong>注释插入</strong>: sel/**/ect 绕过关键字检测</li>
              <li>• <strong>空白符替换</strong>: Tab/换行/注释替代空格</li>
              <li>• <strong>编码组合</strong>: URL+Unicode+HTML 多重编码</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 编码类型选择 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {ENCODING_TYPES.map((type) => {
          const Icon = type.icon
          return (
            <button
              key={type.id}
              onClick={() => {
                setSelectedType(type)
                setSelectedOption(type.options[0])
              }}
              className={cn(
                'p-3 rounded-lg border transition-all text-left',
                selectedType.id === type.id
                  ? 'bg-theme-primary/20 border-theme-primary text-theme-primary'
                  : 'bg-theme-card border-theme-border hover:border-theme-primary/50 text-theme-muted'
              )}
            >
              <Icon className="w-5 h-5 mb-2" />
              <div className="text-sm font-medium">{type.name}</div>
              <div className="text-xs opacity-60 truncate">{type.description}</div>
            </button>
          )
        })}
      </div>

      {/* 编码选项 */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-theme-muted">编码选项:</span>
        <div className="flex flex-wrap gap-2">
          {selectedType.options.map((option, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedOption(option)}
              className={cn(
                'px-3 py-1.5 text-sm rounded-lg border transition-all',
                selectedOption === option
                  ? 'bg-theme-primary/20 border-theme-primary text-theme-primary'
                  : 'bg-theme-bg border-theme-border hover:border-theme-primary/50 text-theme-muted'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        
        {selectedType.id === 'url' && (
          <label className="flex items-center gap-2 text-sm text-theme-muted cursor-pointer">
            <input
              type="checkbox"
              checked={encodeAll}
              onChange={(e) => setEncodeAll(e.target.checked)}
              className="rounded border-theme-border"
            />
            编码所有字符
          </label>
        )}
      </div>

      {/* 输入输出区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 输入 */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-theme-text">输入</label>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入要编码的 Payload..."
            className="w-full h-40 p-3 bg-theme-bg border border-theme-border rounded-lg text-theme-text font-mono text-sm resize-none focus:outline-none focus:border-theme-primary"
          />
        </div>
        
        {/* 输出 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-theme-text">输出</label>
            {output && (
              <button
                onClick={() => handleCopy()}
                className="text-sm text-theme-muted hover:text-theme-primary transition-colors flex items-center gap-1"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                复制
              </button>
            )}
          </div>
          <textarea
            value={output}
            readOnly
            placeholder="编码结果将显示在这里..."
            className="w-full h-40 p-3 bg-theme-bg border border-theme-border rounded-lg text-theme-text font-mono text-sm resize-none"
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleEncode}
          disabled={loading || !input.trim()}
          className="btn btn-primary flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Code className="w-4 h-4" />}
          编码
        </button>
        
        {canDecode && (
          <button
            onClick={handleDecode}
            disabled={loading || !input.trim()}
            className="btn btn-secondary flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            解码
          </button>
        )}
        
        <button
          onClick={handleGenerateAll}
          disabled={loading || !input.trim()}
          className="btn btn-secondary flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          一键生成所有编码
        </button>
        
        <button
          onClick={() => {
            setInput('')
            setOutput('')
            setAllEncodings(null)
            setShowAllEncodings(false)
          }}
          className="btn btn-ghost"
        >
          清空
        </button>
      </div>

      {/* 所有编码结果 */}
      {showAllEncodings && allEncodings && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-theme-text">所有编码形式</h3>
            <button
              onClick={() => setShowAllEncodings(false)}
              className="text-sm text-theme-muted hover:text-theme-primary"
            >
              收起
            </button>
          </div>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {Object.entries(allEncodings).map(([key, value]) => (
              <div key={key} className="group">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-theme-muted uppercase">{key.replace(/_/g, ' ')}</span>
                  <button
                    onClick={() => handleCopy(value)}
                    className="text-xs text-theme-muted hover:text-theme-primary opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"
                  >
                    <Copy className="w-3 h-3" />
                    复制
                  </button>
                </div>
                <div className="p-2 bg-theme-bg rounded border border-theme-border font-mono text-sm text-theme-text break-all">
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

