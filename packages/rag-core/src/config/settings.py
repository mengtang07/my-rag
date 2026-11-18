"""配置管理

按模块划分前缀：通用 / WEB_ / DB_ / MILVUS_ / LLM_ / RAG_ / LOG_。
钉钉的配置独立在 `config/dingding_setting.py`。
每个前缀一个配置类，模块级暴露单例，调用方 `from config import db_settings`。

环境变量文件统一放在仓库最外层：`.env`
（样例是 `.env.example`，复制一份改名即可）。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 本包所在目录（config/）
CONFIG_DIR: Path = Path(__file__).resolve().parent
# 仓库根目录（config/ → src/ → rag-core/ → packages/ → 仓库根）
PROJECT_ROOT: Path = CONFIG_DIR.parents[3]


def _resolve_env_file() -> str:
    """找到环境变量文件

    只有仓库最外层的 `.env`；没有就退回当前工作目录，
    再没有也不报错（pydantic-settings 会直接用字段默认值）。
    """
    root_env = PROJECT_ROOT / ".env"
    if root_env.is_file():
        return str(root_env)
    return str(Path.cwd() / ".env")


ENV_FILE: str = _resolve_env_file()


class _BaseSettingsWithEnv(BaseSettings):
    """所有配置类的基类

    注意：子类的 `model_config` 必须**重复声明** `env_file`。
    pydantic-settings 在子类里换掉整个 `model_config` 时，
    只写 `env_prefix` 会把 `env_file` 一起冲掉，`.env` 就读不到了。
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


# ---------- 通用 ----------
class _CommonSettings(_BaseSettingsWithEnv):
    """通用配置"""

    environment: str = "development"


# ---------- Web 服务 ----------
class _WebSettings(_BaseSettingsWithEnv):
    """Web 服务配置"""

    app_name: str = "my-rag API"

    # 跨域配置
    cors_origins: str = "*"
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"
    cors_expose_headers: str = ""
    cors_allow_credentials: bool = False
    cors_max_age: int = 600

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="WEB_", extra="ignore")


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


# ---------- Milvus ----------
class _MilvusSettings(_BaseSettingsWithEnv):
    """Milvus 向量库配置"""

    uri: str = "http://localhost:19530"
    collection: str = "rag_chunks"
    # 必须与网关 embedding 模型的实际维度一致，否则插不进去
    embed_dim: int = 1024
    search_ef: int = 64
    batch_size: int = 500
    timeout: int = 30
    token: str = ""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="MILVUS_", extra="ignore")


# ---------- LiteLLM 网关 ----------
class _LLMSettings(_BaseSettingsWithEnv):
    """LiteLLM 网关配置（对话 / 向量化 / 重排都走它）"""

    api_base: str = "http://localhost:4000"
    api_key: str = ""
    chat_model: str = "chat-standard"
    embed_model: str = "text-embedding"
    rerank_model: str = "rerank"
    embed_batch_size: int = 32
    timeout: int = 60
    temperature: float = 0.2
    max_tokens: int = 1024
    context_window: int = 32000

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="LLM_", extra="ignore")


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


# ---------- 日志 ----------
class _LogSettings(_BaseSettingsWithEnv):
    """日志配置"""

    level: str = "INFO"

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="LOG_", extra="ignore")


common_settings = _CommonSettings()
web_settings = _WebSettings()
db_settings = _DBSettings()
milvus_settings = _MilvusSettings()
llm_settings = _LLMSettings()
rag_settings = _RAGSettings()
log_settings = _LogSettings()
