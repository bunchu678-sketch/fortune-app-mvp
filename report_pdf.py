"""PDF export reuses the complete Excel export, including source isolation and naming."""
from pathlib import Path
from pdf_converter import get_pdf_converter
from report_export_service import export_reading, export_tokens


def export_pdf_reading(owner, payload, repository=None, tokens=export_tokens, converter=None, session_id=None, source_authorizer=None):
    scopes=[]
    def authorize(organization_id):
        source_authorizer(organization_id);scopes.append(organization_id)
    filename, xlsx = export_reading(owner, payload, repository, tokens, session_id,authorize if source_authorizer else None)
    adapter = converter if converter is not None else get_pdf_converter()
    body=adapter.convert(xlsx)
    if source_authorizer:source_authorizer(scopes[-1])
    return str(Path(filename).with_suffix(".pdf")),body
