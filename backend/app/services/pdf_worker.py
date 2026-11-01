"""PDF-only implementation of the common extraction contract; bounded child process."""
import sys

from app.schemas.extraction import (
    ContentUnit, ExtractionError, ExtractionFile, ExtractionResult, PageLocator, pdf_unit_id,
)


class PDFExtractor:
    def extract(self, file: ExtractionFile) -> ExtractionResult:
        from pypdf import PdfReader
        errors = []
        try:
            if file.metadata.source_format != 'pdf':
                raise ValueError('Only PDF extraction is supported.')
            reader = PdfReader(file.path, strict=True)
            if reader.is_encrypted:
                raise ValueError('Encrypted PDFs are not supported. Import an unlocked text-based PDF.')
            if not 1 <= len(reader.pages) <= 100:
                raise ValueError('Import a PDF containing 1–100 pages.')
            units = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                value = (page.extract_text() or '').replace('\x00', '').strip()
                total += len(value)
                if total > 1_000_000:
                    raise ValueError('Extracted text exceeds the 1 million character limit.')
                unit = ContentUnit(id=pdf_unit_id(file.metadata.revision_id, number),
                                   locator=PageLocator(page_number=number), text=value)
                units.append(unit)
                if not value:
                    errors.append(ExtractionError(code='page_without_text', unit_id=unit.id,
                                                  message=f'Page {number} has no extracted text; OCR is unavailable.'))
            if not any(unit.text.strip() for unit in units):
                raise ValueError('No readable text. Scanned/image PDFs require OCR, which is unavailable.')
            return ExtractionResult(metadata=file.metadata, status='partial' if errors else 'ready',
                                    units=units, errors=errors, extractor='pdf-text-v1')
        except ValueError as error:
            message = str(error)
        except Exception:
            message = 'Unreadable PDF. Import a valid text-based PDF.'
        return ExtractionResult(metadata=file.metadata, status='failed', extractor='pdf-text-v1',
                                errors=[ExtractionError(code='pdf_extraction_failed', message=message)])


if __name__ == '__main__':
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    except ImportError:
        pass
    file = ExtractionFile.model_validate_json(sys.stdin.read())
    print(PDFExtractor().extract(file).model_dump_json())
