from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.vessels import create_vessel_router
from app.core.config import Settings
from app.db.session import create_database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine, sessions = create_database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(
        title="Maritime AI Assistant",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.engine = engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    # JSON-only writes with an explicit Origin check also protect against browser
    # requests from unrelated websites; CORS alone does not reject such writes.
    @app.middleware("http")
    async def local_write_guard(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            from starlette.responses import JSONResponse

            origin = request.headers.get("origin")
            if origin and origin not in settings.allowed_origins:
                return JSONResponse(
                    {"detail": "Origin is not permitted"}, status_code=403
                )
            if (
                request.headers.get("content-type", "").split(";")[0]
                != "application/json"
            ):
                return JSONResponse({"detail": "Use application/json"}, status_code=415)
        return await call_next(request)

    @app.get("/api/health")
    def health():
        from sqlalchemy import text

        with engine.connect() as connection:
            connection.execute(text("SELECT id FROM vessels LIMIT 1"))
        return {"status": "ok", "ai_provider": "mock-development-only"}

    app.include_router(create_vessel_router(sessions))
    return app
