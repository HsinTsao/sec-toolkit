import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 是否正在刷新 token
let isRefreshing = false
// 等待刷新的请求队列
let refreshSubscribers: ((token: string) => void)[] = []

// 添加到等待队列
const subscribeTokenRefresh = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback)
}

// 通知所有等待的请求
const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach((callback) => callback(token))
  refreshSubscribers = []
}

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 自动刷新 token
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    
    // 如果是 401 错误且不是刷新 token 的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      const { refreshToken, setTokens, logout } = useAuthStore.getState()
      
      // 如果没有 refresh token，直接登出
      if (!refreshToken) {
        logout()
        window.location.href = '/login'
        return Promise.reject(error)
      }
      
      // 如果正在刷新，将请求加入队列
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(api(originalRequest))
          })
        })
      }
      
      originalRequest._retry = true
      isRefreshing = true
      
      try {
        // 刷新 token
        const { data } = await axios.post('/api/auth/refresh', { 
          refresh_token: refreshToken 
        })
        
        const newToken = data.access_token
        const newRefreshToken = data.refresh_token
        
        // 保存新 token
        setTokens(newToken, newRefreshToken)
        
        // 通知等待的请求
        onTokenRefreshed(newToken)
        
        // 重试原请求
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        // 刷新失败，登出
        logout()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }
    
    return Promise.reject(error)
  }
)

export default api

// ==================== Auth API ====================
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  
  register: (email: string, username: string, password: string) =>
    api.post('/auth/register', { email, username, password }),
  
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
}

// ==================== User API ====================
export const userApi = {
  getMe: () => api.get('/users/me'),
  updateMe: (data: { username?: string; avatar?: string; settings?: object }) =>
    api.patch('/users/me', data),
}

// ==================== Notes API ====================
export const notesApi = {
  getCategories: () => api.get('/notes/categories'),
  createCategory: (data: { name: string; parent_id?: string; icon?: string }) =>
    api.post('/notes/categories', data),
  deleteCategory: (id: string) => api.delete(`/notes/categories/${id}`),
  
  getTags: () => api.get('/notes/tags'),
  createTag: (data: { name: string; color?: string }) =>
    api.post('/notes/tags', data),
  deleteTag: (id: string) => api.delete(`/notes/tags/${id}`),
  
  getNotes: (params?: { category_id?: string; tag_id?: string; search?: string }) =>
    api.get('/notes', { params }),
  getNote: (id: string) => api.get(`/notes/${id}`),
  createNote: (data: { title: string; content?: string; category_id?: string; tag_ids?: string[] }) =>
    api.post('/notes', data),
  updateNote: (id: string, data: { title?: string; content?: string; category_id?: string; tag_ids?: string[] }) =>
    api.post(`/notes/${id}/update`, data),  // 使用 POST 替代 PATCH，兼容某些网络环境
  deleteNote: (id: string) => api.delete(`/notes/${id}`),
}

