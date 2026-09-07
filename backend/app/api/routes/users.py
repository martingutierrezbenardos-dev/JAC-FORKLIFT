from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.USERS_READ_ALL)),
) -> list[UserOut]:
    return list(user_service.list_all(db))


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserOut:
    with domain_errors_as_http():
        user = user_service.create_user(db, payload)
        db.commit()
    return user
