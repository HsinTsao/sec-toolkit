# Agent Tool Calling 架构

这是一个标准化的 Tool Calling 中间架构，遵循 OpenAI Function Calling 格式，兼容大多数 LLM。

**🆕 新增双 LLM 架构**：Token 消耗降低 60-70%！详见下方"双 LLM 架构"章节。

## 架构概览

```
app/agent/
├── __init__.py      # 模块入口，导出主要组件
├── base.py          # 基类定义：BaseTool, ToolParameter, ToolResult
├── registry.py      # 工具注册中心：ToolRegistry
├── executor.py      # 工具执行器：ToolExecutor
├── tools/           # 内置工具
│   ├── __init__.py  # 注册入口
│   ├── encoding.py  # 编码/解码工具
│   ├── hash.py      # 哈希计算工具
│   └── network.py   # 网络查询工具
└── README.md
```

## 快速开始

### 1. 创建自定义工具

**方式一：继承 BaseTool**

```python
from app.agent import BaseTool, ToolParameter, ToolResult, ParameterType

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具描述"
    category = "custom"
    parameters = [
        ToolParameter(
            name="input",
            type=ParameterType.STRING,
            description="输入内容"
        )
    ]
    
    async def execute(self, input: str) -> ToolResult:
        result = f"处理结果: {input}"
        return ToolResult.ok(result)

# 注册工具
from app.agent import tool_registry
tool_registry.register(MyTool)
```

**方式二：使用装饰器**

```python
from app.agent import tool_registry
from app.agent.base import ToolParameter

@tool_registry.tool(
    name="uppercase",
    description="将文本转换为大写",
    parameters=[ToolParameter(name="text", description="输入文本")],
    category="text"
)
def uppercase(text: str) -> str:
    return text.upper()
```

**方式三：注册现有函数**

```python
from app.agent import tool_registry
from app.agent.base import ToolParameter

def my_function(text: str) -> str:
    return text.lower()

tool_registry.register_function(
    name="lowercase",
    description="将文本转换为小写",
    func=my_function,
    parameters=[ToolParameter(name="text", description="输入文本")],
    category="text"
)
```

### 2. 执行工具

```python
from app.agent import tool_executor

# 直接执行
result = await tool_executor.execute("base64_encode", {"text": "hello"})
print(result.success)  # True
print(result.data)     # "aGVsbG8="

# 批量执行
results = await tool_executor.execute_batch([
    {"tool_name": "base64_encode", "arguments": {"text": "hello"}},
    {"tool_name": "url_encode", "arguments": {"text": "hello world"}},
])
```

### 3. 获取工具定义

```python
from app.agent import tool_registry

# 获取所有工具
tools = tool_registry.get_all()

# 按分类获取
encoding_tools = tool_registry.get_by_category("encoding")

# 获取 OpenAI 格式（用于 LLM API）
openai_tools = tool_registry.get_openai_tools()
```

## API 端点

### 获取工具列表
```
GET /api/llm/agent/tools?category=encoding
```

### 获取 OpenAI 格式工具
```
GET /api/llm/agent/tools/openai-format
```

### 执行工具
```
POST /api/llm/agent/execute
{
    "tool_name": "base64_encode",
    "arguments": {"text": "hello"}
}
```

### Agent 聊天（支持 Tool Calling）
```
POST /api/llm/agent/chat
{
    "message": "帮我把 'hello world' 进行 base64 编码",
    "use_tools": true,
    "tool_categories": ["encoding", "hash"],
    "use_knowledge": false,
    "max_tool_iterations": 5
}
```

## 内置工具

### 编码工具 (encoding)
- `base64_encode` - Base64 编码
- `base64_decode` - Base64 解码
- `url_encode` - URL 编码
- `url_decode` - URL 解码
- `html_encode` - HTML 实体编码
- `html_decode` - HTML 实体解码
- `hex_encode` - 十六进制编码
- `hex_decode` - 十六进制解码
- `unicode_encode` - Unicode 编码
- `unicode_decode` - Unicode 解码
- `rot13` - ROT13 编码/解码

### 哈希工具 (hash)
- `calculate_hash` - 计算哈希值（支持 MD5/SHA1/SHA256 等）
- `calculate_all_hashes` - 计算所有常用哈希
- `calculate_hmac` - 计算 HMAC
- `compare_hash` - 比较哈希值

### 网络工具 (network)
- `dns_lookup` - DNS 查询
- `whois_lookup` - WHOIS 查询
- `ip_info` - IP 信息查询
- `reverse_dns` - 反向 DNS 查询
- `analyze_target` - 综合目标分析

## 扩展工具

在 `app/agent/tools/` 目录下创建新文件，参考现有工具的实现方式。

然后在 `app/agent/tools/__init__.py` 中导入并注册：

```python
from .my_tools import register_my_tools

def register_builtin_tools() -> None:
    register_encoding_tools(tool_registry)
    register_hash_tools(tool_registry)
    register_network_tools(tool_registry)
    register_my_tools(tool_registry)  # 添加这行
```

## 注意事项

1. **工具名称必须唯一**：注册同名工具会覆盖之前的
2. **异步支持**：工具函数可以是同步或异步的，执行器会自动处理
3. **错误处理**：工具执行异常会被捕获并返回 `ToolResult.fail()`
4. **确认机制**：设置 `requires_confirmation=True` 可要求用户确认后再执行危险操作


## 🚀 双 LLM 架构（省 Token 模式）

```
            ┌────────────┐
User Input →│ Intent LLM │  (~200 tokens)
            └─────┬──────┘
                  │ JSON
        ┌─────────▼─────────┐
        │ Deterministic Core │  (0 tokens)
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │ Tool / Code Layer │  (0 tokens)
        └─────────┬─────────┘
                  │
            ┌─────▼─────┐
            │ Summary   │  (~200–400 tokens)
            │   LLM     │
            └───────────┘
```

### Token 消耗对比

| 架构 | 每次请求 Token | 100万 Token 可用次数 |
|------|---------------|---------------------|
| 传统 Tool Calling | ~1500 | ~666 次 |
| 双 LLM 架构 | ~400 | **~2500 次** |
| 双 LLM + 规则匹配 | ~0-200 | **~5000+ 次** |

### 快速使用

```python
from app.agent import DualLLMAgent, LLMConfig

agent = DualLLMAgent(LLMConfig(
    base_url="https://api.deepseek.com/v1",
    api_key="sk-...",
    model="deepseek-chat",
))

result = await agent.process("把 hello world 转成 base64")
print(result.content)  # ✅ Base64 编码结果: aGVsbG8gd29ybGQ=
print(result.tokens_estimated)  # 0 (规则匹配)
```

### API 端点

- `POST /api/llm/fast/chat` - 快速聊天（非流式）
- `POST /api/llm/fast/chat/stream` - 快速聊天（流式）
- `GET /api/llm/fast/info` - 获取快速模式信息

