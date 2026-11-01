from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Text = Annotated[str, Field(max_length=200)]
Measurement = Annotated[
    Decimal, Field(gt=0, max_digits=14, decimal_places=3, allow_inf_nan=False)
]
Count = Annotated[int, Field(gt=0, le=2_000_000_000, strict=True)]


class VesselValues(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    vessel_name: Text | None = None
    former_name: Text | None = None
    imo_number: Annotated[str, Field(pattern=r"^[0-9]{7}$")] | None = None
    mmsi: Annotated[str, Field(pattern=r"^[0-9]{9}$")] | None = None
    call_sign: Text | None = None
    flag: Text | None = None
    port_of_registry: Text | None = None
    vessel_type: Text | None = None
    classification_society: Text | None = None
    main_engine_manufacturer: Text | None = None
    main_engine_model: Text | None = None
    year_built: Annotated[int, Field(ge=1800, le=2100, strict=True)] | None = None
    gross_tonnage: Count | None = None
    net_tonnage: Count | None = None
    length_overall: Measurement | None = None
    length_between_perpendiculars: Measurement | None = None
    breadth_moulded: Measurement | None = None
    depth_moulded: Measurement | None = None
    summer_draft: Measurement | None = None
    summer_deadweight: Measurement | None = None
    main_engine_power: Measurement | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("imo_number")
    @classmethod
    def valid_imo(cls, value):
        if value and sum(
            int(digit) * weight for digit, weight in zip(value[:6], range(7, 1, -1))
        ) % 10 != int(value[-1]):
            raise ValueError("IMO number checksum is invalid")
        return value

    @model_validator(mode="after")
    def consistent_values(self):
        if (
            self.net_tonnage is not None
            and self.gross_tonnage is not None
            and self.net_tonnage > self.gross_tonnage
        ):
            raise ValueError("Net tonnage must not exceed gross tonnage")
        if (
            self.length_between_perpendiculars is not None
            and self.length_overall is not None
            and self.length_between_perpendiculars > self.length_overall
        ):
            raise ValueError(
                "Length between perpendiculars must not exceed length overall"
            )
        return self


class FieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    extraction_method: Literal["user_entered", "imported", "ai_extracted"] = (
        "user_entered"
    )
    source_document: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    verification_status: Literal["unverified", "verified"] = "unverified"
    last_updated: datetime | None = None


class VesselWrite(VesselValues):
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_provenance(self):
        for name, metadata in self.provenance.items():
            if name not in VesselValues.model_fields:
                raise ValueError(f"Unknown provenance field: {name}")
            if name not in self.model_fields_set:
                raise ValueError(
                    f"Provide the value when setting provenance for {name}"
                )
            if getattr(self, name) is None:
                raise ValueError(
                    f"Cannot attach provenance to an unknown value: {name}"
                )
            if (
                metadata.extraction_method == "ai_extracted"
                and metadata.verification_status == "verified"
            ):
                raise ValueError(
                    "AI extraction must be unverified; record human verification separately"
                )
        return self


class VesselRead(VesselValues):
    model_config = ConfigDict(from_attributes=True)
    id: str
    field_provenance: dict[str, FieldProvenance]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def utc_timestamps(cls, value):
        # SQLite strips timezone information; all server timestamps are UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
