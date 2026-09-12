"""
MediKiosk API.

Wires the routers, installs the cross-cutting middleware, and turns every
`AppError` into one consistent JSON shape so the frontend never has to guess.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.core.rate_limit import limiter
from app.db.session import engine
from app.services.ai.factory import get_ai_service
from app.services.ocr.factory import get_ocr_service
from app.services.escalation.screen_loader import load_screen
from app.services.questioning.schema import load_pathways
from app.services.storage.factory import get_storage_service

configure_logging(settings.DEBUG)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate pathway files at boot. A malformed JSON file should stop the
    # deploy, not surface halfway through a patient's intake.
    pathways = load_pathways()
    log.info("Pathways loaded", extra={"extra": {"count": len(pathways), "ids": sorted(pathways)}})

    # The safety screen is a control, not content. A malformed screen file must
    # stop the deploy rather than silently disable escalation.
    screen = load_screen()
    from app.services.escalation.rules import RULES

    unsigned = [r.id for r in RULES if not r.signed_off]
    log.info(
        "Safety screen loaded",
        extra={"extra": {"options": len(screen.nodes[0].options or []), "rules": len(RULES)}},
    )
    if unsigned:
        log.warning(
            "Escalation rules awaiting clinical sign-off",
            extra={"extra": {"rules": unsigned, "enforced_in_production": True}},
        )
    log.info(
        "Providers resolved",
        extra={
            "extra": {
                "ai": get_ai_service().name,
                "ocr": get_ocr_service().name,
                "storage": get_storage_service().name,
                "env": settings.ENV,
            }
        },
    )
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Pre-consultation patient case-taking API. AI prepares, the doctor verifies, "
        "the doctor decides. No endpoint in this service diagnoses, prescribes, or "
        "makes a clinical decision."
    ),
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENV != "production" else None,
)

app.state.limiter = limiter
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # explicit list; never "*" with credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def context_and_headers(request: Request, call_next):
    """Give every request an id, and set the security headers on the way out."""
    incoming = request.headers.get("x-request-id")
    request_id = incoming or uuid.uuid4().hex[:16]
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "request_id": request_id_ctx.get()},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request"
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_failed",
            "message": f"{field}: {first.get('msg', 'is not valid')}",
            "request_id": request_id_ctx.get(),
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "code": "rate_limited",
            "message": "Too many attempts. Wait a moment and try again.",
            "request_id": request_id_ctx.get(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the detail, return none of it: stack traces are not for the client.
    log.exception("Unhandled error", extra={"extra": {"path": request.url.path}})
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "Something went wrong at our end. Try again.",
            "request_id": request_id_ctx.get(),
        },
    )


@app.get("/health", tags=["ops"])
async def health() -> dict:
    """Liveness. Deliberately does not touch the database."""
    return {"status": "ok", "env": settings.ENV}


@app.get("/health/ready", tags=["ops"])
async def readiness() -> JSONResponse:
    """Readiness. Reports the database honestly instead of always returning ok."""
    healthy = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        database = f"unavailable: {str(exc)[:120]}"

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "database": database,
            "ai_provider": get_ai_service().name,
            "ocr_provider": get_ocr_service().name,
            "storage_provider": get_storage_service().name,
        },
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
