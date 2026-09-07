from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.vehicle import VehicleOut
from app.services import vehicle_service

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleOut])
def list_vehicles(
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.VEHICLES_READ)),
) -> list[VehicleOut]:
    return list(vehicle_service.list_all(db))
