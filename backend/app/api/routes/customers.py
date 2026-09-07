from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.customer import CustomerOut
from app.services import customer_service

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    _current=Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> list[CustomerOut]:
    return list(customer_service.list_all(db))
