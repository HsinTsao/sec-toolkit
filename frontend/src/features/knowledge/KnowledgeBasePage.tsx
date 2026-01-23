import { useState, useEffect, useCallback } from 'react'
import {
  FileText,
  Link2,
  FileUp,
  RefreshCw,
  Trash2,
  Search,
  Check,
  X,
  Upload,
  Loader2,
  FileType,
  BookOpen,
  ToggleLeft,
  ToggleRight,
  Sparkles,
  Edit3,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import api from '@/lib/api'

interface KnowledgeItem {
  id: string
  source_type: 'note' | 'bookmark' | 'file'
  source_id: string
  title: string
  summary: string | null
  content_preview: string | null
  url: string | null
  is_enabled: boolean
  has_summary: boolean
  created_at: string
  updated_at: string
}

interface UploadedFile {
  id: string
  original_name: string
  file_type: string
  file_size: number
  note_id: string | null
  created_at: string
}

const SOURCE_TYPES = [
  { id: 'all', label: '全部', icon: BookOpen },
  { id: 'note', label: '笔记', icon: FileText },
  { id: 'bookmark', label: '书签', icon: Link2 },
  { id: 'file', label: '文件', icon: FileUp },
]

export default function KnowledgeBasePage() {
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [generatingSummary, setGeneratingSummary] = useState<Set<string>>(new Set())
  const [editingSummary, setEditingSummary] = useState<string | null>(null)
  const [editSummaryText, setEditSummaryText] = useState('')
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [batchGenerating, setBatchGenerating] = useState(false)
  
  // 加载知识库列表
  const loadItems = useCallback(async () => {
    try {
      const params = sourceFilter !== 'all' ? { source_type: sourceFilter } : {}
      const { data } = await api.get('/knowledge/items', { params })
      setItems(data)
    } catch (error) {
      console.error('加载知识库失败:', error)
      toast.error('加载知识库失败')
    }
  }, [sourceFilter])
  
  // 加载文件列表
  const loadFiles = useCallback(async () => {
    try {
      const { data } = await api.get('/knowledge/files')
      setFiles(data)
    } catch (error) {
      console.error('加载文件列表失败:', error)
    }
  }, [])
  
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.all([loadItems(), loadFiles()])
      setLoading(false)
    }
    load()
  }, [loadItems, loadFiles])
  
  // 同步知识库
  const handleSync = async () => {
    setSyncing(true)
    try {
      const { data } = await api.post('/knowledge/sync', {
        sync_notes: true,
        sync_bookmarks: true,
        sync_files: true,
      })
      toast.success(`同步完成: 新增 ${data.added}, 更新 ${data.updated}, 删除 ${data.removed}`)
      await loadItems()
    } catch (error) {
      console.error('同步失败:', error)
      toast.error('同步失败')
    } finally {
      setSyncing(false)
    }
  }
  
  // 切换启用状态
  const handleToggleEnabled = async (item: KnowledgeItem) => {
    try {
      await api.patch(`/knowledge/items/${item.id}`, {
        is_enabled: !item.is_enabled,
      })
      setItems(items.map(i => 
        i.id === item.id ? { ...i, is_enabled: !i.is_enabled } : i
      ))
      toast.success(item.is_enabled ? '已禁用' : '已启用')
    } catch (error) {
      console.error('更新失败:', error)
      toast.error('更新失败')
    }
  }
  
  // 删除知识条目
  const handleDelete = async (item: KnowledgeItem) => {
    if (!confirm(`确定要从知识库中移除「${item.title}」吗？`)) return
    
    try {
      await api.delete(`/knowledge/items/${item.id}`)
      setItems(items.filter(i => i.id !== item.id))
      toast.success('已移除')
    } catch (error) {
      console.error('删除失败:', error)
      toast.error('删除失败')
    }
  }
  
  // 生成单条摘要
  const handleGenerateSummary = async (item: KnowledgeItem) => {
    setGeneratingSummary(prev => new Set([...prev, item.id]))
    try {
      const { data } = await api.post('/knowledge/items/generate-summary', {
        item_ids: [item.id],
      })
      if (data.success > 0) {
        toast.success('摘要生成成功')
        await loadItems()
      } else {
        toast.error(data.results[0]?.error || '生成失败')
      }
    } catch (error: any) {
      console.error('生成摘要失败:', error)
      toast.error(error.response?.data?.detail || '生成摘要失败')
    } finally {
      setGeneratingSummary(prev => {
        const next = new Set(prev)
        next.delete(item.id)
        return next
      })
    }
  }
  
  // 批量生成摘要
  const handleBatchGenerateSummary = async () => {
    const itemIds = Array.from(selectedItems)
    if (itemIds.length === 0) {
      toast.error('请先选择要生成摘要的条目')
      return
    }
    
    setBatchGenerating(true)
    try {
      const { data } = await api.post('/knowledge/items/generate-summary', {
        item_ids: itemIds,
      })
      toast.success(`生成完成: 成功 ${data.success}, 失败 ${data.failed}`)
      await loadItems()
      setSelectedItems(new Set())
    } catch (error: any) {
      console.error('批量生成摘要失败:', error)
      toast.error(error.response?.data?.detail || '批量生成摘要失败')
    } finally {
      setBatchGenerating(false)
    }
  }
  
  // 开始编辑摘要
  const handleStartEditSummary = (item: KnowledgeItem) => {
    setEditingSummary(item.id)
    setEditSummaryText(item.summary || '')
  }
  
  // 保存摘要编辑
  const handleSaveSummary = async (itemId: string) => {
    try {
      await api.patch(`/knowledge/items/${itemId}`, {
        summary: editSummaryText,
      })
      setItems(items.map(i => 
        i.id === itemId 
          ? { ...i, summary: editSummaryText, has_summary: !!editSummaryText.trim() } 
          : i
      ))
      setEditingSummary(null)
      toast.success('摘要已保存')
    } catch (error) {
      console.error('保存摘要失败:', error)
      toast.error('保存摘要失败')
    }
  }
  
  // 取消编辑摘要
  const handleCancelEditSummary = () => {
    setEditingSummary(null)
    setEditSummaryText('')
  }
  
  // 切换展开状态
  const toggleExpanded = (itemId: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }
  
  // 切换选中状态
  const toggleSelected = (itemId: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }
  
  // 全选/取消全选
  const handleSelectAll = () => {
    if (selectedItems.size === filteredItems.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(filteredItems.map(i => i.id)))
    }
  }
  
  // 过滤后的列表
  const filteredItems = items.filter(item => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return item.title.toLowerCase().includes(query) ||
        (item.content_preview?.toLowerCase().includes(query))
    }
    return true
  })
  
  // 统计
  const stats = {
    total: items.length,
    enabled: items.filter(i => i.is_enabled).length,
    withSummary: items.filter(i => i.has_summary).length,
    notes: items.filter(i => i.source_type === 'note').length,
    bookmarks: items.filter(i => i.source_type === 'bookmark').length,
    files: items.filter(i => i.source_type === 'file').length,
  }
  
  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'note': return <FileText className="w-4 h-4 text-blue-400" />
      case 'bookmark': return <Link2 className="w-4 h-4 text-green-400" />
      case 'file': return <FileUp className="w-4 h-4 text-orange-400" />
      default: return <FileType className="w-4 h-4" />
    }
  }
  
  return (
    <div className="h-full flex flex-col animate-fadeIn">
      {/* 头部 */}
      <div className="flex-shrink-0 p-6 border-b border-theme-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-theme-text flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-theme-primary" />
              知识库管理
            </h1>
            <p className="text-theme-muted text-sm mt-1">
              管理 AI 对话时可引用的知识来源
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowUploadModal(true)}
              className="btn btn-outline flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              上传文件
            </button>
            <button
              onClick={handleSync}
              disabled={syncing}
              className="btn btn-primary flex items-center gap-2"
            >
              <RefreshCw className={cn('w-4 h-4', syncing && 'animate-spin')} />
              {syncing ? '同步中...' : '同步数据'}
            </button>
          </div>
        </div>
        
        {/* 统计 */}
        <div className="grid grid-cols-6 gap-4">
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-theme-text">{stats.total}</div>
            <div className="text-xs text-theme-muted">总条目</div>
          </div>
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-theme-success">{stats.enabled}</div>
            <div className="text-xs text-theme-muted">已启用</div>
          </div>
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-purple-400">{stats.withSummary}</div>
            <div className="text-xs text-theme-muted">有摘要</div>
          </div>
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-blue-400">{stats.notes}</div>
            <div className="text-xs text-theme-muted">笔记</div>
          </div>
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{stats.bookmarks}</div>
            <div className="text-xs text-theme-muted">书签</div>
          </div>
          <div className="bg-theme-bg rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-orange-400">{stats.files}</div>
            <div className="text-xs text-theme-muted">文件</div>
          </div>
        </div>
      </div>
      
      {/* 筛选和搜索 */}
      <div className="flex-shrink-0 p-4 border-b border-theme-border flex items-center gap-4">
        {/* 来源类型筛选 */}
        <div className="flex items-center gap-1 bg-theme-bg rounded-lg p-1">
          {SOURCE_TYPES.map(type => (
            <button
              key={type.id}
              onClick={() => setSourceFilter(type.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
                sourceFilter === type.id
                  ? 'bg-theme-primary text-theme-bg'
                  : 'text-theme-muted hover:text-theme-text'
              )}
            >
              <type.icon className="w-3.5 h-3.5" />
              {type.label}
            </button>
          ))}
        </div>
        
        {/* 搜索 */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索知识条目..."
            className="w-full pl-10 pr-4 py-2 bg-theme-bg border border-theme-border rounded-lg text-sm"
          />
        </div>
        
        {/* 批量操作 */}
        {selectedItems.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-theme-muted">
              已选 {selectedItems.size} 项
            </span>
            <button
              onClick={handleBatchGenerateSummary}
              disabled={batchGenerating}
              className="btn btn-sm bg-purple-500/20 text-purple-400 border-purple-500/30 hover:bg-purple-500/30"
            >
              {batchGenerating ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1" />
              )}
              批量生成摘要
            </button>
            <button
              onClick={() => setSelectedItems(new Set())}
              className="btn btn-sm btn-ghost"
            >
              取消选择
            </button>
          </div>
        )}
      </div>
      
      {/* 列表 */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-8 h-8 animate-spin text-theme-primary" />
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-theme-muted">
            <BookOpen className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg mb-2">知识库为空</p>
            <p className="text-sm">点击「同步数据」将笔记和书签添加到知识库</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* 全选按钮 */}
            <div className="flex items-center gap-2 mb-2">
              <button
                onClick={handleSelectAll}
                className="text-sm text-theme-muted hover:text-theme-text flex items-center gap-1"
              >
                {selectedItems.size === filteredItems.length && filteredItems.length > 0 ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <div className="w-4 h-4 border border-theme-border rounded" />
                )}
                {selectedItems.size === filteredItems.length && filteredItems.length > 0 ? '取消全选' : '全选'}
              </button>
            </div>
            
            {filteredItems.map(item => {
              const isExpanded = expandedItems.has(item.id)
              const isEditing = editingSummary === item.id
              const isGenerating = generatingSummary.has(item.id)
              const isSelected = selectedItems.has(item.id)
              
              return (
                <div
                  key={item.id}
                  className={cn(
                    'bg-theme-card border border-theme-border rounded-lg p-4 transition-colors',
                    !item.is_enabled && 'opacity-50',
                    isSelected && 'border-theme-primary'
                  )}
                >
                  <div className="flex items-start gap-3">
                    {/* 选择框 */}
                    <button
                      onClick={() => toggleSelected(item.id)}
                      className={cn(
                        'flex-shrink-0 w-5 h-5 rounded border transition-colors mt-1',
                        isSelected 
                          ? 'bg-theme-primary border-theme-primary text-white'
                          : 'border-theme-border hover:border-theme-primary'
                      )}
                    >
                      {isSelected && <Check className="w-4 h-4" />}
                    </button>
                    
                    {/* 来源图标 */}
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-theme-bg flex items-center justify-center">
                      {getSourceIcon(item.source_type)}
                    </div>
                    
                    {/* 内容 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-theme-text truncate">
                          {item.title}
                        </h3>
                        {item.has_summary && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400">
                            有摘要
                          </span>
                        )}
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-theme-primary hover:underline text-xs"
                          >
                            访问链接
                          </a>
                        )}
                      </div>
                      
                      {/* 摘要区域 */}
                      {isEditing ? (
                        <div className="mt-2">
                          <textarea
                            value={editSummaryText}
                            onChange={(e) => setEditSummaryText(e.target.value)}
                            className="w-full px-3 py-2 bg-theme-bg border border-theme-border rounded-lg text-sm resize-none"
                            rows={3}
                            placeholder="输入摘要..."
                          />
                          <div className="flex justify-end gap-2 mt-2">
                            <button
                              onClick={handleCancelEditSummary}
                              className="btn btn-sm btn-ghost"
                            >
                              取消
                            </button>
                            <button
                              onClick={() => handleSaveSummary(item.id)}
                              className="btn btn-sm btn-primary"
                            >
                              保存
                            </button>
                          </div>
                        </div>
                      ) : item.summary ? (
                        <div 
                          className="mt-2 p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg cursor-pointer"
                          onClick={() => toggleExpanded(item.id)}
                        >
                          <div className="flex items-start gap-2">
                            <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                            <p className={cn(
                              'text-sm text-theme-text',
                              !isExpanded && 'line-clamp-2'
                            )}>
                              {item.summary}
                            </p>
                          </div>
                          {item.summary.length > 100 && (
                            <div className="flex justify-end mt-1">
                              {isExpanded ? (
                                <ChevronUp className="w-4 h-4 text-theme-muted" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-theme-muted" />
                              )}
                            </div>
                          )}
                        </div>
                      ) : item.content_preview && (
                        <p className="text-sm text-theme-muted mt-1 line-clamp-2">
                          {item.content_preview}
                        </p>
                      )}
                      
                      <div className="flex items-center gap-3 mt-2 text-xs text-theme-muted">
                        <span>
                          {item.source_type === 'note' ? '📝 笔记' : 
                           item.source_type === 'bookmark' ? '🔗 书签' : '📄 文件'}
                        </span>
                        <span>
                          更新于 {new Date(item.updated_at).toLocaleDateString('zh-CN')}
                        </span>
                      </div>
                    </div>
                    
                    {/* 操作 */}
                    <div className="flex items-center gap-1">
                      {/* 生成/重新生成摘要 */}
                      <button
                        onClick={() => handleGenerateSummary(item)}
                        disabled={isGenerating}
                        className={cn(
                          'p-2 rounded-lg transition-colors',
                          isGenerating 
                            ? 'text-theme-muted cursor-wait'
                            : 'text-purple-400 hover:bg-purple-500/10'
                        )}
                        title={item.has_summary ? "重新生成摘要" : "生成 AI 摘要"}
                      >
                        {isGenerating ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4" />
                        )}
                      </button>
                      
                      {/* 编辑摘要（有摘要时显示） */}
                      {item.has_summary && (
                        <button
                          onClick={() => handleStartEditSummary(item)}
                          className="p-2 rounded-lg text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                          title="编辑摘要"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                      )}
                      
                      <button
                        onClick={() => handleToggleEnabled(item)}
                        className={cn(
                          'p-2 rounded-lg transition-colors',
                          item.is_enabled 
                            ? 'text-theme-success hover:bg-theme-success/10'
                            : 'text-theme-muted hover:bg-theme-bg'
                        )}
                        title={item.is_enabled ? '点击禁用' : '点击启用'}
                      >
                        {item.is_enabled ? (
                          <ToggleRight className="w-5 h-5" />
                        ) : (
                          <ToggleLeft className="w-5 h-5" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDelete(item)}
                        className="p-2 rounded-lg text-theme-muted hover:text-theme-danger hover:bg-theme-danger/10 transition-colors"
                        title="从知识库移除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
      
      {/* 文件上传弹窗 */}
      {showUploadModal && (
        <FileUploadModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            loadItems()
            loadFiles()
          }}
        />
      )}
    </div>
  )
}

// 文件上传弹窗
function FileUploadModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: () => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [autoAddKnowledge, setAutoAddKnowledge] = useState(true)
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const droppedFiles = Array.from(e.dataTransfer.files)
    addFiles(droppedFiles)
  }
  
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files))
    }
  }
  
  const addFiles = (newFiles: File[]) => {
    const validFiles = newFiles.filter(file => {
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (!['txt', 'md', 'pdf', 'docx'].includes(ext || '')) {
        toast.error(`不支持的文件类型: ${file.name}`)
        return false
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`文件过大: ${file.name}`)
        return false
      }
      return true
    })
    setFiles(prev => [...prev, ...validFiles])
  }
  
  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }
  
  const handleUpload = async () => {
    if (files.length === 0) return
    
    setUploading(true)
    let successCount = 0
    
    for (const file of files) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        
        await api.post(`/knowledge/files/upload?auto_add_knowledge=${autoAddKnowledge}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        successCount++
      } catch (error) {
        console.error('上传失败:', file.name, error)
        toast.error(`上传失败: ${file.name}`)
      }
    }
    
    setUploading(false)
    
    if (successCount > 0) {
      toast.success(`成功上传 ${successCount} 个文件`)
      onSuccess()
      onClose()
    }
  }
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-lg p-6 animate-fadeIn">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Upload className="w-5 h-5 text-theme-primary" />
            上传文件
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-theme-bg">
            <X className="w-5 h-5 text-theme-muted" />
          </button>
        </div>
        
        {/* 拖拽区域 */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-theme-border rounded-lg p-8 text-center hover:border-theme-primary/50 transition-colors cursor-pointer"
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <FileUp className="w-10 h-10 mx-auto text-theme-muted mb-3" />
          <p className="text-theme-text mb-1">拖拽文件到此处，或点击选择</p>
          <p className="text-xs text-theme-muted">支持: PDF, TXT, MD, DOCX (最大 10MB)</p>
          <input
            id="file-input"
            type="file"
            multiple
            accept=".txt,.md,.pdf,.docx"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
        
        {/* 已选文件列表 */}
        {files.length > 0 && (
          <div className="mt-4 space-y-2 max-h-40 overflow-y-auto">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between bg-theme-bg rounded-lg px-3 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileType className="w-4 h-4 text-theme-muted flex-shrink-0" />
                  <span className="text-sm truncate">{file.name}</span>
                  <span className="text-xs text-theme-muted flex-shrink-0">
                    ({formatFileSize(file.size)})
                  </span>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 text-theme-muted hover:text-theme-danger"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        
        {/* 选项 */}
        <label className="flex items-center gap-2 mt-4 cursor-pointer">
          <input
            type="checkbox"
            checked={autoAddKnowledge}
            onChange={(e) => setAutoAddKnowledge(e.target.checked)}
            className="rounded border-theme-border"
          />
          <span className="text-sm text-theme-text">上传后自动加入知识库索引</span>
        </label>
        
        {/* 按钮 */}
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn btn-ghost">
            取消
          </button>
          <button
            onClick={handleUpload}
            disabled={files.length === 0 || uploading}
            className="btn btn-primary"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                上传中...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4 mr-2" />
                上传 ({files.length})
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

