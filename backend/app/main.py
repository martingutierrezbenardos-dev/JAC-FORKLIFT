from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, expenses, reports, tasks, users, whatsapp
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title="Jacobea AI",
    description="IA conversacional de gestión interna para Jacobea Forklift Chile",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(expenses.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(whatsapp.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
