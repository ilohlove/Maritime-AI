from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models.vessel import Vessel
from app.schemas.vessel import VesselRead, VesselWrite
from app.services.vessels import list_vessels, save_vessel


def create_vessel_router(sessions) -> APIRouter:
    router = APIRouter(prefix="/api/vessels", tags=["vessels"])

    @router.get("", response_model=list[VesselRead])
    def get_vessels():
        with sessions() as session:
            return list_vessels(session)

    @router.get("/{vessel_id}", response_model=VesselRead)
    def get_vessel(vessel_id: str):
        with sessions() as session:
            vessel = session.get(Vessel, vessel_id)
            if vessel is None:
                raise HTTPException(404, "Vessel profile not found")
            return vessel

    def persist(payload, vessel_id=None):
        with sessions() as session:
            vessel = session.get(Vessel, vessel_id) if vessel_id else None
            if vessel_id and vessel is None:
                raise HTTPException(404, "Vessel profile not found")
            try:
                return save_vessel(session, payload, vessel)
            except ValidationError as error:
                raise RequestValidationError(error.errors()) from error

    @router.post("", response_model=VesselRead, status_code=201)
    def create_vessel(payload: VesselWrite):
        return persist(payload)

    @router.patch("/{vessel_id}", response_model=VesselRead)
    def update_vessel(vessel_id: str, payload: VesselWrite):
        return persist(payload, vessel_id)

    return router
