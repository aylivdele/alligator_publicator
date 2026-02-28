
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.domain.models import InstagramAccount
from app.infrastructure.database.sqlite import get_db


router = APIRouter()

@router.get("/accounts/{instagram_id}/token/")
async def get_token(instagram_id: str, db: Session = Depends(get_db)):
    account = db.query(InstagramAccount).filter_by(instagram_id=instagram_id).first()
    if not account:
        return {"error": "Аккаунт не найден"}
    return {"access_token": account.access_token, "username": account.username}

@router.get("/accounts")
async def get_accounts(db: Session = Depends(get_db)):
    accounts = db.query(InstagramAccount).all()
    return [
        {
            "id": a.id,
            "instagram_id": a.instagram_id,
            "username": a.username,
            "expires_in": a.expires_in,
            "created_at": str(a.created_at),
            "folder_id": a.folder_id,
            "folder_name": a.folder.name if a.folder else None
        }
        for a in accounts
    ]


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(InstagramAccount).filter_by(id=account_id).first()
    if not account:
        return JSONResponse({"error": "Аккаунт не найден"}, status_code=404)
    db.delete(account)
    db.commit()
    return {"success": True}
