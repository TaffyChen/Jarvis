# Jarvis

个人 A 股交易参谋：仪表盘 + 本地纪律知识库 + 站内对话（HITL 写入）+ HTTP / MCP 共用能力层。

- **前后端**：Vue3 + Pinia + FastAPI `:1690`
- **模型**：DeepSeek 对话 + 硅基流动 BGE-M3 / reranker（可选）+ LangGraph
- **数据**：业务在 MySQL；知识向量可选 Milvus；原文在 `knowledge/`；部署见 `deploy/`
- **账户**：MySQL RBAC（管理员 / 成员）；无库时回退 `.env` 单账号
- **规则**：`rules/agent.md` · 架构：`docs/ARCHITECTURE.md`（分层 + 入库 + RAG）· 视觉：`docs/DESIGN.md` · 协作：`docs/BRANCH_RULES.md`

## 快速启动

```bash
cp .env.example .env   # 填写 LLM_API_KEY，以及 MySQL / Milvus 相关项
bash start.sh          # 前端 :5173 · 后端 :1690（按 .env 自动拉起 MySQL / Milvus）
bash stop.sh           # 只停网页
bash stop-all.sh       # 网页 + MySQL + Milvus/Attu 全关（数据卷保留）
bash reindex.sh        # 改过 knowledge/ 后重建向量索引
```

浏览器：[http://127.0.0.1:5173](http://127.0.0.1:5173)  
默认账号：`.env` 的 `AUTH_ACCOUNT` / `AUTH_PASSWORD`（预置为管理员 `jarvis`）

根目录脚本是稳定入口，实现在 `scripts/`。

| 脚本 | 作用 |
|------|------|
| `start.sh` | 启网页；若配置了 MySQL / `VECTOR_BACKEND=milvus` 会先起对应容器 |
| `stop.sh` | 只停前端/后端进程 |
| `stop-all.sh` | 停网页 + `jarvis-mysql` + `jarvis-milvus` / Attu |
| `reindex.sh` | 把 Markdown / 分析 / 沉淀写入本地向量或 Milvus |
| `scripts/mysql.sh` | `up \| down \| status`（`deploy/mysql`） |
| `scripts/milvus.sh` | `up \| down \| status`（`deploy/milvus`） |
| `scripts/deploy.sh` | `build` 打镜像 / `save` 导出 tar / `up` 启动（见 `deploy/README.md`） |
| `scripts/mcp.sh` | Cursor MCP（stdio，按需拉起） |

## 常用地址

| 服务 | 地址 |
|------|------|
| 网页 | http://127.0.0.1:5173 |
| API / 文档 | http://127.0.0.1:1690/docs |
| MySQL | `127.0.0.1:3307` / 库 `jarvis` |
| Milvus | `127.0.0.1:19530` / collection `jarvis_kb` |
| Attu（Milvus UI） | http://127.0.0.1:18000 |

## 数据存在哪

| 类型 | 位置 | 说明 |
|------|------|------|
| 策略原文 | `knowledge/*.md` | 源文件；管理员可在网页「知识库」编辑，改完要重建索引 |
| MySQL | Docker 卷 + `kv_docs` | 持仓 / 分析 / 日记 / 对话；表结构见 `deploy/mysql/init/` |
| 本地向量（可选） | `data/vectordb/` | `VECTOR_BACKEND=local` 时使用 |
| Milvus | Docker 卷 `jarvis-milvus-*` | `VECTOR_BACKEND=milvus` |

`data/*.json` 默认不再双写、也不进 Git。迁移数据用 `bash deploy/mysql/export-data.sh`。

服务器 / 一体部署见 [`deploy/README.md`](deploy/README.md)。

`stop.sh` / `stop-all.sh` **不会**删数据卷。不要对 compose 使用 `down -v`。

## 账户与权限

MySQL 预置：

- 角色：`admin` 管理员、`member` 成员
- 用户：`AUTH_ACCOUNT`（默认 `jarvis`）→ 管理员
- 表：`users` / `roles` / `permissions` / `user_roles` / `role_permissions` / `auth_sessions`

接口除登录、`/api/health` 外需登录。知识库维护 / 重建索引仅管理员。

## MCP（Cursor 按需）

```bash
bash scripts/mcp.sh
```

```json
{
  "mcpServers": {
    "jarvis": {
      "command": "/你的绝对路径/Jarvis/scripts/mcp.sh"
    }
  }
}
```

| | 网页 `start.sh` | MCP |
|--|-----------------|-----|
| 启动 | 手动常驻 | Cursor 按需拉起 |
| 用途 | 仪表盘 + 站内对话 | 外部 Agent 调同一套能力 |
| 写入 | 补丁需点确认 | 工具可直接写（仅可信环境） |

需要 `backend/.venv`，Python **≥ 3.10**（推荐 3.12）。

## 目录

```
Jarvis/
├── README.md
├── start.sh / stop.sh / stop-all.sh / reindex.sh
├── .env.example
├── rules/agent.md                 # 开发规则书
├── docs/
│   ├── ARCHITECTURE.md            # 分层与数据架构
│   ├── DESIGN.md                  # 视觉规范
│   └── decision-graph.md          # 决策图走查
├── scripts/                       # 启停 / MySQL / Milvus / MCP / deploy
├── deploy/                        # 镜像、compose、MySQL 初始化 SQL
├── docker/README.md               # 指向 deploy/
├── backend/app/
│   ├── api/                       # HTTP（含 auth / 鉴权中间件）
│   ├── mcp/                       # MCP Server
│   ├── agents/                    # chat + LangGraph
│   ├── capabilities/              # 唯一业务入口
│   ├── domain/                    # 代码规范化 / memory
│   ├── infra/                     # storage / identity / llm / kb / market
│   ├── scripts/reindex_kb.py
│   ├── config.py
│   └── main.py
├── backend/tests/
├── frontend/src/                  # Vue3 仪表盘
├── knowledge/                     # 策略纪律 Markdown
└── data/                          # JSON 镜像（勿泄露）
```

## 站内对话（RAG）

链路：

```
问题 → 查询扩展（含多轮上下文）→ 向量+关键词多路召回 → RRF → bge-reranker
     → 纪律原文注入提示词 → DeepSeek（可再调行情/持仓工具）→ 结论 + HITL 补丁
```

只读：行情、评分、持仓、知识库、沉淀。  
写入（HITL）：加观察池、加/改/删持仓、分析/日记提案、对话沉淀。

`ChatPanel → /api/jarvis/chat → LangGraph → patch → 你点采纳 → capabilities`

Embedding / Rerank 配在 `.env`（`EMBEDDING_*` / `RERANK_*`）。DeepSeek 只负责生成，不提供向量接口。改完知识库要重建索引。

架构图与模型分工见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)；单次对话逐步走查见 [`docs/decision-graph.md`](docs/decision-graph.md)。

## 单测

```bash
cd backend && .venv/bin/pytest -q
```

## 安全

- API Key、库密码只放 `.env`，勿提交  
- MCP 写入会改本地/库数据，仅可信环境  
- 分层细节见 `docs/ARCHITECTURE.md`
