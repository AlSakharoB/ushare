import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from receiptsplit.api.auth import router as auth_router
from receiptsplit.api.errors import AppError
from receiptsplit.api.members import router as members_router
from receiptsplit.api.receipts import router as receipts_router
from receiptsplit.config import Settings
from receiptsplit.db.session import build_engine
from receiptsplit.domain.clock import SystemClock

logger = logging.getLogger("receiptsplit")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="ReceiptSplit", version="0.1.0")
    app.state.settings = settings
    app.state.engine = build_engine(settings.database_url)
    app.state.clock = SystemClock()
    app.include_router(auth_router)
    app.include_router(members_router)
    app.include_router(receipts_router)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            logger.error("request_id=%s error=internal_error", request.state.request_id)
            response = JSONResponse(
                {
                    "code": "internal_error",
                    "message": "Внутренняя ошибка",
                    "details": {},
                    "request_id": request.state.request_id,
                },
                status_code=500,
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request.state.request_id,
            },
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "code": "validation_error",
                "message": "Некорректные данные",
                "details": {"fields": [list(e["loc"]) for e in exc.errors()]},
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> Any:
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ready"}
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    return app


app = create_app()
