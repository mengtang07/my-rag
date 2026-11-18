"""OpenAPI 文档定制

统一响应中间件会把 `/api/` 接口的响应体包装成：

```json
{"code": "0", "data": ..., "message": "success"}
```

但 `FastAPI` 默认生成的 `openapi.json` 里，响应体 schema 还是不带包装的原始结构，
接口文档和真实返回对不上。

这里接管 `app.openapi`，在 schema 生成之后做一次后处理：把 `/api/` 下所有接口
成功响应（200/201）的 schema 替换成包装后的结构，让文档与实际返回保持一致。
"""

from typing import Any

from fastapi import FastAPI

# 参与包装的接口前缀
API_PREFIX: str = "/api/"

# 需要遍历的 HTTP 方法
HTTP_METHODS: tuple[str, ...] = ("get", "post", "put", "delete", "patch")

# 只包装这些状态码的成功响应
WRAPPED_STATUS_CODES: frozenset[int] = frozenset({200, 201})

# 无响应体的状态码：保持原样（包装了也没有内容可包）
NO_CONTENT_STATUS_CODES: frozenset[int] = frozenset({204, 304})


def _envelope_properties(data_schema: dict[str, Any]) -> dict[str, Any]:
    """统一响应体的三个字段"""
    return {
        "code": {
            "type": "string",
            "description": "状态码，0 表示成功",
            "example": "0",
        },
        "data": data_schema,
        "message": {
            "type": "string",
            "description": "提示信息",
            "example": "success",
        },
    }


def _envelope(data_schema: dict[str, Any]) -> dict[str, Any]:
    """内联包装：直接把 schema 展开在响应里，不登记到 components"""
    return {
        "type": "object",
        "properties": _envelope_properties(data_schema),
        "required": ["code", "data", "message"],
    }


def _register_wrapper(
    openapi_schema: dict[str, Any],
    wrapper_name: str,
    title: str,
    data_schema: dict[str, Any],
) -> dict[str, Any]:
    """把包装后的 schema 登记到 components.schemas，返回它的 $ref

    登记成独立 schema 而不是内联展开，多个接口可以共用同一份定义。
    """
    components: dict[str, Any] = openapi_schema.setdefault("components", {})
    schemas: dict[str, Any] = components.setdefault("schemas", {})

    if wrapper_name not in schemas:
        schemas[wrapper_name] = {
            "title": title,
            "type": "object",
            "properties": _envelope_properties(data_schema),
            "required": ["code", "data", "message"],
        }

    return {"$ref": f"#/components/schemas/{wrapper_name}"}


def _wrap_ref_schema(
    openapi_schema: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    """包装 $ref 类型的响应体"""
    ref_name: str = schema["$ref"].split("/")[-1]
    return _register_wrapper(
        openapi_schema,
        wrapper_name=f"ApiResponse_{ref_name}",
        title=f"ApiResponse[{ref_name.replace('_', ' ')}]",
        data_schema=schema,
    )


def _wrap_array_schema(
    openapi_schema: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    """包装数组类型的响应体"""
    items = schema.get("items")
    if isinstance(items, dict) and "$ref" in items:
        item_name: str = items["$ref"].split("/")[-1]
        return _register_wrapper(
            openapi_schema,
            wrapper_name=f"ApiResponse_List_{item_name}",
            title=f"ApiResponse[List[{item_name.replace('_', ' ')}]]",
            data_schema=schema,
        )

    return _envelope(schema)


def setup_openapi(app: FastAPI) -> None:
    """接管 `app.openapi`，生成后把成功响应包装成统一结构"""
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema: dict[str, Any] = original_openapi()

        for path, path_item in schema.get("paths", {}).items():
            if not path.startswith(API_PREFIX):
                continue

            for method in HTTP_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue

                responses: dict[str, Any] = operation.get("responses", {})
                for status_code_str, response in list(responses.items()):
                    # 状态码可能不是数字（例如 "default"），跳过
                    if not status_code_str.isdigit():
                        continue

                    status_code = int(status_code_str)

                    # 无响应体的状态码保持原样
                    if status_code in NO_CONTENT_STATUS_CODES:
                        continue

                    # 错误响应不在这里展示，由应用描述里的错误码说明表统一交代
                    if status_code not in WRAPPED_STATUS_CODES:
                        del responses[status_code_str]
                        continue

                    json_content = response.get("content", {}).get("application/json")
                    if json_content is None:
                        continue

                    original_schema = json_content.get("schema")
                    if original_schema is None:
                        continue

                    if "$ref" in original_schema:
                        wrapped = _wrap_ref_schema(schema, original_schema)
                    elif original_schema.get("type") == "array":
                        wrapped = _wrap_array_schema(schema, original_schema)
                    else:
                        wrapped = _envelope(original_schema)

                    json_content["schema"] = wrapped

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
