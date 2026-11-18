"""LiteLLM 异常到业务异常的映射测试"""

import litellm
import pytest

from app.core.llm import _translate_error
from app.exception.llm import LLMException
from app.exception.llm_timeout import LLMTimeoutException


def test_authentication_error() -> None:
    """鉴权失败 → LLMException"""
    error = _translate_error(
        litellm.AuthenticationError(
            message="bad key", llm_provider="openai", model="gpt-4o"
        )
    )
    assert isinstance(error, LLMException)
    assert "鉴权" in error.message


def test_rate_limit_error() -> None:
    """限流 → LLMException"""
    error = _translate_error(
        litellm.RateLimitError(
            message="slow down", llm_provider="openai", model="gpt-4o"
        )
    )
    assert isinstance(error, LLMException)
    assert "限流" in error.message


def test_timeout_error_maps_to_timeout_exception() -> None:
    """超时 → LLMTimeoutException（子类，有独立的 504 码）"""
    error = _translate_error(
        litellm.Timeout(message="too slow", model="gpt-4o", llm_provider="openai")
    )
    assert isinstance(error, LLMTimeoutException)
    assert isinstance(error, LLMException)


def test_context_window_error() -> None:
    """上下文超窗 → LLMException"""
    error = _translate_error(
        litellm.ContextWindowExceededError(message="too long", model="x", llm_provider="openai")
    )
    assert isinstance(error, LLMException)
    assert "上下文" in error.message


def test_unknown_error_falls_back() -> None:
    """未知异常兜底成 LLMException"""
    error = _translate_error(RuntimeError("boom"))
    assert isinstance(error, LLMException)
    assert error.detail


def test_timeout_has_own_error_code() -> None:
    """超时在错误码表里命中自己的条目（按 MRO 查找）"""
    from app.exception.handler.errors import ERROR_MAP

    assert ERROR_MAP[LLMTimeoutException][1] == 504
    assert ERROR_MAP[LLMException][1] == 502
