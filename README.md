# Jarvis

个人 A 股交易参谋：帮你盯盘、守纪律、复盘，而不是替你下单。

把自选与持仓、实时评分与预警、策略知识库、站内对话写在一起；改观察池 / 持仓等写入，必须你在对话里点「采纳」后才落库。

- **前后端**：Vue3 + Pinia + Vite `:5173` · FastAPI `:1690`
- **模型**：DeepSeek 负责生成；向量 / 重排可用硅基 BGE-M3、`bge-reranker-v2-m3`（也可 `EMBEDDING_BACKEND=hash` 本地算法不上网）
- **编排**：LangGraph 决策图（预检索 → 工具 → 结论 / HITL 补丁）
- **数据**：业务在 **MySQL 专用表**；知识向量在 **Milvus**；策略原文在 `knowledge/`。二者都是产品路径，不是可选项
- **账户**：MySQL RBAC（`admin` / `member`）；无库时回退 `.env` 单账号（仅应急）
- **文档**：开发规则 [`rules/agent.md`](rules/agent.md) · 架构 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · 视觉 [`docs/DESIGN.md`](docs/DESIGN.md) · 协作 [`docs/BRANCH_RULES.md`](docs/BRANCH_RULES.md)

## 产品功能

| 能力 | 做什么 |
|------|--------|
| **自选标的** | 观察池卡片 / 列表：实时行情、综合评分、评级（可买入 / 观察 / 不追等）、火花图与板块筛选 |
| **利空门禁** | 「利空通过 / 未过」：分数够仍须你复核；通过且 ≤14 天才允许「可买入」，否则最高「观察」 |
| **持仓与预警** | 登记持仓；破均线、止盈回撤、五灯仓位等告警；可一键写入纪律日记（不改仓、不下单） |
| **策略引擎** | 侧栏抽屉看纪律摘要：三原则、五灯、评分档位等（原文在 `knowledge/`） |
| **板块资金** | 板块净流入 / 流出排行，辅助看资金偏好 |
| **盘后选股池** | 按纪律初筛候选；上榜 ≠ 可买，加入自选后仍要过利空门禁 |
| **竞价异动榜** | 开盘竞价异动排序，适合盘前扫一眼 |
| **纪律日记** | 告警留痕：当时什么票、什么级别、建议什么、你怎么做；支持关键词与级别搜索 |
| **Jarvis 对话** | 基于知识库 + 行情 / 持仓 / 日记做参谋；结论可带补丁，你确认后才写入 |
| **知识库**（管理员） | 在网页维护 / 上传策略文档（md、pdf、docx 等），改完 `reindex.sh` 重建向量 |
| **Cursor MCP** | 同一套业务能力挂到 Cursor；只读随意，写入仅可信环境 |

**不做的事**：不下单、不接券商、不替你承担买卖决策；日记与预警只提醒与留痕，不会自动平仓。

网页侧栏大致对应：自选 · 板块资金 · 盘后选股 · 竞价 · 纪律日记 · 持仓 ·（管理员）知识库 · 对话。

## 快速启动

需要本机已装 Docker（拉 MySQL / Milvus），以及 Python **≥ 3.10**（推荐 3.12）。第一次 `start.sh` 会自动建 `backend/.venv`。

```bash
cp .env.example .env   # 至少填 LLM_API_KEY；库密码按需改
bash start.sh          # 前端 :5173 · 后端 :1690 · 按需拉起 MySQL / Milvus
bash stop.sh           # 只停网页进程
bash stop-all.sh       # 网页 + MySQL + Milvus / Attu（数据卷保留）
bash reindex.sh        # 改过 knowledge/ 或分析、沉淀后，重建 Milvus 索引
```

