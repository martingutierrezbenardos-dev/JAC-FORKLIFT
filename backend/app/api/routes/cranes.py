from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import get_current_user, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.crane import CraneContractCreate
from app.services import crane_service

router = APIRouter(prefix="/api/crane-contracts", tags=["cranes"])


@router.get("")
def list_contracts(
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.CRANES_MANAGE)),
) -> list[dict]:
    return crane_service.list_active_contracts(db)


@router.post("", status_code=201)
def create_contract(
    payload: CraneContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    with domain_errors_as_http():
        result = crane_service.create_crane_contract(db, actor=current_user, data=payload, canal="web")
        db.commit()
    return result
