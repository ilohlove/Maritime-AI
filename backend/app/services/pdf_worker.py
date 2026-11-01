"""Bounded, disposable PDF parser process. Never runs PDF actions or scripts."""
import json
import sys
from pathlib import Path
from typing import Protocol


class TextExtractor(Protocol):
    def extract(self, path: Path) -> list[str]: ...


class PDFExtractor:
    def extract(self, path: Path) -> list[str]:
        from pypdf import PdfReader
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported. Import an unlocked text-based PDF.")
        if not 1 <= len(reader.pages) <= 100:
            raise ValueError("Import a PDF containing 1–100 pages.")
        pages = []
        total = 0
        for page in reader.pages:
            value = (page.extract_text() or "").replace("\x00", "").strip()
            total += len(value)
            if total > 1_000_000:
                raise ValueError("Extracted text exceeds the 1 million character limit.")
            pages.append(value)
        if not any(value.strip() for value in pages):
            raise ValueError("No readable text. Scanned/image PDFs require OCR, which is unavailable.")
        return pages


if __name__ == "__main__":
    # Linux safety limit; Windows still has process isolation and a parent timeout.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    except ImportError:
        pass
    try:
        print(json.dumps({"pages": PDFExtractor().extract(Path(sys.argv[1]))}))
    except ValueError as error:
        print(json.dumps({"error": str(error)}))
    except Exception:
        print(json.dumps({"error": "Unreadable PDF. Import a valid text-based PDF."}))
