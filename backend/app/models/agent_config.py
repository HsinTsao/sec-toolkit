"""Agent 配置模型"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database import Base


class AgentTraceHistory(Base):
    """
    Agent 执行历史表
    
    用于保存执行过程，支持历史回放功能。
    """
    __tablename__ = "agent_trace_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 会话信息
    trace_id = Column(String(36), nullable=False)
    session_id = Column(String(36), nullable=True)
    
    # 执行信息
    user_input = Column(Text, nullable=False)
    final_output = Column(Text, nullable=True)
    events = Column(JSON, nullable=False, default=list)  # 完整的 trace 事件列表
    
    # 配置快照
    config_snapshot = Column(JSON, nullable=True)  # 执行时的配置
    
    # 统计信息
    total_time_ms = Column(String(20), nullable=True)
    total_tokens = Column(String(20), nullable=True)
    
    # 标记
    is_starred = Column(Boolean, default=False)  # 星标（收藏）
    tags = Column(JSON, nullable=True, default=list)  # 标签
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="trace_history")


class AgentConfig(Base):
    """
    Agent 配置表
    
    存储用户的 Agent 配置，包括：
    - System Prompt 自定义
    - 模块启用状态
    - 其他 Agent 参数
    """
    __tablename__ = "agent_configs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # System Prompt
    system_prompt = Column(Text, nullable=True)  # 自定义系统提示词
    system_prompt_enabled = Column(Boolean, default=False)  # 是否启用自定义提示词
    
    # 模块配置
    modules_config = Column(JSON, nullable=True, default=dict)  # 各模块的配置
    # 格式: {"rag": {"enabled": true, "top_k": 5}, "mcp": {"enabled": false}}
    
    # Agent 参数
    temperature = Column(String(10), default="0.7")  # LLM 温度
    max_tokens = Column(String(10), default="2048")  # 最大 token 数
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="agent_config")


# 默认 System Prompt
DEFAULT_SYSTEM_PROMPT = """你是一个专业的 AI 安全助手，具备以下能力：

1. **编码/解码**：Base64、URL、Hex、HTML 等多种编码格式的转换
2. **哈希计算**：MD5、SHA1、SHA256 等哈希算法
3. **网络查询**：DNS 查询、WHOIS 信息、IP 地理位置
4. **天气查询**：获取指定城市的天气信息
5. **股票分析**：A股、港股、美股行情查询和技术分析

请根据用户的问题，选择合适的工具来完成任务。如果问题不需要工具，直接给出专业的回答。

注意事项：
- 对于安全相关问题，请给出详细的技术分析
- 对于投资建议，请附上风险提示
- 保持回答简洁专业
"""
