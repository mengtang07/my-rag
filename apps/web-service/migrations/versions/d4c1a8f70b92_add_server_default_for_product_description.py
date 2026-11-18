"""add server default for product.description

模型里 `product.description` 声明了 `server_default=text("''")`，但上一版迁移
（7f956c318d85）只把该列改成 NOT NULL，没有同步服务端默认值。结果模型与数据库
不一致：绕过 ORM 直接 `INSERT INTO product (name) VALUES (...)` 会违反 NOT NULL。

Revision ID: d4c1a8f70b92
Revises: 7f956c318d85
Create Date: 2026-11-11 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4c1a8f70b92'
down_revision: Union[str, None] = '7f956c318d85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'product',
        'description',
        existing_type=sa.Text(),
        server_default=sa.text("''"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'product',
        'description',
        existing_type=sa.Text(),
        server_default=None,
        existing_nullable=False,
    )
