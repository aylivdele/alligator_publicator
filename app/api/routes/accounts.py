from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.domain.models import Folder, FolderInstagramAccount, FolderSmmboxAccount, InstagramAccount, SmmboxAccount, User, UserRole
from app.infrastructure.database.db import get_db


router = APIRouter()


@router.get("/accounts/{instagram_id}/token/")
async def get_token(instagram_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    account = db.query(InstagramAccount).filter_by(instagram_id=instagram_id).first()
    if not account:
        return {"error": "Аккаунт не найден"}
    return {"access_token": account.access_token, "username": account.username}


@router.get("/accounts")
async def get_accounts(db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
    if current_user.role == UserRole.admin:
        accounts = db.query(InstagramAccount).all()
        return [
            {
                "id": a.id,
                "instagram_id": a.instagram_id,
                "username": a.username,
                "access_token": a.access_token[:10],
                "expires_at": str(a.expires_at) if a.expires_at else None,
                "created_at": str(a.created_at),
                "folder_ids": [
                    r.folder_id
                    for r in db.query(FolderInstagramAccount).filter_by(instagram_account_id=a.id).all()
                ],
            }
            for a in accounts
        ]
    else:
        accessible_folder_ids = {fa.folder_id for fa in current_user.folder_accesses}
        accounts = (
            db.query(InstagramAccount)
            .join(FolderInstagramAccount, InstagramAccount.id == FolderInstagramAccount.instagram_account_id)
            .filter(FolderInstagramAccount.folder_id.in_(accessible_folder_ids))
            .distinct()
            .all()
        )
        return [
            {
                "id": a.id,
                "username": a.username,
                "folder_ids": [
                    r.folder_id
                    for r in db.query(FolderInstagramAccount).filter_by(instagram_account_id=a.id).all()
                ],
            }
            for a in accounts
        ]


@router.get("/smmbox-accounts")
async def get_smmbox_accounts(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_auth)):
    if current_user.role != UserRole.admin:
        accessible_ids = {fa.folder_id for fa in current_user.folder_accesses}
        if folder_id not in accessible_ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этой папке")
    accounts = (
        db.query(SmmboxAccount)
        .join(FolderSmmboxAccount, SmmboxAccount.id == FolderSmmboxAccount.smmbox_account_id)
        .filter(FolderSmmboxAccount.folder_id == folder_id)
        .all()
    )
    return [{"id": a.id, "name": a.name, "social": a.social, "type": a.type} for a in accounts]


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    account = db.query(InstagramAccount).filter_by(id=account_id).first()
    if not account:
        return JSONResponse({"error": "Аккаунт не найден"}, status_code=404)
    db.delete(account)
    db.commit()
    return {"success": True}
