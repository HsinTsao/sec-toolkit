import { useState } from 'react'
import { ToolCard, ToolInput, ToolOutput, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

export default function FormatTools() {
  const { addRecentTool } = useToolStore()
  
  // JSON 格式化
  const [jsonInput, setJsonInput] = useState('')
  const [jsonOutput, setJsonOutput] = useState('')
  
  // 正则测试
  const [regexPattern, setRegexPattern] = useState('')
  const [regexText, setRegexText] = useState('')
  const [regexResult, setRegexResult] = useState('')
  
  // 时间戳
  const [timestamp, setTimestamp] = useState('')
  const [timestampResult, setTimestampResult] = useState('')
  
  // 进制转换
  const [baseValue, setBaseValue] = useState('')
  const [fromBase, setFromBase] = useState('10')
  const [toBase, setToBase] = useState('16')
  const [baseResult, setBaseResult] = useState('')
  
  const [loading, setLoading] = useState(false)
  
  // JSON 格式化
  const handleFormatJson = async () => {
    if (!jsonInput.trim()) {
      toast.error('请输入 JSON')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.formatJson(jsonInput)
      setJsonOutput(data.result)
      addRecentTool('format')
    } catch {
      toast.error('格式化失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 正则测试
  const handleTestRegex = async () => {
    if (!regexPattern.trim() || !regexText.trim()) {
      toast.error('请输入正则表达式和测试文本')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.testRegex(regexPattern, regexText)
      
      if (data.error) {
        setRegexResult(`错误: ${data.error}`)
      } else {
        let result = `匹配数: ${data.match_count}\n\n`
        data.matches.forEach((match: { match: string; start: number; end: number }, i: number) => {
          result += `匹配 ${i + 1}: "${match.match}" (位置: ${match.start}-${match.end})\n`
        })
        setRegexResult(result || '无匹配')
      }
      addRecentTool('format')
    } catch {
      toast.error('测试失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 时间戳转换
  const handleConvertTimestamp = async () => {
    setLoading(true)
    try {
      const params: { timestamp?: number; datetime_str?: string } = {}
      
      if (timestamp.trim()) {
        // 检查是时间戳还是日期字符串
        if (/^\d+$/.test(timestamp.trim())) {
          params.timestamp = parseInt(timestamp.trim())
        } else {
          params.datetime_str = timestamp.trim()
        }
      }
      
      const { data } = await toolsApi.convertTimestamp(params)
      
      if (data.error) {
        setTimestampResult(`错误: ${data.error}`)
      } else {
        let result = ''
        if (data.datetime) result += `日期时间: ${data.datetime}\n`
        if (data.timestamp) result += `时间戳 (秒): ${data.timestamp}\n`
        if (data.timestamp_ms) result += `时间戳 (毫秒): ${data.timestamp_ms}\n`
        if (data.iso) result += `ISO 格式: ${data.iso}\n`
        setTimestampResult(result)
      }
      addRecentTool('format')
    } catch {
      toast.error('转换失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 进制转换
  const handleBaseConvert = async () => {
    if (!baseValue.trim()) {
      toast.error('请输入要转换的值')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.baseConvert(baseValue, parseInt(fromBase), parseInt(toBase))
      setBaseResult(data.result)
      addRecentTool('format')
    } catch {
      toast.error('转换失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 生成 UUID
  const handleGenerateUuid = async () => {
    setLoading(true)
    try {
      const { data } = await toolsApi.generateUuid()
      setJsonOutput(`UUID v1: ${data.uuid1}\nUUID v4: ${data.uuid4}\n\n无连字符:\nUUID v1: ${data.uuid1_no_dash}\nUUID v4: ${data.uuid4_no_dash}`)
      addRecentTool('format')
    } catch {
      toast.error('生成失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">格式处理</h1>
        <p className="text-theme-muted mt-1">
          JSON 格式化、正则测试、时间戳转换、进制转换等
        </p>
      </div>
      
      {/* JSON 格式化 */}
      <ToolCard title="JSON 格式化" toolKey="format-json">
        <div className="space-y-4">
          <ToolInput
            label="输入 JSON"
            value={jsonInput}
            onChange={setJsonInput}
            placeholder='{"key": "value"}'
            rows={6}
          />
          
          <div className="flex gap-3">
            <ToolButton onClick={handleFormatJson} loading={loading}>
              格式化
            </ToolButton>
            <ToolButton onClick={handleGenerateUuid} loading={loading} variant="ghost">
              生成 UUID
            </ToolButton>
          </div>
          
          <ToolOutput label="结果" value={jsonOutput} />
        </div>
      </ToolCard>
      
      {/* 正则测试 */}
      <ToolCard title="正则表达式测试" toolKey="format-regex">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">正则表达式</label>
            <input
              type="text"
              value={regexPattern}
              onChange={(e) => setRegexPattern(e.target.value)}
              placeholder="例: \d+|[a-z]+"
              className="w-full font-mono"
            />
          </div>
          
          <ToolInput
            label="测试文本"
            value={regexText}
            onChange={setRegexText}
            placeholder="输入要测试的文本..."
          />
          
          <ToolButton onClick={handleTestRegex} loading={loading}>
            测试
          </ToolButton>
          
          <ToolOutput label="匹配结果" value={regexResult} />
        </div>
      </ToolCard>
      
      {/* 时间戳转换 */}
      <ToolCard title="时间戳转换" toolKey="format-timestamp">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">
              时间戳或日期 (留空获取当前时间)
            </label>
            <input
              type="text"
              value={timestamp}
              onChange={(e) => setTimestamp(e.target.value)}
              placeholder="1234567890 或 2024-01-01 12:00:00"
              className="w-full"
            />
          </div>
          
          <ToolButton onClick={handleConvertTimestamp} loading={loading}>
            转换
          </ToolButton>
          
          <ToolOutput label="结果" value={timestampResult} />
        </div>
      </ToolCard>
      
      {/* 进制转换 */}
      <ToolCard title="进制转换" toolKey="format-base">
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-theme-muted mb-2">输入值</label>
              <input
                type="text"
                value={baseValue}
                onChange={(e) => setBaseValue(e.target.value)}
                placeholder="255"
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-sm text-theme-muted mb-2">源进制</label>
              <select
                value={fromBase}
                onChange={(e) => setFromBase(e.target.value)}
                className="w-full"
              >
                <option value="2">二进制 (2)</option>
                <option value="8">八进制 (8)</option>
                <option value="10">十进制 (10)</option>
                <option value="16">十六进制 (16)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-theme-muted mb-2">目标进制</label>
              <select
                value={toBase}
                onChange={(e) => setToBase(e.target.value)}
                className="w-full"
              >
                <option value="2">二进制 (2)</option>
                <option value="8">八进制 (8)</option>
                <option value="10">十进制 (10)</option>
                <option value="16">十六进制 (16)</option>
              </select>
            </div>
          </div>
          
          <ToolButton onClick={handleBaseConvert} loading={loading}>
            转换
          </ToolButton>
          
          <ToolOutput label="结果" value={baseResult} />
        </div>
      </ToolCard>
    </div>
  )
}

