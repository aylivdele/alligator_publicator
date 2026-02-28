
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import config
from app.domain.models import Folder, InstagramAccount
from app.infrastructure.database.sqlite import get_db
from app.infrastructure.instagram.graph_api_client import InstagramGraphApiClient


def create_auth_routes(graph_api: InstagramGraphApiClient):
    router = APIRouter()
    templates = Jinja2Templates(directory="templates")
    settings = config.settings

    def get_auth_url(folder_id: Optional[int] = None):
        state = str(folder_id) if folder_id else "0"
        return (
            f"https://www.instagram.com/oauth/authorize"
            f"?client_id={settings.CLIENT_ID}"
            f"&redirect_uri={settings.REDIRECT_URI}"
            f"&scope=instagram_business_basic,instagram_business_content_publish"
            f"&response_type=code"
            f"&state={state}"
        )

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})


    @router.get("/start-auth")
    async def start_auth(folder_id: Optional[int] = None):
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

            account = db.query(InstagramAccount).filter_by(instagram_id=instagram_id).first()
            if account:
                account.access_token = long_token
                account.expires_in = expires_in
                account.username = username
                if folder_id is not None:
                    account.folder_id = folder_id
            else:
                account = InstagramAccount(
                    instagram_id=instagram_id,
                    username=username,
                    access_token=long_token,
                    expires_in=expires_in,
                    folder_id=folder_id
                )
                db.add(account)

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
            return templates.TemplateResponse("result.html", {
                    "request": request,
                    "success": False,
                    "error": f"Непредвиденная ошибка: {e}"
                })
    return router
