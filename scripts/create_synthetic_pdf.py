"""Create a two-page synthetic acceptance fixture; requires installed pypdf."""
import io
import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def create_pdf() -> bytes:
    writer = PdfWriter()
    for lines in [
        ['SYNTHETIC TRAINING ONLY - NOT OPERATIONAL GUIDANCE',
         'Lifejacket inspections take place every Friday.',
         'This fictional schedule is not a maritime regulation.'],
        ['SYNTHETIC TRAINING ONLY - NOT OPERATIONAL GUIDANCE',
         'Fire drill attendance is recorded by the officer.',
         'No vessel particulars are stated in this document.'],
    ]:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): writer._add_object(font)})})
        commands = ['BT /F1 11 Tf 30 760 Td']
        for line in lines:
            commands.append('(' + line + ') Tj 0 -24 Td')
        commands.append('ET')
        stream = DecodedStreamObject(); stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    buffer = io.BytesIO(); writer.write(buffer)
    return buffer.getvalue()


if __name__ == '__main__':
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else 'synthetic-training.pdf')
    if destination.exists():
        raise SystemExit('Destination already exists; choose a new filename.')
    destination.write_bytes(create_pdf())
    print(destination.resolve())
