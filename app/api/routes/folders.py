from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.domain.models import Folder
from app.infrastructure.database.sqlite import get_db


router = APIRouter()


@router.get("/folders")
async def get_folders(db: Session = Depends(get_db)):
    folders = db.query(Folder).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "count": len(f.accounts)
        }
        for f in folders
    ]


@router.post("/folders")
async def create_folder(request: Request, db: Session = Depends(get_db)):
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