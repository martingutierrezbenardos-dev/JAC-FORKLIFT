from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException, status

from app.core.errors import DomainError, NotFoundError, PermissionDeniedError, ValidationDomainError


@contextmanager
def domain_errors_as_http():
    """Traduce excepciones de dominio a códigos HTTP apropiados en los endpoints REST."""
    try:
        yield
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationDomainError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
