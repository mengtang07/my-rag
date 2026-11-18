from pydantic_settings import BaseSettings


class _BaseSettingsWithEnv(BaseSettings):
    # 配置读取方式
    model_config = {"env_file": ".env", "extra": "ignore"}  # env文件的位置


# 通用配置
class _CommonSettings(_BaseSettingsWithEnv):
    environment: str = "development"


# web服务配置
class _WebSettings(_BaseSettingsWithEnv):
    app_name: str = "Web Service API"  # 实际读取 WEB_APP_NAME

    # 跨域配置
    cors_origins: str = ""  # 跨域白名单，多个来源用逗号分隔，* 表示允许所有
    cors_allow_methods: str = "*"  # 允许的请求方法，逗号分隔
    cors_allow_headers: str = "*"  # 允许的请求头，逗号分隔
    cors_expose_headers: str = ""  # 允许前端读取的响应头，逗号分隔
    cors_allow_credentials: bool = False  # 是否允许携带 Cookie 等凭证
    cors_max_age: int = 600  # 预检结果的缓存秒数

    # 配置读取方式
    model_config = {"env_prefix": "WEB_"}


# 数据库配置
class _DBSettings(_BaseSettingsWithEnv):
    host: str = ""
    port: str = ""
    name: str = ""
    user: str = ""
    password: str = ""

    model_config = {"env_prefix": "DB_"}


# 阿里云 OSS 配置
class _OSSSettings(_BaseSettingsWithEnv):
    access_key_id: str = ""  # OSS_ACCESS_KEY_ID
    access_key_secret: str = ""  # OSS_ACCESS_KEY_SECRET
    bucket_name: str = ""  # OSS_BUCKET_NAME
    endpoint: str = ""  # OSS_ENDPOINT，如 oss-cn-hangzhou.aliyuncs.com
    expire_seconds: int = 3600  # 上传凭证有效期（秒）
    mime_types: str = ""  # 允许上传的 MIME 类型，逗号分隔；留空表示不限制
    dir_strategy: str = "date"  # 存储目录策略：date（按日期分层）/ flat（扁平）

    model_config = {"env_prefix": "OSS_"}


common_settings = _CommonSettings()
web_settings = _WebSettings()
db_settings = _DBSettings()
oss_settings = _OSSSettings()
