"""应用入口：创建 app、注册中间件与异常处理器"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from config import common_settings, web_settings
from app.core.middleware import register_middleware
from app.core.openapi import setup_openapi
from app.exception import BusinessException
from app.exception.handler.docs import generate_error_docs
from app.exception.handler.handlers import exception_handler

app = FastAPI(
    title=web_settings.app_name,
    description=generate_error_docs(),
    docs_url=None if common_settings.environment == "production" else "/docs",
    redoc_url=None if common_settings.environment == "production" else "/redoc",
    openapi_url=(
        None if common_settings.environment == "production" else "/openapi.json"
    ),
)

# 注册中间件（统一响应结构）
register_middleware(app)

# 设置 OpenAPI 文档格式（成功响应包装成统一结构）
setup_openapi(app)

# 注册全局异常处理器（覆盖 Starlette/FastAPI 内置处理器 + 兜底未知异常）
# BusinessException 必须单独注册：否则业务异常会落到最外层的 ServerErrorMiddleware，
# 它在所有用户中间件之外（耗时统计拿不到），而且处理完还会把异常重新抛给服务器
app.add_exception_handler(RequestValidationError, exception_handler)
app.add_exception_handler(HTTPException, exception_handler)
app.add_exception_handler(BusinessException, exception_handler)
app.add_exception_handler(Exception, exception_handler)


# 注册路由
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.health import system_router
from app.api.search import router as search_router

app.include_router(health_router)
app.include_router(system_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(conversations_router)
