import json
import uuid
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.domain.models import (
    Folder,
    PublishTask,
    TaskSelectedInstagramAccount,
    TaskSelectedSmmboxAccount,
    TaskStatus,
    User,
    UserFolderAccess,
    UserRole,
)
from app.infrastructure.database.db import get_db


def create_publish_routes():
    router = APIRouter()

    @router.post("/tasks")
    async def publish_reels(
        file: UploadFile = File(...),
        caption: str = Form(...),
        selected_folder_id: int = Form(...),
        is_test_mode: bool = Form(...),
        # JSON-массивы ID выбранных аккаунтов, None = все аккаунты папки
        selected_instagram_account_ids: Optional[str] = Form(None),
        selected_smmbox_account_ids: Optional[str] = Form(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(require_auth),
    ):
        if current_user.role != UserRole.admin:
            accessible_ids = [fa.folder_id for fa in current_user.folder_accesses]
            if selected_folder_id not in accessible_ids:
                raise HTTPException(status_code=403, detail="Нет доступа к этой папке")

        # Обычный пользователь может выбрать только 1 Instagram-аккаунт
        if current_user.role != UserRole.admin:
            ig_ids = json.loads(selected_instagram_account_ids) if selected_instagram_account_ids else []
            if len(ig_ids) > 1:
                raise HTTPException(status_code=403, detail="Обычный пользователь может выбрать только один аккаунт")

        temp_path = f"/shared/{uuid.uuid4()}.mp4"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = PublishTask(
            folder_id=selected_folder_id,
            created_by_user_id=current_user.id,
            status=TaskStatus.pending,
            file_path=temp_path,
            caption=caption,
            is_test_mode=is_test_mode,
        )
        db.add(task)
        db.flush()  # получаем task.id до создания связанных записей

        # Сохраняем выбранные Instagram-аккаунты
        if selected_instagram_account_ids:
            for acc_id in json.loads(selected_instagram_account_ids):
                db.add(TaskSelectedInstagramAccount(task_id=task.id, instagram_account_id=acc_id))

        # Сохраняем выбранные SMMBox-аккаунты
        if selected_smmbox_account_ids:
            for acc_id in json.loads(selected_smmbox_account_ids):
                db.add(TaskSelectedSmmboxAccount(task_id=task.id, smmbox_account_id=acc_id))

        db.commit()
        db.refresh(task)

        return {
            "task_id": str(task.id),
            "status": task.status,
        }

    @router.get("/tasks/{task_id}")
    def get_task(task_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_auth)):
        task = db.get(PublishTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        return {
            "status": task.status,
            "stage": task.stage,
            "error": task.error,
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
            if is_admin:
                ig_results = [
                    {
                        "instagram_id": r.account.instagram_id if r.account else None,
                        "username": r.account.username if r.account else None,
                        "status": r.status,
                        "error": r.error,
                    }
                    for r in task.instagram_results
                ]
                smm_results = [
                    {
                        "name": r.account.name if r.account else None,
                        "social": r.account.social if r.account else None,
                        "status": r.status,
                        "error": r.error,
                    }
                    for r in task.smmbox_results
                ]
            else:
                ig_results = [
                    {
                        "instagram_id": r.account.instagram_id if r.account else None,
                        "status": r.status,
                    }
                    for r in task.instagram_results
                ]
                smm_results = [
                    {
                        "social": r.account.social if r.account else None,
                        "status": r.status,
                    }
                    for r in task.smmbox_results
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
                "instagram_results": ig_results,
                "smmbox_results": smm_results,
            })

        return rows

    return router
