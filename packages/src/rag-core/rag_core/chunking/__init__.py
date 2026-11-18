"""切块：把结构块切成适合向量化与塞进上下文的片段"""

from rag_core.chunking.chunker import chunk_blocks, split_long_text

__all__ = ["chunk_blocks", "split_long_text"]
