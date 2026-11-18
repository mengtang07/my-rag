"""token 估算测试"""

from rag_core.text.estimate import estimate_tokens, is_cjk


def test_empty_text() -> None:
    """空文本估算为 0"""
    assert estimate_tokens("") == 0


def test_cjk_counts_one_token_per_char() -> None:
    """CJK 字符按 1 token/字估算"""
    assert estimate_tokens("中文") == 2
    assert estimate_tokens("中文字符测试") == 6


def test_latin_counts_four_chars_per_token() -> None:
    """非 CJK 按 4 字符/token 估算"""
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2


def test_mixed_text() -> None:
    """中英混排按各自规则累加"""
    # 2 个 CJK + 4 个拉丁 = 2 + 1
    assert estimate_tokens("中文abcd") == 3


def test_is_cjk() -> None:
    """CJK 判定"""
    assert is_cjk("中")
    assert is_cjk("。")
    assert not is_cjk("a")
    assert not is_cjk("1")
