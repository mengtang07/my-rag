"""跨域中间件"""

from fastapi.middleware.cors import CORSMiddleware

from config import web_settings


def _split(value: str) -> list[str]:
    """把逗号分隔的配置拆成列表"""
    return [item.strip() for item in value.split(",") if item.strip()]


MIDDLEWARE: tuple[type, dict[str, object]] = (
    CORSMiddleware,
    {
        "allow_origins": _split(web_settings.cors_origins) or ["*"],
        "allow_methods": _split(web_settings.cors_allow_methods) or ["*"],
        "allow_headers": _split(web_settings.cors_allow_headers) or ["*"],
        "expose_headers": _split(web_settings.cors_expose_headers),
        "allow_credentials": web_settings.cors_allow_credentials,
        "max_age": web_settings.cors_max_age,
    },
)
