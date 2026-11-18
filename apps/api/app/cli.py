"""命令行入口

```shell
python -m app.cli ingest <文件>          # 摄入单个文件
python -m app.cli ingest --dir <目录>     # 摄入整个目录（递归）
python -m app.cli reindex --doc <id>      # 重建某个文档的向量
python -m app.cli reindex --all           # 全量重建
python -m app.cli search "<问题>"         # 只检索，不调大模型
python -m app.cli dingtalk workspaces    # 列出钉钉知识库
python -m app.cli dingtalk tree           # 打印钉钉知识库的目录树
python -m app.cli dingtalk pull           # 拉整个知识库（目录树 + 正文）成 JSON
```
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import dingtalk_settings
from app.core.database import get_session_factory
from app.core.vector_store import get_vector_store
from app.exception.base import BusinessException
from app.model.chunk import Chunk
from app.model.document import Document
from app.service.ingest_service import IngestService
from app.service.retrieval_service import RetrievalService
from rag_core.dingding import DingTalkClient, DingTalkService
from rag_core.dingding.models import DingNode
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


def _render_tree(nodes: list[DingNode], indent: int = 0) -> None:
    """把目录树打印成缩进列表"""
    for node in nodes:
        marker = "📁" if node.kind == "folder" else "📄"
        extra = f"  [{node.content_type}]" if node.content_type else ""
        print(f"{'  ' * indent}{marker} {node.name}{extra}")
        if node.children:
            _render_tree(node.children, indent + 1)


async def _dingtalk_workspaces() -> None:
    """列出钉钉知识库"""
    client = _build_dingtalk_client()
    try:
        workspaces = await client.list_workspaces()
    finally:
        await client.close()

    if not workspaces:
        print("没有可见的知识库")
        return

    print(f"共 {len(workspaces)} 个知识库：\n")
    for workspace in workspaces:
        workspace_id = workspace.get("workspaceId") or workspace.get("id") or ""
        name = workspace.get("name") or "(未命名)"
        root = workspace.get("rootNodeId") or ""
        print(f"  {name}")
        print(f"    workspaceId: {workspace_id}")
        print(f"    rootNodeId:  {root}")


async def _dingtalk_tree(workspace_id: str | None) -> None:
    """打印钉钉知识库的目录树"""
    client = _build_dingtalk_client()
    try:
        tree, _ = await DingTalkService(client).pull(
            workspace_id, skip_content=True
        )
    finally:
        await client.close()

    print(f"知识库：{tree.workspace_name or tree.workspace_id}\n")
    _render_tree(tree.nodes)


async def _dingtalk_pull(workspace_id: str | None, out: str | None) -> None:
    """拉整个知识库（目录树 + 正文）存成 JSON"""
    client = _build_dingtalk_client()
    try:
        tree, documents = await DingTalkService(client).pull(workspace_id)
    finally:
        await client.close()

    payload = {
        "tree": tree.model_dump(),
        "documents": [document.model_dump() for document in documents],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"已写入 {out}（{len(documents)} 篇文档）")
    else:
        print(text)


def _build_dingtalk_client() -> DingTalkClient:
    """按配置建钉钉客户端"""
    return DingTalkClient(
        app_key=dingtalk_settings.app_key,
        app_secret=dingtalk_settings.app_secret,
        operator_id=dingtalk_settings.operator_id,
        base_url=dingtalk_settings.base_url,
        timeout=float(dingtalk_settings.timeout),
    )


async def _dingtalk_unionid(user_id: str) -> None:
    """由 userId 查 unionId"""
    client = _build_dingtalk_client()
    try:
        union_id = await client.get_union_id(user_id)
    finally:
        await client.close()

    print(f"userId {user_id} → unionId {union_id}")
    print("把它填到 .env 的 DINGTALK_OPERATOR_ID")


# 各个接口需要的权限 Scope（实测自钉钉的报错信息，不是猜的）
DINGTALK_SCOPES: tuple[tuple[str, str, bool], ...] = (
    ("Wiki.Workspace.Read", "列出知识库", True),
    ("Wiki.Node.Read", "读知识库节点（目录树）", True),
    ("Storage.File.Read", "读文档正文（blocks）", True),
    ("Contact.User.Read", "查 unionId（只在需要时开）", False),
)


def _dingtalk_scopes() -> None:
    """打印待授权的 Scope 与一键申请链接"""
    app_key = dingtalk_settings.app_key
    print("钉钉接口需要的权限（点链接申请并开通）：\n")
    for scope, purpose, required in DINGTALK_SCOPES:
        mark = "必需" if required else "可选"
        print(f"  [{mark}] {scope}")
        print(f"         {purpose}")
        if app_key:
            print(f"         https://open-dev.dingtalk.com/appscope/apply?content={app_key}%23{scope}")
    print("\n申请完记得「创建版本 → 发布」，权限点发布后才生效。")


async def _dingtalk_check() -> None:
    """体检整条凭证链：能不能鉴权 → 有没有知识库 → 能不能读节点"""
    client = _build_dingtalk_client()
    try:
        print("1) 鉴权 …", end=" ", flush=True)
        await client.access_token()
        print("✓")

        print("2) 列知识库 …", end=" ", flush=True)
        workspaces = await client.list_workspaces()
        print(f"✓ {len(workspaces)} 个")

        if not workspaces:
            print("   没有可见的知识库：检查「应用可见范围」里有没有你")
            return

        workspace = workspaces[0]
        root_node_id = str(workspace.get("rootNodeId") or "")
        print(f"   知识库：{workspace.get('name')}（{workspace.get('workspaceId')}）")

        if not root_node_id:
            print("   ⚠️ 没拿到 rootNodeId，没法往下拉目录树")
            return

        print("3) 读根节点 …", end=" ", flush=True)
        nodes = await client.list_nodes(root_node_id)
        print(f"✓ {len(nodes)} 个")
        for node in nodes[:10]:
            print(f"     {node.get('name')}  ({node.get('type')})")
    finally:
        await client.close()


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

    dingtalk_parser = subparsers.add_parser("dingtalk", help="钉钉知识库")
    dingtalk_sub = dingtalk_parser.add_subparsers(dest="action", required=True)
    dingtalk_sub.add_parser("check", help="体检整条凭证链")
    dingtalk_sub.add_parser("scopes", help="打印待授权的权限与申请链接")
    dingtalk_sub.add_parser("workspaces", help="列出知识库")
    unionid_parser = dingtalk_sub.add_parser("unionid", help="由 userId 查 unionId")
    unionid_parser.add_argument("userid", help="组织内的 userId")
    tree_parser = dingtalk_sub.add_parser("tree", help="打印目录树")
    tree_parser.add_argument("--workspace", help="知识库 id")
    pull_parser = dingtalk_sub.add_parser("pull", help="拉整个知识库（目录树 + 正文）")
    pull_parser.add_argument("--workspace", help="知识库 id")
    pull_parser.add_argument("--out", help="输出 JSON 文件路径")

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

    if args.command == "dingtalk":
        workspace = getattr(args, "workspace", None) or dingtalk_settings.workspace_id
        if args.action == "check":
            asyncio.run(_dingtalk_check())
        elif args.action == "scopes":
            _dingtalk_scopes()
        elif args.action == "workspaces":
            asyncio.run(_dingtalk_workspaces())
        elif args.action == "unionid":
            asyncio.run(_dingtalk_unionid(args.userid))
        elif args.action == "tree":
            asyncio.run(_dingtalk_tree(workspace))
        elif args.action == "pull":
            asyncio.run(_dingtalk_pull(workspace, args.out))
        return


if __name__ == "__main__":
    try:
        main()
    except BusinessException as exc:
        # 命令行给人话看，不甩 traceback
        print(f"✗ {exc.message}", file=sys.stderr)
        if exc.detail:
            print(f"  {exc.detail}", file=sys.stderr)
        sys.exit(1)
