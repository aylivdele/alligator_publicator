
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import config
from app.api.deps import get_current_user, require_admin
from app.domain.models import Folder, FolderInstagramAccount, InstagramAccount, User
from app.infrastructure.database.db import get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient


def create_auth_routes(graph_api: InstagramGraphApiClient, settings: Optional[config.Settings] = None):
    router = APIRouter()
    module_path = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(module_path, 'templates')
    templates = Jinja2Templates(directory=template_dir)
    if settings is None:
        settings = config.settings

    def get_auth_url(folder_id: Optional[int] = None):
        state = str(folder_id) if folder_id else "0"
        return (
            f"https://www.instagram.com/oauth/authorize?force_reauth=true&client_id=1981989866068427&redirect_uri=https://alligator.meta-box.ru/auth&response_type=code&scope=instagram_business_basic%2Cinstagram_business_content_publish%2Cinstagram_business_manage_insights&state={state}"
        )

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request, current_user: Optional[User] = Depends(get_current_user)):
        if current_user is None:
            return RedirectResponse("/login", status_code=302)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "views_refresh_minutes": settings.VIEWS_REFRESH_MINUTES,
            "views_max_age_hours": settings.VIEWS_MAX_AGE_HOURS,
        })

    @router.get("/start-auth")
    async def start_auth(folder_id: Optional[int] = None, _: User = Depends(require_admin)):
        url = get_auth_url(folder_id)
        return RedirectResponse(url=url)

    @router.get("/auth", response_class=HTMLResponse)
    async def auth_callback(request: Request, db: Session = Depends(get_db)):
        code = request.query_params.get("code")
        error = request.query_params.get("error_description")
        state = request.query_params.get("state", "0")

        folder_id = None
        folder_name = None
        try:
            fid = int(state)
            if fid > 0:
                folder = db.query(Folder).filter_by(id=fid).first()
                if folder:
                    folder_id = folder.id
                    folder_name = folder.name
        except (ValueError, TypeError):
            pass

        if error:
            return templates.TemplateResponse("result.html", {
                "request": request,
                "success": False,
                "error": error
            })

        if not code:
            return RedirectResponse(url="/")

        try:
            long_token, expires_in = await graph_api.get_token(code)
            me = await graph_api.get_account_info(long_token)

            if "id" not in me:
                return templates.TemplateResponse("result.html", {
                    "request": request,
                    "success": False,
                    "error": f"Не удалось получить данные аккаунта: {me}"
                })

            instagram_id = me["id"]
            username = me.get("username", "unknown")
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

            account = db.query(InstagramAccount).filter_by(instagram_id=instagram_id).first()
            if account:
                account.access_token = long_token
                account.expires_at = expires_at
                account.username = username
            else:
                account = InstagramAccount(
                    instagram_id=instagram_id,
                    username=username,
                    access_token=long_token,
                    expires_at=expires_at,
                )
                db.add(account)
                db.flush()  # получаем account.id

            # Привязываем к папке через junction-таблицу
            if folder_id is not None:
                existing_link = db.query(FolderInstagramAccount).filter_by(
                    folder_id=folder_id, instagram_account_id=account.id
                ).first()
                if not existing_link:
                    db.add(FolderInstagramAccount(folder_id=folder_id, instagram_account_id=account.id))

            db.commit()

            return templates.TemplateResponse("result.html", {
                "request": request,
                "success": True,
                "username": username,
                "instagram_id": instagram_id,
                "token_preview": long_token[:40] + "...",
                "expires_days": expires_in // 86400,
                "folder_name": folder_name
            })
        except Exception as e:
            logging.getLogger(__name__).exception("Auth error: %s", e)
            return templates.TemplateResponse("result.html", {
                "request": request,
                "success": False,
                "error": f"Непредвиденная ошибка: {e}"
            })

    return router
