# tests/test_exports.py
from core.exports import build_newsletter, export_pdf, export_word, share_package
from core.scoring import DEFAULT_WEIGHTS


def _doc():
    return {"title": "T", "newsletter": "N", "summary": "Resumo.",
            "key_points": ["p1"], "organization": [], "event": [],
            "breakthrough": [], "financial_activity": [], "related_country": ["USA"],
            "classification_weight": {"Business": 35, "Technological": 0,
                                      "Scientific": 0, "Others": 0}}


def test_build_newsletter_orders_by_relevance():
    low = _doc()
    high = dict(_doc(), summary="Resumo relevante.")
    structure = build_newsletter([low, high], DEFAULT_WEIGHTS, "automatico", {})
    assert structure["mode"] == "automatico"
    assert len(structure["sections"]) == 2


def test_pdf_and_word_magic_bytes(tmp_path):
    structure = build_newsletter([_doc()], DEFAULT_WEIGHTS, "automatico", {"title": "Q"})
    pdf = export_pdf(structure, tmp_path / "n.pdf")
    assert open(pdf, "rb").read(4) == b"%PDF"
    docx = export_word(structure, tmp_path / "n.docx")
    assert open(docx, "rb").read(2) == b"PK"
