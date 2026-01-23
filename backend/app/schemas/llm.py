"""LLM 相关 Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== LLM 提供商配置 ====================

class LLMProvider(BaseModel):
    """LLM 提供商信息"""
    id: str
    name: str
    base_url: str
    models: List[str]
    default_model: str
    description: str
    icon: str


# 预设的 LLM 提供商
LLM_PROVIDERS = [
    LLMProvider(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        default_model="gpt-4o-mini",
        description="OpenAI 官方 API",
        icon="🤖"
    ),
    LLMProvider(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        default_model="llama-3.3-70b-versatile",
        description="超快推理，免费额度",
        icon="⚡"
    ),
    LLMProvider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        models=["deepseek-chat", "deepseek-coder"],
        default_model="deepseek-chat",
        description="国产模型，价格低廉",
        icon="🔮"
    ),
    LLMProvider(
        id="siliconflow",
        name="硅基流动",
        base_url="https://api.siliconflow.cn/v1",
        models=["Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"],
        default_model="Qwen/Qwen2.5-7B-Instruct",
        description="国内平台，多模型支持",
        icon="🌊"
    ),
    LLMProvider(
        id="zhipu",
        name="智谱 AI",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=["glm-4-flash", "glm-4", "glm-4-plus"],
        default_model="glm-4-flash",
        description="GLM 系列，中文优化",
        icon="🧠"
    ),
    LLMProvider(
        id="ollama",
        name="Ollama (本地)",
        base_url="http://localhost:11434/v1",
        models=["qwen2.5:7b", "llama3.2:3b", "deepseek-r1:7b"],
        default_model="qwen2.5:7b",
        description="本地部署，完全免费",
        icon="🦙"
    ),
    LLMProvider(
        id="custom",
        name="自定义",
        base_url="",
        models=[],
        default_model="",
        description="OpenAI 兼容接口",
        icon="⚙️"
    ),
]

LLM_PROVIDERS_MAP = {p.id: p for p in LLM_PROVIDERS}


# ==================== 用户 LLM 配置 ====================

class LLMConfigCreate(BaseModel):
    """创建/更新 LLM 配置"""
    provider_id: str = Field(..., description="提供商 ID")
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="自定义 API 地址")
    model: str = Field(..., description="模型名称")


class LLMConfigResponse(BaseModel):
    """LLM 配置响应"""
    id: str
    provider_id: str
    api_key_set: bool  # 是否已设置 API Key（不返回实际值）
    base_url: Optional[str]
    model: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 聊天相关 ====================

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色: user/assistant/system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息")
    history: List[ChatMessage] = Field(default=[], description="对话历史")
    use_rag: bool = Field(default=True, description="是否使用 RAG 增强")


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str = Field(..., description="AI 回复内容")
    sources: List[str] = Field(default=[], description="引用的知识库来源")


class StreamChatChunk(BaseModel):
    """流式聊天块"""
    content: str = Field(..., description="内容片段")
    done: bool = Field(default=False, description="是否结束")

