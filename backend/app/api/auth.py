from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)


def create_auth_router(auth, settings):
    router = APIRouter(prefix="/api/auth")

    @router.post("/login")
    def login(payload: Login, request: Request, response: Response):
        session = auth.login(
            payload.username,
            payload.password,
            request.client.host if request.client else "unknown",
        )
        if settings.auth_transport == "cookie":
            response.set_cookie(
                "__Host-maritime_session",
                session.pop("access_token"),
                max_age=settings.session_seconds,
                httponly=True,
                secure=True,
                samesite="strict",
                path="/",
            )
        return session

    @router.get("/session")
    def current(request: Request):
        return {"user": request.state.user, "transport": settings.auth_transport}

    @router.post("/logout")
    def logout(request: Request, response: Response):
        auth.logout(request.state.session_digest)
        response.delete_cookie(
            "__Host-maritime_session",
            path="/",
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return {"status": "logged_out"}

    return router
