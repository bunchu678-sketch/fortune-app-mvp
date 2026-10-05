"""PDF export reuses the complete Excel export, including source isolation and naming."""
from pathlib import Path
from pdf_converter import get_pdf_converter
from report_export_service import export_reading, export_tokens


def export_pdf_reading(owner, payload, repository=None, tokens=export_tokens, converter=None):
    filename, xlsx = export_reading(owner, payload, repository, tokens)
    adapter = converter if converter is not None else get_pdf_converter()
    return str(Path(filename).with_suffix(".pdf")), adapter.convert(xlsx)
