"""WeasyPrint renderer: small PDFs, no JavaScript, selectable text."""

from __future__ import annotations

import io

from weasyprint import HTML


def render_pdf(html_document: str) -> bytes:
    buffer = io.BytesIO()
    HTML(string=html_document).write_pdf(
        target=buffer,
        optimize_images=True,
        jpeg_quality=85,
        uncompressed_pdf=False,
    )
    return buffer.getvalue()