浏览器：[http://127.0.0.1:5173](http://127.0.0.1:5173)  
默认账号：`.env` 的 `AUTH_ACCOUNT` / `AUTH_PASSWORD`（预置管理员 `jarvis`）

后端日志：`/tmp/jarvis-backend.log`（可 `tail -f`）。根目录脚本是稳定入口，实现在 `scripts/`。

| 脚本 | 作用 |
|------|------|
| `start.sh` | 启前后端，并拉起 MySQL + Milvus 容器 |
| `stop.sh` | 只停前端 / 后端进程 |
| `stop-all.sh` | 停网页 + `jarvis-mysql` + `jarvis-milvus` / Attu |
| `reindex.sh` | 把 `knowledge/*.md`、分析底稿、沉淀切块写入 **Milvus** |
| `scripts/mysql.sh` | `up \| down \| status`（`deploy/mysql`） |
| `scripts/milvus.sh` | `up \| down \| status`（`deploy/milvus`） |
| `scripts/deploy.sh` | `build` 打镜像 / `save` 导出 tar / `up` 启动（见 [`deploy/README.md`](deploy/README.md)） |
| `scripts/mcp.sh` | Cursor MCP（stdio，一般不必手动常驻） |

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
| 策略原文 | `knowledge/*.md` | 源文件；管理员可在网页「知识库」编辑 / 上传，改完执行 `reindex.sh` |
| 业务数据 | MySQL（Docker 卷 + 专用表） | 观察池、持仓、分析、日记、沉淀、提案、对话流水、RBAC；SQL 见 `deploy/mysql/init/` |
| 知识向量 | Milvus collection `jarvis_kb` | 切块向量；可用 Attu 查看。不是 MySQL |
| 导出备份 | `bash deploy/mysql/export-data.sh` | 从库导出业务数据 |

仓库里**没有** `data/` 产品目录。若本机还留着旧的 `data/*.json`，启动时会迁进 MySQL 再删掉文件；新环境不必建这个文件夹。单测用内存，不代表产品存储。

服务器一体部署见 [`deploy/README.md`](deploy/README.md)（镜像里没有 `.env` 和持仓数据）。

`stop.sh` / `stop-all.sh` **不会**删 Docker 数据卷。不要对 compose 使用 `down -v`。

## 账户与权限

- 角色：`admin` 管理员、`member` 成员
- 预置用户：`.env` 的 `AUTH_ACCOUNT`（默认 `jarvis`）→ 管理员，首次写入 `users` 表
- 权限表：`users` / `roles` / `permissions` / `user_roles` / `role_permissions` / `auth_sessions`
- 除 `/api/auth/*`、`/api/health` 外需请求头 `x-jarvis-token`
- 知识库页要 `kb.manage`；重建索引要 `kb.reindex`

## MCP（Cursor 按需）

MCP 与网页共用 `services/`，不是另一套业务。一般由 Cursor 拉起，不必单独常驻。

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
| 启动 | 你手动常驻 | Cursor 配置后按需拉起 |
| 用途 | 仪表盘 + 站内对话 + 知识库维护 | 外部 Agent 调同一套 services |
| 写入 | 对话补丁须点「采纳」；日记按钮直接写库 | 工具可直接写库（仅可信环境） |
| 发现能力 | `GET /api/jarvis/capabilities` | MCP resource / tools |
## 目录

分层约定：**接入层（api / mcp / agents）→ 应用层（services）→ 领域（domain）/ 基建（infrastructure）**。  
业务只写在 `services/`；网页、MCP、对话工具都调同一套服务。细节见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

```
Jarvis/
├── README.md                      # 本文件：产品功能、启动、目录、RAG 与安全
├── .env.example                   # 环境变量模板（复制为 .env 后填写密钥）
├── .gitignore
├── pyrightconfig.json             # Python 跳转 / 分析路径（指向 backend/.venv）
├── start.sh / stop.sh / stop-all.sh / reindex.sh
│                                  # 根目录稳定入口，实际逻辑在 scripts/
│
├── rules/agent.md                 # 开发规则书（分层、HITL、MCP、新会话模板）
├── .cursor/rules/jarvis.mdc       # Cursor 常驻摘要规则
├── .github/CODEOWNERS             # main 分支代码归属
│
├── docs/
│   ├── ARCHITECTURE.md            # 分层、入库、RAG、RBAC、多入口
│   ├── DESIGN.md                  # 前端视觉规范
│   ├── decision-graph.md          # 单次对话决策图逐步走查
│   └── BRANCH_RULES.md            # 分支保护与协作约定
│
├── scripts/                       # 启停与运维脚本（被根目录 sh 转发）
│   ├── start.sh / stop.sh / stop-all.sh / reindex.sh
│   ├── dev-backend.sh             # 仅起 FastAPI（uvicorn :1690）
│   ├── mysql.sh / milvus.sh       # 本地 Docker 依赖 up/down/status
│   ├── mcp.sh                     # Cursor 按需拉起的 MCP stdio
│   └── deploy.sh                  # 打镜像 / 导出 tar / 服务器 up
│
├── deploy/                        # 服务器 / 一体部署
│   ├── README.md                  # 打包与上线说明
│   ├── Dockerfile / compose.yml   # 应用镜像与编排
│   ├── mysql/                     # MySQL compose、建表 SQL、导出脚本
│   └── milvus/                    # Milvus + Attu compose
│
├── knowledge/                     # 策略纪律原文（Markdown，改完需 reindex）
│   ├── Jarvis角色.md / 知识库索引.md
│   ├── 三原则两防线.md / 五灯仓位.md / 评分与分类.md
│   ├── 持仓预警.md / 主升第一天.md / …
│
├── backend/                       # FastAPI 后端（工作目录、venv 在此）
│   ├── .venv/                     # Python 3.12 虚拟环境
│   ├── requirements.txt
│   ├── tests/                     # pytest：store / 写入 / RAG / 身份
│   └── app/
│       ├── main.py                # 组合根：路由、鉴权中间件、行情循环、启动迁库
│       ├── core/                  # 横切
│       │   ├── config.py          # 读 .env：LLM / MySQL / Milvus / 间隔
│       │   └── deps.py            # 登录用户、权限校验
│       ├── api/                   # HTTP 薄路由，只调 services
│       │   ├── health.py          # GET /api/health
│       │   ├── auth.py            # 登录 / 登出 / 当前用户
│       │   ├── market.py          # 行情、K 线、选股、竞价、板块资金
│       │   ├── journal.py         # 纪律日记
│       │   ├── positions.py       # 持仓
│       │   ├── analyses.py        # 分析底稿 / 利空复核
│       │   ├── codes.py           # 观察池搜索与加减
│       │   ├── jarvis.py          # 对话、补丁确认、沉淀确认
│       │   ├── knowledge.py       # 知识库维护（管理员）
│       │   └── services.py        # 能力发现与 invoke（路径仍 /capabilities）
│       ├── mcp/                   # MCP Server（stdio，Cursor 按需拉起）
│       ├── agents/                # 站内对话 Agent
│       │   ├── chat.py            # 对话入口
│       │   ├── common.py          # 补丁/意图解析
│       │   └── graph/             # LangGraph：state / tools / graph / runner
│       ├── services/              # 唯一业务入口（网页 / MCP / 工具共用）
│       │   ├── journal.py         # 日记
│       │   ├── positions.py       # 持仓
│       │   ├── analyses.py        # 分析
│       │   ├── codes.py           # 观察池
│       │   ├── quotes.py          # 行情快照与评分
│       │   ├── screen.py          # 盘后选股 / 竞价 / 板块资金
│       │   ├── memory.py          # 对话沉淀读写
│       │   ├── patches.py         # 确认后执行 strategy_patch
│       │   ├── conversations.py   # 对话流水
│       │   ├── auth.py            # 登录会话
│       │   ├── knowledge.py       # 知识库文档 CRUD / 重建索引
│       │   ├── rag.py             # 对话检索：扩查询、多路召回、重排
│       │   └── registry.py        # 能力清单，供 MCP / invoke 发现
│       ├── domain/                # 纯规则，不碰数据库
│       │   ├── codes.py           # 股票代码规范化（600693 → sh600693）
│       │   └── memory.py          # 沉淀卡片规范化 / 检索打分
│       ├── infrastructure/        # 外部系统与落库
│       │   ├── persistence/       # MySQL：各业务表 store + schema/migrate/identity
│       │   ├── kb/                # 知识库：切块 / 抽取 / 向量 / 检索 / 重排 / Milvus
│       │   ├── market/            # 腾讯等行情拉取与缓存
│       │   └── llm.py             # DeepSeek 客户端与系统提示词
│       └── scripts/reindex_kb.py  # 重建知识库索引（reindex.sh 调用）
│
└── frontend/                      # Vue3 + Pinia + Vite（开发 :5173）
    ├── package.json
    └── src/
        ├── main.js / App.vue / style.css
        ├── api/index.js           # axios 封装，统一带登录 token
        ├── views/                 # 页面：工作区 / 自选标的
        ├── components/            # 卡片、日记、知识库、对话、选股等面板
        ├── stores/                # dashboard / auth / chat
        └── utils/                 # 五灯信号、评分展示、Markdown
```

## 站内对话（RAG）

```
ChatPanel
  → POST /api/jarvis/chat
  → agents/chat.py → graph/runner.py
  → services/rag.py（扩查询 + 向量/关键词 + RRF + 可选 rerank）
  → DeepSeek（可再调只读工具：行情 / 持仓 / 日记 / 知识库 / 沉淀）
  → 结论 + 可选 strategy_patch / memory_patch
  → 你点「采纳」后才走 services/patches.py 或 services/memory.py 落库
```

首页预警「记日记」不经过对话，直接 `POST /api/journal` → `services/journal.py`。

只读工具可随时调；写入在站内对话必须 HITL。DeepSeek **没有** embedding 接口。向量 / 重排看 `.env` 的 `EMBEDDING_*`、`RERANK_*`。改完知识库或沉淀后执行 `bash reindex.sh`。

逐步走查：[`docs/decision-graph.md`](docs/decision-graph.md)。

## 单测

```bash
cd backend && .venv/bin/pytest -q
```

测试走内存存储，不依赖本机 MySQL。覆盖 store 往返、持仓写入、日记、RAG 扩查询、身份校验等。

## 安全

- API Key、MySQL 密码只放 `.env`，不要提交、不要写进镜像  
- MCP 写入会直接改库，只在自己机器 / 可信环境使用  
- 公开仓库勿提交持仓、对话流水、`.env`；勿把旧 `data/*.json` 加回 Git  
- 分层与调用链以 `docs/ARCHITECTURE.md` 为准
