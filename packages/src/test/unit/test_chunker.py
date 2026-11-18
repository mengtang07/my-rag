"""切块算法测试"""

from rag_core.chunking import chunk_blocks, split_long_text
from rag_core.models import Block


def test_short_block_becomes_one_chunk() -> None:
    """短内容只切出一块"""
    blocks = [Block(text="这是一段很短的内容。")]
    drafts = chunk_blocks(blocks, max_chars=1200, min_chars=80, overlap=150)

    assert len(drafts) == 1
    assert drafts[0].chunk_index == 0
    assert drafts[0].text == "这是一段很短的内容。"


def test_heading_path_becomes_prefix() -> None:
    """标题路径会拼到正文前面（参与向量化）"""
    blocks = [Block(text="正文内容。", heading_path=("安装", "依赖"))]
    drafts = chunk_blocks(blocks, max_chars=1200, min_chars=80, overlap=150)

    assert drafts[0].text.startswith("## 安装 > 依赖\n\n")
    assert drafts[0].heading_path == "安装 > 依赖"


def test_long_block_split_by_paragraph() -> None:
    """超长区块按段落降级"""
    paragraph = "句。" * 300  # 约 600 字符
    blocks = [Block(text=f"{paragraph}\n\n{paragraph}")]
    drafts = chunk_blocks(blocks, max_chars=800, min_chars=80, overlap=0)

    assert len(drafts) > 1
    assert all(len(draft.text) <= 800 + 100 for draft in drafts)


def test_overlap_only_inside_same_block() -> None:
    """重叠只发生在同一区块内，跨标题不重叠"""
    text = "甲" * 200 + "\n\n" + "乙" * 200
    blocks = [
        Block(text=text, heading_path=("A",)),
    ]
    drafts = chunk_blocks(blocks, max_chars=250, min_chars=0, overlap=50)

    # 第一块不含上一块的尾巴（它是第一块）
    assert not drafts[0].text.startswith("甲" * 50 + "甲" * 200)
    # 后续块带上了前一块的尾巴
    assert len(drafts) >= 2
    assert len(drafts[1].text) > 250


def test_different_heading_never_merged() -> None:
    """不同标题下的短块不会被合并到一起"""
    blocks = [
        Block(text="短", heading_path=("A",)),
        Block(text="也短", heading_path=("B",)),
    ]
    drafts = chunk_blocks(blocks, max_chars=1200, min_chars=80, overlap=0)

    assert len(drafts) == 2
    assert drafts[0].heading_path == "A"
    assert drafts[1].heading_path == "B"


def test_short_chunk_merged_into_previous_same_heading() -> None:
    """同标题下的过短块会并入前一块"""
    blocks = [Block(text="A" * 200 + "\n\n" + "B", heading_path=("H",))]
    drafts = chunk_blocks(blocks, max_chars=1200, min_chars=80, overlap=0)

    assert len(drafts) == 1
    assert drafts[0].text.endswith("B")


def test_chunk_index_is_continuous() -> None:
    """切块序号从 0 连续编号"""
    blocks = [Block(text="段落\n\n" * 50)]
    drafts = chunk_blocks(blocks, max_chars=200, min_chars=0, overlap=0)

    assert [draft.chunk_index for draft in drafts] == list(range(len(drafts)))


def test_page_number_preserved() -> None:
    """页码会带到切块上"""
    blocks = [Block(text="第一页", page_number=1)]
    drafts = chunk_blocks(blocks, max_chars=1200, min_chars=0, overlap=0)

    assert drafts[0].page_number == 1


def test_split_long_text_rejects_bad_max_chars() -> None:
    """max_chars 必须大于 0"""
    try:
        split_long_text("内容", 0)
    except ValueError:
        return
    raise AssertionError("max_chars=0 应当抛 ValueError")


def test_split_long_text_empty_input() -> None:
    """空文本切出空列表"""
    assert split_long_text("", 100) == []
    assert split_long_text("   \n  ", 100) == []
