from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.machine import MachineOut
from app.services import machine_service

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("", response_model=list[MachineOut])
def list_machines(
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.MACHINES_READ)),
) -> list[MachineOut]:
    return list(machine_service.list_all(db))
