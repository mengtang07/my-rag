"""LiteLLM 网关配置"""

from pydantic_settings import SettingsConfigDict

from config.settings import ENV_FILE, _BaseSettingsWithEnv


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


llm_settings = _LLMSettings()
