# Jarvis 架构

分层从外到内，**依赖只允许向内**：

```
┌─────────────────────────────────────────────────────────┐
│  interfaces  接入层                                       │
│  api/          HTTP（网页、脚本）                          │
│  mcp/          MCP（Cursor / 外部 Agent）                  │
│  agents/       对话 Agent（chat 入口 + LangGraph）         │
└───────────────────────────┬─────────────────────────────┘
                            │ 只调 services / 读配置
┌───────────────────────────▼─────────────────────────────┐
│  application  应用服务层                                   │
│  services/     journal / positions / analyses / codes     │
│                quotes / memory / patches / knowledge/rag  │
│                （唯一业务入口）                            │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────────────┐
        ▼                                               ▼
┌───────────────────┐                     ┌─────────────────────────┐
│ domain            │                     │ infrastructure         │
│ codes / memory    │                     │ storage / identity      │
│                   │                     │ llm / kb* / market      │
└───────────────────┘                     └─────────────────────────┘
```

`kb*` = `infrastructure/kb/`（chunk / extract / embed / search / rerank / index / milvus）

## 目录对照

| 路径 | 层 | 职责 |
|------|----|------|
| `app/api/` | 接入 | 薄路由：health / market / journal / positions / analyses / codes / auth / jarvis / knowledge |
| `app/mcp/` | 接入 | MCP Server，`python -m app.mcp` |
| `app/agents/` | 接入 | `chat.py` 入口；`graph/` 决策图 |
| `app/services/` | 应用 | 按业务：journal / positions / analyses / codes / quotes / memory / patches / knowledge / rag |
| `app/domain/` | 领域 | 纯规则：`codes` / `memory`（不碰存储） |
| `app/infrastructure/` | 基建 | `persistence/*_store` · `kb/` · `market/` · `llm.py` |
| `app/core/` | 横切 | `config.py` · `deps.py` |
| `app/scripts/` | 工具 | `reindex_kb` |
| `app/main.py` | 组合根 | 路由、鉴权中间件、行情循环、启动建表/迁数据 |

业务只写在 `services/`，不要在 MCP 或 tools 里复制。

---

## 总览：三条主链路

```
① 知识入库（离线）     knowledge/*.md ──reindex──► Milvus（产品路径）
② 站内对话（在线 RAG）  问题 ──rag──► 原文注入 ──DeepSeek──► 工具/结论/HITL
③ 业务数据             MySQL 专用表（持仓/分析/日记/沉淀/对话）+ RBAC
```

网页 `bash start.sh` 常驻；MCP `bash scripts/mcp.sh` 由 Cursor 按需拉起。两套入口共用 services。

---

## 知识入库（离线）

```
knowledge/*.md          管理员网页「知识库」新建 / 上传 / 编辑，或直接改文件
上传 md/txt/pdf/docx/xlsx/html/csv → infrastructure/kb/extract 抽成 Markdown
analyses / memory       一并切进索引
        │
        ▼  chunk          infrastructure/kb/chunk.py
 Markdown 标题路径 + 段/句窗口 + overlap
        │
        ▼  embed          infrastructure/kb/embed.py
 hash-384  或  硅基 BAAI/bge-m3 (1024d)
        │
        ▼  store          Milvus collection jarvis_kb
        │
        └─ kb_meta        记在 MySQL kv_docs（embedding / 时间 / 切块数）
```

| 开关 | 含义 |
|------|------|
| `MILVUS_URI` / `MILVUS_COLLECTION` | 知识向量库 |
| `EMBEDDING_BACKEND=hash` | 本地 n-gram hashing，不上网 |
| `EMBEDDING_BACKEND=openai` | 兼容 `/embeddings`（DeepSeek **没有**此接口） |

改完原文必须重建：网页「重建索引」或 `bash reindex.sh`。维数变了（如 hash→bge-m3）旧索引不能混用。

---

## 站内对话 RAG（在线）

模型分工：

| 组件 | 谁 | 干什么 |
|------|-----|--------|
| 生成 | DeepSeek `LLM_*` | 读上下文、调工具、写结论与 patch |
| 向量 | 硅基 `BAAI/bge-m3` | 「意思近不近」 |
| 重排 | 硅基 `BAAI/bge-reranker-v2-m3` | 候选里再精排 |
| 编排 | LangGraph | bootstrap → agent ⇄ tools → END |