// ==================== Tools API ====================
export const toolsApi = {
  // 收藏
  getFavorites: () => api.get('/tools/favorites'),
  addFavorite: (toolKey: string) =>
    api.post('/tools/favorites', { tool_key: toolKey }),
  removeFavorite: (toolKey: string) =>
    api.delete(`/tools/favorites/${toolKey}`),
  
  // 历史
  getHistory: (toolKey?: string) =>
    api.get('/tools/history', { params: { tool_key: toolKey } }),
  addHistory: (data: { tool_key: string; input_data?: unknown; output_data?: unknown }) =>
    api.post('/tools/history', data),
  clearHistory: (toolKey?: string) =>
    api.delete('/tools/history', { params: { tool_key: toolKey } }),
  
  // 编码工具
  base64Encode: (text: string) =>
    api.post('/tools/encoding/base64/encode', { text }),
  base64Decode: (text: string) =>
    api.post('/tools/encoding/base64/decode', { text }),
  urlEncode: (text: string) =>
    api.post('/tools/encoding/url/encode', { text }),
  urlDecode: (text: string) =>
    api.post('/tools/encoding/url/decode', { text }),
  htmlEncode: (text: string) =>
    api.post('/tools/encoding/html/encode', { text }),
  htmlDecode: (text: string) =>
    api.post('/tools/encoding/html/decode', { text }),
  hexEncode: (text: string) =>
    api.post('/tools/encoding/hex/encode', { text }),
  hexDecode: (text: string) =>
    api.post('/tools/encoding/hex/decode', { text }),
  unicodeEncode: (text: string) =>
    api.post('/tools/encoding/unicode/encode', { text }),
  unicodeDecode: (text: string) =>
    api.post('/tools/encoding/unicode/decode', { text }),
  
  // 哈希工具
  calculateHash: (text: string, algorithm: string) =>
    api.post('/tools/hash/calculate', { text, algorithm }),
  calculateAllHashes: (text: string) =>
    api.post('/tools/hash/all', { text }),
  
  // 加密工具
  aesEncrypt: (text: string, key: string, iv?: string) =>
    api.post('/tools/crypto/aes/encrypt', { text, key, iv }),
  aesDecrypt: (text: string, key: string, iv?: string) =>
    api.post('/tools/crypto/aes/decrypt', { text, key, iv }),
  rsaGenerateKeys: (keySize: number = 2048) =>
    api.post('/tools/crypto/rsa/generate', { key_size: keySize }),
  rsaEncrypt: (text: string, key: string) =>
    api.post('/tools/crypto/rsa/encrypt', { text, key }),
  rsaDecrypt: (text: string, key: string) =>
    api.post('/tools/crypto/rsa/decrypt', { text, key }),
  
  // JWT 工具
  jwtDecode: (token: string) =>
    api.post('/tools/jwt/decode', { token }),
  jwtEncode: (payload: object, secret: string, algorithm: string = 'HS256') =>
    api.post('/tools/jwt/encode', { payload, secret, algorithm }),
  
  // 密码工具
  generatePassword: (params: { length?: number; uppercase?: boolean; lowercase?: boolean; digits?: boolean; special?: boolean }) =>
    api.post('/tools/password/generate', params),
  checkPasswordStrength: (password: string) =>
    api.post('/tools/password/strength', { password }),
  
  // 格式工具
  formatJson: (text: string) =>
    api.post('/tools/format/json', { text }),
  formatXml: (text: string) =>
    api.post('/tools/format/xml', { text }),
  testRegex: (pattern: string, text: string, flags?: string) =>
    api.post('/tools/format/regex/test', { pattern, text, flags }),
  textDiff: (text1: string, text2: string) =>
    api.post('/tools/format/diff', { text1, text2 }),
  convertTimestamp: (params: { timestamp?: number; datetime_str?: string; format?: string }) =>
    api.post('/tools/misc/timestamp', params),
  baseConvert: (value: string, fromBase: number, toBase: number) =>
    api.post('/tools/misc/base-convert', { value, from_base: fromBase, to_base: toBase }),
  generateUuid: () =>
    api.post('/tools/misc/uuid'),
  
  // 网络工具
  dnsLookup: (domain: string, recordType: string = 'A') =>
    api.post('/tools/network/dns', { domain, record_type: recordType }),
  whoisLookup: (domain: string) =>
    api.post('/tools/network/whois', { domain }),
  ipInfo: (ip: string) =>
    api.post('/tools/network/ip/info', { ip }),
  analyzeTarget: (target: string) =>
    api.post('/tools/network/analyze', { target }),
  
  // 资源连通性测试工具
  crawlResources: (params: {
    url: string
    filter_ids?: string[]
    timeout?: number
    concurrency?: number
    include_types?: string[]
    custom_headers?: Record<string, string>
  }) => api.post('/tools/crawler/crawl', params),
  testSingleResource: (params: {
    url: string
    timeout?: number
    custom_headers?: Record<string, string>
  }) => api.post('/tools/crawler/test-single', params),
  batchTestUrls: (params: {
    urls: string[]
    timeout?: number
    concurrency?: number
    custom_headers?: Record<string, string>
  }) => api.post('/tools/crawler/batch-test', params),
  batchCrawlResources: (params: {
    urls: string[]
    filter_ids?: string[]
    timeout?: number
    concurrency?: number
    include_types?: string[]
    custom_headers?: Record<string, string>
  }) => api.post('/tools/crawler/batch-crawl', params),
  // 只提取资源（不测试）
  extractResources: (params: {
    urls: string[]
    include_types?: string[]
    custom_headers?: Record<string, string>
    use_browser?: boolean  // 是否使用浏览器渲染（用于动态页面）
    browser_wait_time?: number  // 浏览器等待时间（秒）
    fetch_size?: boolean  // 是否获取文件大小
    size_concurrency?: number  // 获取文件大小的并发数
  }) => api.post('/tools/crawler/extract', params, {
    // 批量提取可能需要很长时间，特别是浏览器渲染模式
    // 每个 URL 约需 10-20 秒，所以设置 10 分钟超时
    timeout: 600000
  }),
  // 测试选定的资源
  testSelectedResources: (params: {
    resources: Array<{ url: string; resource_type: string; source_url?: string }>
    timeout?: number
    concurrency?: number
    enhanced?: boolean
    custom_headers?: Record<string, string>
  }) => api.post('/tools/crawler/test-selected', params, {
    // 测试大量资源需要较长时间
    timeout: 600000
  }),
  getResourceTypes: () => api.get('/tools/crawler/resource-types'),
}

