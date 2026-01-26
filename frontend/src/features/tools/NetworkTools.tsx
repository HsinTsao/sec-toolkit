import { useState } from 'react'
import { ToolCard, ToolOutput, ToolButton, ToolSelect } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import toast from 'react-hot-toast'

const dnsRecordTypes = [
  { value: 'A', label: 'A - IPv4 地址' },
  { value: 'AAAA', label: 'AAAA - IPv6 地址' },
  { value: 'CNAME', label: 'CNAME - 别名' },
  { value: 'MX', label: 'MX - 邮件交换' },
  { value: 'TXT', label: 'TXT - 文本记录' },
  { value: 'NS', label: 'NS - 名称服务器' },
]

// 定义分析结果类型
interface AnalyzeResult {
  input: string
  parsed: {
    type: 'ip' | 'domain' | 'unknown'
    value: string
    ip_version?: number
    original_url?: string
    error?: string
  }
  results: {
    dns?: Record<string, {
      domain?: string
      record_type?: string
      records?: string[]
      ttl?: number
      error?: string
    }>
    whois?: Record<string, unknown>
    ip_info?: Record<string, unknown>
    reverse_dns?: { ip?: string; hostname?: string; error?: string }
    hostname_whois?: Record<string, unknown>
  }
  error?: string
}

