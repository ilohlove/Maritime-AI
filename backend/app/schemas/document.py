from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentImport(StrictModel):
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    format: Literal["text", "pdf"]
    # JSON/base64 keeps the existing JSON-only cross-origin write boundary.
    content: str = Field(min_length=1, max_length=14_000_000)


class Question(StrictModel):
    question: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    provider: str = Field(default="openai", max_length=80)
    model: str = Field(min_length=1, max_length=100)
    external_consent: StrictBool = False


class QueryTerms(StrictModel):
    english: str = Field(max_length=1000)
    vietnamese: str = Field(max_length=1000)


class EvidenceClaim(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    excerpt_id: int
    quote: str = Field(min_length=1, max_length=1800)


class GroundedAnswer(StrictModel):
    status: Literal["answered", "declined"]
    claims: list[EvidenceClaim] = Field(max_length=8)
