# rag-core

my-rag 的共享包：**纯 RAG 领域逻辑**，不依赖 FastAPI / SQLAlchemy / litellm。

| 模块 | 职责 |
| --- | --- |
| `models.py` | `Block` / `ParsedDocument` / `ChunkDraft` 三个数据类 |
| `parsing/` | 按格式解析文档：markdown / pdf / docx / html / txt |
| `chunking/` | 结构感知切块（标题树 → 段落 → 句子 → 硬切） |
| `text/` | CJK 感知的 token 估算 |

## 设计要点

- **标题路径随块走**：markdown / docx / html 能还原标题层级，切块带上
  `安装 > 依赖` 这样的路径，回答时才能精确引用到章节。
- **切块带标题前缀**：入库正文是 `## 标题路径\n\n正文`，前缀参与向量化，
  检索「依赖安装」时更容易命中对应章节。
- **PDF 退化**：PDF 通常没有标题结构，退化成「按页切」，引用时给页码。
