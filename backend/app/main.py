"""FastAPI application entry point.

Run locally:
    uv run fastapi dev app/main.py
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import (
    cognition,
    health,
    live,
    members,
    mood,
    summary,
    tiredness,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        summary="EEG mood tracking & tiredness detection over the AWEAR API",
        version="0.1.0",
    )

    app.include_router(health.router)
    app.include_router(members.router)
    app.include_router(mood.router)
    app.include_router(tiredness.router)
    app.include_router(cognition.router)
    app.include_router(live.router)
    app.include_router(summary.router)

    return app


app = create_app()
