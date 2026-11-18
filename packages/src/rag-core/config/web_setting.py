"""Web 服务配置"""

from pydantic_settings import SettingsConfigDict

from config.base_setting import ENV_FILE, _BaseSettingsWithEnv


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


web_settings = _WebSettings()
