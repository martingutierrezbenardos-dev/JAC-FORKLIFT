from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import verify_password
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_login)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = user_service.get_by_email(db, payload.email)
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user)
