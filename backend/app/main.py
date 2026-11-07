import logging
from contextlib import asynccontextmanager
from threading import BoundedSemaphore

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.api.auth import create_auth_router
from app.api.documents import create_document_router
from app.api.vessels import create_vessel_router
from app.core.config import Settings
from app.core.object_storage import create_storage
from app.core.storage import document_directory, validate_storage
from app.db.session import create_database
from app.services.ai_limits import AIGuard
from app.services.auth import AuthService
from app.services.document_ai import ProviderRegistration, WorkflowError
from app.services.openai_provider import OpenAIProvider


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.environment == "production":
        for name in (
            "openai",
            "httpx",
            "httpcore",
            "sqlalchemy.engine",
            "boto3",
            "botocore",
            "s3transfer",
            "psycopg",
        ):
            logging.getLogger(name).setLevel(logging.WARNING)
        # Parser diagnostics can contain untrusted document fragments.
        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    engine, sessions = create_database(settings.database_url)

    directory = document_directory(settings)
    storage = create_storage(settings, directory)
    auth = AuthService(engine, settings)

    @asynccontextmanager
    async def lifespan(app):
        try:
            validate_storage(engine, settings, directory, storage)
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Maritime AI Assistant",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.document_directory = directory
    app.state.storage = storage
    app.state.upload_slot = BoundedSemaphore(1)
    app.state.settings = settings
    app.state.ai_guard = AIGuard(engine, settings)
    app.state.auth = auth
    app.state.document_providers = {
        "openai": ProviderRegistration(
            True, lambda model: OpenAIProvider(settings, model)
        )
    }

    @app.exception_handler(WorkflowError)
    async def workflow_error(request, error):
        return JSONResponse(
            {"detail": {"code": error.code, "message": error.message}},
            status_code=error.status,
        )

    @app.exception_handler(RequestValidationError)
    async def input_error(request, error):
        return JSONResponse(
            {
                "detail": [
                    {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ]
            },
            status_code=422,
        )

    @app.middleware("http")
    async def security_guard(request: Request, call_next):
        try:
            if settings.environment == "production" and request.url.scheme != "https":
                raise WorkflowError("https_required", "HTTPS is required.", 400)
            origin = request.headers.get("origin")
            if origin and origin not in settings.allowed_origins:
                raise WorkflowError(
                    "origin_not_permitted", "Origin is not permitted.", 403
                )
            public = (
                request.method in {"GET", "HEAD"} and request.url.path == "/api/health"
            ) or (request.method == "POST" and request.url.path == "/api/auth/login")
            if not public and request.method != "OPTIONS":
                await run_in_threadpool(auth.authenticate, request)
            if (
                settings.disposable_test_mode
                and request.url.path.startswith("/api/vessels")
                and request.method in {"POST", "PATCH", "PUT", "DELETE"}
            ):
                raise WorkflowError(
                    "disposable_vessel_write_disabled",
                    "Vessel writes are disabled in synthetic disposable testing.",
                    403,
                )
            if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
                if (
                    request.headers.get("content-type", "").split(";")[0]
                    != "application/json"
                ):
                    raise WorkflowError("json_required", "Use application/json", 415)
                limit = (
                    settings.upload_request_bytes
                    if request.url.path == "/api/documents"
                    else (4096 if request.url.path == "/api/auth/login" else 65536)
                )
                body = bytearray()
                async for part in request.stream():
                    if len(body) + len(part) > limit:
                        raise WorkflowError(
                            "request_too_large",
                            "Request exceeds the allowed size.",
                            413,
                        )
                    body.extend(part)
                # Starlette's cached Request replays this bounded body to FastAPI.
                request._body = bytes(body)
            response = await call_next(request)
        except WorkflowError as error:
            response = JSONResponse(
                {"detail": {"code": error.code, "message": error.message}},
                status_code=error.status,
            )
        except Exception as error:  # noqa: BLE001 - never log document text, credentials or SQL parameters
            logging.getLogger("maritime.security").error(
                "Request failed (%s)", type(error).__name__
            )
            response = JSONResponse(
                {
                    "detail": {
                        "code": "internal_error",
                        "message": "The backend could not complete the request. Contact the administrator.",
                    }
                },
                status_code=500,
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    # CORS wraps owner-auth failures; host and gateway checks also guard preflight.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )
    if settings.https_transport == "signed-gateway":
        from app.core.gateway import SignedGatewayMiddleware

        app.add_middleware(
            SignedGatewayMiddleware,
            engine=engine,
            secret=settings.gateway_secret,
            upload_limit=settings.upload_request_bytes
            if settings.online_mvp_mode
            else 65536,
        )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts)
    )

    @app.get("/api/health")
    def health():
        from sqlalchemy import text

        with engine.connect() as connection:
            connection.execute(text("SELECT id FROM vessels LIMIT 1"))
        return {"status": "ok"}

    app.include_router(create_auth_router(auth, settings))
    app.include_router(create_vessel_router(sessions, settings))
    app.include_router(create_document_router(sessions, settings))
    return app
