# core/selfcheck.py
"""Frozen-bundle self check (dev/CI hook, runs with ``QUIIN_SMOKE=1``).

Proves the packaged app can exercise its riskiest runtime dependencies —
keyring (OS vault roundtrip), reportlab (PDF), python-docx (DOCX) and the
bundled customtkinter — without opening the GUI. Raises on any failure;
``main.py`` logs the traceback and exits non-zero.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from keyring.errors import PasswordDeleteError

logger = logging.getLogger(__name__)


def run_self_check() -> None:
    """Exercise frozen keyring/reportlab/docx/customtkinter; raise on failure."""
    import customtkinter  # noqa: F401  (Tk + bundled assets)
    import keyring

    keyring.set_password("quiin_smoke", "probe", "value")
    try:
        if keyring.get_password("quiin_smoke", "probe") != "value":
            raise RuntimeError("keyring roundtrip failed")
    finally:
        try:
            keyring.delete_password("quiin_smoke", "probe")
        except PasswordDeleteError:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        from reportlab.pdfgen import canvas

        pdf_path = Path(tmp) / "smoke.pdf"
        pdf = canvas.Canvas(str(pdf_path))
        pdf.drawString(72, 720, "QuIIN smoke")
        pdf.save()
        if pdf_path.stat().st_size == 0:
            raise RuntimeError("reportlab produced an empty PDF")

        from docx import Document

        docx_path = Path(tmp) / "smoke.docx"
        doc = Document()
        doc.add_paragraph("QuIIN smoke")
        doc.save(str(docx_path))
        if docx_path.stat().st_size == 0:
            raise RuntimeError("python-docx produced an empty document")

    logger.info("QUIIN SMOKE OK: keyring, reportlab, docx, customtkinter")