// ==================== Bookmarks API ====================
export const bookmarksApi = {
  getBookmarks: (category?: string) =>
    api.get('/bookmarks', { params: { category } }),
  createBookmark: (data: { title: string; url: string; icon?: string; category?: string }) =>
    api.post('/bookmarks', data),
  updateBookmark: (id: string, data: { title?: string; url?: string; icon?: string; category?: string }) =>
    api.patch(`/bookmarks/${id}`, data),
  deleteBookmark: (id: string) =>
    api.delete(`/bookmarks/${id}`),
  // 获取 URL meta 信息
  getUrlMeta: (url: string) =>
    api.post<{ title: string | null; description: string | null; icon: string | null; url: string }>('/bookmarks/meta', { url }),
}

// ==================== Callback API ====================
export const callbackApi = {
  // Token 管理
  createToken: (data: { name?: string; expires_hours?: number }) =>
    api.post('/callback/tokens', data),
  getTokens: () =>
    api.get('/callback/tokens'),
  deleteToken: (tokenId: string) =>
    api.delete(`/callback/tokens/${tokenId}`),
  renewToken: (tokenId: string, expiresHours: number = 24) =>
    api.patch(`/callback/tokens/${tokenId}/renew`, { expires_hours: expiresHours }),
  
  // 记录查询
  getRecords: (tokenId: string, limit?: number) =>
    api.get(`/callback/tokens/${tokenId}/records`, { params: { limit } }),
  clearRecords: (tokenId: string) =>
    api.delete(`/callback/tokens/${tokenId}/records`),
  pollRecords: (tokenId: string, since?: string) =>
    api.get(`/callback/tokens/${tokenId}/poll`, { params: { since } }),
  
  // 统计分析
  getTokenStats: (tokenId: string) =>
    api.get(`/callback/tokens/${tokenId}/stats`),
  getAllStats: () =>
    api.get('/callback/stats/all'),
  
  // PoC 规则
  getPocTemplates: () =>
    api.get('/callback/poc-templates'),
  getPocRules: (tokenId: string) =>
    api.get(`/callback/tokens/${tokenId}/rules`),
  createPocRule: (tokenId: string, data: {
    name: string;
    description?: string;
    status_code?: number;
    content_type?: string;
    response_body?: string;
    response_headers?: Record<string, string>;
    redirect_url?: string;
    delay_ms?: number;
    enable_variables?: boolean;
  }) => api.post(`/callback/tokens/${tokenId}/rules`, data),
  updatePocRule: (tokenId: string, ruleId: string, data: {
    name?: string;
    description?: string;
    status_code?: number;
    content_type?: string;
    response_body?: string;
    response_headers?: Record<string, string>;
    redirect_url?: string;
    delay_ms?: number;
    enable_variables?: boolean;
    is_active?: boolean;
  }) => api.patch(`/callback/tokens/${tokenId}/rules/${ruleId}`, data),
  deletePocRule: (tokenId: string, ruleId: string) =>
    api.delete(`/callback/tokens/${tokenId}/rules/${ruleId}`),
}

