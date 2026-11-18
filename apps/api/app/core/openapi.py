"""OpenAPI 文档定制

把 `/api/` 下的成功响应 schema 包装成统一信封结构，
让 `/docs` 里展示出来的就是接口真实返回的形状。
"""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

API_PREFIX: str = "/api/"
HTTP_METHODS: tuple[str, ...] = ("get", "post", "put", "delete", "patch")
WRAPPED_STATUS_CODES: frozenset[int] = frozenset({200, 201})

# SSE 端点不设 response_model，文档里是它自己的事件协议，不包装
EXEMPT_PATHS: frozenset[str] = frozenset({"/api/chat/stream"})


def _model_name(schema: dict[str, Any]) -> str:
    """从 schema 里推出模型名（用于注册信封组件）"""
    reference = schema.get("$ref")
    if reference:
        return reference.rsplit("/", 1)[-1]

    items = schema.get("items")
    if isinstance(items, dict):
        inner = items.get("$ref")
        if inner:
            return f"List_{inner.rsplit('/', 1)[-1]}"

    return "Any"


def _data_schema(schema: dict[str, Any], model_name: str) -> dict[str, Any]:
    """信封里 `data` 字段的 schema"""
    if "$ref" in schema:
        return {"$ref": f"#/components/schemas/{model_name}"}
    return schema


def _build_envelope(
    schema: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any]:
    """构造（或复用）信封 schema"""
    model_name = _model_name(schema)
    component_name = f"ApiResponse_{model_name}"

    if component_name not in components:
        components[component_name] = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "example": "0"},
                "data": _data_schema(schema, model_name),
                "message": {"type": "string", "example": "success"},
            },
            "required": ["code", "data", "message"],
            "title": component_name,
        }

    return {"$ref": f"#/components/schemas/{component_name}"}


def setup_openapi(app: FastAPI) -> None:
    """接管 `app.openapi`，包装 `/api/` 下的成功响应"""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        components = schema.setdefault("components", {}).setdefault("schemas", {})

        for path, operations in schema.get("paths", {}).items():
            if not path.startswith(API_PREFIX) or path in EXEMPT_PATHS:
                continue

            for method, operation in operations.items():
                if method not in HTTP_METHODS:
                    continue

                responses = operation.get("responses", {})
                for status_code in list(responses):
                    if not str(status_code).isdigit():
                        continue
                    if int(status_code) not in WRAPPED_STATUS_CODES:
                        continue

                    content = responses[status_code].get("content", {})
                    json_content = content.get("application/json")
                    if not json_content:
                        continue

                    original = json_content.get("schema")
                    if not isinstance(original, dict):
                        continue

                    json_content["schema"] = _build_envelope(original, components)

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
