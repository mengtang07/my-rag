"""中间件注册

中间件的执行顺序与注册顺序相反（后注册的位于最外层），
`call_next` 会依次穿过外层到内层，再按相反顺序返回。
"""

import inspect
from collections.abc import Callable
from functools import partial
from typing import Any, cast

from fastapi import FastAPI

from app.core.middleware import cors, process_time, response

# (中间件, 额外参数)
# 注意：注册顺序与执行顺序相反，后注册的位于最外层。
# 这里的顺序让执行顺序变成：统一响应 -> 跨域 -> 耗时统计 -> 路由
MIDDLEWARES: list[tuple[Callable[..., Any], dict[str, Any]]] = [
    process_time.MIDDLEWARE,
    cors.MIDDLEWARE,
    response.MIDDLEWARE,
]


def register_middleware(app: FastAPI) -> None:
    """把中间件注册到应用上

    - 类形式的中间件：走 `add_middleware`，额外参数交给构造器
    - 函数形式的中间件：走 `middleware("http")`，额外参数用 `partial` 绑定
    """
    for middleware, kwargs in MIDDLEWARES:
        if inspect.isclass(middleware):
            app.add_middleware(cast(Any, middleware), **kwargs)
        else:
            app.middleware("http")(cast(Any, partial(middleware, **kwargs)))
