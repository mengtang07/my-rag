"""钉钉开放平台配置"""

from pydantic_settings import SettingsConfigDict

from config.base_setting import ENV_FILE, _BaseSettingsWithEnv


class _DingtalkSettings(_BaseSettingsWithEnv):
    """钉钉开放平台配置

    `operator_id` 必须是用户的 **unionId**，不是 userId ——
    拿错了接口会返回权限错误。
    """

    app_key: str = ""
    app_secret: str = ""
    operator_id: str = ""
    workspace_id: str = ""
    base_url: str = "https://api.dingtalk.com"
    timeout: int = 30

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="DINGTALK_", extra="ignore")


dingtalk_settings = _DingtalkSettings()
