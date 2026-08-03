from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


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

    data_dir: Path = ROOT / "data"
    knowledge_dir: Path = ROOT / "knowledge"
    vector_dir: Path = ROOT / "data" / "vectordb"

    quote_interval_sec: int = 15
    kline_interval_sec: int = 300

    analysis_stale_days: int = 14

    def model_post_init(self, __context) -> None:
        # .env 中的相对路径统一锚定到项目根，避免从 backend/ 启动时指错目录
        for name in ("data_dir", "knowledge_dir", "vector_dir"):
            p = getattr(self, name)
            if not p.is_absolute():
                object.__setattr__(self, name, (ROOT / p).resolve())
            else:
                object.__setattr__(self, name, p.resolve())


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
settings.vector_dir.mkdir(parents=True, exist_ok=True)
