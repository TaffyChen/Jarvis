# Jarvis · 个人交易参谋 · 开发规则书

> 本文件是 Jarvis 的**开发上下文入口**：新会话读完即可按分层、能力边界、启停与 MCP 接入方式继续开发。  
> 架构细节另见：`docs/ARCHITECTURE.md`  
> **禁止**把 HarnessOs 企业平台的多租户 / Docker / 服务器账号约定直接套到本项目。

---

## 一、产品定位

Jarvis 是**个人** A 股交易参谋数字员工，不是多租户 SaaS。

| 能力 | 说明 |
|------|------|
| 行情仪表盘 | 自选 / 持仓 / 五灯 / 主升 / 选股 / 竞价 |
| 纪律知识库 | `knowledge/*.md` → 本地向量或 Docker Milvus |
| 对话参谋 | LangGraph 多工具决策图 + HITL 补丁 |
| 对话沉淀 | `memory_notes` 认知卡片 |
| 共用服务层 | `services` 供对话框 / HTTP / MCP 共用 |

**架构主线**：

```
接入层 api / mcp / agents
    ↓
应用层 services（唯一业务入口）
    ↓
领域层 domain（codes / memory）
    ↓
基础设施 infrastructure（persistence / kb / market / llm）
```

依赖只允许**向内**。业务逻辑禁止写在 MCP、tools 适配层里复制一份。

---

## 二、技术栈与目录

| 层 | 路径 | 约定 |
|----|------|------|
| HTTP | `backend/app/api/` | FastAPI；行情 / 对话 / knowledge / services |
| MCP | `backend/app/mcp/` | 官方 `mcp` FastMCP；`python -m app.mcp` |
| Agent | `backend/app/agents/` | `chat.py` 入口 + `graph/` 决策图 |
| 服务 | `backend/app/services/` | journal / positions / analyses / codes / quotes / memory / patches / knowledge / rag |
| 横切 | `backend/app/core/` | config / deps |
| 领域 | `backend/app/domain/` | 代码规范化、沉淀模型 |
| 基础设施 | `backend/app/infrastructure/` | storage / identity(RBAC) / llm / 本地或 Milvus 向量 / 行情 |
| 文档 | `docs/` | 架构、视觉、决策图 |
| 部署 | `deploy/` | Dockerfile / compose / MySQL init SQL |
| 前端 | `frontend/` | Vue3 + Pinia；Element 仅弹层/表格 |
| 知识 | `knowledge/` | 策略 Markdown |
| 数据 | MySQL + Milvus | 业务表与 RBAC 在 MySQL；知识向量在 Milvus；原文在 `knowledge/` |

**运行时**：Python **≥ 3.10**（推荐 3.12），`backend/.venv`；LLM 为 DeepSeek（OpenAI 兼容）。

---

## 三、启停与 MCP（务必分清）

### 3.1 网页应用（常驻服务）

```bash
bash start.sh    # FastAPI :1690 + Vite :5173
bash stop.sh           # 只停网页
bash stop-all.sh       # 网页 + MySQL + Milvus/Attu
bash reindex.sh  # 重建知识库索引
```

根目录 `start.sh / stop.sh / stop-all.sh / reindex.sh` 是稳定入口；实现集中在 `scripts/`（薄封装 + 可维护实现分离）。

### 3.2 MCP（按需由客户端拉起）

MCP Server 是 **stdio 进程**：Cursor 需要时自动启动。  
脚本：`bash scripts/mcp.sh`

| | 网页 Jarvis | MCP Jarvis |
|--|-------------|------------|
| 谁启动 | 你执行 `start.sh` | Cursor 配置后自动拉起 |
| 是否常驻 | 是 | 通常否（stdio） |
| 用途 | 仪表盘 + 站内对话 | 外部 Agent 调同一套 services |
| 写入 | 对话补丁需 HITL 确认 | MCP 写入工具会直接改本地，仅可信环境 |

---

## 四、能力与写入边界

### 4.1 只读（可自由调）

`search_knowledge` / `search_memory` / `get_quote` / `get_score` / `get_analysis` / `get_positions` / `get_market_overview` / `get_journal` / `list_kb_documents` / `get_kb_document` / `preview_kb_chunks` / `kb_overview`

### 4.2 写入（须谨慎）

