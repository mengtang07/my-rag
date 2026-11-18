"""ORM 模型导入本包即完成所有模型的注册（Alembic 生成迁移脚本时依赖这一点）。

新增模型时**必须**在这里加一行 import，否则 autogenerate 会认为这张表不存在，
生成的迁移脚本里就会凭空少一张表 —— 这是最容易被忽略、也最难排查的坑。
"""

from app.model.base import Base, IDMixin, TimestampMixin
from app.model.chunk import Chunk
from app.model.conversation import Conversation
from app.model.document import Document
from app.model.message import Message

__all__ = [
    "Base",
    "Chunk",
    "Conversation",
    "Document",
    "IDMixin",
    "Message",
    "TimestampMixin",
]
