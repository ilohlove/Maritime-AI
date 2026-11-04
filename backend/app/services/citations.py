"""Validate exact source quotes and construct references from local metadata."""

import re

from app.schemas.document import GroundedAnswer
from app.services.document_ai import Excerpt, WorkflowError


def validate_answer(answer: GroundedAnswer, excerpts: list[Excerpt], document: dict):
    if answer.status == "declined":
        raise WorkflowError(
            "model_declined",
            "The model could not support an answer from the retrieved evidence.",
            422,
        )
    evidence = {e.id: e for e in excerpts}
    if not answer.claims:
        raise WorkflowError(
            "citation_validation_failed",
            "The answer has no supporting citations. Retry or review the source.",
            422,
        )
    claims = []
    for claim in answer.claims:
        excerpt = evidence.get(claim.excerpt_id)
        # References and quoted strings must be rendered from validated source data,
        # never model-authored page numbers, references or quotations in claim text.
        if (
            excerpt is None
            or not claim.quote.strip()
            or claim.quote not in excerpt.text
            or re.search(
                r"(?:\b(?:pages?|trang|source|document|reference)\s*[:#]?\s*\d|\[\d+\]|[\"“”])",
                claim.text,
                re.IGNORECASE,
            )
        ):
            raise WorkflowError(
                "citation_validation_failed",
                "An answer citation did not match the supplied evidence. Review the source or retry.",
                422,
            )
        claims.append(
            {
                "text": claim.text,
                "source": {
                    "document_id": document["id"],
                    "title": document["title"],
                    "page": excerpt.page,
                    "excerpt_id": excerpt.id,
                    "quote": claim.quote,
                },
            }
        )
    return claims
