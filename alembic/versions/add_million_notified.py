"""add million_notified to task_account_results

Revision ID: add_million_notified
Revises:
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_million_notified'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'task_account_results',
        sa.Column('million_notified', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('task_account_results', 'million_notified')
