import { useState } from 'react'
import { ToolCard, ToolInput, ToolOutput, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

const encodingTypes = [
  { id: 'base64', name: 'Base64' },
  { id: 'url', name: 'URL' },
  { id: 'html', name: 'HTML 实体' },
  { id: 'hex', name: 'Hex' },
  { id: 'unicode', name: 'Unicode' },
]

export default function EncodingTools() {
  const { addRecentTool } = useToolStore()
  const [activeType, setActiveType] = useState('base64')
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  
  const handleEncode = async () => {
    if (!input.trim()) {
      toast.error('请输入要编码的内容')
      return
    }
    
    setLoading(true)
    try {
      let result
      switch (activeType) {
        case 'base64':
          result = await toolsApi.base64Encode(input)
          break
        case 'url':
          result = await toolsApi.urlEncode(input)
          break
        case 'html':
          result = await toolsApi.htmlEncode(input)
          break
        case 'hex':
          result = await toolsApi.hexEncode(input)
          break
        case 'unicode':
          result = await toolsApi.unicodeEncode(input)
          break
      }
      setOutput(result?.data?.result || '')
      addRecentTool('encoding')
    } catch {
      toast.error('编码失败')
    } finally {
      setLoading(false)
    }
  }
  
  const handleDecode = async () => {
    if (!input.trim()) {
      toast.error('请输入要解码的内容')
      return
    }
    
    setLoading(true)
    try {
      let result
      switch (activeType) {
        case 'base64':
          result = await toolsApi.base64Decode(input)
          break
        case 'url':
          result = await toolsApi.urlDecode(input)
          break
        case 'html':
          result = await toolsApi.htmlDecode(input)
          break
        case 'hex':
          result = await toolsApi.hexDecode(input)
          break
        case 'unicode':
          result = await toolsApi.unicodeDecode(input)
          break
      }
      setOutput(result?.data?.result || '')
      addRecentTool('encoding')
    } catch {
      toast.error('解码失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">编码/解码</h1>
        <p className="text-theme-muted mt-1">
          支持 Base64、URL、HTML、Hex、Unicode 等多种编码格式
        </p>
      </div>
      
      {/* 编码类型选择 */}
      <div className="flex gap-2 flex-wrap">
        {encodingTypes.map((type) => (
          <button
            key={type.id}
            onClick={() => setActiveType(type.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeType === type.id
                ? 'bg-theme-primary text-theme-bg'
                : 'bg-theme-card border border-theme-border text-theme-muted hover:text-theme-text hover:border-theme-primary'
            }`}
          >
            {type.name}
          </button>
        ))}
      </div>
      
      <ToolCard title={`${encodingTypes.find(t => t.id === activeType)?.name} 编码/解码`} toolKey="encoding">
        <div className="space-y-4">
          <ToolInput
            label="输入"
            value={input}
            onChange={setInput}
            placeholder="输入要编码或解码的文本..."
          />
          
          <div className="flex gap-3">
            <ToolButton onClick={handleEncode} loading={loading}>
              编码
            </ToolButton>
            <ToolButton onClick={handleDecode} loading={loading} variant="secondary">
              解码
            </ToolButton>
          </div>
          
          <ToolOutput label="输出" value={output} />
        </div>
      </ToolCard>
    </div>
  )
}

