"""端到端冒烟：验证骨架真的能用

前置条件：`make docker-up` + `make db-init` + `make milvus-init`，
并且服务已经在跑（`make dev`）。

用法：
    uv run --package api python apps/api/scripts/smoke.py
"""

import sys
import time
from typing import Any

import httpx

BASE_URL: str = "http://localhost:8088"

SAMPLE_MARKDOWN = """# 部署手册

## 前置条件

需要 Docker 29 以上版本与 8GB 内存。

## 安装步骤

执行 `docker compose up -d` 启动依赖服务。

## 常见问题

### 端口冲突

本机 5432 已被占用，compose 把 PostgreSQL 映射到了 5433。
"""

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """记录一条断言结果"""
    if condition:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name}{f' —— {detail}' if detail else ''}")
        _failures.append(name)


def main() -> int:
    """跑一遍冒烟断言"""
    print("== 1. 服务存活 ==")
    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=5)
    except httpx.HTTPError as exc:
        print(f"  ✗ 连不上 {BASE_URL}：{exc}")
        print("     先跑 `make dev` 再执行冒烟")
        return 1

    check("GET /health 返回 200", health.status_code == 200, str(health.status_code))
    check("健康检查不套信封", health.json() == {"status": "ok"}, health.text)

    print("== 2. 系统状态 ==")
    status = httpx.get(f"{BASE_URL}/api/system/status", timeout=30).json()
    data = status.get("data", {})
    check("统一信封 code == 0", status.get("code") == "0", status.get("message", ""))
    check("数据库连通", data.get("database") == "ok", str(data.get("database")))
    check("向量库连通", data.get("milvus") == "ok", str(data.get("milvus")))
    check(
        "集合维度与配置一致",
        data.get("details", {}).get("milvus", {}).get("collection_dim") == 1024,
        str(data.get("details", {}).get("milvus")),
    )

    print("== 3. 文档入库 ==")
    response = httpx.post(
        f"{BASE_URL}/api/documents",
        files={"file": ("冒烟测试.md", SAMPLE_MARKDOWN.encode("utf-8"), "text/markdown")},
        timeout=120,
    )
    check("上传返回 201", response.status_code == 201, response.text[:200])
    ingest = response.json().get("data", {})
    document_id = ingest.get("document_id")
    check("状态是 ready", ingest.get("status") == "ready", str(ingest.get("status")))
    check("切块数大于 0", (ingest.get("chunk_count") or 0) > 0, str(ingest.get("chunk_count")))

    print("== 4. 落库可见 ==")
    listing = httpx.get(f"{BASE_URL}/api/documents", timeout=30).json()
    total = listing.get("data", {}).get("total", 0)
    check("文档列表能看到刚上传的", total >= 1, f"total={total}")

    print("== 5. 检索命中 ==")
    search = httpx.post(
        f"{BASE_URL}/api/search",
        json={"query": "端口冲突怎么办", "top_k": 3},
        timeout=60,
    ).json()
    hits = search.get("data", {}).get("hits", [])
    check("检索有命中", len(hits) >= 1, f"hits={len(hits)}")
    if hits:
        # 断言「命中的是讲端口冲突的那一节」，而不是「命中哪个文档」——
        # 库里可能已经有内容相同的文档，谁排第一说不准
        check(
            "命中的是端口冲突那一节",
            "端口冲突" in hits[0].get("heading_path", ""),
            str(hits[0].get("heading_path")),
        )
        check("命中带标题路径", bool(hits[0].get("heading_path")), str(hits[0]))

    print("== 6. 流式问答 ==")
    frames: list[str] = []
    body_parts: list[str] = []
    with httpx.stream(
        "POST",
        f"{BASE_URL}/api/chat/stream",
        json={"question": "部署需要什么前置条件？"},
        timeout=120,
    ) as stream:
        content_type = stream.headers.get("content-type", "")
        for line in stream.iter_lines():
            if line.startswith("event:"):
                frames.append(line.split(":", 1)[1].strip())
            elif line.startswith("data:"):
                body_parts.append(line)

    check("content-type 是 text/event-stream", content_type.startswith("text/event-stream"), content_type)
    check("先推 sources", frames[:1] == ["sources"], str(frames[:3]))
    check("中间是 token", "token" in frames, str(frames))
    check("最后是 done", frames[-1:] == ["done"], str(frames[-3:]))
    check("SSE 没被统一信封包住", not "".join(body_parts).lstrip().startswith('{"code"'))

    print("== 7. 删除 ==")
    deleted = httpx.delete(f"{BASE_URL}/api/documents/{document_id}", timeout=30)
    check("删除返回 204", deleted.status_code == 204, str(deleted.status_code))
    missing = httpx.get(f"{BASE_URL}/api/documents/{document_id}", timeout=30)
    check("删完再取是 404", missing.status_code == 404, str(missing.status_code))
    check(
        "错误码是 404001",
        missing.json().get("code") == "404001",
        missing.text[:120],
    )

    print()
    if _failures:
        print(f"冒烟失败：{len(_failures)} 条断言没过 —— {'、'.join(_failures)}")
        return 1

    print("冒烟通过：全部断言成立")
    return 0


if __name__ == "__main__":
    sys.exit(main())
