"""钉钉知识库：客户端与树结构测试

用 `httpx.MockTransport` 打桩，不发真实请求。
"""

from typing import Any

import httpx
import pytest

from dingding.client import DingTalkClient
from dingding.exceptions import DingTalkError
from dingding.models import KIND_DOCUMENT, KIND_FOLDER
from dingding.tree import (
    DingTalkService,
    build_block_tree,
    iter_blocks,
    iter_document_nodes,
    parse_heading_level,
    parse_node,
)

# ---------- 打桩 ----------

WORKSPACES: dict[str, Any] = {
    "workspaces": [
        {
            "workspaceId": "ws-1",
            "name": "团队知识库",
            "rootNodeId": "root-1",
        }
    ]
}

# 根节点下有两个文件夹
ROOT_NODES: dict[str, Any] = {
    "nodes": [
        {
            "nodeId": "folder-1",
            "name": "研发",
            "type": "FOLDER",
            "workspaceId": "ws-1",
        },
        {
            "nodeId": "doc-0",
            "name": "总览",
            "type": "FILE",
            "category": "ALIDOC",
            "workspaceId": "ws-1",
            "url": "https://alidocs.dingtalk.com/i/nodes/doc-0",
        },
    ]
}

FOLDER_NODES: dict[str, Any] = {
    "nodes": [
        {
            "nodeId": "doc-1",
            "name": "部署手册",
            "type": "FILE",
            "category": "ALIDOC",
            "workspaceId": "ws-1",
        }
    ]
}

BLOCKS: list[dict[str, Any]] = [
    {
        "blockType": "heading",
        "heading": {"level": "heading-1", "text": "快速开始"},
        "index": 0,
        "id": "b0",
    },
    {
        "blockType": "paragraph",
        "paragraph": {"text": "第一段正文"},
        "index": 1,
        "id": "b1",
    },
    {
        "blockType": "heading",
        "heading": {"level": "heading-2", "text": "前置条件"},
        "index": 2,
        "id": "b2",
    },
    {
        "blockType": "paragraph",
        "paragraph": {"text": "需要 Docker 29 以上"},
        "index": 3,
        "id": "b3",
    },
    {
        "blockType": "heading",
        "heading": {"level": "heading-2", "text": "安装步骤"},
        "index": 4,
        "id": "b4",
    },
    {
        "blockType": "paragraph",
        "paragraph": {"text": "执行 docker compose up"},
        "index": 5,
        "id": "b5",
    },
]


def _make_client(
    handler: Any,
) -> tuple[DingTalkClient, list[str]]:
    """建一个走 MockTransport 的客户端，顺便记录请求过的路径"""
    calls: list[str] = []

    def recording(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return handler(request)

    transport = httpx.MockTransport(recording)
    http = httpx.AsyncClient(transport=transport)
    client = DingTalkClient(
        app_key="key",
        app_secret="secret",
        operator_id="union-1",
        http_client=http,
    )
    return client, calls


def _default_handler(request: httpx.Request) -> httpx.Response:
    """默认打桩：鉴权 + 知识库 + 两层节点 + 文档正文"""
    path = request.url.path

    if path == "/v1.0/oauth2/accessToken":
        return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})

    if path == "/v2.0/wiki/workspaces":
        return httpx.Response(200, json={"result": WORKSPACES, "success": True})

    if path == "/v2.0/wiki/nodes":
        parent = request.url.params.get("parentNodeId")
        if parent == "root-1":
            return httpx.Response(200, json={"result": ROOT_NODES, "success": True})
        if parent == "folder-1":
            return httpx.Response(200, json={"result": FOLDER_NODES, "success": True})
        return httpx.Response(200, json={"result": {"nodes": []}, "success": True})

    if path.startswith("/v1.0/doc/suites/documents/"):
        return httpx.Response(
            200, json={"result": {"data": BLOCKS}, "success": True}
        )

    return httpx.Response(404, json={"code": "not.found", "message": "没有这个接口"})


# ---------- 客户端 ----------


async def test_access_token_is_cached() -> None:
    """token 只取一次，后面复用"""
    client, calls = _make_client(_default_handler)

    await client.list_workspaces()
    await client.list_workspaces()
    await client.list_nodes("root-1")

    assert calls.count("/v1.0/oauth2/accessToken") == 1
    await client.close()


async def test_token_header_is_sent() -> None:
    """业务请求带上 x-acs-dingtalk-access-token"""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-acs-dingtalk-access-token", ""))
        return _default_handler(request)

    client, _ = _make_client(handler)
    await client.list_workspaces()

    # 鉴权请求本身不带 token（那是拿 token 的请求），业务请求才带
    assert seen == ["", "tok"]
    await client.close()


