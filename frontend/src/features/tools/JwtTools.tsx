import { useState } from 'react'
import { ToolCard, ToolInput, ToolOutput, ToolButton } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

export default function JwtTools() {
  const { addRecentTool } = useToolStore()
  
  // 解码状态
  const [token, setToken] = useState('')
  const [decodedHeader, setDecodedHeader] = useState('')
  const [decodedPayload, setDecodedPayload] = useState('')
  const [decodedInfo, setDecodedInfo] = useState('')
  
  // 编码状态
  const [payload, setPayload] = useState('{\n  "sub": "1234567890",\n  "name": "John Doe",\n  "iat": 1516239022\n}')
  const [secret, setSecret] = useState('')
  const [encodedToken, setEncodedToken] = useState('')
  
  const [loading, setLoading] = useState(false)
  
  // 解码 JWT
  const handleDecode = async () => {
    if (!token.trim()) {
      toast.error('请输入 JWT Token')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.jwtDecode(token)
      
      if (data.error) {
        toast.error(data.error)
        return
      }
      
      setDecodedHeader(JSON.stringify(data.header, null, 2))
      setDecodedPayload(JSON.stringify(data.payload, null, 2))
      
      let info = ''
      if (data.expiration) {
        if (data.expiration.exp) {
          info += `过期时间: ${data.expiration.exp}\n`
          info += `是否过期: ${data.expiration.expired ? '是 ❌' : '否 ✅'}\n`
        }
        if (data.expiration.iat) {
          info += `签发时间: ${data.expiration.iat}\n`
        }
      }
      setDecodedInfo(info || '无时间信息')
      
      addRecentTool('jwt')
    } catch {
      toast.error('解码失败')
    } finally {
      setLoading(false)
    }
  }
  
  // 编码 JWT
  const handleEncode = async () => {
    if (!payload.trim() || !secret.trim()) {
      toast.error('请输入 Payload 和 Secret')
      return
    }
    
    let parsedPayload
    try {
      parsedPayload = JSON.parse(payload)
    } catch {
      toast.error('Payload 不是有效的 JSON')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.jwtEncode(parsedPayload, secret)
      setEncodedToken(data.result)
      addRecentTool('jwt')
    } catch {
      toast.error('编码失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">JWT 工具</h1>
        <p className="text-theme-muted mt-1">
          JSON Web Token 解码、编码、验证
        </p>
      </div>
      
      {/* JWT 解码 */}
      <ToolCard title="JWT 解码" toolKey="jwt-decode">
        <div className="space-y-4">
          <ToolInput
            label="JWT Token"
            value={token}
            onChange={setToken}
            placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
          />
          
          <ToolButton onClick={handleDecode} loading={loading}>
            解码
          </ToolButton>
          
          {decodedHeader && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-theme-muted mb-2">Header</label>
                <pre className="bg-theme-bg border border-theme-border rounded-lg p-4 font-mono text-sm overflow-auto">
                  {decodedHeader}
                </pre>
              </div>
              <div>
                <label className="block text-sm text-theme-muted mb-2">Payload</label>
                <pre className="bg-theme-bg border border-theme-border rounded-lg p-4 font-mono text-sm overflow-auto">
                  {decodedPayload}
                </pre>
              </div>
            </div>
          )}
          
          {decodedInfo && (
            <div>
              <label className="block text-sm text-theme-muted mb-2">Token 信息</label>
              <pre className="bg-theme-bg border border-theme-border rounded-lg p-4 font-mono text-sm whitespace-pre-wrap">
                {decodedInfo}
              </pre>
            </div>
          )}
        </div>
      </ToolCard>
      
      {/* JWT 编码 */}
      <ToolCard title="JWT 编码" toolKey="jwt-encode">
        <div className="space-y-4">
          <ToolInput
            label="Payload (JSON)"
            value={payload}
            onChange={setPayload}
            rows={6}
          />
          
          <div>
            <label className="block text-sm text-theme-muted mb-2">Secret</label>
            <input
              type="text"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="输入签名密钥..."
              className="w-full"
            />
          </div>
          
          <ToolButton onClick={handleEncode} loading={loading}>
            生成 JWT
          </ToolButton>
          
          <ToolOutput label="生成的 Token" value={encodedToken} />
        </div>
      </ToolCard>
    </div>
  )
}