```
ChatPanel
  → POST /api/jarvis/chat
  → agents/chat.py
  → graph/runner.py
  → LangGraph
        │
        ▼ bootstrap
   services/rag.py
     1. 查询扩展（原话 + 历史代码/名称 + 纪律关键词）
     2. 多路召回：向量 + 关键词 → RRF
     3. 可选 rerank
     4. 纪律原文 + 沉淀 写入 user 消息
        │
        ▼ agent（DeepSeek）
   已有条文 → 可直接答纪律题
   缺行情/持仓/评分 → tool_calls
        │
        ▼ tools（只读）
   services/*（quotes / positions / journal / …）→ 回写 messages
        │
        ▼ agent 再答
   结论 + 可选 strategy_patch / memory_patch
        │
        ▼ 前端 HITL
   你点「采纳 / 确认记住」才落库
```

对应代码：

| 步骤 | 文件 |
|------|------|
| 查询扩展 / 多路召回 | `services/rag.py` |
| 向量+关键词 / RRF | `infrastructure/kb/search.py` + `index.py` / `milvus.py` |
| 重排 | `infrastructure/kb/rerank.py` |
| 图节点 | `agents/graph/graph.py` |
| 工具适配 | `agents/graph/tools.py`（不写业务） |
| 一次对话走查 | `docs/decision-graph.md` |

配置：`.env` 的 `EMBEDDING_*`、`RERANK_*`、`JARVIS_GRAPH_MAX_TOOL_ROUNDS`。  
`RERANK_ENABLED=false` 时跳过重排，仍用向量+关键词。

---

## 数据落在哪

```
knowledge/*.md  ──reindex──►  Milvus jarvis_kb
      ▲                              ▲                ▲
  网页知识库维护                 embedding           Attu :18000
                         MySQL 业务表 / users / roles / sessions
```

| 后端 | 开关 | 存什么 |
|------|------|--------|
| MySQL | `MYSQL_HOST` | 业务专用表 + RBAC。空库跑 `deploy/mysql/init/*.sql` |
| Milvus | `MILVUS_URI` | 知识库向量 |

启动若发现本机遗留 `data/*.json` 或 `kv_docs`，会迁进专用表后清掉。正式运行只读写 MySQL 业务表 + Milvus，仓库不包含 `data/`。

部署打包在 `deploy/`：应用镜像 + compose + 建表 SQL。说明见 `deploy/README.md`。  
本仓库部署按**单人实例**设计，不要套企业多租户约定。

---

## 账户与 RBAC

`infrastructure/persistence/identity.py` + `api/auth.py` + `main.py` 中间件。

- 角色：`admin`、`member`
- 权限：`data.read` / `data.write` / `chat.use` / `kb.manage` / `kb.reindex` / `user.manage`
- 预置用户：`.env` 的 `AUTH_ACCOUNT` → `admin`
- 无 MySQL 时回退 `.env` 单账号，视为管理员
- 除 `/api/auth/*`、`/api/health` 外需 `x-jarvis-token`
- 知识库页：`kb.manage`；重建索引：`kb.reindex`

---

## 多入口共用

1. **对话框**：bootstrap → `services.rag`；工具 → 各业务 services；写入 HITL → `services.patches` / `services.memory`
2. **HTTP**：`POST /api/jarvis/capabilities/invoke`
3. **MCP / Cursor**：`app/mcp` → `services.registry.invoke`

对话工具**只读**。`strategy_patch` / `memory_patch` 须前端确认后才写。  
支持：加观察池、加/改/删持仓、分析/日记/规则提案、对话沉淀。

---

## 前端要点

- Vue3 + Pinia；Element Plus 主要用于 dialog / table / 登录
- 页面拆分：`views/WorkspaceView.vue` / `StocksView.vue`；自选卡片 / 列表
- **纪律日记**独立页：`JournalPanel.vue`（关键词 + 级别筛选；API 亦支持 `q` / `level` / `code`）
- 利空门禁：卡片「通过 / 未过」写入分析底稿，约束「可买入」
- 深浅主题见 `docs/DESIGN.md`；产品能力总览见根目录 `README.md`
- 管理员侧栏「知识库」：编辑 md、上传、预览切块、试检索、重建索引
- 对话抽屉展示 `toolTrace`（含 `rag_retrieve`）与依据来源
- 请求头 `x-jarvis-token`

---

## MCP

官方 **mcp SDK（FastMCP）**。`backend/.venv` 需 **Python ≥ 3.10**（推荐 3.12）。

```bash
bash scripts/mcp.sh
```

决策图逐步走查：`docs/decision-graph.md`。  
协作与 bypass：`docs/BRANCH_RULES.md`。

---

最后更新时间：2026-08-06
