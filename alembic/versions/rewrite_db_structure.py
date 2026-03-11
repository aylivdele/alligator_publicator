"""rewrite db structure: proper M:M, expires_at, split results

Revision ID: rewrite_db_structure
Revises: add_selected_account_ids
Create Date: 2026-03-11

Изменения:
- instagram_accounts: убрать folder_id, expires_in → expires_at (datetime)
- smmbox_accounts: убрать folder_id
- instagram_account_folders → folder_instagram_accounts (rename table + column account_id → instagram_account_id)
- smmbox_account_folders → folder_smmbox_accounts (rename table + column account_id → smmbox_account_id)
- publish_tasks: убрать selected_account_ids, добавить created_by_user_id
- task_account_results → task_instagram_results (rename table + column account_id → instagram_account_id)
- Новые таблицы: task_smmbox_results, task_selected_instagram_accounts, task_selected_smmbox_accounts
"""
from alembic import op
import sqlalchemy as sa

revision = 'rewrite_db_structure'
down_revision = 'add_selected_account_ids'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── instagram_accounts ────────────────────────────────────────────────────
    # Добавляем expires_at, вычисляя из expires_in + updated_at/created_at
    op.add_column('instagram_accounts', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE instagram_accounts
        SET expires_at = (COALESCE(updated_at, created_at) + (expires_in * INTERVAL '1 second'))
        WHERE expires_in IS NOT NULL AND COALESCE(updated_at, created_at) IS NOT NULL
    """)
    op.drop_column('instagram_accounts', 'expires_in')
    op.drop_column('instagram_accounts', 'folder_id')

    # ── smmbox_accounts ───────────────────────────────────────────────────────
    op.drop_column('smmbox_accounts', 'folder_id')

    # ── instagram_account_folders → folder_instagram_accounts ─────────────────
    op.execute("ALTER TABLE instagram_account_folders RENAME TO folder_instagram_accounts")
    op.execute("ALTER TABLE folder_instagram_accounts RENAME COLUMN account_id TO instagram_account_id")

    # ── smmbox_account_folders → folder_smmbox_accounts ──────────────────────
    op.execute("ALTER TABLE smmbox_account_folders RENAME TO folder_smmbox_accounts")
    op.execute("ALTER TABLE folder_smmbox_accounts RENAME COLUMN account_id TO smmbox_account_id")

    # ── publish_tasks ─────────────────────────────────────────────────────────
    op.drop_column('publish_tasks', 'selected_account_ids')
    op.add_column(
        'publish_tasks',
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )

    # ── task_account_results → task_instagram_results ─────────────────────────
    op.execute("ALTER TABLE task_account_results RENAME TO task_instagram_results")
    op.execute("ALTER TABLE task_instagram_results RENAME COLUMN account_id TO instagram_account_id")

    # ── Новые таблицы ─────────────────────────────────────────────────────────
    op.create_table(
        'task_selected_instagram_accounts',
        sa.Column('task_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('publish_tasks.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('instagram_account_id', sa.Integer(),
                  sa.ForeignKey('instagram_accounts.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'task_selected_smmbox_accounts',
        sa.Column('task_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('publish_tasks.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('smmbox_account_id', sa.Integer(),
                  sa.ForeignKey('smmbox_accounts.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'task_smmbox_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('publish_tasks.id'), nullable=False),
        sa.Column('smmbox_account_id', sa.Integer(),
                  sa.ForeignKey('smmbox_accounts.id'), nullable=True),
        sa.Column('status', sa.Enum('success', 'failed', name='account_result_status_enum',
                                    create_type=False), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('task_smmbox_results')
    op.drop_table('task_selected_smmbox_accounts')
    op.drop_table('task_selected_instagram_accounts')

    op.execute("ALTER TABLE task_instagram_results RENAME COLUMN instagram_account_id TO account_id")
    op.execute("ALTER TABLE task_instagram_results RENAME TO task_account_results")

    op.drop_column('publish_tasks', 'created_by_user_id')
    op.add_column('publish_tasks', sa.Column('selected_account_ids', sa.Text(), nullable=True))

    op.execute("ALTER TABLE folder_smmbox_accounts RENAME COLUMN smmbox_account_id TO account_id")
    op.execute("ALTER TABLE folder_smmbox_accounts RENAME TO smmbox_account_folders")

    op.execute("ALTER TABLE folder_instagram_accounts RENAME COLUMN instagram_account_id TO account_id")
    op.execute("ALTER TABLE folder_instagram_accounts RENAME TO instagram_account_folders")

    op.add_column('smmbox_accounts', sa.Column('folder_id', sa.Integer(),
                                                sa.ForeignKey('folders.id'), nullable=True))
    op.add_column('instagram_accounts', sa.Column('folder_id', sa.Integer(),
                                                   sa.ForeignKey('folders.id'), nullable=True))
    op.add_column('instagram_accounts', sa.Column('expires_in', sa.Integer(), nullable=True))
    op.drop_column('instagram_accounts', 'expires_at')
