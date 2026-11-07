from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from sqlalchemy import select
from app.services.documents import owner_filter
from app.models.vessel import Vessel
from app.schemas.vessel import VesselRead, VesselWrite
from app.services.vessels import save_vessel


def create_vessel_router(sessions, settings) -> APIRouter:
    router = APIRouter(prefix="/api/vessels", tags=["vessels"])

    @router.get("", response_model=list[VesselRead])
    def get_vessels(request: Request):
        with sessions() as session:
            return session.scalars(
                select(Vessel)
                .where(
                    owner_filter(
                        Vessel, request.state.user, not settings.online_mvp_mode
                    )
                )
                .order_by(Vessel.created_at, Vessel.id)
            ).all()

    @router.get("/{vessel_id}", response_model=VesselRead)
    def get_vessel(vessel_id: str, request: Request):
        with sessions() as session:
            vessel = session.get(Vessel, vessel_id)
            if vessel is None or (
                vessel.owner_id != request.state.user
                and not (vessel.owner_id is None and not settings.online_mvp_mode)
            ):
                raise HTTPException(404, "Vessel profile not found")
            return vessel

    def persist(payload, owner, vessel_id=None):
        with sessions() as session:
            vessel = session.get(Vessel, vessel_id) if vessel_id else None
            if vessel_id and (
                vessel is None
                or (
                    vessel.owner_id != owner
                    and not (vessel.owner_id is None and not settings.online_mvp_mode)
                )
            ):
                raise HTTPException(404, "Vessel profile not found")
            if vessel is None:
                vessel = Vessel(owner_id=owner)
            try:
                return save_vessel(session, payload, vessel)
            except ValidationError as error:
                raise RequestValidationError(error.errors()) from error

    @router.post("", response_model=VesselRead, status_code=201)
    def create_vessel(payload: VesselWrite, request: Request):
        return persist(payload, request.state.user)

    @router.patch("/{vessel_id}", response_model=VesselRead)
    def update_vessel(vessel_id: str, payload: VesselWrite, request: Request):
        return persist(payload, request.state.user, vessel_id)

    return router
