"""结构感知切块

为什么不用纯定长窗口切分：定长会把「标题」和它下面的正文切开、把表格/代码块拦腰截断，
结果是①检索命中的块语义不完整②引用出处对不上原文结构③embedding 质量下降。

这里的策略是**结构感知为主、定长兜底**：

1. 先按标题层级把文档切成「带标题路径的区块」（这一步由解析器完成）
2. 区块正文过长时，按 段落 → 句子 → 硬切 三级降到长度上限
3. 相邻片段之间保留一点重叠（**只在同一个区块内**，跨标题不重叠，否则语义会串）
4. 过短的片段并入同一标题路径下的前一片段（宁可小也别丢内容）
5. 入库正文前面拼上 `## 标题路径`，让向量也带上章节信息
"""

import re
from dataclasses import replace

from rag_core.models import Block, ChunkDraft
from rag_core.text.estimate import estimate_tokens

# 句末标点（中英文）；零宽切分，切点落在标点之后
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；!?;])\s*|(?<=[.!?;])\s+")

# 段落分隔：空行
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def split_long_text(text: str, max_chars: int) -> list[str]:
    """把一段超长文本切成不超过 `max_chars` 的片段

    三级降级：段落 → 句子 → 硬切。

    Args:
        text: 原始文本
        max_chars: 单片最大字符数（必须大于 0）

    Returns:
        片段列表，按原文顺序

    Examples:
        >>> split_long_text("短文本", 100)
        ['短文本']
        >>> split_long_text("", 100)
        []
    """
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")

    stripped = text.strip()
    if not stripped:
        return []
    if len(stripped) <= max_chars:
        return [stripped]

    pieces: list[str] = []
    current = ""

    for paragraph in _PARAGRAPH_SPLIT.split(stripped):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_chars:
            # 单段就超限 → 降级到句子级
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_by_sentence(paragraph, max_chars))
            continue

        if not current:
            current = paragraph
        elif len(current) + 2 + len(paragraph) <= max_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            pieces.append(current)
            current = paragraph

    if current:
        pieces.append(current)

    return pieces


def _split_by_sentence(text: str, max_chars: int) -> list[str]:
    """按句子切；单句仍超限则硬切"""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]

    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_hard_split(sentence, max_chars))
            continue

        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            pieces.append(current)
            current = sentence

    if current:
        pieces.append(current)

    return pieces


def _hard_split(text: str, max_chars: int) -> list[str]:
    """按字符硬切；尽量切在空白处"""
    pieces: list[str] = []
    rest = text.strip()

    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        head = rest[:cut].strip()
        if head:
            pieces.append(head)
        rest = rest[cut:].strip()

    if rest:
        pieces.append(rest)

    return pieces


def _apply_overlap(pieces: list[str], overlap: int) -> list[str]:
    """相邻片段之间加重叠：后一片段前面拼上前一片段的尾部

    重叠只在**同一个区块内**生效（调用方按区块分别调用），跨标题不重叠。
    """
    if overlap <= 0 or len(pieces) <= 1:
        return pieces

    result: list[str] = []
    for index, piece in enumerate(pieces):
        if index == 0:
            result.append(piece)
            continue
        tail = pieces[index - 1][-overlap:]
        result.append(f"{tail}{piece}" if tail else piece)

    return result


def chunk_blocks(
    blocks: list[Block],
    *,
    max_chars: int = 1200,
    min_chars: int = 80,
    overlap: int = 150,
) -> list[ChunkDraft]:
    """把结构块切成待入库的片段

    Args:
        blocks: 解析器产出的结构块
        max_chars: 单片最大字符数
        min_chars: 单片最小字符数；小于它且与前一片同标题路径的会并入前一片
        overlap: 同一区块内相邻片段的重叠字符数

    Returns:
        切块列表，`chunk_index` 从 0 连续编号
    """
    drafts: list[ChunkDraft] = []

    for block in blocks:
        heading = " > ".join(block.heading_path)
        pieces = _apply_overlap(split_long_text(block.text, max_chars), overlap)

        for piece in pieces:
            body = piece.strip()
            if not body:
                continue

            # 标题前缀参与向量化：检索"依赖安装"时更容易命中对应章节
            text = f"## {heading}\n\n{body}" if heading else body
            drafts.append(
                ChunkDraft(
                    text=text,
                    heading_path=heading,
                    chunk_index=0,
                    page_number=block.page_number,
                    char_start=block.char_start,
                    char_end=block.char_end,
                    token_count=estimate_tokens(text),
                )
            )

    drafts = _merge_short(drafts, min_chars)

    for index, draft in enumerate(drafts):
        draft.chunk_index = index

    return drafts


def _merge_short(drafts: list[ChunkDraft], min_chars: int) -> list[ChunkDraft]:
    """把过短的片段并入**同一标题路径**下的前一片段

    跨标题不合并 —— 把上一节末尾和下一节开头揉在一起会让引用出处失真。
    """
    if min_chars <= 0:
        return drafts

    merged: list[ChunkDraft] = []
    for draft in drafts:
        if (
            merged
            and len(draft.text) < min_chars
            and merged[-1].heading_path == draft.heading_path
        ):
            previous = merged[-1]
            text = f"{previous.text}\n\n{draft.text}"
            merged[-1] = replace(
                previous,
                text=text,
                token_count=estimate_tokens(text),
            )
            continue
        merged.append(draft)

    return merged