async def test_list_nodes_follows_pagination() -> None:
    """有 nextPageToken 就继续翻页"""
    pages = {
        "": {"nodes": [{"nodeId": "n1", "name": "一", "type": "FILE"}], "nextPageToken": "p2"},
        "p2": {"nodes": [{"nodeId": "n2", "name": "二", "type": "FILE"}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        token = request.url.params.get("nextToken", "")
        return httpx.Response(200, json={"result": pages[token], "success": True})

    client, _ = _make_client(handler)
    nodes = await client.list_nodes("root-1")

    assert [node["nodeId"] for node in nodes] == ["n1", "n2"]
    await client.close()


async def test_http_error_raises_business_exception() -> None:
    """HTTP 错误翻译成业务异常"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        return httpx.Response(500, text="boom")

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError):
        await client.list_workspaces()
    await client.close()


async def test_success_false_raises() -> None:
    """success=false 也翻译成业务异常"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        return httpx.Response(
            200, json={"success": False, "code": "no.permission", "message": "没权限"}
        )

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError):
        await client.list_workspaces()
    await client.close()


async def test_missing_credentials_raise() -> None:
    """没配 appKey/appSecret 时给出明确提示"""
    client = DingTalkClient(app_key="", app_secret="", operator_id="u")
    with pytest.raises(DingTalkError, match="DINGTALK_APP_KEY"):
        await client.access_token()


# ---------- unionId 转换 ----------


def _user_handler(request: httpx.Request) -> httpx.Response:
    """旧版接口的打桩"""
    if request.url.path == "/gettoken":
        return httpx.Response(
            200, json={"access_token": "old-token", "expires_in": 7200}
        )
    if request.url.path == "/topapi/v2/user/get":
        return httpx.Response(
            200,
            json={
                "errcode": 0,
                "result": {"unionid": "union-xyz", "name": "张三"},
            },
        )
    return httpx.Response(404)


async def test_get_union_id_reads_result_unionid() -> None:
    """unionId 取的是 result.unionid（没有下划线）"""
    client, _ = _make_client(_user_handler)
    assert await client.get_union_id("user-1") == "union-xyz"
    await client.close()


async def test_get_union_id_reports_errcode() -> None:
    """errcode 不为 0 时报出来"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/gettoken":
            return httpx.Response(200, json={"access_token": "old", "expires_in": 7200})
        return httpx.Response(
            200, json={"errcode": 40002, "errmsg": "不合法的userid"}
        )

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError, match="不合法的userid"):
        await client.get_union_id("bad-id")
    await client.close()


async def test_get_union_id_when_field_missing() -> None:
    """返回里没有 unionId 时也报错（而不是静默返回空串）"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/gettoken":
            return httpx.Response(200, json={"access_token": "old", "expires_in": 7200})
        return httpx.Response(200, json={"errcode": 0, "result": {"union_id": ""}})

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError, match="unionId"):
        await client.get_union_id("user-1")
    await client.close()


# ---------- 节点解析 ----------


def test_parse_node_from_wiki_fields() -> None:
    """wiki 接口的字段（type / category）"""
    node = parse_node(
        {
            "nodeId": "doc-1",
            "name": "部署手册",
            "type": "FILE",
            "category": "ALIDOC",
            "url": "https://alidocs.dingtalk.com/i/nodes/doc-1",
        },
        ["研发"],
    )

    assert node.node_id == "doc-1"
    assert node.kind == KIND_DOCUMENT
    assert node.content_type == "ALIDOC"
    assert node.doc_key == "doc-1"  # wiki 文档的 docKey 就是 nodeId
    assert node.path == ["研发", "部署手册"]


def test_parse_node_from_storage_fields() -> None:
    """企业存储接口的字段（nodeType / contentType / uuid）"""
    node = parse_node(
        {
            "id": "dentry-1",
            "uuid": "uuid-1",
            "name": "会议纪要",
            "nodeType": "file",
            "contentType": "ALIDOC",
        },
        [],
    )

    assert node.kind == KIND_DOCUMENT
    assert node.doc_key == "uuid-1"  # 存储接口的 docKey 是 uuid
    assert node.path == ["会议纪要"]


def test_parse_node_folder() -> None:
    """文件夹节点"""
    node = parse_node({"nodeId": "f1", "name": "研发", "type": "FOLDER"}, [])
    assert node.kind == KIND_FOLDER
    assert node.doc_key is None


# ---------- 标题树 ----------


def test_parse_heading_level_accepts_both_formats() -> None:
    """level 见过 "2" 和 "heading-2" 两种写法"""
    assert parse_heading_level("2") == 2
    assert parse_heading_level("heading-2") == 2
    assert parse_heading_level(3) == 3
    assert parse_heading_level("") is None
    assert parse_heading_level(None) is None
    assert parse_heading_level("abc") is None


def test_build_block_tree_nests_by_heading_level() -> None:
    """按标题层级拼成树"""
    roots = build_block_tree(BLOCKS)

    assert len(roots) == 1
    quick = roots[0]
    assert quick.text == "快速开始"
    assert quick.level == 1

    # 快速开始 → [第一段正文, 前置条件, 安装步骤]
    assert len(quick.children) == 3
    assert quick.children[0].text == "第一段正文"
    assert quick.children[1].text == "前置条件"
    assert quick.children[1].level == 2
    assert quick.children[1].children[0].text == "需要 Docker 29 以上"


