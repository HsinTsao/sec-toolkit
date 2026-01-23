import { useState } from 'react'
import { ToolCard, ToolInput, ToolOutput, ToolButton, ToolSelect } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

const hashAlgorithms = [
  { value: 'md5', label: 'MD5' },
  { value: 'sha1', label: 'SHA1' },
  { value: 'sha224', label: 'SHA224' },
  { value: 'sha256', label: 'SHA256' },
  { value: 'sha384', label: 'SHA384' },
  { value: 'sha512', label: 'SHA512' },
  { value: 'sha3_256', label: 'SHA3-256' },
  { value: 'sha3_512', label: 'SHA3-512' },
]

export default function HashTools() {
  const { addRecentTool } = useToolStore()
  const [input, setInput] = useState('')
  const [algorithm, setAlgorithm] = useState('md5')
  const [output, setOutput] = useState('')
  const [allHashes, setAllHashes] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  
  const handleCalculate = async () => {
    if (!input.trim()) {
      toast.error('请输入要计算哈希的内容')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.calculateHash(input, algorithm)
      setOutput(data.result)
      addRecentTool('hash')
    } catch {
      toast.error('计算失败')
    } finally {
      setLoading(false)
    }
  }
  
  const handleCalculateAll = async () => {
    if (!input.trim()) {
      toast.error('请输入要计算哈希的内容')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.calculateAllHashes(input)
      setAllHashes(data.result)
      setOutput('')
      addRecentTool('hash')
    } catch {
      toast.error('计算失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">哈希计算</h1>
        <p className="text-theme-muted mt-1">
          支持 MD5、SHA1、SHA256、SHA512 等多种哈希算法
        </p>
      </div>
      
      <ToolCard title="哈希计算" toolKey="hash">
        <div className="space-y-4">
          <ToolInput
            label="输入文本"
            value={input}
            onChange={setInput}
            placeholder="输入要计算哈希的文本..."
          />
          
          <ToolSelect
            label="哈希算法"
            value={algorithm}
            onChange={setAlgorithm}
            options={hashAlgorithms}
          />
          
          <div className="flex gap-3">
            <ToolButton onClick={handleCalculate} loading={loading}>
              计算 {algorithm.toUpperCase()}
            </ToolButton>
            <ToolButton onClick={handleCalculateAll} loading={loading} variant="secondary">
              计算所有
            </ToolButton>
          </div>
          
          {output && (
            <ToolOutput label={`${algorithm.toUpperCase()} 哈希值`} value={output} />
          )}
          
          {Object.keys(allHashes).length > 0 && (
            <div className="space-y-3">
              <label className="text-sm text-theme-muted">所有哈希值</label>
              <div className="space-y-2">
                {Object.entries(allHashes).map(([algo, hash]) => (
                  <div key={algo} className="bg-theme-bg border border-theme-border rounded-lg p-3">
                    <div className="text-xs text-theme-muted mb-1">{algo.toUpperCase()}</div>
                    <div className="font-mono text-sm break-all">{hash}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ToolCard>
    </div>
  )
}