| 能力 | 站内对话 | MCP / invoke |
|------|----------|--------------|
| 加标的 / 加改删持仓 / patch / 沉淀 | 先 patch，用户点确认 | 可直接 `invoke`，视为已授权 |
| 知识库 Markdown / 重建索引 | 管理员网页「知识库」直接改文件 | MCP `save_kb_document` / `reindex_knowledge` 直接写 |

禁止在回答里声称「已写入」而未走确认（站内对话）。

代码规范化：`domain.codes.normalize_code`（`600693` → `sh600693`）。

### 4.3 多入口必须共用

```
agents/graph/tools.py  → services.quotes / positions / journal / ...
api/services.py        → services.invoke
mcp/server.py          → services.invoke
api patches/apply      → services.patches
```

发现能力：`GET /api/jarvis/capabilities`

---

## 五、对话 Agent 约定

- 编排：LangGraph（`agents/chat.py` → `graph/`）
- RAG：`services/rag.py`（查询扩展 → 多路召回 → rerank）→ bootstrap 注入原文
- Embedding / Rerank：`.env` 的 `EMBEDDING_*` / `RERANK_*`（与 DeepSeek 对话 Key 分开）
- 工具轮次上限：`JARVIS_GRAPH_MAX_TOOL_ROUNDS`（默认 4）
- 学习走查：`docs/decision-graph.md`
- 角色与纪律：`knowledge/Jarvis角色.md` 及同目录策略模块

回答风格：先给可执行结论（持有/减仓/清仓/观察），再给依据并点名知识库文档；不编造未提供的行情或未检索到的条款；不承诺收益。

---

## 六、前端约定

- 对话抽屉：`ChatPanel.vue`；Markdown 渲染助手回复
- 知识库页：`KnowledgePanel.vue`（管理员 `kb.manage`）
- API：`frontend/src/api/index.js`，baseURL `/api`，登录头 `x-jarvis-token`
- 深色 / 浅色主题；自选卡片 / 列表；Element 主要用于 dialog/table
- 视觉规范：`docs/DESIGN.md`
- **不修改**原 `dashboard` / `bussness_harnessos` 仓库

---

## 七、安全与仓库卫生

- `LLM_API_KEY` 只在 `.env`，勿提交、勿写进 rules
- 勿把旧 `data/*.json`、持仓、对话流水提交进 Git
- 本规则书**不得**粘贴任何服务器密码、SSH、生产 Admin 账号

---

## 八、标准开发清单

### 8.1 新增只读能力

1. `services/query.py` 实现  
2. `registry.py` 注册 meta + CALLABLES  
3. `agents/graph/tools.py` 增加 OpenAI tool schema（若对话要用）  
4. `mcp/server.py` 增加 `@mcp.tool`（若 MCP 要用）  
5. 更新 `docs/decision-graph.md` / 本文件能力表  

### 8.2 新增写入能力

1. `services/mutate.py`  
2. registry +（可选）MCP tool，描述标明【写入】  
3. 站内对话：扩展 `strategy_patch` target + `/patches/apply`  
4. 前端补丁卡片文案  

### 8.3 改策略纪律

1. 网页「知识库」或直接改 `knowledge/*.md`  
2. 页面点「重建索引」或 `bash reindex.sh`  
3. 必要时同步 `knowledge/Jarvis角色.md`  

---

## 九、新会话快速模板

```
请阅读 @rules/agent.md 与 @docs/ARCHITECTURE.md。

当前任务：[填写]

要求：
1) 业务只进 services，禁止在 mcp/tools 复制逻辑
2) 站内写入走 HITL 补丁；分清 start.sh（网页）与 mcp.sh（Cursor 按需）
3) Python >= 3.10（venv 用 3.12）；不改 harnessos / 旧 dashboard 原仓
4) 简体中文沟通
```

---

## 十、文档索引

| 文件 | 用途 |
|------|------|
| `rules/agent.md` | 本文件 · 总规则 |
| `docs/ARCHITECTURE.md` | 分层、入库、RAG 对话、数据、RBAC、MCP |
| `docs/DESIGN.md` | 视觉规范 |
| `docs/decision-graph.md` | 决策图走查 |
| `knowledge/*.md` | 交易纪律知识库 |
| `README.md` | 启停与目录总览 |

---

*Jarvis · 个人交易参谋 · rules v2.1 · 2026-08-05*
