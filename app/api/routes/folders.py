from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.domain.models import Folder, InstagramAccount, PublishTask, TaskStatus, User, UserFolderAccess, UserRole
from app.infrastructure.database.db import get_db


router = APIRouter()


@router.get("/folders")
async def get_folders(db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
    if current_user.role == UserRole.admin:
        folders = db.query(Folder).all()
    else:
        accessible_ids = [fa.folder_id for fa in current_user.folder_accesses]
        folders = db.query(Folder).filter(Folder.id.in_(accessible_ids)).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "count": len(f.accounts)
        }
        for f in folders
    ]


@router.post("/folders")
async def create_folder(request: Request, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Название папки обязательно"}, status_code=400)
    existing = db.query(Folder).filter_by(name=name).first()
    if existing:
        return JSONResponse({"error": "Папка с таким названием уже существует"}, status_code=400)
    folder = Folder(name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "count": 0}


@router.patch("/folders/{folder_id}")
async def rename_folder(folder_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Название папки обязательно"}, status_code=400)
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Папка не найдена")
    existing = db.query(Folder).filter(Folder.name == name, Folder.id != folder_id).first()
    if existing:
        return JSONResponse({"error": "Папка с таким названием уже существует"}, status_code=400)
    folder.name = name
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "count": len(folder.accounts)}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Папка не найдена")
    active_count = db.query(PublishTask).filter(
        PublishTask.folder_id == folder_id,
        PublishTask.status.in_([TaskStatus.pending, TaskStatus.processing]),
    ).count()
    if active_count:
        raise HTTPException(status_code=400, detail=f"Нельзя удалить папку: есть {active_count} активных выкладок")
    tasks = db.query(PublishTask).filter_by(folder_id=folder_id).all()
    for task in tasks:
        db.delete(task)
    db.query(InstagramAccount).filter_by(folder_id=folder_id).update({"folder_id": None})
    db.query(UserFolderAccess).filter_by(folder_id=folder_id).delete()
    db.delete(folder)
    db.commit()
    return {"ok": True}
