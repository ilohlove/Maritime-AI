"""Small extraction boundary. Formats listed here are not import capabilities."""
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Protocol
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class PageLocator(Record):
    kind: Literal['page'] = 'page'
    page_number: int = Field(ge=1)


class SectionLocator(Record):
    kind: Literal['section'] = 'section'
    heading: str
    paragraph: int | None = Field(default=None, ge=1)


class SheetLocator(Record):
    kind: Literal['sheet'] = 'sheet'
    sheet_name: str
    cell_range: str


class RowsLocator(Record):
    kind: Literal['rows'] = 'rows'
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start:
            raise ValueError('Source range end precedes start')
        return self


class LinesLocator(RowsLocator):
    kind: Literal['lines'] = 'lines'


class ImageLocator(Record):
    kind: Literal['image'] = 'image'
    # Pixel coordinates in the original image; absent means the whole image.
    bbox: tuple[int, int, int, int] | None = None


SourceLocator = Annotated[PageLocator | SectionLocator | SheetLocator | RowsLocator | LinesLocator | ImageLocator,
                          Field(discriminator='kind')]


class TableContent(Record):
    columns: list[str | None]
    rows: list[list[str | None]]

    @model_validator(mode='after')
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError('Table rows must match column count')
        return self


class DocumentMetadata(Record):
    document_id: UUID
    revision_id: UUID
    name: str
    source_format: Literal['pdf', 'docx', 'doc', 'xlsx', 'xls', 'txt', 'csv', 'markdown', 'image']
    media_type: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    size_bytes: int = Field(ge=0)
    business_version: str | None = None
    effective_date: date | None = None


class ExtractionFile(Record):
    path: Path
    metadata: DocumentMetadata


class ContentUnit(Record):
    id: UUID
    kind: Literal['text', 'table'] = 'text'
    locator: SourceLocator
    text: str
    table: TableContent | None = None

    @model_validator(mode='after')
    def table_required(self):
        if (self.kind == 'table') != (self.table is not None):
            raise ValueError('Only table units must carry structured table content')
        return self


class ExtractionError(Record):
    code: str
    message: str
    unit_id: UUID | None = None


class ExtractionResult(Record):
    metadata: DocumentMetadata
    status: Literal['ready', 'partial', 'failed']
    units: list[ContentUnit] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)
    extractor: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'failed' and (self.units or not self.errors):
            raise ValueError('Failed extraction requires errors and no indexed units')
        if self.status != 'failed' and not self.units:
            raise ValueError('Successful extraction requires content units')
        if len({unit.id for unit in self.units}) != len(self.units):
            raise ValueError('Content unit IDs must be unique within a revision')
        return self


class Extractor(Protocol):
    def extract(self, file: ExtractionFile) -> ExtractionResult: ...


def initial_revision_id(document_id: str | UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f'maritime:{document_id}:revision:1')


def pdf_unit_id(revision_id: str | UUID, page_number: int) -> UUID:
    return uuid5(NAMESPACE_URL, f'maritime:{revision_id}:page:{page_number}')
