"""add is_active flag to chunks

Revision ID: 877580c6b70c
Revises: b60e99985095
Create Date: 2026-08-06 18:27:22.297635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '877580c6b70c'
down_revision: Union[str, Sequence[str], None] = 'b60e99985095'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chunks',
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunks', 'is_active')
