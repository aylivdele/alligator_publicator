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
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='expires_at'
            ) THEN
                ALTER TABLE instagram_accounts ADD COLUMN expires_at TIMESTAMPTZ;
            END IF;
        END $$;
    """)
    op.execute("""
        UPDATE instagram_accounts
        SET expires_at = (COALESCE(updated_at, created_at) + (expires_in * INTERVAL '1 second'))
        WHERE expires_in IS NOT NULL
          AND COALESCE(updated_at, created_at) IS NOT NULL
          AND expires_at IS NULL
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='expires_in'
            ) THEN
                ALTER TABLE instagram_accounts DROP COLUMN expires_in;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='folder_id'
            ) THEN
                ALTER TABLE instagram_accounts DROP COLUMN folder_id;
            END IF;
        END $$;
    """)

    # ── smmbox_accounts ───────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='smmbox_accounts' AND column_name='folder_id'
            ) THEN
                ALTER TABLE smmbox_accounts DROP COLUMN folder_id;
            END IF;
        END $$;
    """)

    # ── instagram_account_folders → folder_instagram_accounts ─────────────────
    # If both tables exist, old one is stale — drop it.
    # If only old exists, rename it. If only new exists, nothing to do.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='instagram_account_folders')
               AND EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='folder_instagram_accounts')
            THEN
                DROP TABLE instagram_account_folders;
            ELSIF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='instagram_account_folders')
            THEN
                ALTER TABLE instagram_account_folders RENAME TO folder_instagram_accounts;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='folder_instagram_accounts' AND column_name='account_id'
            ) THEN
                ALTER TABLE folder_instagram_accounts RENAME COLUMN account_id TO instagram_account_id;
            END IF;
        END $$;
    """)

    # ── smmbox_account_folders → folder_smmbox_accounts ──────────────────────
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='smmbox_account_folders')
               AND EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='folder_smmbox_accounts')
            THEN
                DROP TABLE smmbox_account_folders;
            ELSIF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='smmbox_account_folders')
            THEN
                ALTER TABLE smmbox_account_folders RENAME TO folder_smmbox_accounts;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='folder_smmbox_accounts' AND column_name='account_id'
            ) THEN
                ALTER TABLE folder_smmbox_accounts RENAME COLUMN account_id TO smmbox_account_id;
            END IF;
        END $$;
    """)

    # ── publish_tasks ─────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='publish_tasks' AND column_name='selected_account_ids'
            ) THEN
                ALTER TABLE publish_tasks DROP COLUMN selected_account_ids;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='publish_tasks' AND column_name='created_by_user_id'
            ) THEN
                ALTER TABLE publish_tasks ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);
            END IF;
        END $$;
    """)

    # ── task_account_results → task_instagram_results ─────────────────────────
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='task_account_results')
               AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='task_instagram_results')
            THEN
                ALTER TABLE task_account_results RENAME TO task_instagram_results;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='task_instagram_results' AND column_name='account_id'
            ) THEN
                ALTER TABLE task_instagram_results RENAME COLUMN account_id TO instagram_account_id;
            END IF;
        END $$;
    """)

    # ── Новые таблицы (IF NOT EXISTS) ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_selected_instagram_accounts (
            task_id UUID NOT NULL REFERENCES publish_tasks(id) ON DELETE CASCADE,
            instagram_account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, instagram_account_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS task_selected_smmbox_accounts (
            task_id UUID NOT NULL REFERENCES publish_tasks(id) ON DELETE CASCADE,
            smmbox_account_id INTEGER NOT NULL REFERENCES smmbox_accounts(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, smmbox_account_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS task_smmbox_results (
            id SERIAL PRIMARY KEY,
            task_id UUID NOT NULL REFERENCES publish_tasks(id),
            smmbox_account_id INTEGER REFERENCES smmbox_accounts(id),
            status account_result_status_enum NOT NULL,
            error TEXT,
            created_at TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_smmbox_results")
    op.execute("DROP TABLE IF EXISTS task_selected_smmbox_accounts")
    op.execute("DROP TABLE IF EXISTS task_selected_instagram_accounts")

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='task_instagram_results' AND column_name='instagram_account_id'
            ) THEN
                ALTER TABLE task_instagram_results RENAME COLUMN instagram_account_id TO account_id;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='task_instagram_results')
               AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='task_account_results')
            THEN
                ALTER TABLE task_instagram_results RENAME TO task_account_results;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='publish_tasks' AND column_name='created_by_user_id'
            ) THEN
                ALTER TABLE publish_tasks DROP COLUMN created_by_user_id;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='publish_tasks' AND column_name='selected_account_ids'
            ) THEN
                ALTER TABLE publish_tasks ADD COLUMN selected_account_ids TEXT;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='folder_smmbox_accounts' AND column_name='smmbox_account_id'
            ) THEN
                ALTER TABLE folder_smmbox_accounts RENAME COLUMN smmbox_account_id TO account_id;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='folder_smmbox_accounts')
               AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='smmbox_account_folders')
            THEN
                ALTER TABLE folder_smmbox_accounts RENAME TO smmbox_account_folders;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='folder_instagram_accounts' AND column_name='instagram_account_id'
            ) THEN
                ALTER TABLE folder_instagram_accounts RENAME COLUMN instagram_account_id TO account_id;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='folder_instagram_accounts')
               AND NOT EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='instagram_account_folders')
            THEN
                ALTER TABLE folder_instagram_accounts RENAME TO instagram_account_folders;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='smmbox_accounts' AND column_name='folder_id'
            ) THEN
                ALTER TABLE smmbox_accounts ADD COLUMN folder_id INTEGER REFERENCES folders(id);
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='folder_id'
            ) THEN
                ALTER TABLE instagram_accounts ADD COLUMN folder_id INTEGER REFERENCES folders(id);
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='expires_in'
            ) THEN
                ALTER TABLE instagram_accounts ADD COLUMN expires_in INTEGER;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name='instagram_accounts' AND column_name='expires_at'
            ) THEN
                ALTER TABLE instagram_accounts DROP COLUMN expires_at;
            END IF;
        END $$;
    """)
