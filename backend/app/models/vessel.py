from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utc_now():
    return datetime.now(UTC)


class Vessel(Base):
    __tablename__ = "vessels"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    vessel_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    former_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imo_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mmsi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    call_sign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    flag: Mapped[str | None] = mapped_column(String(200), nullable=True)
    port_of_registry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vessel_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classification_society: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    main_engine_manufacturer: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    main_engine_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    year_built: Mapped[int | None] = mapped_column(nullable=True)
    gross_tonnage: Mapped[int | None] = mapped_column(nullable=True)
    net_tonnage: Mapped[int | None] = mapped_column(nullable=True)
    length_overall: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    length_between_perpendiculars: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    breadth_moulded: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    depth_moulded: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    summer_draft: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    summer_deadweight: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    main_engine_power: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    field_provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
