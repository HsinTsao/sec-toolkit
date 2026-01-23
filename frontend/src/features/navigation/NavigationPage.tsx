import { useState } from 'react'
import { ExternalLink, Search, Shield, Github, FileCode, AlertTriangle } from 'lucide-react'

// CVE 搜索链接生成器
const generateCveLinks = (cve: string) => {
  const cveId = cve.toUpperCase().trim()
  return {
    info: [
      {
        title: 'NVD (美国国家漏洞库)',
        url: `https://nvd.nist.gov/vuln/detail/${cveId}`,
        icon: '🛡️',
        desc: '官方漏洞详情、CVSS评分、参考链接',
      },
      {
        title: 'CVE Details',
        url: `https://www.cvedetails.com/cve/${cveId}/`,
        icon: '🔍',
        desc: '漏洞详情、影响产品、统计数据',
      },
      {
        title: 'MITRE CVE',
        url: `https://cve.mitre.org/cgi-bin/cvename.cgi?name=${cveId}`,
        icon: '📋',
        desc: 'CVE 官方记录',
      },
      {
        title: 'CNNVD (中国国家漏洞库)',
        url: `https://www.cnnvd.org.cn/home/globalSearch?keyword=${cveId}`,
        icon: '🇨🇳',
        desc: '中文漏洞信息',
      },
      {
        title: 'VulnDB',
        url: `https://vuldb.com/?search=${cveId}`,
        icon: '📊',
        desc: '漏洞情报、时间线',
      },
    ],
    poc: [
      {
        title: 'Google 搜索 POC',
        url: `https://www.google.com/search?q=${cveId}+poc+site:github.com`,
        icon: '🔍',
        desc: '通过 Google 搜索 GitHub POC',
      },
      {
        title: 'Exploit-DB',
        url: `https://www.exploit-db.com/search?cve=${cveId}`,
        icon: '💥',
        desc: '公开的漏洞利用代码',
      },
      {
        title: 'Sploitus',
        url: `https://sploitus.com/?query=${cveId}`,
        icon: '🎯',
        desc: 'Exploit 和工具搜索引擎',
      },
      {
        title: 'POCHouse',
        url: `https://pochouse.com/search?keyword=${cveId}`,
        icon: '🏠',
        desc: 'POC 收集平台',
      },
      {
        title: 'Vulhub',
        url: `https://vulhub.org/#/environments/`,
        icon: '🐳',
        desc: 'Docker 漏洞环境（手动查找）',
      },
      {
        title: 'Packet Storm',
        url: `https://packetstormsecurity.com/search/?q=${cveId}`,
        icon: '⚡',
        desc: '安全工具和漏洞利用',
      },
      {
        title: 'Seebug',
        url: `https://www.seebug.org/search/?keywords=${cveId}`,
        icon: '🐛',
        desc: '知道创宇漏洞平台',
      },
      {
        title: '0day.today',
        url: `https://0day.today/search?search_request=${cveId}`,
        icon: '☠️',
        desc: 'Exploit 数据库',
      },
    ],
  }
}

// 验证 CVE 格式
const isValidCve = (cve: string) => {
  return /^CVE-\d{4}-\d{4,}$/i.test(cve.trim())
}

// 预设的安全资源导航
const defaultNavigation = [
  {
    category: '漏洞平台',
    items: [
      { title: 'CVE Details', url: 'https://www.cvedetails.com/', icon: '🔍' },
      { title: 'NVD', url: 'https://nvd.nist.gov/', icon: '🛡️' },
      { title: 'Exploit-DB', url: 'https://www.exploit-db.com/', icon: '💥' },
      { title: 'Vulhub', url: 'https://vulhub.org/', icon: '🐳' },
    ],
  },
  {
    category: '安全社区',
    items: [
      { title: '先知社区', url: 'https://xz.aliyun.com/', icon: '📚' },
      { title: 'FreeBuf', url: 'https://www.freebuf.com/', icon: '📰' },
      { title: '安全客', url: 'https://www.anquanke.com/', icon: '🔐' },
      { title: 'Seebug', url: 'https://www.seebug.org/', icon: '🐛' },
    ],
  },
  {
    category: '在线工具',
    items: [
      { title: 'CyberChef', url: 'https://gchq.github.io/CyberChef/', icon: '🍳' },
      { title: 'VirusTotal', url: 'https://www.virustotal.com/', icon: '🦠' },
      { title: 'Shodan', url: 'https://www.shodan.io/', icon: '🔎' },
      { title: 'Censys', url: 'https://search.censys.io/', icon: '🌐' },
    ],
  },
  {
    category: '靶场环境',
    items: [
      { title: 'HackTheBox', url: 'https://www.hackthebox.com/', icon: '📦' },
      { title: 'TryHackMe', url: 'https://tryhackme.com/', icon: '🎯' },
      { title: 'DVWA', url: 'https://dvwa.co.uk/', icon: '🕸️' },
      { title: 'WebGoat', url: 'https://owasp.org/www-project-webgoat/', icon: '🐐' },
    ],
  },
  {
    category: '安全框架',
    items: [
      { title: 'OWASP', url: 'https://owasp.org/', icon: '🏛️' },
      { title: 'MITRE ATT&CK', url: 'https://attack.mitre.org/', icon: '⚔️' },
      { title: 'NIST', url: 'https://www.nist.gov/cybersecurity', icon: '📋' },
      { title: 'CIS Controls', url: 'https://www.cisecurity.org/controls', icon: '✅' },
    ],
  },
  {
    category: '工具下载',
    items: [
      { title: 'Kali Linux', url: 'https://www.kali.org/', icon: '🐉' },
      { title: 'Burp Suite', url: 'https://portswigger.net/burp', icon: '🔧' },
      { title: 'Nmap', url: 'https://nmap.org/', icon: '📡' },
      { title: 'Metasploit', url: 'https://www.metasploit.com/', icon: '💎' },
    ],
  },
]

