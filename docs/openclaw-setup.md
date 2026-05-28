# OpenClaw 安装配置与使用说明

## 一、术语解释

| 术语 | 含义 |
|------|------|
| **OpenClaw** | 开源 AI Agent 框架，自托管在自己服务器上的私人 AI 助手 |
| **Gateway** | OpenClaw 核心服务进程，所有消息经过它路由到 AI 模型，同时提供网页聊天界面 |
| **API Key** | 调用 AI 大模型的密钥，不同提供商（通义千问、OpenAI）各有各的 |
| **Auth Token** | 访问 OpenClaw 网页的密码，防止未授权访问 |
| **设备配对** | 安全机制，新设备首次访问需要在服务器上手动批准 |
| **MCP** | AI 调用外部工具的标准协议，OpenClaw 生态有 5700+ 个插件 |
| **Skill / 插件** | OpenClaw 的扩展能力，每个 Skill 教会 AI 一项新能力 |
| **Channel / 渠道** | 连接外部聊天平台（飞书、钉钉、Telegram 等） |
| **Session / 会话** | 和 Agent 的一次完整对话，OpenClaw 只有一个 main session |

---

## 二、安装步骤

### 1. 安装 Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
node -v   # 应显示 v22.x.x
```

### 2. 安装 OpenClaw

```bash
npm install -g openclaw@latest
openclaw --version
```

### 3. 创建配置文件

```bash
mkdir -p ~/.openclaw
```

编辑 `~/.openclaw/openclaw.json`（以通义千问为例）：

```json
{
  "models": {
    "providers": {
      "qwen": {
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "apiKey": "你的 API Key",
        "api": "openai-completions",
        "models": [
          { "id": "qwen-turbo", "name": "Qwen Turbo（快速）", "contextWindow": 131072, "maxTokens": 8192 },
          { "id": "qwen-plus", "name": "Qwen Plus（均衡）", "contextWindow": 131072, "maxTokens": 8192 },
          { "id": "qwen-max", "name": "Qwen Max（最强）", "contextWindow": 32768, "maxTokens": 8192 },
          { "id": "qwen-long", "name": "Qwen Long（长文本）", "contextWindow": 1000000, "maxTokens": 8192 }
        ]
      }
    }
  },
  "web": { "enabled": true }
}
```

### 4. 初始化

```bash
openclaw doctor --fix
openclaw config set gateway.mode local
openclaw config set agents.defaults.model.primary "qwen/qwen-plus"
chmod 700 ~/.openclaw && chmod 600 ~/.openclaw/openclaw.json
```

### 5. 注册为系统服务

```bash
cat > /etc/systemd/system/openclaw-gateway.service << 'EOF'
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
Type=simple
User=root
Environment=NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
Environment=OPENCLAW_NO_RESPAWN=1
ExecStart=/usr/bin/openclaw gateway
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/tmp/openclaw-compile-cache
systemctl daemon-reload
systemctl enable openclaw-gateway
systemctl start openclaw-gateway
```

---

## 三、访问方式

### 本机直接访问

```
http://127.0.0.1:18789
```

### 外网 HTTPS 访问（通过 Nginx 反代）

Nginx 配置（`/etc/nginx/sites-available/openclaw`）：

```nginx
server {
    listen 8443 ssl;
    server_name _;
    ssl_certificate     /path/to/server.crt;
    ssl_certificate_key /path/to/server.key;

    location / {
        proxy_pass http://127.0.0.1:18789;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

外网访问地址（需在云安全组放通对应端口）：

```
https://你的服务器IP:8443
```

### 免输 Token 的快捷链接

把 Token 放在 URL 里，收藏即可免登录：

```
https://你的服务器IP:8443/#token=你的auth_token
```

### 查看 Auth Token

```bash
cat ~/.openclaw/openclaw.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['gateway']['auth']['token'])
"
```

### 设备配对

新设备首次访问会提示 "pairing required"，在服务器上执行：

```bash
openclaw devices approve --latest    # 批准最新的请求
openclaw devices list                # 查看所有待配对和已配对设备
```

---

## 四、日常使用

### 聊天斜杠命令

在对话输入框中输入以下命令：

| 命令 | 作用 | 示例 |
|------|------|------|
| `/model <名称>` | 切换 AI 模型 | `/model qwen-max` |
| `/models` | 查看可用模型列表 | `/models` |
| `/sessions` | 查看所有会话 | `/sessions` |
| `/memory` | 查看 Agent 记忆 | `/memory` |
| `/status` | 查看当前状态 | `/status` |
| `/help` | 查看所有可用命令 | `/help` |

### 切换模型

对话中直接输入：

```
/model qwen-turbo    ← 快速、便宜
/model qwen-plus     ← 均衡、推荐
/model qwen-max      ← 最强、贵
/model qwen-long     ← 超长文本（100万 token）
```

Agent 会确认切换成功，后续消息使用新模型。

### 会话管理

- **New Session** 会重置当前对话（旧内容自动归档，不会丢失）
- OpenClaw 只有一个 main session，不像传统聊天工具有多个对话窗口
- 历史对话通过 **Memory 系统**自动记住关键信息
- 想找以前聊过的内容，直接问 Agent："帮我搜索之前聊过的 xxx"

### 让 Agent 执行系统命令

当前配置 `tools.profile: "full"`，Agent 可以执行 shell 命令。你可以直接说：

- "帮我查看服务器内存使用情况"
- "运行 openclaw plugins list 看看有哪些插件"
- "帮我安装 web-search 插件"

---

## 五、服务器管理命令

### Gateway 管理

```bash
systemctl start openclaw-gateway     # 启动
systemctl stop openclaw-gateway      # 停止
systemctl restart openclaw-gateway   # 重启
systemctl status openclaw-gateway    # 状态
journalctl -u openclaw-gateway -f    # 实时日志
```

### OpenClaw CLI 命令

| 命令 | 说明 |
|------|------|
| `openclaw --version` | 查看版本 |
| `openclaw status` | 运行状态 |
| `openclaw doctor` | 诊断检查 |
| `openclaw doctor --fix` | 自动修复 |
| `openclaw config set <key> <value>` | 修改配置（需重启生效） |
| `openclaw plugins list` | 已安装插件 |
| `openclaw plugins install <name>` | 安装插件 |
| `openclaw devices list` | 设备配对列表 |
| `openclaw devices approve --latest` | 批准最新设备 |

---

## 六、模型配置

### 切换默认模型

```bash
openclaw config set agents.defaults.model.primary "qwen/qwen-max"
systemctl restart openclaw-gateway
```

### 添加新的模型提供商

编辑 `~/.openclaw/openclaw.json`，在 `models.providers` 中新增：

```json
"deepseek": {
  "baseUrl": "https://api.deepseek.com/v1",
  "apiKey": "你的 DeepSeek API Key",
  "api": "openai-completions",
  "models": [
    { "id": "deepseek-chat", "name": "DeepSeek Chat", "contextWindow": 65536, "maxTokens": 8192 }
  ]
}
```

然后切换：

```bash
openclaw config set agents.defaults.model.primary "deepseek/deepseek-chat"
systemctl restart openclaw-gateway
```

### 常见提供商 baseUrl

| 提供商 | baseUrl |
|--------|---------|
| 通义千问（国内） | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 通义千问（海外） | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenAI | `https://api.openai.com/v1` |

---

## 七、连接飞书 / 钉钉

### 飞书

1. [飞书开放平台](https://open.feishu.cn/app) → 创建企业自建应用
2. 添加权限：`im:message`、`im:message:send_as_bot`、`im:resource`
3. 开启「机器人」能力 → 事件订阅选 **WebSocket 长连接模式** → 添加 `im.message.receive_v1`
4. 发布应用并审批通过

```bash
openclaw plugins install @openclaw/feishu
openclaw channels add   # 选择 Feishu，输入 App ID 和 App Secret
systemctl restart openclaw-gateway
```

### 钉钉

```bash
openclaw plugins install @openclaw/dingtalk
openclaw channels add
systemctl restart openclaw-gateway
```

> 飞书和钉钉都用 WebSocket 长连接，不需要公网回调地址和 SSL 证书。

---

## 八、与 SecToolkit 并行部署

### 端口规划

| 服务 | 端口 | 协议 |
|------|------|------|
| SecToolkit 前端 | 443 | HTTPS（Vite dev） |
| SecToolkit 后端 | 8000 | HTTPS（uvicorn） |
| OpenClaw WebChat | 8443 | HTTPS（Nginx 反代） |
| OpenClaw Gateway | 18789 | HTTP（仅 localhost） |

### 启动顺序

```bash
# SecToolkit（端口 443 + 8000）
cd /code/sec-toolkit && ./start.sh dev --ssl

# OpenClaw（systemd 管理，开机自启）
systemctl start openclaw-gateway

# Nginx（反代 OpenClaw 到 8443）
systemctl start nginx
```

### 内存占用（生产环境，无 Cursor）

| 进程 | 内存 |
|------|------|
| SecToolkit 后端 | ~130 MB |
| SecToolkit 前端 | ~175 MB |
| OpenClaw Gateway | ~380 MB |
| Nginx | ~20 MB |
| 系统 | ~300 MB |
| **合计** | **~1.0 GB / 1.9 GB** |

---

## 九、文件位置速查

| 文件 | 路径 |
|------|------|
| 配置文件 | `~/.openclaw/openclaw.json` |
| 配置备份 | `~/.openclaw/openclaw.json.bak` |
| 会话数据 | `~/.openclaw/agents/main/sessions/` |
| 运行日志 | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` |
| systemd 服务 | `/etc/systemd/system/openclaw-gateway.service` |
| Nginx 反代配置 | `/etc/nginx/sites-available/openclaw` |
| SSL 证书 | `/code/sec-toolkit/certs/server.crt` + `server.key` |

---

## 十、常见问题

### Q: 访问网页报 "origin not allowed"

需要把访问地址加到允许列表：

```bash
openclaw config set gateway.controlUi.allowedOrigins '["https://你的IP:8443"]'
systemctl restart openclaw-gateway
```

### Q: 访问网页报 "pairing required"

在服务器上批准设备：

```bash
openclaw devices approve --latest
```

### Q: 页面打不开 / 连接被拒绝

1. 确认 Gateway 在运行：`systemctl status openclaw-gateway`
2. 确认 Nginx 在运行：`systemctl status nginx`
3. 确认端口在监听：`ss -tlnp | grep -E "18789|8443"`
4. 确认云安全组已放通对应端口

### Q: Agent 说不能执行命令

确认工具权限为 full：

```bash
openclaw config set tools.profile "full"
systemctl restart openclaw-gateway
```

### Q: 怎么切换模型

在对话中输入 `/model qwen-max`（或其他模型名）即可即时切换。

### Q: New Session 后对话消失了

没有丢失，旧对话自动归档在 `~/.openclaw/agents/main/sessions/` 目录中。OpenClaw 只有一个 main session，点 New Session 是重置当前对话。想找以前的内容，直接问 Agent "搜索之前聊过的 xxx"。

### Q: 怎么更新 OpenClaw

```bash
npm update -g openclaw
systemctl restart openclaw-gateway
```
