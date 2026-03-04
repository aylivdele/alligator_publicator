"""add selected_account_ids to publish_tasks

Revision ID: add_selected_account_ids
Revises: add_million_notified
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_selected_account_ids'
down_revision = 'add_million_notified'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'publish_tasks',
        sa.Column('selected_account_ids', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('publish_tasks', 'selected_account_ids')
