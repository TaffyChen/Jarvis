from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jarvis_host: str = "127.0.0.1"
    jarvis_port: int = 1690

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    auth_account: str = "jarvis"
    auth_password: str = "change-me"
    auth_token_ttl_hours: int = 24

    # 仅用于启动时把遗留 JSON 迁进 MySQL；正式读写不依赖此目录，也不再自动创建
    data_dir: Path = ROOT / "data"
    knowledge_dir: Path = ROOT / "knowledge"
    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_collection: str = "jarvis_kb"
    milvus_port: int = 19530

    # hash=本地 n-gram hashing；openai=兼容 /embeddings（DeepSeek 无此接口）
    embedding_backend: str = "hash"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # 对话 RAG：召回后交叉编码重排（硅基流动 bge-reranker 等）
    rerank_enabled: bool = True
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rag_candidate_k: int = 12
    kb_upload_max_mb: int = 8

    mysql_host: str = ""
    mysql_port: int = 3307
    mysql_user: str = "jarvis"
    mysql_password: str = ""
    mysql_database: str = "jarvis"

    quote_interval_sec: int = 15
    kline_interval_sec: int = 300

    analysis_stale_days: int = 14

    # 决策图最多完整执行几轮工具；达到后强制不再下发 tools，逼模型收束回答
    jarvis_graph_max_tool_rounds: int = 4

    def model_post_init(self, __context) -> None:
        # .env 中的相对路径统一锚定到项目根，避免从 backend/ 启动时指错目录
        for name in ("data_dir", "knowledge_dir"):
            p = getattr(self, name)
            if not p.is_absolute():
                object.__setattr__(self, name, (ROOT / p).resolve())
            else:
                object.__setattr__(self, name, p.resolve())


settings = Settings()
settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
