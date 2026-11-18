"""跨域中间件

浏览器的同源策略会拦下跨域请求的响应，这里通过一组响应头告诉浏览器
"哪些来源可以读我、可以发什么请求、可以读我哪些响应头"。

所有配置都来自 `.env`（前缀 `WEB_CORS_`），改配置不用改代码：

```shell
WEB_CORS_ORIGINS=*                              # 来源白名单，逗号分隔，* 表示不限
WEB_CORS_ALLOW_METHODS=*                        # 允许的请求方法
WEB_CORS_ALLOW_HEADERS=*                        # 允许的请求头
WEB_CORS_EXPOSE_HEADERS=X-Process-Time          # 允许前端读取的响应头
WEB_CORS_ALLOW_CREDENTIALS=false                # 是否允许携带 Cookie
WEB_CORS_MAX_AGE=600                            # 预检结果缓存秒数
```
"""

from typing import Any

from starlette.middleware.cors import CORSMiddleware

from app.core.config import web_settings


def _split_csv(value: str) -> list[str]:
    """把逗号分隔的配置值拆成列表"""
    return [item.strip() for item in value.split(",") if item.strip()]


# 允许的来源；["*"] 表示不限制，空列表表示不放行任何来源
origins: list[str] = _split_csv(web_settings.cors_origins)

MIDDLEWARE: tuple[Any, dict[str, Any]] = (
    CORSMiddleware,
    {
        "allow_origins": origins,
        "allow_credentials": web_settings.cors_allow_credentials,
        "allow_methods": _split_csv(web_settings.cors_allow_methods) or ["*"],
        "allow_headers": _split_csv(web_settings.cors_allow_headers) or ["*"],
        "expose_headers": _split_csv(web_settings.cors_expose_headers),
        "max_age": web_settings.cors_max_age,
    },
)
