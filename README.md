# Jarvis

个人交易参谋：仪表盘（行情 / 策略 / 持仓）+ 本地知识库对话 + 策略演进提案。

- **前后分离**：Vue3 前端 + FastAPI 后端  
- **大模型**：DeepSeek（OpenAI 兼容）  
- **检索**：第一期本地轻量向量（字符 n-gram + 余弦），接口预留后续切 Milvus  
- **独立项目**：不修改 `dashboard` / `bussness_harnessos` 原仓  

## 快速启动

### 1. 配置

```bash
cd /Users/shuqin/workplace/develop/code/sq/Jarvis
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY
```

### 2. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 1690
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（默认 http://localhost:5173）。

### 4. 重建本地知识库索引

```bash
cd backend && source .venv/bin/activate
python -m app.scripts.reindex_kb
```

## 目录

```
Jarvis/
├── backend/          # FastAPI
├── frontend/         # Vue3
├── knowledge/        # 策略知识库 Markdown
├── data/             # positions / analyses / journal / vectordb
└── README.md
```

## 安全

- API Key 只放 `.env`，勿提交 Git、勿发到聊天  
- 若 Key 曾泄露，请立即在 DeepSeek 控制台轮换  
