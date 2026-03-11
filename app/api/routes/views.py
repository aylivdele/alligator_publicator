from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import config
from app.api.deps import require_auth
from app.domain.models import Folder, PublishTask, TaskInstagramResult, User, UserRole
from app.infrastructure.database.db import get_db


def create_views_router(settings: config.Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/views")
    def get_views(
        db: Session = Depends(get_db),
        current_user: User = Depends(require_auth),
    ) -> Any:
        cutoff = datetime.utcnow() - timedelta(hours=settings.VIEWS_MAX_AGE_HOURS)
        is_admin = current_user.role == UserRole.admin

        query = (
            db.query(PublishTask, Folder.name)
            .join(Folder, Folder.id == PublishTask.folder_id)
            .filter(PublishTask.created_at >= cutoff)
        )

        if not is_admin:
            accessible_ids = [fa.folder_id for fa in current_user.folder_accesses]
            query = query.filter(PublishTask.folder_id.in_(accessible_ids))

        rows = query.order_by(PublishTask.created_at.desc()).all()

        result = []
        for task, folder_name in rows:
            accounts = []
            for r in task.instagram_results:
                if r.media_id is None:
                    continue
                entry: dict = {
                    "instagram_id": r.account.instagram_id if r.account else None,
                    "view_count": r.view_count,
                    "views_updated_at": r.views_updated_at,
                    "permalink": r.permalink,
                }
                if is_admin:
                    entry["username"] = r.account.username if r.account else None
                accounts.append(entry)

            if not accounts:
                continue

            result.append({
                "task_id": str(task.id),
                "folder_name": folder_name,
                "created_at": task.created_at,
                "is_test_mode": task.is_test_mode,
                "accounts": accounts,
            })

        return result

    return router
