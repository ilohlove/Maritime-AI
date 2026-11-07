"""Killable PDF parser subprocess. No model, network or credentials needed here."""

import json
import logging
import sys


def main():
    logging.disable(logging.CRITICAL)
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    from app.schemas.document import DocumentImport
    from app.services.documents import extract
    from app.services.document_ai import WorkflowError

    try:
        raw = sys.stdin.buffer.read(4_100_001)
        payload = DocumentImport.model_validate_json(raw)
        _, pages = extract(
            payload, max_bytes=3_000_000, max_pages=50, max_chars=200_000
        )
        print(json.dumps({"pages": pages}))
    except WorkflowError as error:
        print(json.dumps({"error": [error.code, error.message, error.status]}))
    except Exception:
        print(
            json.dumps(
                {
                    "error": [
                        "invalid_document",
                        "Cannot process this PDF within parser limits.",
                        422,
                    ]
                }
            )
        )


if __name__ == "__main__":
    main()
