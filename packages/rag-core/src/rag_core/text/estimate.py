"""token 数估算

优先用 `litellm.token_counter`（走网关侧的精确 tokenizer），
但它不在共享包里、且模型名不在 LiteLLM 映射表里时会抛异常。
这时退到这里做**保守估算**：宁可估高（宁可少塞点上下文）也不要估低。
"""


def is_cjk(char: str) -> bool:
    """判断单个字符是否属于 CJK / 假名 / 谚文 / 全角标点

    这些字符在主流 tokenizer 里大致 1 字 1 token（部分标点会合并），
    按 1 token 估算是偏保守的方向。
    """
    code = ord(char)
    return (
        0x3040 <= code <= 0x30FF  # 平假名 / 片假名
        or 0x3400 <= code <= 0x4DBF  # 扩展 A
        or 0x4E00 <= code <= 0x9FFF  # 基本区
        or 0xAC00 <= code <= 0xD7AF  # 谚文音节
        or 0xF900 <= code <= 0xFAFF  # 兼容表意文字
        or 0xFF00 <= code <= 0xFF60  # 全角字符
        or 0x3000 <= code <= 0x303F  # CJK 标点
    )


def estimate_tokens(text: str) -> int:
    """估算一段文本的 token 数

    规则：CJK 字符按 1 token/字，其余按 4 字符/token。

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数（不小于 0）

    Examples:
        >>> estimate_tokens("")
        0
        >>> estimate_tokens("abcd")
        1
        >>> estimate_tokens("中文")
        2
    """
    if not text:
        return 0

    cjk = 0
    for char in text:
        if is_cjk(char):
            cjk += 1

    other = len(text) - cjk
    return cjk + (other + 3) // 4
