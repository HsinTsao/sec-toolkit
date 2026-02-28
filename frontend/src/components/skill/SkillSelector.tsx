import { useState, useEffect, useRef } from 'react'
import { Sparkles, ChevronDown, X, Zap, Shield, Hash, Search, Settings, Wrench, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSkillStore, type SkillListItem } from '@/stores/skillStore'

const categoryIcons: Record<string, React.ReactNode> = {
  finance: <Zap className="w-3.5 h-3.5" />,
  security: <Shield className="w-3.5 h-3.5" />,
  encoding: <Hash className="w-3.5 h-3.5" />,
  search: <Search className="w-3.5 h-3.5" />,
  custom: <Settings className="w-3.5 h-3.5" />,
}

interface SkillSelectorProps {
  onSkillChange?: (skillIds: string[]) => void
  onManageClick?: () => void
}

export function SkillSelector({ onSkillChange, onManageClick }: SkillSelectorProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  
  const {
    builtinSkills,
    customSkills,
    activeSkillIds,
    activeSkills,
    loading,
    loadSkills,
    toggleSkill,
    isSkillActive,
    clearActiveSkills,
  } = useSkillStore()
  
  useEffect(() => { loadSkills() }, [loadSkills])
  
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  
  const handleToggle = async (skill: SkillListItem) => {
    await toggleSkill(skill.id)
    const newActiveIds = isSkillActive(skill.id)
      ? activeSkillIds.filter(id => id !== skill.id)
      : [...activeSkillIds, skill.id]
    onSkillChange?.(newActiveIds)
  }
  
  const doClearAll = () => {
    clearActiveSkills()
    onSkillChange?.([])
  }
  const handleClearAll = (e: React.MouseEvent) => {
    e.stopPropagation()
    doClearAll()
  }
  
  const allSkills = [...builtinSkills, ...customSkills]
  const activeCount = activeSkillIds.length
  
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all',
          activeCount > 0
            ? 'bg-theme-primary/10 text-theme-primary border border-theme-primary/30'
            : 'bg-theme-surface text-theme-muted hover:text-theme-text hover:bg-theme-surface-hover border border-theme-border'
        )}
      >
        {activeCount > 0 ? (
          <>
            <div className="flex -space-x-1">
              {activeSkills.slice(0, 3).map(skill => (
                <span key={skill.id} className="text-base">{skill.icon}</span>
              ))}
            </div>
            <span className="font-medium">
              {activeCount === 1 ? activeSkills[0].name : activeCount + ' 个 Skill'}
            </span>
            <span
              role="button"
              tabIndex={0}
              onClick={handleClearAll}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); doClearAll() } }}
              className="ml-1 p-0.5 rounded hover:bg-theme-surface-hover cursor-pointer inline-flex"
              title="清除全部"
            >
              <X className="w-3.5 h-3.5" />
            </span>
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            <span>激活 Skill</span>
            <ChevronDown className={cn('w-4 h-4 transition-transform', open && 'rotate-180')} />
          </>
        )}
      </button>
      
      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-80 bg-theme-card border border-theme-border rounded-xl shadow-2xl z-[100] overflow-hidden">
          <div className="px-3 py-2 bg-theme-surface-secondary border-b border-theme-border">
            <p className="text-xs text-theme-muted">激活后，AI 会根据对话内容智能选择是否使用</p>
          </div>
          
          {loading ? (
            <div className="p-4 text-center text-theme-muted">加载中...</div>
          ) : allSkills.length === 0 ? (
            <div className="p-4 text-center text-theme-muted">暂无可用 Skill</div>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              {builtinSkills.length > 0 && (
                <div>
                  <div className="px-3 py-2 text-xs font-medium text-theme-muted bg-theme-surface-secondary">预置 Skill</div>
                  {builtinSkills.map(skill => (
                    <SkillItem key={skill.id} skill={skill} active={isSkillActive(skill.id)} onClick={() => handleToggle(skill)} />
                  ))}
                </div>
              )}
              
              {customSkills.length > 0 && (
                <div>
                  <div className="px-3 py-2 text-xs font-medium text-theme-muted bg-theme-surface-secondary">我的 Skill</div>
                  {customSkills.map(skill => (
                    <SkillItem key={skill.id} skill={skill} active={isSkillActive(skill.id)} onClick={() => handleToggle(skill)} />
                  ))}
                </div>
              )}
              
              <div className="border-t border-theme-border">
                <button
                  onClick={() => { setOpen(false); onManageClick?.() }}
                  className="w-full px-3 py-2.5 flex items-center gap-2 text-sm text-theme-muted hover:text-theme-text hover:bg-theme-surface-hover transition-colors"
                >
                  <Wrench className="w-4 h-4" />
                  管理 Skill
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SkillItem({ skill, active, onClick }: { skill: SkillListItem; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn('w-full px-3 py-2.5 flex items-start gap-3 text-left transition-colors', active ? 'bg-theme-primary/10' : 'hover:bg-theme-surface-hover')}
    >
      <div className={cn('w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5', active ? 'bg-theme-primary border-theme-primary text-white' : 'border-theme-border')}>
        {active && <Check className="w-3 h-3" />}
      </div>
      <span className="text-xl flex-shrink-0">{skill.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('font-medium truncate', active ? 'text-theme-primary' : 'text-theme-text')}>{skill.name}</span>
          <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-theme-surface-secondary text-theme-muted">
            {categoryIcons[skill.category] || categoryIcons.custom}
            {skill.tools_count > 0 ? skill.tools_count + ' 工具' : '全部'}
          </span>
        </div>
        <p className="text-xs text-theme-muted truncate mt-0.5">{skill.description}</p>
      </div>
    </button>
  )
}

export function SkillWelcome() {
  const { activeSkills } = useSkillStore()
  if (activeSkills.length === 0) return null
  
  return (
    <div className="mb-4 p-4 bg-theme-primary/5 border border-theme-primary/20 rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex -space-x-1">
          {activeSkills.map(skill => (<span key={skill.id} className="text-xl">{skill.icon}</span>))}
        </div>
        <span className="font-medium text-theme-primary">
          {activeSkills.length === 1 ? activeSkills[0].name : activeSkills.length + ' 个 Skill 已激活'}
        </span>
      </div>
      {activeSkills.length === 1 && activeSkills[0].welcome_message && (
        <p className="text-sm text-theme-text">{activeSkills[0].welcome_message}</p>
      )}
      {activeSkills.length > 1 && (
        <p className="text-sm text-theme-text">AI 会根据对话内容智能选择最合适的 Skill</p>
      )}
      {activeSkills.length === 1 && activeSkills[0].example_prompts?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {activeSkills[0].example_prompts.map((prompt, i) => (
            <button key={i} className="px-3 py-1.5 text-xs bg-theme-surface rounded-lg hover:bg-theme-surface-hover text-theme-text">{prompt}</button>
          ))}
        </div>
      )}
    </div>
  )
}
