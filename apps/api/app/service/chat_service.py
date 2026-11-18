"""对话：检索 → 组装上下文 → 流式生成 → 落库

助手消息在**流结束后显式提交**：不依赖请求结束时依赖清理那一次提交，
流式响应发出时请求级 session 的生命周期还没走完。
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import llm_settings, rag_settings
from app.core.llm import LiteLLMClient, get_llm_client
from app.core.prompt import RAG_SYSTEM_PROMPT
from app.core.vector_store import VectorStore, get_vector_store
from app.model.conversation import Conversation
from app.model.message import ROLE_ASSISTANT, ROLE_USER, Message
from app.schema.chat import ChatResponse, Citation
from app.service.base import BaseService
from app.service.retrieval_service import RetrievedChunk, RetrievalService
from rag_core.text.estimate import estimate_tokens

# 上下文预算占模型窗口的比例，留 20% 余量
BUDGET_RATIO: float = 0.8
# 会话标题取首条问题的字数
TITLE_LENGTH: int = 40


class ChatService(BaseService):
    """问答编排"""

    def __init__(
        self,
        db: AsyncSession,
        llm: LiteLLMClient | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        super().__init__(db)
        self._llm = llm
        self._vector_store = vector_store

    @property
    def llm(self) -> LiteLLMClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def stream_answer(
        self,
        question: str,
        *,
        conversation_id: int | None = None,
        top_k: int | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """产出 SSE 事件

        事件顺序：`sources`（先给来源，界面立刻能显示）→ `token`（逐段增量）→ `done`。
        """
        conversation, messages, citations = await self._prepare(
            question, conversation_id, top_k
        )

        yield ("sources", {"citations": [item.model_dump() for item in citations]})

        parts: list[str] = []
        async for text in self.llm.stream_chat(messages):
            parts.append(text)
            yield ("token", {"text": text})

        answer = "".join(parts)
        message_id = await self._save_assistant_message(
            conversation.id, answer, citations
        )

        yield (
            "done",
            {"conversation_id": conversation.id, "message_id": message_id},
        )

    async def complete_answer(
        self,
        question: str,
        *,
        conversation_id: int | None = None,
        top_k: int | None = None,
    ) -> ChatResponse:
        """非流式问答（CLI 与端到端测试用）"""
        conversation, messages, citations = await self._prepare(
            question, conversation_id, top_k
        )

        answer = await self.llm.complete_chat(messages)
        message_id = await self._save_assistant_message(
            conversation.id, answer, citations
        )

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=message_id,
            answer=answer,
            citations=citations,
        )

    async def _prepare(
        self,
        question: str,
        conversation_id: int | None,
        top_k: int | None,
    ) -> tuple[Conversation, list[dict[str, Any]], list[Citation]]:
        """检索 → 组装上下文 → 准备消息 → 落库用户消息"""
        retrieval = RetrievalService(
            self.db, llm=self._llm, vector_store=self._vector_store
        )
        hits = await retrieval.search(question, top_k=top_k)
        context, used = await retrieval.build_context(
            hits, max_tokens=rag_settings.max_context_tokens
        )
        citations = self._build_citations(used)

        conversation = await self._ensure_conversation(conversation_id, question)
        history = await self._load_history(conversation.id)
        messages = self._build_messages(question, context, history)

        # 用户消息先提交：助手消息走独立 session 写，
        # 那时它必须已经能在库里看到这条会话
        self.db.add(
            Message(
                conversation_id=conversation.id,
                role=ROLE_USER,
                content=question,
            )
        )
        await self.db.commit()

        return conversation, messages, citations

    async def _ensure_conversation(
        self, conversation_id: int | None, question: str
    ) -> Conversation:
        """拿到会话；没给或找不到就新建一个"""
        if conversation_id is not None:
            conversation = await self.db.get(Conversation, conversation_id)
            if conversation is not None:
                return conversation

        conversation = Conversation(title=question[:TITLE_LENGTH])
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def _load_history(self, conversation_id: int) -> list[dict[str, Any]]:
        """取最近若干轮历史（最新的在最后）"""
        rows = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(rag_settings.history_turns * 2)
        )
        messages = list(reversed(list(rows.scalars().all())))
        return [{"role": item.role, "content": item.content} for item in messages]

    def _build_messages(
        self, question: str, context: str, history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """拼装给模型的消息，并按 token 预算裁剪历史"""
        user_content = question
        if context:
            user_content = (
                "以下是知识库中的资料片段：\n\n"
                f"{context}\n\n"
                "请基于这些资料回答下面的问题：\n"
                f"{question}"
            )

        system: dict[str, Any] = {"role": "system", "content": RAG_SYSTEM_PROMPT}
        user: dict[str, Any] = {"role": "user", "content": user_content}

        return self._fit_budget(system, history, user)

    def _fit_budget(
        self,
        system: dict[str, Any],
        history: list[dict[str, Any]],
        user: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """按 token 预算裁剪历史消息（从最旧的开始丢）"""
        budget = int(
            (llm_settings.context_window - llm_settings.max_tokens) * BUDGET_RATIO
        )
        remaining = max(0, budget - self.llm.estimate_tokens([system, user]))

        kept: list[dict[str, Any]] = []
        for message in reversed(history):
            tokens = self.llm.estimate_tokens([message])
            if tokens > remaining:
                break
            kept.insert(0, message)
            remaining -= tokens

        return [system] + kept + [user]

    def _build_citations(self, hits: list[RetrievedChunk]) -> list[Citation]:
        """把命中片段转成引用列表"""
        return [
            Citation(
                index=index,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_title=hit.document_title,
                heading_path=hit.heading_path,
                page_number=hit.page_number,
                score=round(hit.score, 4),
            )
            for index, hit in enumerate(hits, start=1)
        ]

    async def _save_assistant_message(
        self, conversation_id: int, answer: str, citations: list[Citation]
    ) -> int:
        """落库助手消息

        这里**显式提交**，不依赖请求结束时依赖清理那一次提交：
        流式响应发出时请求级 session 的生命周期还没走完，
        等它结束时再提交不可靠。
        """
        message = Message(
            conversation_id=conversation_id,
            role=ROLE_ASSISTANT,
            content=answer,
            citations=[item.model_dump() for item in citations],
            token_count=estimate_tokens(answer),
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message.id
