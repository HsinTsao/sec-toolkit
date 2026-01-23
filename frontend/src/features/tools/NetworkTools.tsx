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

export default function NetworkTools() {
  const { addRecentTool } = useToolStore()
  
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
        const fields = [
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
          DNS 查询、WHOIS 查询、IP 地理位置查询
        </p>
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

