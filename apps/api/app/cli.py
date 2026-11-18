"""命令行入口

```shell
python -m app.cli ingest <文件>          # 摄入单个文件
python -m app.cli ingest --dir <目录>     # 摄入整个目录（递归）
python -m app.cli reindex --doc <id>      # 重建某个文档的向量
python -m app.cli reindex --all           # 全量重建
python -m app.cli search "<问题>"         # 只检索，不调大模型
```
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.vector_store import get_vector_store
from app.model.chunk import Chunk
from app.model.document import Document
from app.service.ingest_service import IngestService
from app.service.retrieval_service import RetrievalService
from rag_core.parsing.base import SUPPORTED_SUFFIXES


def _collect_files(directory: Path) -> list[Path]:
    """递归收集目录下所有支持的文件"""
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower().lstrip(".") in SUPPORTED_SUFFIXES:
            files.append(path)
    return files


async def _ingest(paths: list[Path]) -> int:
    """逐个摄入文件，返回成功数量"""
    vector_store = get_vector_store()
    await vector_store.ensure_ready()

    succeeded = 0
    async with get_session_factory()() as session:
        service = IngestService(session, vector_store=vector_store)
        for path in paths:
            try:
                document, reused = await service.ingest_bytes(
                    path.read_bytes(), path.name, source_type="file"
                )
            except Exception as exc:  # noqa: BLE001 - 命令行要继续处理后面的文件
                print(f"✗ {path}: {exc}")
                continue
            suffix = "（已存在，复用）" if reused else ""
            print(
                f"✓ {path}: 文档 id={document.id} 状态={document.status} "
                f"切块数={document.chunk_count}{suffix}"
            )
            succeeded += 1

    print(f"\n共处理 {len(paths)} 个文件，成功 {succeeded} 个")
    return succeeded


async def _reindex(document_id: int | None) -> int:
    """重建向量；document_id 为 None 表示全量"""
    vector_store = get_vector_store()
    await vector_store.ensure_ready()

    async with get_session_factory()() as session:
        if document_id is not None:
            documents = list(
                (
                    await session.execute(
                        select(Document).where(Document.id == document_id)
                    )
                ).scalars()
            )
        else:
            documents = list((await session.execute(select(Document))).scalars())

        if not documents:
            print("没有需要重建的文档")
            return 0

        service = IngestService(session, vector_store=vector_store)
        total = 0
        for document in documents:
            try:
                count = await service.reindex_document(document)
            except Exception as exc:  # noqa: BLE001
                print(f"✗ 文档 {document.id}: {exc}")
                continue
            print(f"✓ 文档 {document.id}: 重建 {count} 个向量")
            total += count

    print(f"\n共重建 {total} 个向量")
    return total


async def _search(query: str, top_k: int) -> None:
    """只做检索，不调大模型"""
    vector_store = get_vector_store()
    await vector_store.ensure_ready()

    async with get_session_factory()() as session:
        service = RetrievalService(session, vector_store=vector_store)
        hits = await service.search(query, top_k=top_k)

    if not hits:
        print("没有命中任何片段")
        return

    print(f"问题：{query}\n")
    for index, hit in enumerate(hits, start=1):
        source = hit.document_title
        if hit.heading_path:
            source += f" / {hit.heading_path}"
        if hit.page_number:
            source += f" / 第 {hit.page_number} 页"
        print(f"[{index}] {source}  (score={hit.score:.4f}, chunk={hit.chunk_id})")
        print(f"{hit.content}\n")


def main() -> None:
    """命令行入口"""
    parser = argparse.ArgumentParser(prog="app.cli", description="my-rag 命令行")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="摄入文档")
    ingest_parser.add_argument("file", nargs="?", help="要摄入的文件")
    ingest_parser.add_argument("--dir", help="要摄入的目录（递归）")

    reindex_parser = subparsers.add_parser("reindex", help="重建向量索引")
    reindex_parser.add_argument("--doc", type=int, help="文档 id")
    reindex_parser.add_argument("--all", action="store_true", help="全量重建")

    search_parser = subparsers.add_parser("search", help="检索知识库")
    search_parser.add_argument("query", help="检索问题")
    search_parser.add_argument("--top-k", type=int, default=5, help="返回条数")

    args = parser.parse_args()

    if args.command == "ingest":
        paths: list[Path] = []
        if args.dir:
            directory = Path(args.dir)
            if not directory.is_dir():
                raise SystemExit(f"目录不存在：{directory}")
            paths = _collect_files(directory)
        elif args.file:
            path = Path(args.file)
            if not path.is_file():
                raise SystemExit(f"文件不存在：{path}")
            paths = [path]
        else:
            raise SystemExit("请指定文件或 --dir")

        if not paths:
            print("没有找到可摄入的文件")
            return
        asyncio.run(_ingest(paths))
        return

    if args.command == "reindex":
        if args.all:
            asyncio.run(_reindex(None))
        elif args.doc is not None:
            asyncio.run(_reindex(args.doc))
        else:
            raise SystemExit("请指定 --doc <id> 或 --all")
        return

    if args.command == "search":
        asyncio.run(_search(args.query, args.top_k))
        return


if __name__ == "__main__":
    main()
