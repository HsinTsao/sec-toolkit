import { useState, useEffect, useCallback } from 'react'
import { 
  X,
  Loader2,
  RefreshCw,
  Edit3,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import { llmApi } from '@/lib/api'
import { useLLMStore } from '@/stores/llmStore'

export default function SettingsModal({
  onClose,
}: {
  onClose: () => void
}) {
  const { providers, config, updateConfig } = useLLMStore()
  
  const [defaultConfig, setDefaultConfig] = useState<{
    available: boolean
    provider_id: string | null
    provider_name?: string
    model: string | null
    models: string[]
  } | null>(null)
  
  const [formData, setFormData] = useState({
    provider_id: config?.provider_id || 'qwen',
    api_key: '',
    base_url: config?.base_url || '',
    model: config?.model || '',
    use_system_default: config?.use_system_default || false,
  })
  const [showApiKey, setShowApiKey] = useState(false)
  const [useCustomModel, setUseCustomModel] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [fetchedModels, setFetchedModels] = useState<string[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelsFetchError, setModelsFetchError] = useState<string | null>(null)
  
  const currentProvider = providers.find(p => p.id === formData.provider_id)
  
  useEffect(() => {
    const loadDefaultConfig = async () => {
      try {
        const { data } = await llmApi.getDefaultConfig()
        setDefaultConfig(data)
      } catch {
        setDefaultConfig({ available: false, provider_id: null, model: null, models: [] })
      }
    }
    loadDefaultConfig()
  }, [])
  
  useEffect(() => {
    if (config) {
      setFormData({
        provider_id: config.provider_id,
        api_key: '',
        base_url: config.base_url || '',
        model: config.model,
        use_system_default: config.use_system_default || false,
      })
    }
  }, [config])
  
  const availableModels = formData.use_system_default && defaultConfig?.available
    ? defaultConfig.models
    : [
        ...(currentProvider?.models || []),
        ...fetchedModels.filter(m => !currentProvider?.models.includes(m))
      ]
  
  const handleProviderChange = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId)
    if (provider) {
      setFormData({
        ...formData,
        provider_id: providerId,
        base_url: provider.base_url,
        model: provider.default_model,
      })
      setFetchedModels([])
      setModelsFetchError(null)
      setUseCustomModel(false)
    }
  }
  
  const fetchModels = useCallback(async () => {
    if (!formData.base_url) {
      toast.error('请先填写 API 地址')
      return
    }
    
    if (formData.provider_id !== 'ollama' && !formData.api_key && !config?.api_key_set) {
      toast.error('请先填写 API Key')
      return
    }
    
    setIsLoadingModels(true)
    setModelsFetchError(null)
    
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      
      const apiKey = formData.api_key || (config?.api_key_set ? 'SAVED' : '')
      if (apiKey && formData.provider_id !== 'ollama') {
        if (apiKey === 'SAVED') {
          toast.error('请输入新的 API Key 或使用后端代理')
          setIsLoadingModels(false)
          return
        }
        headers['Authorization'] = `Bearer ${apiKey}`
      }
      
      const response = await fetch(`${formData.base_url}/models`, { headers })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      let models: string[] = []
      if (Array.isArray(data)) {
        models = data.map((m: { name?: string; id?: string }) => m.name || m.id || '').filter(Boolean)
      } else if (data.data && Array.isArray(data.data)) {
        models = data.data.map((m: { id?: string; name?: string }) => m.id || m.name || '').filter(Boolean)
      } else if (data.models && Array.isArray(data.models)) {
        models = data.models.map((m: string | { id?: string; name?: string }) => 
          typeof m === 'string' ? m : (m.id || m.name || '')
        ).filter(Boolean)
      }
      
      if (models.length === 0) {
        setModelsFetchError('未获取到任何模型')
      } else {
        setFetchedModels(models)
        toast.success(`获取到 ${models.length} 个模型`)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取模型列表失败'
      setModelsFetchError(message)
      toast.error(message)
    } finally {
      setIsLoadingModels(false)
    }
  }, [formData.base_url, formData.api_key, formData.provider_id, config?.api_key_set])
  
  const handleSave = async () => {
    if (!formData.model) {
      toast.error('请选择模型')
      return
    }
    
    if (!formData.use_system_default && !config?.api_key_set && !formData.api_key && formData.provider_id !== 'ollama') {
      toast.error('请填写 API Key')
      return
    }
    
    setIsSaving(true)
    try {
      await updateConfig({
        provider_id: formData.use_system_default && defaultConfig?.provider_id ? defaultConfig.provider_id : formData.provider_id,
        api_key: formData.use_system_default ? undefined : (formData.api_key || undefined),
        base_url: formData.use_system_default ? undefined : formData.base_url,
        model: formData.model,
        use_system_default: formData.use_system_default,
      })
      toast.success('配置已保存')
      onClose()
    } catch {
      // 错误已在 store 中处理
    } finally {
      setIsSaving(false)
    }
  }
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[150] p-4">
      <div className="bg-theme-card border border-theme-border rounded-xl w-full max-w-lg p-6 animate-fadeIn max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">API 设置</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-theme-bg">
            <X className="w-5 h-5 text-theme-muted" />
          </button>
        </div>
        
        <div className="space-y-4">
          {defaultConfig?.available && (
            <div className="p-4 rounded-lg border border-theme-border bg-theme-bg/50">
              <label className="flex items-center justify-between cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">使用系统默认配置</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-theme-primary/20 text-theme-primary">
                      {defaultConfig.provider_name}
                    </span>
                  </div>
                  <p className="text-xs text-theme-muted mt-1">
                    使用管理员预配置的 API Key，无需自行设置
                  </p>
                </div>
                <div 
                  onClick={() => {
                    const useDefault = !formData.use_system_default
                    setFormData({
                      ...formData,
                      use_system_default: useDefault,
                      model: useDefault && defaultConfig?.model ? defaultConfig.model : formData.model,
                    })
                  }}
                  className={cn(
                    'w-12 h-6 rounded-full transition-colors cursor-pointer relative',
                    formData.use_system_default ? 'bg-theme-primary' : 'bg-theme-border'
                  )}
                >
                  <div className={cn(
                    'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                    formData.use_system_default ? 'translate-x-7' : 'translate-x-1'
                  )} />
                </div>
              </label>
            </div>
          )}
          
          <div className={formData.use_system_default ? 'opacity-50 pointer-events-none' : ''}>
            <label className="block text-sm text-theme-muted mb-2">选择服务商</label>
            <div className="grid grid-cols-2 gap-2">
              {providers.map(provider => (
                <button
                  key={provider.id}
                  onClick={() => handleProviderChange(provider.id)}
                  className={cn(
                    'p-3 rounded-lg border text-left transition-all',
                    formData.provider_id === provider.id
                      ? 'border-theme-primary bg-theme-primary/10'
                      : 'border-theme-border hover:border-theme-primary/50'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{provider.icon}</span>
                    <span className="font-medium text-sm">{provider.name}</span>
                  </div>
                  <p className="text-xs text-theme-muted mt-1">{provider.description}</p>
                </button>
              ))}
            </div>
          </div>
          
          {!formData.use_system_default && (
          <div>
            <label className="block text-sm text-theme-muted mb-2">
              API Key 
              {formData.provider_id === 'ollama' && ' (本地无需填写)'}
              {config?.api_key_set && (
                <span className="ml-2 text-xs text-theme-success">✓ 已保存</span>
              )}
            </label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.api_key}
                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                placeholder={
                  config?.api_key_set 
                    ? '已保存，留空保持不变' 
                    : (formData.provider_id === 'ollama' ? '本地部署无需 API Key' : 'sk-...')
                }
                className="w-full pr-20"
              />
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-theme-muted hover:text-theme-text"
              >
                {showApiKey ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          )}
          
          {!formData.use_system_default && (
          <div>
            <label className="block text-sm text-theme-muted mb-2">API 地址</label>
            <input
              type="text"
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              placeholder="https://api.example.com/v1"
              className="w-full"
            />
          </div>
          )}
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">模型</label>
              {!formData.use_system_default && (
              <div className="flex items-center gap-2">
                <button
                  onClick={fetchModels}
                  disabled={isLoadingModels}
                  className="flex items-center gap-1 text-xs text-theme-primary hover:text-theme-secondary transition-colors disabled:opacity-50"
                  title="从 API 获取可用模型列表"
                >
                  <RefreshCw className={cn('w-3 h-3', isLoadingModels && 'animate-spin')} />
                  获取模型
                </button>
                <span className="text-theme-border">|</span>
                <button
                  onClick={() => setUseCustomModel(!useCustomModel)}
                  className={cn(
                    'flex items-center gap-1 text-xs transition-colors',
                    useCustomModel ? 'text-theme-secondary' : 'text-theme-muted hover:text-theme-text'
                  )}
                  title="手动输入模型名称"
                >
                  <Edit3 className="w-3 h-3" />
                  手动输入
                </button>
              </div>
              )}
            </div>
            
            {useCustomModel ? (
              <input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="输入模型名称，如 gpt-4、llama3..."
                className="w-full"
              />
            ) : availableModels.length > 0 ? (
              <select
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                className="w-full"
              >
                {formData.use_system_default ? (
                  availableModels.map(model => (
                    <option key={model} value={model}>{model}</option>
                  ))
                ) : (
                  <>
                    {currentProvider && currentProvider.models.length > 0 && (
                      <optgroup label="推荐模型">
                        {currentProvider.models.map(model => (
                          <option key={model} value={model}>{model}</option>
                        ))}
                      </optgroup>
                    )}
                    {fetchedModels.length > 0 && (
                      <optgroup label="从 API 获取">
                        {fetchedModels
                          .filter(m => !currentProvider?.models.includes(m))
                          .map(model => (
                            <option key={model} value={model}>{model}</option>
                          ))
                        }
                      </optgroup>
                    )}
                  </>
                )}
              </select>
            ) : (
              <input
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                placeholder="输入模型名称"
                className="w-full"
              />
            )}
            
            {modelsFetchError && (
              <p className="text-xs text-theme-danger mt-1">{modelsFetchError}</p>
            )}
            {fetchedModels.length > 0 && !useCustomModel && (
              <p className="text-xs text-theme-muted mt-1">
                已加载 {fetchedModels.length} 个模型
              </p>
            )}
          </div>
        </div>
        
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="btn btn-ghost">
            取消
          </button>
          <button 
            onClick={handleSave} 
            disabled={isSaving}
            className="btn btn-primary"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                保存中...
              </>
            ) : (
              '保存配置'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