def test_build_block_tree_keeps_document_order() -> None:
    """遍历顺序跟原文一致"""
    blocks = build_block_tree(BLOCKS)
    pairs = list(iter_blocks(blocks))

    assert [block.index for block, _ in pairs] == [0, 1, 2, 3, 4, 5]
    assert [path for _, path in pairs] == [
        ("快速开始",),
        ("快速开始",),
        ("快速开始", "前置条件"),
        ("快速开始", "前置条件"),
        ("快速开始", "安装步骤"),
        ("快速开始", "安装步骤"),
    ]


def test_build_block_tree_handles_table() -> None:
    """表格块抽成 markdown 风格的行"""
    blocks = build_block_tree(
        [
            {
                "blockType": "table",
                "table": {"cells": [["表头1", "表头2"], ["数据1", "数据2"]]},
                "index": 0,
                "id": "t1",
            }
        ]
    )
    assert blocks[0].text == "表头1 | 表头2\n数据1 | 数据2"


def test_build_block_tree_handles_unknown_block() -> None:
    """unknown 块（代码块/图片）也不能把流程搞崩"""
    blocks = build_block_tree(
        [
            {"blockType": "unknown", "index": 0, "id": "u1"},
            {
                "blockType": "paragraph",
                "paragraph": {"text": "正常段落"},
                "index": 1,
                "id": "p1",
            },
        ]
    )
    assert len(blocks) == 2
    assert blocks[1].text == "正常段落"


# ---------- 整棵树 ----------


async def test_build_tree_recurses_and_records_path() -> None:
    """目录树递归 + 路径"""
    client, _ = _make_client(_default_handler)
    tree = await DingTalkService(client).build_tree()
    await client.close()

    assert tree.workspace_id == "ws-1"
    assert tree.workspace_name == "团队知识库"
    assert len(tree.nodes) == 2

    folder = tree.nodes[0]
    assert folder.name == "研发"
    assert folder.kind == KIND_FOLDER
    assert len(folder.children) == 1

    document = folder.children[0]
    assert document.name == "部署手册"
    assert document.path == ["研发", "部署手册"]


async def test_pull_fetches_documents_in_order() -> None:
    """拉整个知识库：目录树 + 所有文档正文"""
    client, _ = _make_client(_default_handler)
    tree, documents = await DingTalkService(client).pull()
    await client.close()

    # 遍历顺序 = 树上的自然顺序：研发文件夹里的文档先于它后面的同级「总览」
    assert [document.title for document in documents] == ["部署手册", "总览"]
    assert documents[0].path == ["研发", "部署手册"]
    assert documents[0].blocks[0].text == "快速开始"


async def test_iter_document_nodes_walks_depth_first() -> None:
    """文档遍历是深度优先"""
    client, _ = _make_client(_default_handler)
    tree = await DingTalkService(client).build_tree()
    await client.close()

    titles = [node.name for node in iter_document_nodes(tree.nodes)]
    assert titles == ["部署手册", "总览"]


# ---------- operatorId 缺失时的报错 ----------


async def test_missing_operatorid_error_is_translated() -> None:
    """operatorId 缺失时给出可操作的提示，而不是「没查到知识库」

    钉钉对缺 operatorId 的返回有两种形态，都是 HTTP 4xx/200 + code：
    200 + {"code":"MissingoperatorId"}、400 + {"code":"paramError"}。
    两种都要翻译。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        return httpx.Response(
            400, json={"code": "paramError", "message": "paramError-operatorId"}
        )

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError, match="operatorId"):
        await client.list_workspaces()
    await client.close()


async def test_missing_operatorid_on_http_200_is_translated() -> None:
    """HTTP 200 但 code 表明是错误时也要拦住"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        return httpx.Response(
            200,
            json={
                "code": "MissingoperatorId",
                "message": "operatorId is mandatory for this action.",
            },
        )

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError, match="operatorId"):
        await client.list_workspaces()
    await client.close()


async def test_get_my_union_id() -> None:
    """contact/users/me 直接拿当前授权人的 unionId"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        if request.url.path == "/v1.0/contact/users/me":
            return httpx.Response(
                200,
                json={
                    "unionId": "union-me",
                    "nick": "张三",
                    "openId": "open-1",
                },
            )
        return httpx.Response(404)

    client, _ = _make_client(handler)
    assert await client.get_my_union_id() == "union-me"
    await client.close()


async def test_get_my_union_id_when_field_missing() -> None:
    """没拿到 unionId 字段时报错"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1.0/oauth2/accessToken":
            return httpx.Response(200, json={"accessToken": "tok", "expireIn": 7200})
        return httpx.Response(200, json={"nick": "张三"})

    client, _ = _make_client(handler)
    with pytest.raises(DingTalkError, match="unionId"):
        await client.get_my_union_id()
    await client.close()
