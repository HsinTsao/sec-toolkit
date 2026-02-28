/**
 * AgentConfigPanel - Agent 配置面板
 * 
 * 提供以下配置功能：
 * - System Prompt 编辑
 * - Skill 管理
 * - Agent 参数调整
 */
import { useState, useEffect } from 'react'
import { 
  Settings2, 
  Save, 
  RotateCcw, 
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Sliders,
  Puzzle,
  Loader2,
  Sparkles,
  Plus,
  Edit3,
  Trash2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { useSkillStore, type Skill, type SkillCreateData } from '@/stores/skillStore'
import { useMemoryStore, MEMORY_CATEGORIES } from '@/stores/memoryStore'
import toast from 'react-hot-toast'

interface AgentConfig {
  system_prompt: string | null
  system_prompt_enabled: boolean
  modules_config: Record<string, { enabled: boolean; [key: string]: unknown }>
  temperature: string
  max_tokens: string
  default_system_prompt: string
}

interface AgentConfigPanelProps {
  isOpen: boolean
  onClose: () => void
}

export function AgentConfigPanel({ isOpen, onClose }: AgentConfigPanelProps) {
  const { token } = useAuthStore()
  const [config, setConfig] = useState<AgentConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // 本地编辑状态
  const [systemPrompt, setSystemPrompt] = useState('')
  const [systemPromptEnabled, setSystemPromptEnabled] = useState(false)
  const [temperature, setTemperature] = useState('0.7')
  const [maxTokens, setMaxTokens] = useState('2048')
  
  // 展开状态
  const [expandedSections, setExpandedSections] = useState({
    skills: true,
    memory: false,
    systemPrompt: false,
    params: false,
    modules: false,
  })
  
  // 记忆管理状态
  const {
    memories,
    stats: memoryStats,
    loading: memoryLoading,
    loadMemories,
    loadStats: loadMemoryStats,
    deleteMemory,
    clearMemories,
  } = useMemoryStore()
  const [memoryFilter, setMemoryFilter] = useState('all')
  const [memorySearch, _setMemorySearch] = useState('')
  
  // Skill 管理状态
  const {
    builtinSkills,
    customSkills,
    loadSkills,
    getSkillDetail,
    createSkill,
    updateSkill,
    deleteSkill,
  } = useSkillStore()
  const [skillView, setSkillView] = useState<'list' | 'create' | 'edit'>('list')
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null)
  const [skillForm, setSkillForm] = useState<SkillCreateData>({
    name: '',
    description: '',
    icon: '🤖',
    category: 'custom',
    system_prompt: '',
    tools: [],
    welcome_message: '',
    example_prompts: [],
    max_tool_calls: 10,
  })
  const [exampleInput, setExampleInput] = useState('')
  
  // 加载配置
  useEffect(() => {
    if (isOpen && token) {
      loadConfig()
      loadSkills()
      loadMemories()
      loadMemoryStats()
    }
  }, [isOpen, token, loadSkills, loadMemories, loadMemoryStats])
  
  const loadConfig = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/agent/config', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (response.ok) {
        const data: AgentConfig = await response.json()
        setConfig(data)
        setSystemPrompt(data.system_prompt || data.default_system_prompt)
        setSystemPromptEnabled(data.system_prompt_enabled)
        setTemperature(data.temperature)
        setMaxTokens(data.max_tokens)
      }
    } catch (error) {
      console.error('Failed to load agent config:', error)
      toast.error('加载配置失败')
    } finally {
      setLoading(false)
    }
  }
  
  const saveSystemPrompt = async () => {
    setSaving(true)
    try {
      const response = await fetch('/api/agent/system-prompt', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          system_prompt: systemPrompt,
          enabled: systemPromptEnabled,
        }),
      })
      
      if (response.ok) {
        toast.success('System Prompt 已保存')
      } else {
        throw new Error('保存失败')
      }
    } catch (error) {
      toast.error('保存失败')
    } finally {
      setSaving(false)
    }
  }
  
  const saveParams = async () => {
    setSaving(true)
    try {
      const response = await fetch('/api/agent/params', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          temperature,
          max_tokens: maxTokens,
        }),
      })
      
      if (response.ok) {
        toast.success('参数已保存')
      } else {
        const error = await response.json()
        throw new Error(error.detail || '保存失败')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }
  
  const resetConfig = async () => {
    if (!confirm('确定要重置所有配置吗？')) return
    
    setSaving(true)
    try {
      const response = await fetch('/api/agent/reset', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      if (response.ok) {
        toast.success('配置已重置')
        loadConfig()
      }
    } catch (error) {
      toast.error('重置失败')
    } finally {
      setSaving(false)
    }
  }
  
  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }
  
  // Skill 相关函数
  const resetSkillForm = () => {
    setSkillForm({
      name: '',
      description: '',
      icon: '🤖',
      category: 'custom',
      system_prompt: '',
      tools: [],
      welcome_message: '',
      example_prompts: [],
      max_tool_calls: 10,
    })
    setExampleInput('')
  }
  
  const handleCreateSkill = () => {
    resetSkillForm()
    setSkillView('create')
  }
  
  const handleEditSkill = async (skillId: string) => {
    const skill = await getSkillDetail(skillId)
    if (skill) {
      setEditingSkill(skill)
      setSkillForm({
        name: skill.name,
        description: skill.description,
        icon: skill.icon,
        category: skill.category,
        system_prompt: skill.system_prompt,
        tools: skill.tools,
        welcome_message: skill.welcome_message,
        example_prompts: skill.example_prompts,
        max_tool_calls: skill.max_tool_calls,
      })
      setSkillView('edit')
    }
  }
  
  const handleDeleteSkill = async (skillId: string, skillName: string) => {
    if (!confirm(`确定要删除 "${skillName}" 吗？`)) return
    try {
      await deleteSkill(skillId)
      toast.success('删除成功')
    } catch (error) {
      toast.error((error as Error).message)
    }
  }
  
  const handleSaveSkill = async () => {
    if (!skillForm.name.trim()) {
      toast.error('请输入 Skill 名称')
      return
    }
    if (!skillForm.system_prompt.trim()) {
      toast.error('请输入 System Prompt')
      return
    }
    
    setSaving(true)
    try {
      if (skillView === 'create') {
        await createSkill(skillForm)
        toast.success('创建成功')
      } else if (editingSkill) {
        await updateSkill(editingSkill.id, skillForm)
        toast.success('保存成功')
      }
      setSkillView('list')
      resetSkillForm()
    } catch (error) {
      toast.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }
  
  const addSkillExample = () => {
    if (exampleInput.trim()) {
      setSkillForm({ ...skillForm, example_prompts: [...skillForm.example_prompts, exampleInput.trim()] })
      setExampleInput('')
    }
  }
  
  const removeSkillExample = (index: number) => {
    setSkillForm({
      ...skillForm,
      example_prompts: skillForm.example_prompts.filter((_, i) => i !== index),
    })
  }
  
  // 常用 emoji 图标
  const SKILL_ICONS = ['🤖', '📈', '🔒', '🔤', '🔍', '💡', '🎯', '⚡', '🔧', '📊', '🌐', '📝']
  
  // 分类选项
  const SKILL_CATEGORIES = [
    { id: 'finance', name: '金融分析', icon: '📈' },
    { id: 'security', name: '安全检测', icon: '🔒' },
    { id: 'encoding', name: '编码解码', icon: '🔤' },
    { id: 'search', name: '搜索查询', icon: '🔍' },
    { id: 'custom', name: '自定义', icon: '⚙️' },
  ]
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[150] p-4">
      <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col animate-fadeIn">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-theme-border">
          <div className="flex items-center gap-2">
            <Settings2 className="w-5 h-5 text-theme-primary" />
            <h2 className="text-lg font-semibold text-theme-text">AI 助手配置</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-theme-hover rounded"
          >
            <span className="text-theme-text-secondary">&times;</span>
          </button>
        </div>
        
        {/* 内容 */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-theme-primary" />
            </div>
          ) : (
            <>
              {/* Skill 管理区域 */}
              <div className="border border-theme-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection('skills')}
                  className="w-full flex items-center justify-between px-4 py-3 bg-theme-bg hover:bg-theme-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-theme-primary" />
                    <span className="font-medium text-theme-text">Skill 管理</span>
                    <span className="text-xs bg-theme-primary/20 text-theme-primary px-2 py-0.5 rounded">
                      {builtinSkills.length + customSkills.length} 个
                    </span>
                  </div>
                  {expandedSections.skills ? (
                    <ChevronDown className="w-4 h-4 text-theme-text-secondary" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-theme-text-secondary" />
                  )}
                </button>
                
                {expandedSections.skills && (
                  <div className="p-4">
                    {skillView === 'list' ? (
                      <div className="space-y-4">
                        {/* 预置 Skill */}
                        <div>
                          <h4 className="text-xs font-medium text-theme-text-secondary mb-2">预置 Skill</h4>
                          <div className="grid grid-cols-2 gap-2">
                            {builtinSkills.map(skill => (
                              <div
                                key={skill.id}
                                className="flex items-center gap-2 p-2 bg-theme-bg rounded-lg"
                              >
                                <span className="text-lg">{skill.icon}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm font-medium text-theme-text truncate">{skill.name}</div>
                                  <div className="text-xs text-theme-text-secondary">{skill.tools_count} 工具</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        
                        {/* 自定义 Skill */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-medium text-theme-text-secondary">我的 Skill</h4>
                            <button
                              onClick={handleCreateSkill}
                              className="btn btn-primary btn-sm flex items-center gap-1"
                            >
                              <Plus className="w-3 h-3" />
                              新建
                            </button>
                          </div>
                          {customSkills.length === 0 ? (
                            <p className="text-sm text-theme-text-secondary text-center py-4">
                              还没有自定义 Skill，点击上方按钮创建
                            </p>
                          ) : (
                            <div className="space-y-2">
                              {customSkills.map(skill => (
                                <div
                                  key={skill.id}
                                  className="flex items-center gap-2 p-2 bg-theme-bg rounded-lg"
                                >
                                  <span className="text-lg">{skill.icon}</span>
                                  <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-theme-text truncate">{skill.name}</div>
                                    <div className="text-xs text-theme-text-secondary truncate">{skill.description}</div>
                                  </div>
                                  <button
                                    onClick={() => handleEditSkill(skill.id)}
                                    className="p-1.5 hover:bg-theme-hover rounded text-theme-text-secondary hover:text-theme-text"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteSkill(skill.id, skill.name)}
                                    className="p-1.5 hover:bg-red-500/10 rounded text-theme-text-secondary hover:text-red-500"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      /* 创建/编辑 Skill 表单 */
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-medium text-theme-text">
                            {skillView === 'create' ? '新建 Skill' : '编辑 Skill'}
                          </h4>
                          <button
                            onClick={() => { setSkillView('list'); resetSkillForm(); }}
                            className="text-xs text-theme-text-secondary hover:text-theme-text"
                          >
                            返回列表
                          </button>
                        </div>
                        
                        {/* 名称和图标 */}
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-theme-text-secondary mb-1">名称 *</label>
                            <input
                              type="text"
                              value={skillForm.name}
                              onChange={(e) => setSkillForm({ ...skillForm, name: e.target.value })}
                              className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded-lg"
                              placeholder="如：代码审计专家"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-theme-text-secondary mb-1">图标</label>
                            <div className="flex flex-wrap gap-1">
                              {SKILL_ICONS.map(icon => (
                                <button
                                  key={icon}
                                  onClick={() => setSkillForm({ ...skillForm, icon })}
                                  className={cn(
                                    'w-7 h-7 rounded flex items-center justify-center',
                                    skillForm.icon === icon
                                      ? 'bg-theme-primary/20 ring-1 ring-theme-primary'
                                      : 'hover:bg-theme-hover'
                                  )}
                                >
                                  {icon}
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                        
                        {/* 描述 */}
                        <div>
                          <label className="block text-xs text-theme-text-secondary mb-1">描述</label>
                          <input
                            type="text"
                            value={skillForm.description}
                            onChange={(e) => setSkillForm({ ...skillForm, description: e.target.value })}
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded-lg"
                            placeholder="简短描述这个 Skill 的功能"
                          />
                        </div>
                        
                        {/* 分类 */}
                        <div>
                          <label className="block text-xs text-theme-text-secondary mb-1">分类</label>
                          <div className="flex flex-wrap gap-2">
                            {SKILL_CATEGORIES.map(cat => (
                              <button
                                key={cat.id}
                                onClick={() => setSkillForm({ ...skillForm, category: cat.id })}
                                className={cn(
                                  'px-2 py-1 rounded text-xs flex items-center gap-1',
                                  skillForm.category === cat.id
                                    ? 'bg-theme-primary/20 text-theme-primary'
                                    : 'bg-theme-bg text-theme-text-secondary hover:text-theme-text'
                                )}
                              >
                                <span>{cat.icon}</span>
                                {cat.name}
                              </button>
                            ))}
                          </div>
                        </div>
                        
                        {/* System Prompt */}
                        <div>
                          <label className="block text-xs text-theme-text-secondary mb-1">
                            System Prompt * <span className="text-theme-text-secondary/60">（角色设定）</span>
                          </label>
                          <textarea
                            value={skillForm.system_prompt}
                            onChange={(e) => setSkillForm({ ...skillForm, system_prompt: e.target.value })}
                            className="w-full h-24 px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded-lg resize-none"
                            placeholder="定义 AI 的角色和行为方式..."
                          />
                        </div>
                        
                        {/* 欢迎语 */}
                        <div>
                          <label className="block text-xs text-theme-text-secondary mb-1">欢迎语</label>
                          <input
                            type="text"
                            value={skillForm.welcome_message}
                            onChange={(e) => setSkillForm({ ...skillForm, welcome_message: e.target.value })}
                            className="w-full px-3 py-2 text-sm bg-theme-bg border border-theme-border rounded-lg"
                            placeholder="激活 Skill 后显示的欢迎消息"
                          />
                        </div>
                        
                        {/* 示例提问 */}
                        <div>
                          <label className="block text-xs text-theme-text-secondary mb-1">示例提问</label>
                          <div className="flex gap-2 mb-2">
                            <input
                              type="text"
                              value={exampleInput}
                              onChange={(e) => setExampleInput(e.target.value)}
                              onKeyDown={(e) => e.key === 'Enter' && addSkillExample()}
                              className="flex-1 px-3 py-1.5 text-sm bg-theme-bg border border-theme-border rounded-lg"
                              placeholder="输入示例，按 Enter 添加"
                            />
                            <button onClick={addSkillExample} className="btn btn-ghost btn-sm">
                              <Plus className="w-4 h-4" />
                            </button>
                          </div>
                          {skillForm.example_prompts.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {skillForm.example_prompts.map((prompt, i) => (
                                <span
                                  key={i}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-theme-bg rounded text-xs"
                                >
                                  {prompt}
                                  <button
                                    onClick={() => removeSkillExample(i)}
                                    className="text-theme-text-secondary hover:text-red-500"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        
                        {/* 保存按钮 */}
                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            onClick={() => { setSkillView('list'); resetSkillForm(); }}
                            className="btn btn-ghost text-sm"
                          >
                            取消
                          </button>
                          <button
                            onClick={handleSaveSkill}
                            disabled={saving}
                            className="btn btn-primary text-sm"
                          >
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            保存
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              {/* 长期记忆区域 */}
              <div className="border border-theme-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection('memory')}
                  className="w-full flex items-center justify-between px-4 py-3 bg-theme-bg hover:bg-theme-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-base">🧠</span>
                    <span className="font-medium text-theme-text">长期记忆</span>
                    {memoryStats && memoryStats.total > 0 && (
                      <span className="text-xs bg-emerald-500/20 text-emerald-500 px-2 py-0.5 rounded">
                        {memoryStats.total} 条
                      </span>
                    )}
                  </div>
                  {expandedSections.memory ? (
                    <ChevronDown className="w-4 h-4 text-theme-text-secondary" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-theme-text-secondary" />
                  )}
                </button>
                
                {expandedSections.memory && (
                  <div className="p-4 space-y-4">
                    {/* 说明 */}
                    <p className="text-xs text-theme-text-secondary">
                      AI 会记住你说的重要信息。当你说"记住..."、"以后..."时，AI 会自动保存。
                    </p>
                    
                    {/* 分类筛选 */}
                    <div className="flex flex-wrap gap-1">
                      {MEMORY_CATEGORIES.map(cat => (
                        <button
                          key={cat.id}
                          onClick={() => {
                            setMemoryFilter(cat.id)
                            loadMemories(cat.id === 'all' ? undefined : cat.id, memorySearch || undefined)
                          }}
                          className={cn(
                            'px-2 py-1 rounded text-xs flex items-center gap-1',
                            memoryFilter === cat.id
                              ? 'bg-emerald-500/20 text-emerald-500'
                              : 'bg-theme-bg text-theme-text-secondary hover:text-theme-text'
                          )}
                        >
                          <span>{cat.icon}</span>
                          {cat.name}
                          {memoryStats?.by_category[cat.id] && (
                            <span className="text-[10px] opacity-60">({memoryStats.by_category[cat.id]})</span>
                          )}
                        </button>
                      ))}
                    </div>
                    
                    {/* 记忆列表 */}
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {memoryLoading ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="w-4 h-4 animate-spin text-theme-primary" />
                        </div>
                      ) : memories.length === 0 ? (
                        <p className="text-sm text-theme-text-secondary text-center py-4">
                          还没有任何记忆
                        </p>
                      ) : (
                        memories.map(mem => (
                          <div
                            key={mem.id}
                            className="flex items-start gap-2 p-2 bg-theme-bg rounded-lg group"
                          >
                            <span className="text-base mt-0.5">
                              {MEMORY_CATEGORIES.find(c => c.id === mem.category)?.icon || '💭'}
                            </span>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-theme-text">{mem.content}</p>
                              <p className="text-[10px] text-theme-text-secondary mt-1">
                                {new Date(mem.created_at).toLocaleDateString('zh-CN')}
                              </p>
                            </div>
                            <button
                              onClick={async () => {
                                if (confirm('确定要删除这条记忆吗？')) {
                                  try {
                                    await deleteMemory(mem.id)
                                    toast.success('已删除')
                                  } catch {
                                    toast.error('删除失败')
                                  }
                                }
                              }}
                              className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-500/10 rounded text-theme-text-secondary hover:text-red-500 transition-opacity"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    
                    {/* 清空按钮 */}
                    {memories.length > 0 && (
                      <div className="flex justify-end">
                        <button
                          onClick={async () => {
                            if (confirm('确定要清空所有记忆吗？此操作不可恢复。')) {
                              try {
                                await clearMemories()
                                toast.success('已清空')
                              } catch {
                                toast.error('清空失败')
                              }
                            }
                          }}
                          className="text-xs text-red-500 hover:text-red-600"
                        >
                          清空全部
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              {/* System Prompt 区域 */}
              <div className="border border-theme-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection('systemPrompt')}
                  className="w-full flex items-center justify-between px-4 py-3 bg-theme-bg hover:bg-theme-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-purple-500" />
                    <span className="font-medium text-theme-text">全局 System Prompt</span>
                    {systemPromptEnabled && (
                      <span className="text-xs bg-purple-500/20 text-purple-500 px-2 py-0.5 rounded">
                        自定义
                      </span>
                    )}
                  </div>
                  {expandedSections.systemPrompt ? (
                    <ChevronDown className="w-4 h-4 text-theme-text-secondary" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-theme-text-secondary" />
                  )}
                </button>
                
                {expandedSections.systemPrompt && (
                  <div className="p-4 space-y-4">
                    {/* 启用开关 */}
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={systemPromptEnabled}
                        onChange={(e) => setSystemPromptEnabled(e.target.checked)}
                        className="w-4 h-4 rounded border-theme-border text-theme-primary focus:ring-theme-primary"
                      />
                      <span className="text-sm text-theme-text">启用自定义 System Prompt</span>
                    </label>
                    
                    {/* 编辑器 */}
                    <textarea
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      placeholder="输入自定义的 System Prompt..."
                      className="w-full h-48 p-3 text-sm font-mono bg-theme-bg border border-theme-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
                      disabled={!systemPromptEnabled}
                    />
                    
                    {/* 提示 */}
                    <p className="text-xs text-theme-text-secondary">
                      {systemPromptEnabled 
                        ? '自定义 Prompt 将用于 AI 对话。修改后需要保存才能生效。'
                        : '启用后可以自定义 AI 的行为和风格。'
                      }
                    </p>
                    
                    {/* 保存按钮 */}
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setSystemPrompt(config?.default_system_prompt || '')}
                        className="btn btn-ghost text-sm"
                        disabled={saving}
                      >
                        恢复默认
                      </button>
                      <button
                        onClick={saveSystemPrompt}
                        disabled={saving}
                        className="btn btn-primary text-sm"
                      >
                        {saving ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                        保存
                      </button>
                    </div>
                  </div>
                )}
              </div>
              
              {/* 参数区域 */}
              <div className="border border-theme-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection('params')}
                  className="w-full flex items-center justify-between px-4 py-3 bg-theme-bg hover:bg-theme-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-blue-500" />
                    <span className="font-medium text-theme-text">生成参数</span>
                  </div>
                  {expandedSections.params ? (
                    <ChevronDown className="w-4 h-4 text-theme-text-secondary" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-theme-text-secondary" />
                  )}
                </button>
                
                {expandedSections.params && (
                  <div className="p-4 space-y-4">
                    {/* Temperature */}
                    <div>
                      <label className="block text-sm text-theme-text mb-2">
                        Temperature: {temperature}
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="0.1"
                        value={temperature}
                        onChange={(e) => setTemperature(e.target.value)}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-theme-text-secondary mt-1">
                        <span>精确 (0)</span>
                        <span>平衡 (1)</span>
                        <span>创意 (2)</span>
                      </div>
                    </div>
                    
                    {/* Max Tokens */}
                    <div>
                      <label className="block text-sm text-theme-text mb-2">
                        Max Tokens
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="32000"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(e.target.value)}
                        className="w-full px-3 py-2 bg-theme-bg border border-theme-border rounded-lg"
                      />
                    </div>
                    
                    {/* 保存按钮 */}
                    <div className="flex justify-end">
                      <button
                        onClick={saveParams}
                        disabled={saving}
                        className="btn btn-primary text-sm"
                      >
                        {saving ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                        保存
                      </button>
                    </div>
                  </div>
                )}
              </div>
              
              {/* 模块区域 */}
              <div className="border border-theme-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleSection('modules')}
                  className="w-full flex items-center justify-between px-4 py-3 bg-theme-bg hover:bg-theme-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Puzzle className="w-4 h-4 text-green-500" />
                    <span className="font-medium text-theme-text">模块配置</span>
                    <span className="text-xs text-theme-text-secondary">(即将推出)</span>
                  </div>
                  {expandedSections.modules ? (
                    <ChevronDown className="w-4 h-4 text-theme-text-secondary" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-theme-text-secondary" />
                  )}
                </button>
                
                {expandedSections.modules && (
                  <div className="p-4">
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { id: 'rag', name: 'RAG 检索', desc: '从知识库检索相关内容', status: 'coming' },
                        { id: 'mcp', name: 'MCP 协议', desc: '连接外部工具和数据源', status: 'coming' },
                        { id: 'workflow', name: '工作流', desc: '多步骤任务编排', status: 'coming' },
                        { id: 'agent_loop', name: 'Agent Loop', desc: '自主循环执行', status: 'coming' },
                      ].map(module => (
                        <div
                          key={module.id}
                          className="p-3 border border-theme-border rounded-lg opacity-50"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-theme-text">{module.name}</span>
                            <span className="text-xs text-theme-text-secondary">即将推出</span>
                          </div>
                          <p className="text-xs text-theme-text-secondary">{module.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
        
        {/* 底部 */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-theme-border">
          <button
            onClick={resetConfig}
            disabled={saving || loading}
            className="btn btn-ghost text-sm text-theme-danger"
          >
            <RotateCcw className="w-4 h-4" />
            重置全部
          </button>
          <button
            onClick={onClose}
            className="btn btn-primary"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  )
}

export default AgentConfigPanel
