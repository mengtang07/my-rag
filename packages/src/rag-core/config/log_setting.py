"""日志配置"""

from pydantic_settings import SettingsConfigDict

from config.base_setting import ENV_FILE, _BaseSettingsWithEnv


class _LogSettings(_BaseSettingsWithEnv):
    """日志配置"""

    level: str = "INFO"

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="LOG_", extra="ignore")


log_settings = _LogSettings()
