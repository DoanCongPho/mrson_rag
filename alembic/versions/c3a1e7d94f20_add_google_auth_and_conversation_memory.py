"""add google auth fields, conversation category and memory columns

Revision ID: c3a1e7d94f20
Revises: b4fa4c521864
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1e7d94f20'
down_revision: Union[str, Sequence[str], None] = 'b4fa4c521864'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])

    op.add_column('conversations', sa.Column('category', sa.String(length=20), nullable=True))
    op.add_column('conversations', sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    op.add_column('conversations', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False))
    op.add_column('conversations', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('conversations', sa.Column('summary_until_message_id', sa.Integer(), nullable=True))

    # Existing chats get the time of their first/last message instead of the migration time.
    op.execute("""
        UPDATE conversations c
        SET created_at = m.first_at, updated_at = m.last_at
        FROM (
            SELECT conversation_id, MIN(created_at) AS first_at, MAX(created_at) AS last_at
            FROM messages GROUP BY conversation_id
        ) m
        WHERE m.conversation_id = c.id
    """)

    op.create_index('ix_messages_conversation_id_id', 'messages', ['conversation_id', 'id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_messages_conversation_id_id', table_name='messages')

    op.drop_column('conversations', 'summary_until_message_id')
    op.drop_column('conversations', 'summary')
    op.drop_column('conversations', 'updated_at')
    op.drop_column('conversations', 'created_at')
    op.drop_column('conversations', 'category')

    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'email')
    op.drop_column('users', 'google_sub')
