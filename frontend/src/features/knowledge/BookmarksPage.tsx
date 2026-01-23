import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Plus, 
  Search, 
  ExternalLink, 
  Trash2, 
  Edit2, 
  Globe,
  Link2,
  X,
  Check,
  Loader2,
  Copy
} from 'lucide-react'
import { bookmarksApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

interface Bookmark {
  id: string
  title: string
  url: string
  icon?: string
  category?: string
  created_at: string
}

// 预设分类
const defaultCategories = [
  '全部',
  '常用',
  '工作',
  '学习',
  '安全资源',
  '工具',
  '文档',
  '其他',
]

export default function BookmarksPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('全部')
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingBookmark, setEditingBookmark] = useState<Bookmark | null>(null)
  
  // 表单状态
  const [formUrl, setFormUrl] = useState('')
  const [formTitle, setFormTitle] = useState('')
  const [formCategory, setFormCategory] = useState('常用')
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)
  
  // 获取书签列表
  const { data: bookmarks = [], isLoading } = useQuery<Bookmark[]>({
    queryKey: ['bookmarks'],
    queryFn: async () => {
      const { data } = await bookmarksApi.getBookmarks()
      return data
    },
  })
  
  // 创建书签
  const createMutation = useMutation({
    mutationFn: async (data: { title: string; url: string; category?: string }) => {
      const response = await bookmarksApi.createBookmark(data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
      toast.success('书签添加成功')
      resetForm()
    },
    onError: () => toast.error('添加失败'),
  })
  
  // 更新书签
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { title?: string; url?: string; category?: string } }) => {
      const response = await bookmarksApi.updateBookmark(id, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
      toast.success('书签更新成功')
      resetForm()
    },
    onError: () => toast.error('更新失败'),
  })
  
  // 删除书签
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await bookmarksApi.deleteBookmark(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks'] })
      toast.success('书签删除成功')
    },
    onError: () => toast.error('删除失败'),
  })
  
  const resetForm = () => {
    setShowAddModal(false)
    setEditingBookmark(null)
    setFormUrl('')
    setFormTitle('')
    setFormCategory('常用')
  }
  
  // 从 URL 获取网站 meta 信息
  const fetchUrlMeta = async (url: string) => {
    if (!url) return
    
    // 确保有协议
    let fullUrl = url
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      fullUrl = 'https://' + url
    }
    
    // 简单验证 URL
    try {
      new URL(fullUrl)
    } catch {
      return
    }
    
    setIsLoadingMeta(true)
    try {
      const { data } = await bookmarksApi.getUrlMeta(fullUrl)
      if (data.title) {
        setFormTitle(data.title)
      }
      // 更新 URL（可能被重定向）
      if (data.url && data.url !== formUrl) {
        setFormUrl(data.url)
      }
    } catch {
      // 失败时使用域名作为标题
      try {
        const urlObj = new URL(fullUrl)
        setFormTitle(urlObj.hostname.replace('www.', ''))
      } catch {
        // 忽略
      }
    } finally {
      setIsLoadingMeta(false)
    }
  }
  
  // 防抖定时器
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null)
  
  const handleUrlChange = (url: string) => {
    setFormUrl(url)
    
    // 清除之前的定时器
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    
    // 如果用户手动修改了标题，不自动获取
    if (formTitle && editingBookmark) return
    
    // 防抖：500ms 后获取 meta 信息
    const timer = setTimeout(() => {
      if (url.length > 5) {
        fetchUrlMeta(url)
      }
    }, 500)
    setDebounceTimer(timer)
  }
  
  const handleSubmit = () => {
    if (!formUrl.trim()) {
      toast.error('请输入网址')
      return
    }
    
    // 验证 URL
    try {
      new URL(formUrl)
    } catch {
      toast.error('请输入有效的网址')
      return
    }
    
    const title = formTitle.trim() || new URL(formUrl).hostname
    
    if (editingBookmark) {
      updateMutation.mutate({
        id: editingBookmark.id,
        data: { title, url: formUrl, category: formCategory },
      })
    } else {
      createMutation.mutate({
        title,
        url: formUrl,
        category: formCategory,
      })
    }
  }
  
  const handleEdit = (bookmark: Bookmark) => {
    setEditingBookmark(bookmark)
    setFormUrl(bookmark.url)
    setFormTitle(bookmark.title)
    setFormCategory(bookmark.category || '常用')
    setShowAddModal(true)
  }
  
  // 过滤书签
  const filteredBookmarks = bookmarks.filter((bookmark) => {
    const matchesSearch = 
      bookmark.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bookmark.url.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = selectedCategory === '全部' || bookmark.category === selectedCategory
    return matchesSearch && matchesCategory
  })
  
  // 获取实际存在的分类
  const existingCategories = ['全部', ...new Set(bookmarks.map(b => b.category).filter(Boolean))]
  const allCategories = [...new Set([...existingCategories, ...defaultCategories])]
  
  // 获取网站图标
  const getFavicon = (url: string) => {
    try {
      const urlObj = new URL(url)
      return `https://www.google.com/s2/favicons?domain=${urlObj.hostname}&sz=32`
    } catch {
      return null
    }
  }
  
  return (
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-theme-text">网址收藏</h1>
          <p className="text-theme-muted mt-1">收藏常用的网址，快速访问</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          添加书签
        </button>
      </div>
      
      {/* 搜索和分类 */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-theme-muted" />
          <input
            type="text"
            placeholder="搜索书签..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10"
          />
        </div>
        
        <div className="flex gap-2 flex-wrap">
          {allCategories.slice(0, 8).map((category) => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm transition-colors',
                selectedCategory === category
                  ? 'bg-theme-primary text-theme-bg'
                  : 'bg-theme-card text-theme-muted hover:text-theme-text'
              )}
            >
              {category}
            </button>
          ))}
        </div>
      </div>
      
      {/* 书签列表 */}
      {isLoading ? (
        <div className="text-center py-12 text-theme-muted">加载中...</div>
      ) : filteredBookmarks.length === 0 ? (
        <div className="text-center py-12">
          <Globe className="w-12 h-12 text-theme-muted mx-auto mb-4" />
          <p className="text-theme-muted">
            {searchQuery ? '没有找到匹配的书签' : '暂无书签，点击上方按钮添加'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredBookmarks.map((bookmark) => (
            <div
              key={bookmark.id}
              className="card group hover:border-theme-primary/50 transition-colors"
            >
              <div className="flex items-start gap-3">
                {/* 图标 */}
                <div className="w-10 h-10 rounded-lg bg-theme-bg flex items-center justify-center flex-shrink-0">
                  {getFavicon(bookmark.url) ? (
                    <img
                      src={getFavicon(bookmark.url)!}
                      alt=""
                      className="w-5 h-5"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <Globe className="w-5 h-5 text-theme-muted" />
                  )}
                </div>
                
                {/* 内容 */}
                <div className="flex-1 min-w-0">
                  <a
                    href={bookmark.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-theme-text hover:text-theme-primary transition-colors line-clamp-1 flex items-center gap-1"
                  >
                    {bookmark.title}
                    <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </a>
                  <p className="text-xs text-theme-muted mt-1 line-clamp-1">
                    {bookmark.url}
                  </p>
                  {bookmark.category && (
                    <span className="inline-block mt-2 px-2 py-0.5 bg-theme-bg text-theme-muted text-xs rounded">
                      {bookmark.category}
                    </span>
                  )}
                </div>
              </div>
              
              {/* 操作按钮 */}
              <div className="flex items-center gap-1 mt-3 pt-3 border-t border-theme-border opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(bookmark.url)
                      toast.success('已复制到剪贴板')
                    } catch {
                      toast.error('复制失败')
                    }
                  }}
                  className="p-1.5 rounded text-theme-muted hover:text-theme-secondary hover:bg-theme-bg transition-colors"
                  title="复制链接"
                >
                  <Copy className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEdit(bookmark)}
                  className="p-1.5 rounded text-theme-muted hover:text-theme-primary hover:bg-theme-bg transition-colors"
                  title="编辑"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => {
                    if (confirm('确定删除这个书签吗？')) {
                      deleteMutation.mutate(bookmark.id)
                    }
                  }}
                  className="p-1.5 rounded text-theme-muted hover:text-theme-danger hover:bg-theme-bg transition-colors"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* 添加/编辑弹窗 */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-md p-6 animate-fadeIn">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold">
                {editingBookmark ? '编辑书签' : '添加书签'}
              </h2>
              <button
                onClick={resetForm}
                className="p-1 rounded hover:bg-theme-bg transition-colors"
              >
                <X className="w-5 h-5 text-theme-muted" />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* URL 输入 */}
              <div>
                <label className="block text-sm text-theme-muted mb-2">网址 *</label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-muted" />
                    <input
                      type="url"
                      placeholder="https://example.com"
                      value={formUrl}
                      onChange={(e) => handleUrlChange(e.target.value)}
                      onBlur={() => {
                        // 失去焦点时，如果标题为空则获取
                        if (formUrl && !formTitle) {
                          fetchUrlMeta(formUrl)
                        }
                      }}
                      className="w-full pl-10"
                      autoFocus
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => fetchUrlMeta(formUrl)}
                    disabled={!formUrl || isLoadingMeta}
                    className="btn btn-ghost px-3 flex items-center gap-1.5"
                    title="获取网站信息"
                  >
                    {isLoadingMeta ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Globe className="w-4 h-4" />
                    )}
                    获取
                  </button>
                </div>
                <p className="text-xs text-theme-muted mt-1">
                  输入网址后点击「获取」自动填充标题
                </p>
              </div>
              
              {/* 标题输入 */}
              <div>
                <label className="block text-sm text-theme-muted mb-2">标题</label>
                <input
                  type="text"
                  placeholder="网站标题（自动获取或手动输入）"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full"
                />
              </div>
              
              {/* 分类选择 */}
              <div>
                <label className="block text-sm text-theme-muted mb-2">分类</label>
                <div className="flex flex-wrap gap-2">
                  {defaultCategories.slice(1).map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setFormCategory(category)}
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-sm transition-colors',
                        formCategory === category
                          ? 'bg-theme-primary text-theme-bg'
                          : 'bg-theme-bg text-theme-muted hover:text-theme-text'
                      )}
                    >
                      {category}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            
            {/* 按钮 */}
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={resetForm} className="btn btn-ghost">
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={createMutation.isPending || updateMutation.isPending}
                className="btn btn-primary flex items-center gap-2"
              >
                {(createMutation.isPending || updateMutation.isPending) ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {editingBookmark ? '保存' : '添加'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

