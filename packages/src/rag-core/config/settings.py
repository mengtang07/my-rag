"""配置管理

按模块划分前缀：通用 / DB_ / RAG_。
Web、日志、Milvus、LiteLLM 网关、钉钉各自独立在 `config/web_setting.py`、
`config/log_setting.py`、`config/milvus_setting.py`、`config/llm_setting.py`、
`config/dingding_setting.py`。
配置基类与环境变量文件定位在 `config/base_setting.py`。
每个前缀一个配置类，模块级暴露单例，调用方 `from config import db_settings`。

环境变量文件统一放在仓库最外层：`.env`
（样例是 `.env.example`，复制一份改名即可）。
"""

from pydantic_settings import SettingsConfigDict

from config.base_setting import ENV_FILE, _BaseSettingsWithEnv

# ---------- 通用 ----------
class _CommonSettings(_BaseSettingsWithEnv):
    """通用配置"""

    environment: str = "development"


# ---------- 数据库 ----------
class _DBSettings(_BaseSettingsWithEnv):
    """PostgreSQL 配置（存放文档元数据、切块正文、会话与消息）"""

    host: str = "localhost"
    port: str = "5433"
    name: str = "rag_db"
    user: str = "admin"
    password: str = "123123"
    echo: bool = False

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="DB_", extra="ignore")


# ---------- 检索增强 ----------
class _RAGSettings(_BaseSettingsWithEnv):
    """切块与检索参数"""

    chunk_max_chars: int = 1200
    chunk_min_chars: int = 80
    chunk_overlap: int = 150
    top_k: int = 5
    max_context_tokens: int = 6000
    history_turns: int = 6
    max_file_mb: int = 20
    use_rerank: bool = False

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="RAG_", extra="ignore")


common_settings = _CommonSettings()
db_settings = _DBSettings()
rag_settings = _RAGSettings()
