from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.domain.models import User, UserRole
from app.infrastructure.database.db import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter_by(id=user_id).first()


def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(user: Optional[User] = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
