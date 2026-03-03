from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.domain.models import User
from app.infrastructure.database.db import get_db

import os

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(username=username).first()
    if not user or not pwd_context.verify(password, str(user.password_hash)):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Неверный логин или пароль"}, status_code=401
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@router.get("/api/me")
async def get_me(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        request.session.clear()
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }
