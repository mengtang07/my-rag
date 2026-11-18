"""ORM 模型测试"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model import Base, Chunk, Conversation, Document, Message


def test_all_models_registered() -> None:
    """所有模型都必须注册到 Base.metadata

    新增模型忘了在 `app/model/__init__.py` 里 import 的话，
    Alembic autogenerate 会认为这张表不存在 —— 这里断言住它。
    """
    assert set(Base.metadata.tables) == {
        "document",
        "chunk",
        "conversation",
        "message",
    }


def test_table_names_are_lowercase_class_names() -> None:
    """表名规则：类名小写"""
    assert Document.__tablename__ == "document"
    assert Chunk.__tablename__ == "chunk"
    assert Conversation.__tablename__ == "conversation"
    assert Message.__tablename__ == "message"


async def test_document_cascade_deletes_chunks(db_session: AsyncSession) -> None:
    """删文档会级联删掉它的切块"""
    document = Document(
        title="测试",
        filename="test.md",
        content_hash="hash-1",
        status="ready",
    )
    db_session.add(document)
    await db_session.flush()

    db_session.add(
        Chunk(
            document_id=document.id,
            chunk_index=0,
            content="内容",
            heading_path="",
        )
    )
    await db_session.flush()

    await db_session.delete(document)
    await db_session.flush()

    remaining = await db_session.execute(select(Chunk))
    assert remaining.scalars().all() == []


async def test_chunk_unique_constraint(db_session: AsyncSession) -> None:
    """同一文档里 chunk_index 不能重复"""
    from sqlalchemy.exc import IntegrityError

    document = Document(
        title="测试", filename="test.md", content_hash="hash-2", status="ready"
    )
    db_session.add(document)
    await db_session.flush()

    db_session.add(
        Chunk(document_id=document.id, chunk_index=0, content="A", heading_path="")
    )
    await db_session.flush()

    db_session.add(
        Chunk(document_id=document.id, chunk_index=0, content="B", heading_path="")
    )
    try:
        await db_session.flush()
    except IntegrityError:
        await db_session.rollback()
        return
    raise AssertionError("重复的 (document_id, chunk_index) 应当触发唯一约束")
