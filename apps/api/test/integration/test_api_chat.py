"""对话接口（含 SSE 流式）"""

from httpx import AsyncClient

from test.fakes import FakeLLM

MARKDOWN = """# 部署手册

## 前置条件

需要 Docker 29 以上版本与 8GB 内存。
"""


async def test_chat_complete_returns_answer_and_citations(
    client: AsyncClient,
) -> None:
    """非流式问答返回答案与引用"""
    await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    response = await client.post("/api/chat/complete", json={"question": "需要多少内存"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer"] == "根据资料回答"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["index"] == 1
    assert data["citations"][0]["document_title"] == "部署手册"


async def test_chat_stream_emits_sse_events(client: AsyncClient) -> None:
    """SSE 依次推 sources / token / done"""
    await client.post(
        "/api/documents",
        files={"file": ("部署手册.md", MARKDOWN.encode("utf-8"), "text/markdown")},
    )

    async with client.stream(
        "POST", "/api/chat/stream", json={"question": "需要多少内存"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: sources" in body
    assert "event: token" in body
    assert "event: done" in body
    # 关键：SSE 不能被统一信封包住
    assert not body.lstrip().startswith('{"code"')


async def test_chat_persists_conversation(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    """问答会落库成会话与消息"""
    response = await client.post("/api/chat/complete", json={"question": "你好"})
    data = response.json()["data"]

    conversation_id = data["conversation_id"]
    messages = await client.get(f"/api/conversations/{conversation_id}/messages")
    items = messages.json()["data"]["items"]

    assert len(items) == 2
    assert items[0]["role"] == "user"
    assert items[0]["content"] == "你好"
    assert items[1]["role"] == "assistant"
    assert items[1]["content"] == "根据资料回答"


async def test_history_is_passed_to_model(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    """多轮对话会把历史带进模型"""
    first = await client.post("/api/chat/complete", json={"question": "第一问"})
    conversation_id = first.json()["data"]["conversation_id"]

    await client.post(
        "/api/chat/complete",
        json={"question": "第二问", "conversation_id": conversation_id},
    )

    # 最后一次调用里应该带着上一轮的历史
    last_messages = fake_llm.calls[-1]
    roles = [message["role"] for message in last_messages]
    assert roles[0] == "system"
    assert roles[-1] == "user"
    assert len(last_messages) >= 3