export default function NetworkTools() {
  const { addRecentTool } = useToolStore()
  
  // 一键分析
  const [analyzeInput, setAnalyzeInput] = useState('')
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null)
  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  
  // DNS 查询
  const [dnsDomain, setDnsDomain] = useState('')
  const [dnsRecordType, setDnsRecordType] = useState('A')
  const [dnsResult, setDnsResult] = useState('')
  
  // WHOIS 查询
  const [whoisDomain, setWhoisDomain] = useState('')
  const [whoisResult, setWhoisResult] = useState('')
  
  // IP 查询
  const [ipAddress, setIpAddress] = useState('')
  const [ipResult, setIpResult] = useState('')
  
  const [loading, setLoading] = useState(false)
  
  // 一键分析
  const handleAnalyze = async () => {
    if (!analyzeInput.trim()) {
      toast.error('请输入 URL、域名或 IP 地址')
      return
    }
    
    setAnalyzeLoading(true)
    setAnalyzeResult(null)
    try {
      const { data } = await toolsApi.analyzeTarget(analyzeInput)
      setAnalyzeResult(data)
      addRecentTool('network')
    } catch {
      toast.error('分析失败')
    } finally {
      setAnalyzeLoading(false)
    }
  }
  
  // 格式化分析结果
  const formatAnalyzeResult = (result: AnalyzeResult) => {
    if (result.error) {
      return `❌ 错误: ${result.error}`
    }
    
    const lines: string[] = []
    const parsed = result.parsed
    const results = result.results
    
    // 输入识别信息
    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    lines.push('📋 输入识别')
    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    lines.push(`输入: ${result.input}`)
    lines.push(`类型: ${parsed.type === 'ip' ? 'IP 地址' : parsed.type === 'domain' ? '域名' : '未知'}`)
    lines.push(`解析值: ${parsed.value}`)
    if (parsed.ip_version) lines.push(`IP 版本: IPv${parsed.ip_version}`)
    if (parsed.original_url) lines.push(`原始 URL: ${parsed.original_url}`)
    
    // DNS 查询结果
    if (results.dns) {
      lines.push('')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      lines.push('🌐 DNS 查询结果')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      
      for (const [recordType, data] of Object.entries(results.dns)) {
        if (data.error) {
          lines.push(`${recordType}: ${data.error}`)
        } else if (data.records && data.records.length > 0) {
          lines.push(`${recordType} (TTL: ${data.ttl || 'N/A'}):`)
          data.records.forEach(record => {
            lines.push(`  • ${record}`)
          })
        }
      }
    }
    
    // WHOIS 结果
    if (results.whois && !results.whois.error) {
      lines.push('')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      lines.push('📝 WHOIS 信息')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      
      const whoisFields: [string, string][] = [
        ['domain_name', '域名'],
        ['registrar', '注册商'],
        ['creation_date', '注册时间'],
        ['expiration_date', '过期时间'],
        ['updated_date', '更新时间'],
        ['name_servers', '域名服务器'],
        ['status', '状态'],
        ['country', '国家'],
        ['emails', '邮箱'],
      ]
      
      whoisFields.forEach(([key, label]) => {
        const value = results.whois![key]
        if (value) {
          const displayValue = Array.isArray(value) ? value.join(', ') : String(value)
          lines.push(`${label}: ${displayValue}`)
        }
      })
    }
    
    // IP 信息
    if (results.ip_info && !results.ip_info.error) {
      lines.push('')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      lines.push('📍 IP 地理位置')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      
      const ipFields: [string, string][] = [
        ['ip', 'IP'],
        ['country', '国家'],
        ['region', '地区'],
        ['city', '城市'],
        ['zip', '邮编'],
        ['timezone', '时区'],
        ['isp', 'ISP'],
        ['org', '组织'],
        ['as', 'AS'],
      ]
      
      ipFields.forEach(([key, label]) => {
        const value = results.ip_info![key]
        if (value) {
          if (key === 'country' && results.ip_info!.country_code) {
            lines.push(`${label}: ${value} (${results.ip_info!.country_code})`)
          } else if (key !== 'country_code') {
            lines.push(`${label}: ${value}`)
          }
        }
      })
      
      if (results.ip_info.lat && results.ip_info.lon) {
        lines.push(`坐标: ${results.ip_info.lat}, ${results.ip_info.lon}`)
      }
    }
    
    // 反向 DNS
    if (results.reverse_dns) {
      lines.push('')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      lines.push('🔄 反向 DNS')
      lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
      
      if (results.reverse_dns.error) {
        lines.push(`结果: ${results.reverse_dns.error}`)
      } else {
        lines.push(`IP: ${results.reverse_dns.ip}`)
        lines.push(`主机名: ${results.reverse_dns.hostname}`)
      }
    }
    
    return lines.join('\n')
  }
  
  // DNS 查询
  const handleDnsLookup = async () => {
    if (!dnsDomain.trim()) {
      toast.error('请输入域名')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.dnsLookup(dnsDomain, dnsRecordType)
      
      if (data.error) {
        setDnsResult(`错误: ${data.error}`)
      } else {
        let result = `域名: ${data.domain}\n`
        result += `记录类型: ${data.record_type}\n`
        if (data.ttl) result += `TTL: ${data.ttl}s\n`
        result += `\n记录:\n`
        data.records.forEach((record: string) => {
          result += `  ${record}\n`
        })
        setDnsResult(result)
      }
      addRecentTool('network')
    } catch {
      toast.error('查询失败')
    } finally {
      setLoading(false)
    }
  }
  
  // WHOIS 查询
  const handleWhoisLookup = async () => {
    if (!whoisDomain.trim()) {
      toast.error('请输入域名')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.whoisLookup(whoisDomain)
      
      if (data.error) {
        setWhoisResult(`错误: ${data.error}`)
      } else {
        let result = ''
        const fields: [string, string][] = [
          ['domain_name', '域名'],
          ['registrar', '注册商'],
          ['creation_date', '注册时间'],
          ['expiration_date', '过期时间'],
          ['updated_date', '更新时间'],
          ['name_servers', '域名服务器'],
          ['status', '状态'],
          ['country', '国家'],
          ['emails', '邮箱'],
        ]
        
        fields.forEach(([key, label]) => {
          if (data[key]) {
            const value = Array.isArray(data[key]) ? data[key].join(', ') : data[key]
            result += `${label}: ${value}\n`
          }
        })
        setWhoisResult(result || '无数据')
      }
      addRecentTool('network')
    } catch {
      toast.error('查询失败')
    } finally {
      setLoading(false)
    }
  }
  
  // IP 查询
  const handleIpLookup = async () => {
    if (!ipAddress.trim()) {
      toast.error('请输入 IP 地址')
      return
    }
    
    setLoading(true)
    try {
      const { data } = await toolsApi.ipInfo(ipAddress)
      
      if (data.error) {
        setIpResult(`错误: ${data.error}`)
      } else {
        let result = `IP: ${data.ip}\n`
        result += `国家: ${data.country} (${data.country_code})\n`
        result += `地区: ${data.region}\n`
        result += `城市: ${data.city}\n`
        if (data.zip) result += `邮编: ${data.zip}\n`
        result += `坐标: ${data.lat}, ${data.lon}\n`
        result += `时区: ${data.timezone}\n`
        result += `ISP: ${data.isp}\n`
        if (data.org) result += `组织: ${data.org}\n`
        if (data.as) result += `AS: ${data.as}\n`
        setIpResult(result)
      }
      addRecentTool('network')
    } catch {
      toast.error('查询失败')
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">网络工具</h1>
        <p className="text-theme-muted mt-1">
          一键分析、DNS 查询、WHOIS 查询、IP 地理位置查询
        </p>
      </div>
      
      {/* 一键分析 */}
      <ToolCard title="🎯 一键分析" toolKey="network-analyze">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">
              输入 URL、域名或 IP 地址
            </label>
            <input
              type="text"
              value={analyzeInput}
              onChange={(e) => setAnalyzeInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              placeholder="例如: https://example.com 或 example.com 或 8.8.8.8"
              className="w-full"
            />
            <p className="text-xs text-theme-muted mt-1">
              自动识别输入类型，执行所有相关查询（DNS、WHOIS、IP 地理位置、反向 DNS）
            </p>
          </div>
          
          <ToolButton onClick={handleAnalyze} loading={analyzeLoading}>
            🔍 开始分析
          </ToolButton>
          
          {analyzeResult && (
            <ToolOutput 
              label="分析结果" 
              value={formatAnalyzeResult(analyzeResult)} 
            />
          )}
        </div>
      </ToolCard>
      
      <div className="border-t border-theme-border pt-6">
        <h2 className="text-lg font-semibold text-theme-text mb-4">单项查询</h2>
      </div>
      
      {/* DNS 查询 */}
      <ToolCard title="DNS 查询" toolKey="network-dns">
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-theme-muted mb-2">域名</label>
              <input
                type="text"
                value={dnsDomain}
                onChange={(e) => setDnsDomain(e.target.value)}
                placeholder="example.com"
                className="w-full"
              />
            </div>
            <ToolSelect
              label="记录类型"
              value={dnsRecordType}
              onChange={setDnsRecordType}
              options={dnsRecordTypes}
            />
          </div>
          
          <ToolButton onClick={handleDnsLookup} loading={loading}>
            查询
          </ToolButton>
          
          <ToolOutput label="结果" value={dnsResult} />
        </div>
      </ToolCard>
      
      {/* WHOIS 查询 */}
      <ToolCard title="WHOIS 查询" toolKey="network-whois">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">域名</label>
            <input
              type="text"
              value={whoisDomain}
              onChange={(e) => setWhoisDomain(e.target.value)}
              placeholder="example.com"
              className="w-full"
            />
          </div>
          
          <ToolButton onClick={handleWhoisLookup} loading={loading}>
            查询
          </ToolButton>
          
          <ToolOutput label="结果" value={whoisResult} />
        </div>
      </ToolCard>
      
      {/* IP 查询 */}
      <ToolCard title="IP 地理位置查询" toolKey="network-ip">
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-theme-muted mb-2">IP 地址</label>
            <input
              type="text"
              value={ipAddress}
              onChange={(e) => setIpAddress(e.target.value)}
              placeholder="8.8.8.8"
              className="w-full"
            />
          </div>
          
          <ToolButton onClick={handleIpLookup} loading={loading}>
            查询
          </ToolButton>
          
          <ToolOutput label="结果" value={ipResult} />
        </div>
      </ToolCard>
    </div>
  )
}
