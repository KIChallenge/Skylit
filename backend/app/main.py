"""FastAPI application and local server entry point."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.appointments import router as appointments_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.calendar import router as calendar_router
from app.api.conversations import router as conversations_router
from app.api.dev import router as dev_router
from app.api.documents import router as documents_router
from app.api.escalations import router as escalations_router
from app.api.form_drafts import router as form_drafts_router
from app.api.health import router as health_router
from app.api.messages import router as messages_router
from app.api.schema_events import router as schema_events_router
from app.config import settings
from app.db import engine
from app.rag.embedder import get_embedder

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


async def _warm_embedder() -> None:
    # Load the model in the background so startup and health stay fast.
    try:
        await get_embedder().warm_up()
    except Exception:
        logger.exception("Embedder warm-up failed; retrieval loads it on first use")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    warm_up = (
        asyncio.create_task(_warm_embedder())
        if settings.llm_provider != "fake"
        else None
    )
    try:
        yield
    finally:
        if warm_up is not None:
            warm_up.cancel()
        await engine.dispose()


app = FastAPI(title="SV KI-Lotse API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(dev_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(schema_events_router, prefix="/api")
app.include_router(form_drafts_router, prefix="/api")
app.include_router(escalations_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(audit_router, prefix="/api")

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status_code,
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Routes pass {"code", "message"} via app.deps.api_error; plain details map here.
    detail = exc.detail
    if isinstance(detail, dict) and {"code", "message"} <= detail.keys():
        code, message = str(detail["code"]), str(detail["message"])
    else:
        code = ERROR_CODES.get(exc.status_code, "error")
        message = str(detail)
    return error_response(exc.status_code, code, message, exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    paths = (
        ".".join(str(part) for part in error["loc"] if part != "body")
        for error in exc.errors()
    )
    fields = ", ".join(dict.fromkeys(path for path in paths if path)) or "Anfrage"
    return error_response(422, "validation_error", f"Ungültige Eingabe: {fields}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port or settings.backend_port,
        log_level=settings.log_level.lower(),
    )
