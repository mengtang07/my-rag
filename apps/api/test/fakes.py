"""测试用的假实现

不联网、不连 Milvus，用确定性的行为替代真实的大模型与向量库。
"""

import math
from collections.abc import AsyncIterator
from typing import Any

from app.core.vector_store import VectorHit

EMBED_DIM: int = 8


def fake_vector(text: str, dim: int = EMBED_DIM) -> list[float]:
    """把文本映射成一个确定性向量

    用字符码累加到各维度上再归一化 —— 相同文本永远得到相同向量，
    含有相同字符的文本也会比较接近，够用来验证检索链路。
    """
    vector = [0.0] * dim
    for index, char in enumerate(text):
        vector[index % dim] += float(ord(char) % 17)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    """余弦相似度"""
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class FakeLLM:
    """假的大模型客户端"""

    def __init__(self, embed_dim: int = EMBED_DIM) -> None:
        self.embed_dim = embed_dim
        self.chat_model = "fake-chat"
        self.embed_model = "fake-embed"
        self.rerank_model = "fake-rerank"
        self.calls: list[list[dict[str, Any]]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [fake_vector(text, self.embed_dim) for text in texts]

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        self.calls.append(messages)
        for piece in ("根据", "资料", "回答"):
            yield piece

    async def complete_chat(self, messages: list[dict[str, Any]]) -> str:
        self.calls.append(messages)
        return "根据资料回答"

    async def rerank(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        return [(index, 1.0 - index * 0.01) for index in range(min(top_n, len(documents)))]

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        return sum(len(str(message.get("content", ""))) for message in messages)


class FakeVectorStore:
    """假的向量库：向量存在内存字典里，按余弦相似度检索"""

    def __init__(self, embed_dim: int = EMBED_DIM) -> None:
        self.embed_dim = embed_dim
        self.collection = "fake_chunks"
        self.rows: dict[int, dict[str, Any]] = {}

    async def ensure_ready(self) -> None:
        return None

    async def upsert_chunks(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self.rows[int(row["pk"])] = row
        return len(rows)

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int,
        document_ids: list[int] | None = None,
    ) -> list[VectorHit]:
        scored: list[tuple[int, float, dict[str, Any]]] = []
        for pk, row in self.rows.items():
            if document_ids and int(row["doc_id"]) not in document_ids:
                continue
            scored.append((pk, cosine(vector, row["vector"]), row))

        scored.sort(key=lambda item: item[1], reverse=True)

        return [
            VectorHit(
                chunk_id=pk,
                score=score,
                document_id=int(row["doc_id"]),
                chunk_index=int(row["chunk_index"]),
            )
            for pk, score, row in scored[:top_k]
        ]

    async def delete_document(self, document_id: int) -> None:
        for pk in [pk for pk, row in self.rows.items() if int(row["doc_id"]) == document_id]:
            del self.rows[pk]

    async def delete_chunks(self, chunk_ids: list[int]) -> None:
        for pk in chunk_ids:
            self.rows.pop(pk, None)

    async def count(self) -> int:
        return len(self.rows)

    async def drop(self) -> None:
        self.rows.clear()

    async def close(self) -> None:
        return None