// ==================== LLM API ====================
export interface LLMProvider {
  id: string
  name: string
  base_url: string
  models: string[]
  default_model: string
  description: string
  icon: string
}

export interface LLMConfig {
  id: string
  provider_id: string
  api_key_set: boolean
  base_url: string | null
  model: string
  use_system_default: boolean
  created_at: string
  updated_at: string
}

export interface DefaultLLMConfig {
  available: boolean
  provider_id: string | null
  provider_name?: string
  model: string | null
  models: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export const llmApi = {
  // 获取提供商列表
  getProviders: () =>
    api.get<LLMProvider[]>('/llm/providers'),
  
  // 获取系统默认配置
  getDefaultConfig: () =>
    api.get<DefaultLLMConfig>('/llm/default-config'),
  
  // 获取用户 LLM 配置
  getConfig: () =>
    api.get<LLMConfig>('/llm/config'),
  
  // 更新用户 LLM 配置
  updateConfig: (data: { provider_id: string; api_key?: string; base_url?: string; model: string; use_system_default?: boolean }) =>
    api.put<LLMConfig>('/llm/config', data),
  
  // 删除用户 LLM 配置
  deleteConfig: () =>
    api.delete('/llm/config'),
  
  // 聊天（非流式）
  chat: (data: { message: string; history: ChatMessage[]; use_rag?: boolean }) =>
    api.post<{ content: string; sources: string[] }>('/llm/chat', data),
  
  // 聊天（流式）- 返回 URL，需要用 EventSource 处理
  getChatStreamUrl: () => '/api/llm/chat/stream',

  // 快速模式 API（双 LLM 架构，省 Token）
  fastChat: (data: { message: string; mode?: string; skip_summary?: boolean }) =>
    api.post<{
      content: string
      mode_used: string
      tokens_estimated: number
      rule_matched: boolean
      tool_used: string | null
      fallback_needed: boolean
    }>('/llm/fast/chat', data),
  getFastChatStreamUrl: () => '/api/llm/fast/chat/stream',
  getFastModeInfo: () => api.get('/llm/fast/info'),
}

// ==================== Proxy API ====================
export interface ProxyConfig {
  local_port: number
  target_url: string
  fake_host: string
  enabled: boolean
  preserve_path: boolean
  ssl_verify: boolean
  timeout: number
  custom_headers: Record<string, string>
  running?: boolean
  log_count?: number
}

export interface ProxyLog {
  timestamp: string
  method: string
  path: string
  target_url: string
  fake_host: string
  status_code: number
  response_time: number
  request_headers: Record<string, string>
  response_headers: Record<string, string>
  error: string | null
}

export const proxyApi = {
  // 创建代理
  createProxy: (data: {
    local_port: number
    target_url: string
    fake_host: string
    preserve_path?: boolean
    ssl_verify?: boolean
    timeout?: number
    custom_headers?: Record<string, string>
    auto_start?: boolean
  }) => api.post('/proxy/create', data),
  
  // 快速测试
  quickTest: (data: {
    local_port: number
    target_url: string
    fake_host: string
    preserve_path?: boolean
    ssl_verify?: boolean
    timeout?: number
    custom_headers?: Record<string, string>
  }) => api.post('/proxy/quick-test', data),
  
  // 启动代理
  startProxy: (port: number) =>
    api.post(`/proxy/${port}/start`),
  
  // 停止代理
  stopProxy: (port: number) =>
    api.post(`/proxy/${port}/stop`),
  
  // 删除代理
  deleteProxy: (port: number) =>
    api.delete(`/proxy/${port}`),
  
  // 更新代理配置
  updateProxy: (port: number, data: {
    target_url?: string
    fake_host?: string
    preserve_path?: boolean
    ssl_verify?: boolean
    timeout?: number
    custom_headers?: Record<string, string>
  }) => api.put(`/proxy/${port}`, data),
  
  // 获取代理状态
  getProxyStatus: (port: number) =>
    api.get<{ config: ProxyConfig; running: boolean; log_count: number; local_url: string | null }>(`/proxy/${port}/status`),
  
  // 列出所有代理
  listProxies: () =>
    api.get<{ proxies: ProxyConfig[] }>('/proxy/list'),
  
  // 获取日志
  getProxyLogs: (port: number, limit?: number) =>
    api.get<{ logs: ProxyLog[]; count: number }>(`/proxy/${port}/logs`, { params: { limit } }),
  
  // 清除日志
  clearProxyLogs: (port: number) =>
    api.delete(`/proxy/${port}/logs`),
  
  // ========== iframe 同域代理 ==========
  // 创建 iframe 代理
  createIframeProxy: (data: {
    target_url: string
    fake_host?: string
    rewrite_urls?: boolean
    inject_script?: string
    cookies?: string
    custom_headers?: Record<string, string>
  }) => api.post<{
    success: boolean
    proxy_id: string
    iframe_src: string
    usage: string
    note: string
  }>('/proxy/iframe/create', data),
  
  // 列出 iframe 代理
  listIframeProxies: () =>
    api.get<{ configs: Array<{
      proxy_id: string
      target_url: string
      base_url: string
      fake_host: string
      rewrite_urls: boolean
    }> }>('/proxy/iframe/list'),
  
  // 删除 iframe 代理
  deleteIframeProxy: (proxyId: string) =>
    api.delete(`/proxy/iframe/${proxyId}`),
}

// ==================== Bypass API ====================
export const bypassApi = {
  // URL 编码
  urlEncode: (text: string, level: number = 1, encodeAll: boolean = false) =>
    api.post('/bypass/url/encode', { text, level, encode_all: encodeAll }),
  urlDecode: (text: string, level: number = 1) =>
    api.post('/bypass/url/decode', { text, level }),
  
  // HTML 实体编码
  htmlEncode: (text: string, mode: 'decimal' | 'hex' | 'named' = 'decimal', padding: number = 0) =>
    api.post('/bypass/html/encode', { text, mode, padding }),
  htmlDecode: (text: string) =>
    api.post('/bypass/html/decode', { text }),
  
  // JavaScript 编码
  jsEncode: (text: string, mode: 'octal' | 'hex' | 'unicode' = 'hex') =>
    api.post('/bypass/js/encode', { text, mode }),
  jsDecode: (text: string) =>
    api.post('/bypass/js/decode', { text }),
  
  // 大小写变形
  caseTransform: (text: string, mode: 'upper' | 'lower' | 'random' | 'alternate' = 'random') =>
    api.post('/bypass/case/transform', { text, mode }),
  
  // SQL 绕过
  sqlBypass: (text: string, technique: 'comment' | 'hex' | 'char' = 'comment', dbType: 'mysql' | 'mssql' | 'oracle' = 'mysql') =>
    api.post('/bypass/sql/bypass', { text, technique, db_type: dbType }),
  
  // 空格绕过
  spaceBypass: (text: string, mode: 'comment' | 'tab' | 'newline' | 'plus' | 'parenthesis' = 'comment') =>
    api.post('/bypass/space/bypass', { text, mode }),
  
  // 一键生成所有编码
  generateAll: (text: string) =>
    api.post<{ results: Record<string, string> }>('/bypass/generate-all', { text }),
  
  // 获取 Payload 模板
  getTemplates: () =>
    api.get<{ templates: Record<string, string> }>('/bypass/templates'),
}

