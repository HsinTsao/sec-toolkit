import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Folder, Trash2, Pin, Eye, Edit3, FolderPlus, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { notesApi } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import toast from 'react-hot-toast'

interface Note {
  id: string
  title: string
  content: string
  category_id?: string
  is_pinned: boolean
  is_encrypted: boolean
  created_at: string
  updated_at: string
  tags: { id: string; name: string; color: string }[]
}

interface Category {
  id: string
  name: string
  icon?: string
}

export default function NotesPage() {
  const queryClient = useQueryClient()
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [editingNote, setEditingNote] = useState<Note | null>(null)
  const [showEditor, setShowEditor] = useState(false)
  const [noteTitle, setNoteTitle] = useState('')
  const [noteContent, setNoteContent] = useState('')
  const [noteCategoryId, setNoteCategoryId] = useState<string | null>(null)
  const [isPreviewMode, setIsPreviewMode] = useState(false)
  const [showNewCategory, setShowNewCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  
  // 获取分类
  const { data: categories = [] } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: async () => {
      const { data } = await notesApi.getCategories()
      return data
    },
  })
  
  // 获取所有笔记（用于统计数量）
  const { data: allNotes = [] } = useQuery<Note[]>({
    queryKey: ['notes', 'all'],
    queryFn: async () => {
      const { data } = await notesApi.getNotes({})
      return data
    },
  })
  
  // 获取当前筛选的笔记
  const { data: notes = [], isLoading } = useQuery<Note[]>({
    queryKey: ['notes', selectedCategory, searchQuery],
    queryFn: async () => {
      const { data } = await notesApi.getNotes({
        category_id: selectedCategory || undefined,
        search: searchQuery || undefined,
      })
      return data
    },
  })
  
  // 计算每个分类的笔记数量
  const getCategoryCount = (categoryId: string | null) => {
    if (categoryId === null) {
      return allNotes.length
    }
    return allNotes.filter(note => note.category_id === categoryId).length
  }
  
  // 创建分类
  const createCategoryMutation = useMutation({
    mutationFn: async (name: string) => {
      const response = await notesApi.createCategory({ name })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      toast.success('分类创建成功')
      setShowNewCategory(false)
      setNewCategoryName('')
    },
    onError: () => toast.error('创建分类失败'),
  })
  
  // 删除分类
  const deleteCategoryMutation = useMutation({
    mutationFn: async (id: string) => {
      await notesApi.deleteCategory(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      if (selectedCategory) setSelectedCategory(null)
      toast.success('分类删除成功')
    },
    onError: () => toast.error('删除分类失败'),
  })
  
  // 创建笔记
  const createMutation = useMutation({
    mutationFn: async (data: { title: string; content: string; category_id?: string }) => {
      const response = await notesApi.createNote(data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('笔记创建成功')
      resetEditor()
    },
    onError: () => toast.error('创建失败'),
  })
  
  // 更新笔记
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { title?: string; content?: string; is_pinned?: boolean; category_id?: string | null } }) => {
      const response = await notesApi.updateNote(id, {
        ...data,
        category_id: data.category_id || undefined,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('已保存', { duration: 1500 })
    },
    onError: () => toast.error('更新失败'),
  })
  
  // 静默更新笔记（不关闭编辑器，用于自动保存场景）
  const silentUpdateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { title?: string; content?: string; is_pinned?: boolean; category_id?: string | null } }) => {
      const response = await notesApi.updateNote(id, {
        ...data,
        category_id: data.category_id || undefined,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('已保存', { duration: 1500 })
    },
    onError: () => toast.error('保存失败'),
  })
  
  // 删除笔记
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await notesApi.deleteNote(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('笔记删除成功')
    },
    onError: () => toast.error('删除失败'),
  })
  
  const resetEditor = () => {
    setShowEditor(false)
    setEditingNote(null)
    setNoteTitle('')
    setNoteContent('')
    setNoteCategoryId(null)
    setIsPreviewMode(false)
  }
  
  const handleEdit = (note: Note) => {
    setEditingNote(note)
    setNoteTitle(note.title)
    setNoteContent(note.content)
    setNoteCategoryId(note.category_id || null)
    setShowEditor(true)
  }
  
  const handleSave = () => {
    if (!noteTitle.trim()) {
      toast.error('请输入标题')
      return
    }
    
    if (editingNote) {
      updateMutation.mutate({
        id: editingNote.id,
        data: { 
          title: noteTitle, 
          content: noteContent,
          category_id: noteCategoryId || undefined,
        },
      })
    } else {
      createMutation.mutate({
        title: noteTitle,
        content: noteContent,
        category_id: noteCategoryId || selectedCategory || undefined,
      })
    }
  }
  
  const handleTogglePin = (note: Note) => {
    updateMutation.mutate({
      id: note.id,
      data: { is_pinned: !note.is_pinned },
    })
  }
  
  const handleCreateCategory = () => {
    if (!newCategoryName.trim()) {
      toast.error('请输入分类名称')
      return
    }
    createCategoryMutation.mutate(newCategoryName.trim())
  }
  
  return (
    <div className="h-full flex animate-fadeIn">
      {/* 左侧分类栏 */}
      <div className="w-64 bg-theme-card border-r border-theme-border p-4 flex-shrink-0 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">笔记</h2>
          <button
            onClick={() => setShowNewCategory(!showNewCategory)}
            className="p-1.5 rounded-lg hover:bg-theme-bg text-theme-muted hover:text-theme-primary transition-colors"
            title="新建分类"
          >
            <FolderPlus className="w-4 h-4" />
          </button>
        </div>
        
        {/* 新建分类输入框 */}
        {showNewCategory && (
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              placeholder="分类名称"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateCategory()}
              className="flex-1 px-2 py-1.5 text-sm"
              autoFocus
            />
            <button
              onClick={handleCreateCategory}
              disabled={createCategoryMutation.isPending}
              className="px-2 py-1.5 bg-theme-primary text-theme-bg rounded-lg text-sm hover:bg-theme-primary/80 disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                setShowNewCategory(false)
                setNewCategoryName('')
              }}
              className="px-2 py-1.5 bg-theme-bg text-theme-muted rounded-lg text-sm hover:text-theme-text"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        
        <div className="flex-1 overflow-y-auto">
          {/* 全部笔记 - 顶级项 */}
          <button
            onClick={() => setSelectedCategory(null)}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-colors font-medium',
              selectedCategory === null
                ? 'bg-theme-primary/20 text-theme-primary'
                : 'hover:bg-theme-bg text-theme-text'
            )}
          >
            <Folder className="w-4 h-4" />
            全部笔记
            <span className="ml-auto text-xs font-normal opacity-60">{getCategoryCount(null)}</span>
          </button>
          
          {/* 分类列表 - 子级项 */}
          {categories.length > 0 && (
            <div className="mt-3">
              <div className="px-3 py-1.5 text-xs text-theme-muted uppercase tracking-wider">
                分类
              </div>
              <div className="space-y-0.5 ml-2 border-l border-theme-border/50">
                {categories.map((category) => {
                  const count = getCategoryCount(category.id)
                  return (
                    <div
                      key={category.id}
                      className={cn(
                        'group flex items-center gap-2 pl-4 pr-3 py-2 rounded-r-lg transition-colors cursor-pointer',
                        selectedCategory === category.id
                          ? 'bg-theme-primary/20 text-theme-primary border-l-2 border-l-theme-primary -ml-[1px]'
                          : 'hover:bg-theme-bg text-theme-muted'
                      )}
                      onClick={() => setSelectedCategory(category.id)}
                    >
                      <Folder className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1 truncate text-sm">{category.name}</span>
                      <span className="text-xs opacity-60 group-hover:hidden">{count}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          if (confirm(`确定删除分类 "${category.name}" 吗？`)) {
                            deleteCategoryMutation.mutate(category.id)
                          }
                        }}
                        className="p-1 rounded hidden group-hover:block hover:bg-theme-danger/20 hover:text-theme-danger transition-all"
                        title="删除分类"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          
          {/* 无分类提示 */}
          {categories.length === 0 && (
            <div className="mt-4 px-3 text-xs text-theme-muted text-center">
              点击右上角 + 创建分类
            </div>
          )}
        </div>
      </div>
      
      {/* 中间笔记列表 */}
      <div className="w-80 border-r border-theme-border flex-shrink-0 flex flex-col">
        {/* 搜索和新建 */}
        <div className="p-4 border-b border-theme-border space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-muted" />
            <input
              type="text"
              placeholder="搜索笔记..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 py-2 text-sm"
            />
          </div>
          <button
            onClick={() => {
              resetEditor()
              setShowEditor(true)
            }}
            className="w-full btn btn-primary text-sm flex items-center justify-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            新建笔记
          </button>
        </div>
        
        {/* 笔记列表 */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-theme-muted">加载中...</div>
          ) : notes.length === 0 ? (
            <div className="p-4 text-center text-theme-muted">暂无笔记</div>
          ) : (
            notes.map((note) => {
              const isSelected = editingNote?.id === note.id
              return (
                <div
                  key={note.id}
                  onClick={() => handleEdit(note)}
                  className={cn(
                    'p-4 border-b border-theme-border cursor-pointer transition-all relative',
                    isSelected 
                      ? 'bg-theme-primary/10 border-l-2 border-l-theme-primary' 
                      : 'hover:bg-theme-bg border-l-2 border-l-transparent'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className={cn(
                      'font-medium text-sm line-clamp-1 flex-1 transition-colors',
                      isSelected && 'text-theme-primary'
                    )}>
                      {note.is_pinned && <Pin className="w-3 h-3 inline mr-1 text-theme-warning" />}
                      {note.title}
                    </h3>
                  </div>
                  <p className={cn(
                    'text-xs mt-1 line-clamp-2 transition-colors',
                    isSelected ? 'text-theme-text/70' : 'text-theme-muted'
                  )}>
                    {note.content || '无内容'}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-theme-muted">
                      {formatDate(note.updated_at)}
                    </span>
                    {note.tags.length > 0 && (
                      <div className="flex gap-1">
                        {note.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag.id}
                            className="px-1.5 py-0.5 text-xs rounded"
                            style={{ backgroundColor: tag.color + '20', color: tag.color }}
                          >
                            {tag.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
      
      {/* 右侧编辑区 */}
      <div className="flex-1 flex flex-col">
        {showEditor ? (
          <>
            {/* 工具栏 */}
            <div className="flex items-center justify-between p-4 border-b border-theme-border gap-4">
              <div className="flex-1 flex items-center gap-3">
                <input
                  type="text"
                  placeholder="笔记标题"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  className="text-xl font-semibold bg-transparent border-none outline-none flex-1 min-w-0"
                />
                {/* 分类选择 - 编辑已有笔记时自动保存 */}
                <select
                  value={noteCategoryId || ''}
                  onChange={(e) => {
                    const newCategoryId = e.target.value || null
                    setNoteCategoryId(newCategoryId)
                    // 如果是编辑已有笔记，静默保存分类变更（不关闭编辑器）
                    if (editingNote) {
                      silentUpdateMutation.mutate({
                        id: editingNote.id,
                        data: { category_id: newCategoryId },
                      })
                    }
                  }}
                  className="px-3 py-1.5 text-sm bg-theme-bg border border-theme-border rounded-lg text-theme-text min-w-[120px]"
                >
                  <option value="">无分类</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                {/* 编辑/预览切换 */}
                <div className="flex items-center bg-theme-bg rounded-lg p-1">
                  <button
                    onClick={() => setIsPreviewMode(false)}
                    className={cn(
                      'px-3 py-1.5 rounded-md text-sm flex items-center gap-1.5 transition-colors',
                      !isPreviewMode
                        ? 'bg-theme-primary text-theme-bg'
                        : 'text-theme-muted hover:text-theme-text'
                    )}
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    编辑
                  </button>
                  <button
                    onClick={() => setIsPreviewMode(true)}
                    className={cn(
                      'px-3 py-1.5 rounded-md text-sm flex items-center gap-1.5 transition-colors',
                      isPreviewMode
                        ? 'bg-theme-primary text-theme-bg'
                        : 'text-theme-muted hover:text-theme-text'
                    )}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    预览
                  </button>
                </div>
                
                {editingNote && (
                  <>
                    <button
                      onClick={() => handleTogglePin(editingNote)}
                      className={cn(
                        'p-2 rounded-lg transition-colors',
                        editingNote.is_pinned
                          ? 'text-theme-warning bg-theme-warning/10'
                          : 'text-theme-muted hover:text-theme-warning'
                      )}
                    >
                      <Pin className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('确定删除这条笔记吗？')) {
                          deleteMutation.mutate(editingNote.id)
                          resetEditor()
                        }
                      }}
                      className="p-2 rounded-lg text-theme-muted hover:text-theme-danger transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                )}
                <button onClick={resetEditor} className="btn btn-ghost text-sm">
                  取消
                </button>
                <button
                  onClick={handleSave}
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="btn btn-primary text-sm"
                >
                  保存
                </button>
              </div>
            </div>
            
            {/* 编辑器 / 预览 */}
            {isPreviewMode ? (
              <div className="flex-1 p-4 overflow-y-auto prose prose-invert prose-sm max-w-none">
                {noteContent ? (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ node, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match && !String(children).includes('\n')
                        return isInline ? (
                          <code className="px-1.5 py-0.5 bg-theme-border/50 rounded text-theme-text text-sm font-mono" {...props}>
                            {children}
                          </code>
                        ) : (
                          <SyntaxHighlighter
                            style={vscDarkPlus}
                            language={match ? match[1] : 'text'}
                            PreTag="div"
                            customStyle={{
                              margin: 0,
                              borderRadius: '0.5rem',
                              fontSize: '0.875rem',
                            }}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        )
                      },
                      h1: ({ children }) => <h1 className="text-2xl font-bold text-theme-primary mb-4">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-xl font-semibold text-theme-text mb-3 mt-6">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-lg font-medium text-theme-text mb-2 mt-4">{children}</h3>,
                      p: ({ children }) => <p className="text-theme-text mb-3 leading-relaxed">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>,
                      li: ({ children }) => <li className="text-theme-text">{children}</li>,
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-4 border-theme-primary pl-4 my-4 text-theme-muted italic">
                          {children}
                        </blockquote>
                      ),
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-theme-secondary hover:underline">
                          {children}
                        </a>
                      ),
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-4">
                          <table className="w-full border-collapse border border-theme-border">{children}</table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th className="border border-theme-border bg-theme-bg px-3 py-2 text-left font-semibold">{children}</th>
                      ),
                      td: ({ children }) => (
                        <td className="border border-theme-border px-3 py-2">{children}</td>
                      ),
                      hr: () => <hr className="border-theme-border my-6" />,
                    }}
                  >
                    {noteContent}
                  </ReactMarkdown>
                ) : (
                  <p className="text-theme-muted">暂无内容</p>
                )}
              </div>
            ) : (
              <textarea
                placeholder="支持 Markdown 语法...&#10;&#10;# 标题&#10;## 二级标题&#10;**粗体** *斜体*&#10;- 列表项&#10;```javascript&#10;代码块&#10;```"
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
                className="flex-1 p-4 bg-transparent border-none outline-none resize-none font-mono text-sm"
              />
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-theme-muted">
            选择或创建一个笔记开始编辑
          </div>
        )}
      </div>
    </div>
  )
}

