# tests/test_exports.py
import zipfile
from xml.etree import ElementTree as ET

from core.briefs import BRIEF_MAX_CHARS, BRIEF_MAX_WORDS
from core.exports import build_newsletter, export_pdf, export_word, share_package
from core.scoring import DEFAULT_WEIGHTS

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _doc():
    return {"title": "T", "newsletter": "N", "summary": "Resumo.",
            "key_points": ["p1"], "organization": [], "event": [],
            "breakthrough": [], "financial_activity": [], "related_country": ["USA"],
            "url": "https://example.com/t",
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


def _docx_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter(f"{W_NS}t"))
            for p in root.iter(f"{W_NS}p")]


def test_sections_use_brief_body_without_bullets_by_default():
    structure = build_newsletter([_doc()], DEFAULT_WEIGHTS, "automatico", {})
    assert structure["include_key_points"] is False
    section = structure["sections"][0]
    assert "\n" not in section["summary"]
    assert len(section["summary"]) <= BRIEF_MAX_CHARS
    assert len(section["summary"].split()) <= BRIEF_MAX_WORDS
    assert section["summary"] == "Resumo."  # extractive fallback, no API


def test_word_section_order_title_body_source(tmp_path):
    structure = build_newsletter([_doc()], DEFAULT_WEIGHTS, "automatico", {})
    paras = _docx_paragraphs(export_word(structure, tmp_path / "n.docx"))
    head = next(i for i, p in enumerate(paras) if "Negócio/Economia" in p)
    assert paras[head + 1] == "Resumo."  # exactly 1 paragraph ...
    assert paras[head + 2] == "Fonte: https://example.com/t"  # ... then Fonte
    assert "p1" not in paras  # bullets off by default


def test_word_key_points_return_after_source_when_enabled(tmp_path):
    structure = build_newsletter([_doc()], DEFAULT_WEIGHTS, "personalizado",
                                 {}, include_key_points=True)
    paras = _docx_paragraphs(export_word(structure, tmp_path / "n.docx"))
    head = next(i for i, p in enumerate(paras) if "Negócio/Economia" in p)
    assert paras[head + 1] == "Resumo."
    assert paras[head + 2] == "Fonte: https://example.com/t"
    assert paras[head + 3] == "p1"  # bullets back, AFTER the Fonte line


def test_progress_callback_called_per_document():
    seen = []
    build_newsletter([_doc(), _doc()], DEFAULT_WEIGHTS, "automatico", {},
                     progress_cb=lambda i, n: seen.append((i, n)))
    assert seen == [(1, 2), (2, 2)]
