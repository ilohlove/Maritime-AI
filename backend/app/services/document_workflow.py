"""Consent-gated orchestration; document storage/retrieval has no SDK dependency."""

from app.schemas.document import Question
from app.services import documents
from app.services.citations import validate_answer
from app.services.document_ai import ProviderRegistration, WorkflowError


def answer_question(
    sessions,
    document_id: str,
    payload: Question,
    registration: ProviderRegistration | None,
):
    if registration is None:
        raise WorkflowError(
            "invalid_provider", "Select an installed document AI provider.", 422
        )
    if registration.online and not payload.external_consent:
        raise WorkflowError(
            "consent_required",
            "Explicit consent is required to send the question and retrieved excerpts to the online provider.",
            403,
        )
    document = documents.get_document(sessions, document_id)
    provider = registration.create(payload.model)
    try:
        queries = provider.query_terms(payload.question)
        excerpts = documents.retrieve(
            sessions,
            document_id,
            [payload.question, queries.english, queries.vietnamese],
        )
        if not excerpts:
            return {
                "status": "no_evidence",
                "claims": [],
                "provider": provider.name,
                "model": payload.model,
                "message": "No relevant excerpts found. Try different terms; this does not prove the document lacks the information.",
            }
        answer = provider.answer(payload.question, excerpts)
        return {
            "status": "answered",
            "claims": validate_answer(answer, excerpts, document),
            "provider": provider.name,
            "model": payload.model,
        }
    finally:
        provider.close()
