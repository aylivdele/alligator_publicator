import uuid
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.models import Folder, PublishTask, TaskStatus, User, UserFolderAccess, UserRole
from app.domain.repositories import InstagramPublisher
from app.infrastructure.database.db import get_db


def create_publish_routes(uniqalizer: ReelsUniqalizerService, instagram_publisher: InstagramPublisher):
    router = APIRouter()

    @router.post("/tasks")
    async def publish_reels(
        file: UploadFile = File(...),
        caption: str = Form(...),
        selected_folder_id: int = Form(...),
        is_test_mode: bool = Form(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(require_auth),
    ):
        if current_user.role != UserRole.admin:
            accessible_ids = [fa.folder_id for fa in current_user.folder_accesses]
            if selected_folder_id not in accessible_ids:
                raise HTTPException(status_code=403, detail="Нет доступа к этой папке")

        temp_path = f"/shared/{uuid.uuid4()}.mp4"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = PublishTask()
        task.folder_id = selected_folder_id
        task.status = TaskStatus.pending
        task.file_path = temp_path
        task.caption = caption
        task.is_test_mode = is_test_mode

        db.add(task)
        db.commit()
        db.refresh(task)

        return {
            "task_id": str(task.id),
            "status": task.status
        }

    @router.get("/tasks/{task_id}")
    def get_task(task_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_auth)):
        task = db.get(PublishTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return {
            "status": task.status,
            "stage": task.stage,
            "error": task.error
        }

    @router.get("/tasks")
    def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
        query = select(PublishTask, Folder.name).join(Folder, Folder.id == PublishTask.folder_id)

        if current_user.role != UserRole.admin:
            accessible_ids = [fa.folder_id for fa in current_user.folder_accesses]
            query = query.where(PublishTask.folder_id.in_(accessible_ids))

        result = (
            db.execute(query.order_by(PublishTask.created_at.desc()).limit(10))
            .tuples()
            .all()
        )

        is_admin = current_user.role == UserRole.admin

        rows = []
        for task, folder_name in result:
            account_info = None
            if is_admin:
                account_info = [
                    {
                        "instagram_id": ar.account.instagram_id if ar.account else None,
                        "username": ar.account.username if ar.account else None,
                        "status": ar.status,
                        "error": ar.error,
                    }
                    for ar in task.account_results
                ]
            else:
                account_info = [
                    {
                        "instagram_id": ar.account.instagram_id if ar.account else None,
                        "status": ar.status,
                    }
                    for ar in task.account_results
                ]

            rows.append({
                "id": task.id,
                "folder_name": folder_name,
                "status": task.status,
                "stage": task.stage,
                "error": task.error,
                "created_at": task.created_at,
                "locked_by": task.locked_by,
                "is_test_mode": task.is_test_mode,
                "account_results": account_info,
            })

        return rows

    return router