export default function NavigationPage() {
  const [searchInput, setSearchInput] = useState('')
  const [cveSearch, setCveSearch] = useState('')
  const [navigation] = useState(defaultNavigation)
  
  // 判断输入是否为 CVE 格式
  const isCveFormat = (input: string) => {
    const trimmed = input.trim()
    return isValidCve(trimmed) || /^\d{4}-\d{4,}$/.test(trimmed)
  }
  
  // CVE 搜索结果
  const cveLinks = cveSearch ? generateCveLinks(cveSearch) : null
  
  // 处理搜索（智能识别 CVE 或普通搜索）
  const handleSearch = () => {
    const input = searchInput.trim()
    if (!input) {
      setCveSearch('')
      return
    }
    
    // 检查是否为 CVE 格式
    let cve = input
    if (/^\d{4}-\d{4,}$/.test(input)) {
      cve = `CVE-${input}`
    }
    
    if (isValidCve(cve)) {
      // CVE 搜索
      setCveSearch(cve.toUpperCase())
    } else {
      // 普通资源搜索，清除 CVE 结果
      setCveSearch('')
    }
  }
  
  // 实时过滤导航（非 CVE 格式时）
  const searchQuery = isCveFormat(searchInput) ? '' : searchInput
  
  // 过滤导航
  const filteredNavigation = navigation
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) =>
          item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.url.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    }))
    .filter((group) => group.items.length > 0)
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-theme-text">资源导航</h1>
          <p className="text-theme-muted mt-1">常用安全资源和工具链接</p>
        </div>
      </div>
      
      {/* 统一搜索框 */}
      <div className="card bg-gradient-to-br from-theme-card to-theme-bg border-theme-primary/30">
        <div className="flex items-center gap-3 mb-4 max-w-2xl mx-auto">
          <div className="w-10 h-10 rounded-lg bg-theme-primary/20 flex items-center justify-center flex-shrink-0">
            <Search className="w-5 h-5 text-theme-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-theme-text">智能搜索</h3>
            <p className="text-sm text-theme-muted">输入 CVE 编号查找漏洞，或输入关键词搜索资源</p>
          </div>
        </div>
        
        <div className="flex gap-2 max-w-2xl mx-auto">
          <div className="relative flex-1">
            <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-muted" />
            <input
              type="text"
              placeholder="CVE-2021-44228 / 2021-44228 / 关键词..."
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value)
                // 如果不是 CVE 格式，清除 CVE 结果
                if (!isCveFormat(e.target.value)) {
                  setCveSearch('')
                }
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10"
            />
          </div>
          <button
            onClick={handleSearch}
            className="btn btn-primary flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            搜索
          </button>
        </div>
        
        {/* 搜索提示 */}
        {searchInput && !cveSearch && isCveFormat(searchInput) && (
          <p className="text-center text-sm text-theme-muted mt-3">
            按 Enter 或点击搜索按钮查找 CVE 信息
          </p>
        )}
        
        {/* CVE 搜索结果 */}
        {cveLinks && (
          <div className="mt-6 space-y-4 animate-fadeIn">
            <div className="flex items-center gap-2 text-theme-primary">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-semibold">{cveSearch}</span>
              <button
                onClick={() => {
                  setCveSearch('')
                  setSearchInput('')
                }}
                className="ml-auto text-sm text-theme-muted hover:text-theme-text"
              >
                清除
              </button>
            </div>
            
            {/* 漏洞信息 */}
            <div>
              <h4 className="text-sm font-medium text-theme-muted mb-2 flex items-center gap-2">
                <FileCode className="w-4 h-4" />
                漏洞信息
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {cveLinks.info.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 p-3 rounded-lg bg-theme-bg hover:bg-theme-bg/80 border border-transparent hover:border-theme-border transition-all group"
                  >
                    <span className="text-lg">{link.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-theme-text group-hover:text-theme-primary flex items-center gap-1">
                        {link.title}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100" />
                      </div>
                      <div className="text-xs text-theme-muted line-clamp-1">{link.desc}</div>
                    </div>
                  </a>
                ))}
              </div>
            </div>
            
            {/* POC / Exploit */}
            <div>
              <h4 className="text-sm font-medium text-theme-muted mb-2 flex items-center gap-2">
                <Github className="w-4 h-4" />
                POC / Exploit
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {cveLinks.poc.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 p-3 rounded-lg bg-theme-bg hover:bg-theme-bg/80 border border-transparent hover:border-theme-danger/30 transition-all group"
                  >
                    <span className="text-lg">{link.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-theme-text group-hover:text-theme-danger flex items-center gap-1">
                        {link.title}
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100" />
                      </div>
                      <div className="text-xs text-theme-muted line-clamp-1">{link.desc}</div>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* 导航分类 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredNavigation.map((group) => (
          <div key={group.category} className="card">
            <h3 className="text-lg font-semibold text-theme-text mb-4">
              {group.category}
            </h3>
            <div className="space-y-2">
              {group.items.map((item) => (
                <a
                  key={item.url}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-theme-bg transition-colors group"
                >
                  <span className="text-xl">{item.icon}</span>
                  <span className="flex-1 text-theme-text group-hover:text-theme-primary transition-colors">
                    {item.title}
                  </span>
                  <ExternalLink className="w-4 h-4 text-theme-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
      
      {filteredNavigation.length === 0 && (
        <div className="text-center py-12 text-theme-muted">
          没有找到匹配的资源
        </div>
      )}
    </div>
  )
}

