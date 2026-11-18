"""LiteLLM 网关客户端

对话、向量化、重排都走同一个网关，模型名用网关侧的别名。

`import litellm` **刻意放在方法体内懒加载**：litellm 的导入链很长
（openai / tiktoken / tokenizers / aiohttp / boto3 ...），模块级导入会拖慢
应用启动，也让不碰大模型的单元测试白白等上好几秒。
"""

import asyncio
import inspect
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from loguru import logger

from app.core.config import llm_settings
from app.exception.base import BusinessException
from app.exception.llm import LLMException
from app.exception.llm_timeout import LLMTimeoutException
from rag_core.text.estimate import estimate_tokens

# 重试次数与退避基数（秒）
MAX_RETRIES: int = 3
RETRY_BACKOFF: float = 1.0


def _translate_error(exc: Exception) -> BusinessException:
    """把 LiteLLM 的异常翻译成业务异常

    按「具体 → 通用」的顺序判断：子类先命中，父类兜底。
    """
    import litellm

    detail = f"{type(exc).__name__}: {exc}"

    if isinstance(exc, litellm.AuthenticationError):
        return LLMException(
            message="大模型网关鉴权失败，请检查 LLM_API_KEY",
            detail=detail,
            original_exception=exc,
        )
    if isinstance(exc, litellm.RateLimitError):
        return LLMException(
            message="大模型网关限流，请稍后重试",
            detail=detail,
            original_exception=exc,
        )
    if isinstance(exc, litellm.Timeout):
        return LLMTimeoutException(
            message="大模型调用超时",
            detail=detail,
            original_exception=exc,
        )
    if isinstance(exc, litellm.ContextWindowExceededError):
        return LLMException(
            message="上下文超出模型窗口，请缩短问题或减少引用片段",
            detail=detail,
            original_exception=exc,
        )
    if isinstance(exc, litellm.BadRequestError):
        return LLMException(
            message="大模型请求参数不合法",
            detail=detail,
            original_exception=exc,
        )
    return LLMException(
        message="大模型服务异常", detail=detail, original_exception=exc
    )


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否值得重试（限流 / 超时 / 服务端错误）"""
    import litellm

    if isinstance(exc, litellm.AuthenticationError):
        return False
    if isinstance(exc, litellm.BadRequestError):
        return False
    if isinstance(exc, litellm.ContextWindowExceededError):
        return False
    return True


def _extract_delta(chunk: Any) -> str:
    """从流式分片里取出增量文本"""
    try:
        choice = chunk.choices[0]
    except (AttributeError, IndexError, KeyError, TypeError):
        return ""

    delta = getattr(choice, "delta", None)
    if delta is None:
        return ""

    content = getattr(delta, "content", None)
    if content is None and isinstance(delta, dict):
        content = delta.get("content")

    return content or ""


class LiteLLMClient:
    """对 LiteLLM 网关的薄封装"""

    # LiteLLM 网关本身就是 OpenAI 兼容协议。必须显式声明 provider，
    # 否则 SDK 会试图从模型名（`text-embedding` / `chat-standard`）去猜厂商，
    # 猜不出来就报 "LLM Provider NOT provided"。
    PROVIDER: str = "openai"

    def __init__(self) -> None:
        self.api_base: str = llm_settings.api_base
        self.api_key: str = llm_settings.api_key
        self.chat_model: str = llm_settings.chat_model
        self.embed_model: str = llm_settings.embed_model
        self.rerank_model: str = llm_settings.rerank_model
        self.embed_batch_size: int = llm_settings.embed_batch_size
        self.timeout: int = llm_settings.timeout
        self.temperature: float = llm_settings.temperature
        self.max_tokens: int = llm_settings.max_tokens
        self.context_window: int = llm_settings.context_window

    # ---------- 向量化 ----------

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量向量化

        批次**串行**执行，避免打爆网关的限流；批内一次发多条。

        Args:
            texts: 待向量化的文本列表

        Returns:
            与输入一一对应的向量列表
        """
        if not texts:
            return []

        vectors: list[list[float]] = []
        batch_size = max(1, self.embed_batch_size)

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(await self._embed_batch(batch))

        return vectors

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """一批向量化，失败重试"""
        import litellm

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await litellm.aembedding(
                    model=self.embed_model,
                    input=batch,
                    custom_llm_provider=self.PROVIDER,
                    api_base=self.api_base,
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
                # 网关不保证返回顺序，按 index 排回去
                data = sorted(response.data, key=lambda item: item["index"])
                return [item["embedding"] for item in data]
            except Exception as exc:  # noqa: BLE001 - 统一翻译成业务异常
                last_error = exc
                if not _is_retryable(exc) or attempt == MAX_RETRIES - 1:
                    break
                delay = RETRY_BACKOFF * (3**attempt)
                logger.warning(
                    f"向量化失败（第 {attempt + 1} 次），{delay:.1f}s 后重试：{exc}"
                )
                await asyncio.sleep(delay)

        assert last_error is not None
        raise _translate_error(last_error) from last_error

    # ---------- 对话 ----------

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """流式对话

        Args:
            messages: OpenAI 格式的消息列表

        Yields:
            增量文本
        """
        import litellm

        try:
            stream = litellm.acompletion(
                model=self.chat_model,
                messages=messages,
                custom_llm_provider=self.PROVIDER,
                api_base=self.api_base,
                api_key=self.api_key,
                stream=True,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            # 某些版本返回协程、某些直接返回流对象，两种都兼容
            if inspect.isawaitable(stream):
                stream = await stream

            async for chunk in stream:
                text = _extract_delta(chunk)
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise _translate_error(exc) from exc

    async def complete_chat(self, messages: list[dict[str, Any]]) -> str:
        """非流式对话

        Args:
            messages: OpenAI 格式的消息列表

        Returns:
            完整的回答文本
        """
        import litellm

        try:
            response = await litellm.acompletion(
                model=self.chat_model,
                messages=messages,
                custom_llm_provider=self.PROVIDER,
                api_base=self.api_base,
                api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            raise _translate_error(exc) from exc

    # ---------- 重排 ----------

    async def rerank(
        self, query: str, documents: list[str], top_n: int
    ) -> list[tuple[int, float]]:
        """重排候选片段

        Args:
            query: 用户问题
            documents: 候选文本
            top_n: 保留条数

        Returns:
            `(原文下标, 相关度)` 列表，按相关度降序
        """
        if not documents:
            return []

        import litellm

        try:
            response = await litellm.arerank(
                model=self.rerank_model,
                query=query,
                documents=documents,
                top_n=top_n,
                custom_llm_provider=self.PROVIDER,
                api_base=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
            )
            results = (
                response["results"] if isinstance(response, dict) else response.results
            )
            return [
                (int(item["index"]), float(item["relevance_score"]))
                for item in results
            ]
        except Exception as exc:  # noqa: BLE001
            raise _translate_error(exc) from exc

    # ---------- token 估算 ----------

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算一组消息的 token 数

        优先用网关侧的精确 tokenizer；模型名不在映射表里时会抛异常，
        这时退到 CJK 感知的保守估算。
        """
        try:
            import litellm

            return int(litellm.token_counter(model=self.chat_model, messages=messages))
        except Exception:  # noqa: BLE001 - 计数失败不能影响主流程
            total = 0
            for message in messages:
                content = message.get("content")
                if isinstance(content, str):
                    total += estimate_tokens(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            text = block.get("text")
                            if isinstance(text, str):
                                total += estimate_tokens(text)
            return total


@lru_cache(maxsize=1)
def get_llm_client() -> LiteLLMClient:
    """FastAPI 依赖：获取网关客户端（进程内复用）"""
    return LiteLLMClient()
