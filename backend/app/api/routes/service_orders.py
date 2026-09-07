from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import domain_errors_as_http
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.service_order import ServiceOrderStatus
from app.models.user import User
from app.schemas.service_order import ServiceOrderOut, ServiceOrderSearchParams
from app.services import service_order_service

router = APIRouter(prefix="/api/service-orders", tags=["service-orders"])


@router.get("", response_model=list[ServiceOrderOut])
def search_service_orders(
    estado: ServiceOrderStatus | None = None,
    tecnico_telefono: str | None = None,
    cliente_nombre: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ServiceOrderOut]:
    params = ServiceOrderSearchParams(
        estado=estado, tecnico_telefono=tecnico_telefono, cliente_nombre=cliente_nombre
    )
    with domain_errors_as_http():
        return list(service_order_service.search_service_orders(db, actor=current_user, params=params))
