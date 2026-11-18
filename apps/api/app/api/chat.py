"""对话接口

`/stream` 走 SSE。**刻意不设 `response_model`** —— 设了的话 OpenAPI 会把它
声明成 `application/json`，与实际返回的 `text/event-stream` 对不上。
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.vector_store import VectorStore, get_vector_store
from app.schema.chat import ChatRequest, ChatResponse
from app.service.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/stream", summary="流式问答（SSE）")
async def chat_stream(
    data: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> EventSourceResponse:
    """边检索边回答，逐段推送

    事件顺序：`sources`（引用来源，先推，界面立刻能显示）→ `token`（增量文本）→ `done`。
    """
    service = ChatService(db, llm=llm, vector_store=store)

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        async for event, payload in service.stream_answer(
            data.question,
            conversation_id=data.conversation_id,
            top_k=data.top_k,
        ):
            yield {
                "event": event,
                "data": json.dumps(payload, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/complete", response_model=ChatResponse, summary="非流式问答")
async def chat_complete(
    data: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    llm: Annotated[LiteLLMClient, Depends(get_llm_client)],
    store: Annotated[VectorStore, Depends(get_vector_store)],
) -> ChatResponse:
    """一次性返回完整答案（命令行与端到端测试用）"""
    return await ChatService(db, llm=llm, vector_store=store).complete_answer(
        data.question,
        conversation_id=data.conversation_id,
        top_k=data.top_k,
    )
