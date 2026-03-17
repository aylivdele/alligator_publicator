import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.domain.entities import GroupType, SocialType
from app.domain.models import (
    Folder,
    FolderInstagramAccount,
    FolderSmmboxAccount,
    InstagramAccount,
    PublishTask,
    SmmboxAccount,
    TaskInstagramResult,
    User,
    UserFolderAccess,
    UserRole,
)
from app.domain.repositories import CombinedPublisher
from app.infrastructure.database.db import get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient

_templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_admin_routes(graph_api: InstagramGraphApiClient, smmbox_client: Optional[CombinedPublisher] = None) -> APIRouter:
    router = APIRouter(prefix="/admin")
    templates = _templates
    pwd_context = _pwd_context

    # ─── Admin panel page ─────────────────────────────────────────────────────

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    async def admin_page(request: Request, _: User = Depends(require_admin)):
        return templates.TemplateResponse("admin.html", {"request": request})

    # ─── Users ────────────────────────────────────────────────────────────────

    @router.get("/api/users")
    async def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
        users = db.query(User).all()
        result = []
        for u in users:
            folder_ids = [fa.folder_id for fa in u.folder_accesses]
            result.append({
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "role": u.role,
                "created_at": str(u.created_at),
                "folder_ids": folder_ids,
            })
        return result

    @router.post("/api/users")
    async def create_user(
        username: str = Form(...),
        password: str = Form(...),
        display_name: str = Form(""),
        role: str = Form("employee"),
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        if db.query(User).filter_by(username=username).first():
            raise HTTPException(status_code=400, detail="Пользователь уже существует")
        user = User(
            username=username,
            password_hash=pwd_context.hash(password),
            display_name=display_name or None,
            role=UserRole.admin if role == "admin" else UserRole.employee,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "username": user.username, "role": user.role}

    @router.delete("/api/users/{user_id}")
    async def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        db.delete(user)
        db.commit()
        return {"success": True}

    @router.patch("/api/users/{user_id}")
    async def update_user(
        user_id: int,
        display_name: Optional[str] = Form(None),
        role: Optional[str] = Form(None),
        password: Optional[str] = Form(None),
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if display_name is not None:
            user.display_name = display_name or None
        if role is not None:
            user.role = UserRole.admin if role == "admin" else UserRole.employee
        if password:
            user.password_hash = pwd_context.hash(password)
        db.commit()
        return {"success": True}

    @router.post("/api/users/{user_id}/folders")
    async def grant_folder_access(
        user_id: int,
        folder_id: int = Form(...),
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        existing = db.query(UserFolderAccess).filter_by(user_id=user_id, folder_id=folder_id).first()
        if not existing:
            db.add(UserFolderAccess(user_id=user_id, folder_id=folder_id))
            db.commit()
        return {"success": True}

    @router.delete("/api/users/{user_id}/folders/{folder_id}")
    async def revoke_folder_access(
        user_id: int,
        folder_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        access = db.query(UserFolderAccess).filter_by(user_id=user_id, folder_id=folder_id).first()
        if access:
            db.delete(access)
            db.commit()
        return {"success": True}

    # ─── Instagram accounts ───────────────────────────────────────────────────

    @router.get("/api/accounts")
    async def list_accounts(
        folder_id: Optional[int] = None,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        query = db.query(InstagramAccount)
        if folder_id is not None:
            query = (
                query
                .join(FolderInstagramAccount,
                      InstagramAccount.id == FolderInstagramAccount.instagram_account_id)
                .filter(FolderInstagramAccount.folder_id == folder_id)
            )
        accounts = query.all()

        def _days_left(a: InstagramAccount) -> Optional[int]:
            if a.expires_at is None:
                return None
            exp = a.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return max(0, (exp - datetime.now(timezone.utc)).days)

        def _folders(a: InstagramAccount):
            rows = (
                db.query(FolderInstagramAccount, Folder)
                .join(Folder, FolderInstagramAccount.folder_id == Folder.id)
                .filter(FolderInstagramAccount.instagram_account_id == a.id)
                .all()
            )
            return [r.Folder.id for r in rows], [r.Folder.name for r in rows]

        result = []
        for a in accounts:
            folder_ids, folder_names = _folders(a)
            result.append({
                "id": a.id,
                "instagram_id": a.instagram_id,
                "username": a.username,
                "folder_ids": folder_ids,
                "folder_names": folder_names,
                "days_left": _days_left(a),
            })
        return result

    @router.post("/api/accounts/{account_id}/folders")
    async def add_account_folder(
        account_id: int,
        request: Request,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        data = await request.json()
        folder_id = data.get("folder_id")
        if not folder_id:
            raise HTTPException(status_code=400, detail="folder_id обязателен")
        account = db.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        if not db.query(Folder).filter_by(id=folder_id).first():
            raise HTTPException(status_code=404, detail="Папка не найдена")
        existing = db.query(FolderInstagramAccount).filter_by(
            instagram_account_id=account_id, folder_id=folder_id
        ).first()
        if not existing:
            db.add(FolderInstagramAccount(instagram_account_id=account_id, folder_id=folder_id))
            db.commit()
        return {"success": True}

    @router.delete("/api/accounts/{account_id}/folders/{folder_id}")
    async def remove_account_folder(
        account_id: int,
        folder_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        link = db.query(FolderInstagramAccount).filter_by(
            instagram_account_id=account_id, folder_id=folder_id
        ).first()
        if link:
            db.delete(link)
            db.commit()
        return {"success": True}

    @router.post("/api/accounts/{account_id}/check-connection")
    async def check_connection(
        account_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        account = db.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        try:
            data = await graph_api.get_account_info(str(account.access_token))
            if "error" in data:
                return {"valid": False, "error": data["error"].get("message", "Token invalid")}
            return {"valid": True, "username": data.get("username")}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    @router.post("/api/accounts/{account_id}/refresh-token")
    async def refresh_token(
        account_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        from datetime import timedelta
        account = db.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        try:
            new_token, new_expires_in = await graph_api.refresh_long_lived_token(str(account.access_token))
            account.access_token = new_token
            account.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(new_expires_in))
            account.updated_at = datetime.now(timezone.utc)
            db.commit()
            return {"success": True, "expires_in": new_expires_in}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ошибка обновления токена: {e}")

    @router.delete("/api/accounts/{account_id}")
    async def delete_account(
        account_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        account = db.query(InstagramAccount).filter_by(id=account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        # Обнуляем ссылку в результатах перед удалением аккаунта
        db.query(TaskInstagramResult).filter_by(instagram_account_id=account_id).update(
            {"instagram_account_id": None}
        )
        db.delete(account)
        db.commit()
        return {"success": True}

    # ─── SMMBox accounts ──────────────────────────────────────────────────────

    @router.post("/api/smmbox-accounts/sync")
    async def sync_smmbox_accounts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
        if not smmbox_client:
            raise HTTPException(status_code=400, detail="SMMBox не настроен: укажите SMMBOX_API_KEY")
        try:
            all_groups = smmbox_client.get_user_groups()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ошибка запроса к SMMBox: {e}")

        # non_ig = [g for g in all_groups if g.social != SocialType.INSTAGRAM]
        for g in all_groups:
            existing = db.query(SmmboxAccount).filter_by(smmbox_id=g.id).first()
            if existing:
                existing.name = g.name
                existing.social = g.social.value
                existing.type = g.type.value
            else:
                db.add(SmmboxAccount(
                    smmbox_id=g.id,
                    social=g.social.value,
                    type=g.type.value,
                    name=g.name,
                ))
        db.commit()
        return {"synced": len(non_ig)}

    @router.get("/api/smmbox-accounts")
    async def list_smmbox_accounts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
        accounts = db.query(SmmboxAccount).order_by(SmmboxAccount.social, SmmboxAccount.name).all()

        def _folders(a: SmmboxAccount):
            rows = (
                db.query(FolderSmmboxAccount, Folder)
                .join(Folder, FolderSmmboxAccount.folder_id == Folder.id)
                .filter(FolderSmmboxAccount.smmbox_account_id == a.id)
                .all()
            )
            return [r.Folder.id for r in rows], [r.Folder.name for r in rows]

        result = []
        for a in accounts:
            folder_ids, folder_names = _folders(a)
            result.append({
                "id": a.id,
                "smmbox_id": a.smmbox_id,
                "social": a.social,
                "type": a.type,
                "name": a.name,
                "folder_ids": folder_ids,
                "folder_names": folder_names,
            })
        return result

    @router.post("/api/smmbox-accounts/{account_id}/folders")
    async def add_smmbox_folder(
        account_id: int,
        request: Request,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        data = await request.json()
        folder_id = data.get("folder_id")
        if not folder_id:
            raise HTTPException(status_code=400, detail="folder_id обязателен")
        acc = db.query(SmmboxAccount).filter_by(id=account_id).first()
        if not acc:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")
        if not db.query(Folder).filter_by(id=folder_id).first():
            raise HTTPException(status_code=404, detail="Папка не найдена")
        existing = db.query(FolderSmmboxAccount).filter_by(
            smmbox_account_id=account_id, folder_id=folder_id
        ).first()
        if not existing:
            db.add(FolderSmmboxAccount(smmbox_account_id=account_id, folder_id=folder_id))
            db.commit()
        return {"success": True}

    @router.delete("/api/smmbox-accounts/{account_id}/folders/{folder_id}")
    async def remove_smmbox_folder(
        account_id: int,
        folder_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        link = db.query(FolderSmmboxAccount).filter_by(
            smmbox_account_id=account_id, folder_id=folder_id
        ).first()
        if link:
            db.delete(link)
            db.commit()
        return {"success": True}

    @router.delete("/api/smmbox-accounts/{account_id}")
    async def delete_smmbox_account(
        account_id: int,
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
    ):
        acc = db.query(SmmboxAccount).filter_by(id=account_id).first()
        if acc:
            db.delete(acc)
            db.commit()
        return {"success": True}

    # ─── Tasks ────────────────────────────────────────────────────────────────

    @router.get("/api/tasks")
    async def list_all_tasks(db: Session = Depends(get_db), _: User = Depends(require_admin)):
        tasks = db.query(PublishTask).order_by(PublishTask.created_at.desc()).all()
        result = []
        for task in tasks:
            ig_results = []
            for r in task.instagram_results:
                acc = r.account
                ig_results.append({
                    "account_id": r.instagram_account_id,
                    "instagram_id": acc.instagram_id if acc else None,
                    "username": acc.username if acc else None,
                    "status": r.status,
                    "error": r.error,
                    "media_id": r.media_id,
                    "permalink": r.permalink,
                })
            smm_results = []
            for r in task.smmbox_results:
                acc = r.account
                smm_results.append({
                    "account_id": r.smmbox_account_id,
                    "name": acc.name if acc else None,
                    "social": acc.social if acc else None,
                    "status": r.status,
                    "error": r.error,
                })
            result.append({
                "id": str(task.id),
                "folder_id": task.folder_id,
                "folder_name": task.folder.name if task.folder else None,
                "status": task.status,
                "stage": task.stage,
                "error": task.error,
                "is_test_mode": task.is_test_mode,
                "locked_by": task.locked_by,
                "created_at": str(task.created_at),
                "instagram_results": ig_results,
                "smmbox_results": smm_results,
            })
        return result

    return router
