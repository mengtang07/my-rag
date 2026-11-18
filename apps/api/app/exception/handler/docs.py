"""生成 OpenAPI 文档里的错误码说明表"""

from app.exception.handler.errors import ERROR_MAP, PROTOCOL_ERROR_MAP


def generate_error_docs() -> str:
    """把错误码表渲染成 Markdown，作为 FastAPI 的 description

    Returns:
        Markdown 文本
    """
    lines: list[str] = [
        "个人知识库 RAG 接口。",
        "",
        "所有 `/api/` 开头的接口响应体统一为：",
        "",
        "```json",
        '{"code": "0", "data": {}, "message": "success"}',
        "```",
        "",
        "`code` 为 `0` 表示成功，非 `0` 为业务错误码。",
        "",
        "## 业务错误码",
        "",
        "| 错误码 | HTTP 状态 | 说明 | 异常类型 |",
        "| --- | --- | --- | --- |",
    ]

    for exc_type, (code, status, message) in ERROR_MAP.items():
        lines.append(f"| `{code}` | {status} | {message} | `{exc_type.__name__}` |")

    lines.extend(
        [
            "",
            "## 协议错误",
            "",
            "| HTTP 状态 | 说明 |",
            "| --- | --- |",
        ]
    )

    for status, message in PROTOCOL_ERROR_MAP.items():
        lines.append(f"| {status} | {message} |")

    return "\n".join(lines)
