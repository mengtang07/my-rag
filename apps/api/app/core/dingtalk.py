"""钉钉开放平台客户端

对接的四个接口（都带 `x-acs-dingtalk-access-token` 头）：

| 用途 | 接口 |
| --- | --- |
| 鉴权 | `POST /v1.0/oauth2/accessToken` → `{accessToken, expireIn: 7200}` |
| 知识库列表 | `GET /v2.0/wiki/workspaces` |
| 节点树 | `GET /v2.0/wiki/nodes?parentNodeId=&operatorId=&maxResults=50` |
| 文档正文 | `GET /v1.0/doc/suites/documents/{docKey}/blocks?operatorId=` |

两个容易踩的点：

- `operatorId` 必须是用户的 **unionId**，不是 userId
- 文档的 `docKey`：从 wiki 节点拿到的文档，docKey 就等于 nodeId；
  从企业存储（dentries）拿到的则是 uuid
"""

import time
from typing import Any

import httpx

from app.exception.dingtalk import DingTalkException

DEFAULT_BASE_URL: str = "https://api.dingtalk.com"
TOKEN_HEADER: str = "x-acs-dingtalk-access-token"
# 提前 5 分钟过期，避免边界上拿到一个刚失效的 token
TOKEN_SKEW: float = 300.0


class DingTalkClient:
    """钉钉开放平台接口的异步客户端"""

    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        operator_id: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.operator_id = operator_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_client = http_client
        self._token: str | None = None
        self._token_expire_at: float = 0.0

    # ---------- 底层 ----------

    def _http(self) -> httpx.AsyncClient:
        """拿到 HTTP 客户端（没注入就自己建一个）"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self) -> None:
        """关闭连接"""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
    ) -> Any:
        """发一次请求，返回 `result` 里的内容"""
        request_headers = dict(headers or {})
        if authenticated:
            request_headers[TOKEN_HEADER] = await self.access_token()

        url = f"{self.base_url}{path}"

        try:
            response = await self._http().request(
                method,
                url,
                params=params,
                json=json_body,
                headers=request_headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise DingTalkException(
                message=f"钉钉接口请求失败：{exc}",
                detail=f"{method} {url}",
                original_exception=exc,
            ) from exc

        if response.status_code >= 400:
            raise DingTalkException(
                message=f"钉钉接口返回 HTTP {response.status_code}",
                detail=response.text[:500],
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise DingTalkException(
                message="钉钉接口返回的不是 JSON",
                detail=response.text[:500],
                original_exception=exc,
            ) from exc

        if isinstance(payload, dict):
            if payload.get("success") is False:
                raise DingTalkException(
                    message=(
                        f"钉钉接口报错：{payload.get('code')} "
                        f"{payload.get('message', '')}".strip()
                    ),
                    detail=response.text[:500],
                )
            if "result" in payload:
                return payload["result"]

        return payload

    # ---------- 鉴权 ----------

    async def access_token(self) -> str:
        """取 access_token（带缓存，过期前自动续）"""
        if self._token is not None and time.time() < self._token_expire_at:
            return self._token

        if not self.app_key or not self.app_secret:
            raise DingTalkException(
                message="缺少钉钉应用凭据，请配置 DINGTALK_APP_KEY 与 DINGTALK_APP_SECRET"
            )

        result = await self._request(
            "POST",
            "/v1.0/oauth2/accessToken",
            json_body={"appKey": self.app_key, "appSecret": self.app_secret},
            headers={"Content-Type": "application/json"},
            authenticated=False,
        )

        token = str(result.get("accessToken") or "")
        if not token:
            raise DingTalkException(message="钉钉鉴权失败：返回里没有 accessToken")

        expire_in = float(result.get("expireIn") or 7200)
        self._token = token
        self._token_expire_at = time.time() + max(0.0, expire_in - TOKEN_SKEW)
        return token

    # ---------- 知识库 ----------

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """列出当前用户可见的知识库"""
        result = await self._request(
            "GET",
            "/v2.0/wiki/workspaces",
            params={"operatorId": self.operator_id},
        )
        return _as_list(result, "workspaces")

    async def list_nodes(
        self,
        parent_node_id: str,
        *,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """列出某个节点下的直接子节点（自动翻完所有页）"""
        nodes: list[dict[str, Any]] = []
        next_token = ""

        while True:
            params: dict[str, Any] = {
                "parentNodeId": parent_node_id,
                "operatorId": self.operator_id,
                "maxResults": max_results,
            }
            if next_token:
                params["nextToken"] = next_token

            result = await self._request("GET", "/v2.0/wiki/nodes", params=params)

            batch = _as_list(result, "nodes")
            nodes.extend(batch)

            next_token = str(result.get("nextPageToken") or result.get("nextToken") or "")
            if not next_token or not batch:
                break

        return nodes

    async def get_node(self, node_id: str) -> dict[str, Any]:
        """按 id 取单个节点"""
        result = await self._request(
            "GET",
            f"/v2.0/wiki/nodes/{node_id}",
            params={"operatorId": self.operator_id},
        )
        return result if isinstance(result, dict) else {}

    async def query_node_by_url(self, url: str) -> dict[str, Any]:
        """用钉钉文档链接反查节点 id"""
        result = await self._request(
            "POST",
            "/v2.0/wiki/nodes/queryByUrl",
            params={"operatorId": self.operator_id},
            json_body={"url": url, "operatorId": self.operator_id},
            headers={"Content-Type": "application/json"},
        )
        return result if isinstance(result, dict) else {}

    # ---------- 文档正文 ----------

    async def get_document_blocks(self, doc_key: str) -> list[dict[str, Any]]:
        """取一篇文档的正文块

        Args:
            doc_key: 文档 key（wiki 节点里等于 node_id）

        Returns:
            块列表，按 `index` 升序
        """
        result = await self._request(
            "GET",
            f"/v1.0/doc/suites/documents/{doc_key}/blocks",
            params={"operatorId": self.operator_id},
        )
        blocks = _as_list(result, "data")
        return sorted(blocks, key=lambda item: int(item.get("index") or 0))


def _as_list(result: Any, key: str) -> list[dict[str, Any]]:
    """从响应里取出列表，兼容几种包法"""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
