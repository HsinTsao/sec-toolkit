import { useState } from 'react'
import { ToolCard, ToolInput, ToolOutput, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

export default function CryptoTools() {
  const { addRecentTool } = useToolStore()
  
  // AES 状态
  const [aesInput, setAesInput] = useState('')
  const [aesKey, setAesKey] = useState('')
  const [aesOutput, setAesOutput] = useState('')
  const [aesLoading, setAesLoading] = useState(false)
  
  // RSA 状态
  const [rsaPublicKey, setRsaPublicKey] = useState('')
  const [rsaPrivateKey, setRsaPrivateKey] = useState('')
  const [rsaInput, setRsaInput] = useState('')
  const [rsaOutput, setRsaOutput] = useState('')
  const [rsaLoading, setRsaLoading] = useState(false)
  
  // AES 加密
  const handleAesEncrypt = async () => {
    if (!aesInput.trim() || !aesKey.trim()) {
      toast.error('请输入内容和密钥')
      return
    }
    
    setAesLoading(true)
    try {
      const { data } = await toolsApi.aesEncrypt(aesInput, aesKey)
      setAesOutput(data.result)
      addRecentTool('crypto')
    } catch {
      toast.error('加密失败')
    } finally {
      setAesLoading(false)
    }
  }
  
  // AES 解密
  const handleAesDecrypt = async () => {
    if (!aesInput.trim() || !aesKey.trim()) {
      toast.error('请输入内容和密钥')
      return
    }
    
    setAesLoading(true)
    try {
      const { data } = await toolsApi.aesDecrypt(aesInput, aesKey)
      setAesOutput(data.result)
      addRecentTool('crypto')
    } catch {
      toast.error('解密失败')
    } finally {
      setAesLoading(false)
    }
  }
  
  // 生成 RSA 密钥对
  const handleGenerateRsaKeys = async () => {
    setRsaLoading(true)
    try {
      const { data } = await toolsApi.rsaGenerateKeys(2048)
      setRsaPublicKey(data.public_key)
      setRsaPrivateKey(data.private_key)
      toast.success('密钥对生成成功')
      addRecentTool('crypto')
    } catch {
      toast.error('生成失败')
    } finally {
      setRsaLoading(false)
    }
  }
  
  // RSA 加密
  const handleRsaEncrypt = async () => {
    if (!rsaInput.trim() || !rsaPublicKey.trim()) {
      toast.error('请输入内容和公钥')
      return
    }
    
    setRsaLoading(true)
    try {
      const { data } = await toolsApi.rsaEncrypt(rsaInput, rsaPublicKey)
      setRsaOutput(data.result)
      addRecentTool('crypto')
    } catch {
      toast.error('加密失败')
    } finally {
      setRsaLoading(false)
    }
  }
  
  // RSA 解密
  const handleRsaDecrypt = async () => {
    if (!rsaInput.trim() || !rsaPrivateKey.trim()) {
      toast.error('请输入内容和私钥')
      return
    }
    
    setRsaLoading(true)
    try {
      const { data } = await toolsApi.rsaDecrypt(rsaInput, rsaPrivateKey)
      setRsaOutput(data.result)
      addRecentTool('crypto')
    } catch {
      toast.error('解密失败')
    } finally {
      setRsaLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">加密/解密</h1>
        <p className="text-theme-muted mt-1">
          支持 AES、RSA 等加密算法
        </p>
      </div>
      
      {/* AES 加密 */}
      <ToolCard title="AES 加密/解密" toolKey="crypto-aes">
        <div className="space-y-4">
          <ToolInput
            label="输入文本"
            value={aesInput}
            onChange={setAesInput}
            placeholder="输入要加密/解密的文本..."
          />
          
          <div>
            <label className="block text-sm text-theme-muted mb-2">密钥</label>
            <input
              type="text"
              value={aesKey}
              onChange={(e) => setAesKey(e.target.value)}
              placeholder="输入密钥..."
              className="w-full"
            />
          </div>
          
          <div className="flex gap-3">
            <ToolButton onClick={handleAesEncrypt} loading={aesLoading}>
              AES 加密
            </ToolButton>
            <ToolButton onClick={handleAesDecrypt} loading={aesLoading} variant="secondary">
              AES 解密
            </ToolButton>
          </div>
          
          <ToolOutput label="结果" value={aesOutput} />
        </div>
      </ToolCard>
      
      {/* RSA 加密 */}
      <ToolCard title="RSA 加密/解密" toolKey="crypto-rsa">
        <div className="space-y-4">
          <ToolButton onClick={handleGenerateRsaKeys} loading={rsaLoading} variant="ghost">
            生成 RSA 密钥对 (2048位)
          </ToolButton>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-theme-muted mb-2">公钥</label>
              <textarea
                value={rsaPublicKey}
                onChange={(e) => setRsaPublicKey(e.target.value)}
                placeholder="公钥 (PEM 格式)..."
                rows={6}
                className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-xs resize-none"
              />
            </div>
            <div>
              <label className="block text-sm text-theme-muted mb-2">私钥</label>
              <textarea
                value={rsaPrivateKey}
                onChange={(e) => setRsaPrivateKey(e.target.value)}
                placeholder="私钥 (PEM 格式)..."
                rows={6}
                className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-xs resize-none"
              />
            </div>
          </div>
          
          <ToolInput
            label="输入文本"
            value={rsaInput}
            onChange={setRsaInput}
            placeholder="输入要加密/解密的文本..."
            rows={3}
          />
          
          <div className="flex gap-3">
            <ToolButton onClick={handleRsaEncrypt} loading={rsaLoading}>
              RSA 加密
            </ToolButton>
            <ToolButton onClick={handleRsaDecrypt} loading={rsaLoading} variant="secondary">
              RSA 解密
            </ToolButton>
          </div>
          
          <ToolOutput label="结果" value={rsaOutput} />
        </div>
      </ToolCard>
    </div>
  )
}

