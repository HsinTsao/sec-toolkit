import { Link } from 'react-router-dom'
import {
  Binary,
  Hash,
  Lock,
  Key,
  FileCode,
  Globe,
  KeyRound,
  ArrowRight,
  Clock,
  Star,
} from 'lucide-react'
import { useToolStore } from '@/stores/toolStore'

const tools = [
  {
    id: 'encoding',
    name: '编码/解码',
    description: 'Base64, URL, HTML, Hex, Unicode 等编码转换',
    icon: Binary,
    path: '/tools/encoding',
    color: 'from-emerald-500 to-teal-500',
  },
  {
    id: 'hash',
    name: '哈希计算',
    description: 'MD5, SHA1, SHA256, SHA512 等哈希算法',
    icon: Hash,
    path: '/tools/hash',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    id: 'crypto',
    name: '加密/解密',
    description: 'AES, RSA, DES 等加密算法',
    icon: Lock,
    path: '/tools/crypto',
    color: 'from-purple-500 to-pink-500',
  },
  {
    id: 'jwt',
    name: 'JWT 工具',
    description: 'JWT 解码、编码、验证',
    icon: Key,
    path: '/tools/jwt',
    color: 'from-orange-500 to-amber-500',
  },
  {
    id: 'format',
    name: '格式处理',
    description: 'JSON/XML 格式化、正则测试、Diff 对比',
    icon: FileCode,
    path: '/tools/format',
    color: 'from-rose-500 to-red-500',
  },
  {
    id: 'network',
    name: '网络工具',
    description: 'DNS 查询、WHOIS、IP 信息',
    icon: Globe,
    path: '/tools/network',
    color: 'from-indigo-500 to-violet-500',
  },
  {
    id: 'password',
    name: '密码工具',
    description: '密码生成、强度检测',
    icon: KeyRound,
    path: '/tools/password',
    color: 'from-lime-500 to-green-500',
  },
]

export default function DashboardPage() {
  const { recentTools, favorites } = useToolStore()
  
  return (
    <div className="space-y-8 animate-fadeIn">
      {/* 欢迎区域 */}
      <div className="card bg-gradient-to-r from-theme-primary/10 to-theme-secondary/10 border-theme-primary/30">
        <h1 className="text-2xl font-bold text-theme-text mb-2">
          欢迎使用 Security Toolkit 🔐
        </h1>
        <p className="text-theme-muted">
          专业的安全工具集合，助力您的安全研究工作
        </p>
      </div>
      
      {/* 最近使用 */}
      {recentTools.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-theme-muted" />
            <h2 className="text-lg font-semibold">最近使用</h2>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {recentTools.slice(0, 5).map((toolId) => {
              const tool = tools.find((t) => t.id === toolId)
              if (!tool) return null
              return (
                <Link
                  key={toolId}
                  to={tool.path}
                  className="flex items-center gap-2 px-4 py-2 bg-theme-card border border-theme-border rounded-lg hover:border-theme-primary transition-colors whitespace-nowrap"
                >
                  <tool.icon className="w-4 h-4 text-theme-primary" />
                  <span>{tool.name}</span>
                </Link>
              )
            })}
          </div>
        </div>
      )}
      
      {/* 收藏工具 */}
      {favorites.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Star className="w-5 h-5 text-theme-warning" />
            <h2 className="text-lg font-semibold">收藏工具</h2>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {favorites.map((toolId) => {
              const tool = tools.find((t) => t.id === toolId)
              if (!tool) return null
              return (
                <Link
                  key={toolId}
                  to={tool.path}
                  className="flex items-center gap-2 px-4 py-2 bg-theme-card border border-theme-border rounded-lg hover:border-theme-warning transition-colors whitespace-nowrap"
                >
                  <tool.icon className="w-4 h-4 text-theme-warning" />
                  <span>{tool.name}</span>
                </Link>
              )
            })}
          </div>
        </div>
      )}
      
      {/* 工具列表 */}
      <div>
        <h2 className="text-lg font-semibold mb-4">全部工具</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tools.map((tool) => (
            <Link
              key={tool.id}
              to={tool.path}
              className="group tool-card flex flex-col"
            >
              <div className="flex items-start gap-4">
                <div
                  className={`w-12 h-12 rounded-xl bg-gradient-to-br ${tool.color} flex items-center justify-center flex-shrink-0`}
                >
                  <tool.icon className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-theme-text group-hover:text-theme-primary transition-colors">
                    {tool.name}
                  </h3>
                  <p className="text-sm text-theme-muted mt-1 line-clamp-2">
                    {tool.description}
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-theme-muted group-hover:text-theme-primary group-hover:translate-x-1 transition-all flex-shrink-0" />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

