from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.domain.models import Folder, User, UserFolderAccess, UserRole
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
