from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vessel import Vessel, utc_now
from app.schemas.vessel import FieldProvenance, VesselValues, VesselWrite


def list_vessels(session: Session):
    return session.scalars(select(Vessel).order_by(Vessel.created_at, Vessel.id)).all()


def save_vessel(session: Session, payload: VesselWrite, vessel: Vessel | None = None):
    vessel = vessel or Vessel()
    changes = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    merged = {name: getattr(vessel, name, None) for name in VesselValues.model_fields}
    merged.update(changes)
    VesselValues.model_validate(merged)
    now = utc_now()
    provenance = dict(vessel.field_provenance or {})
    for name, value in changes.items():
        setattr(vessel, name, value)
        if value is None:
            provenance.pop(name, None)
        else:
            metadata = payload.provenance.get(name, FieldProvenance())
            provenance[name] = metadata.model_copy(
                update={"last_updated": now}
            ).model_dump(mode="json")
    vessel.field_provenance = provenance
    vessel.updated_at = now
    session.add(vessel)
    session.commit()
    session.refresh(vessel)
    return vessel
