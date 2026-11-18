"""Milvus 向量库配置"""

from pydantic_settings import SettingsConfigDict

from config.settings import ENV_FILE, _BaseSettingsWithEnv


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


milvus_settings = _MilvusSettings()
