"""Provider-neutral document inference contract, separate from the legacy mock."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.schemas.document import GroundedAnswer, QueryTerms


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


@dataclass(frozen=True)
class Excerpt:
    id: int
    page: int
    text: str


class DocumentAIProvider(Protocol):
    name: str
    online: bool

    def close(self) -> None: ...

    def query_terms(self, question: str) -> QueryTerms: ...

    def answer(self, question: str, excerpts: list[Excerpt]) -> GroundedAnswer: ...


@dataclass(frozen=True)
class ProviderRegistration:
    online: bool
    create: Callable[[str], DocumentAIProvider]
