"""TDD coverage for per-portal scraper parsing (pure functions).

Each portal's metadata/relevance logic is extracted into a pure function so it
can be exercised against captured pages without any network access.
"""
from pathlib import Path

from bs4 import BeautifulSoup

from scrapers.quantumzeitgeist import qz_extract_metadata, qz_is_relevant

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


def _qz_metadata(title="", category=None, keywords=None) -> dict:
    return {
        "title": title,
        "author": "",
        "date": "",
        "datePublished": "",
        "dateModified": "",
        "category": list(category or []),
        "keywords": list(keywords or []),
    }


def test_qz_metadata_extracts_article_at_graph_index_7():
    metadata = qz_extract_metadata(_load("qz_article.html"))

    assert metadata["title"] == (
        "Quanome CEO Pledges Up To $15 Million For Quantum Push"
    )
    assert metadata["author"] == "Ivy Delaney"
    assert metadata["date"] == "2026-10-01"
    assert metadata["datePublished"].startswith("2026-10-01T14:22:54")
    assert metadata["dateModified"].startswith("2026-10-01T14:22:59")
    assert metadata["category"] == [
        "Quantum Computing Business News, Quantum Funding"
    ]


def test_qz_metadata_tags_section_provides_keywords():
    metadata = qz_extract_metadata(_load("qz_article.html"))

    assert metadata["keywords"] == ["NASDAQ", "Quanome", "Quantum Computing"]


def test_qz_relevance_accepts_section_without_quantum_word_when_title_matches():
    metadata = _qz_metadata(
        title="Quantum-inspired photonic chip promises faster computing",
        category=["Deep Tech, Emerging Technology"],
    )

    assert qz_is_relevant(metadata) is True


def test_qz_relevance_rejects_non_quantum_article():
    metadata = _qz_metadata(
        title="Global markets rally as oil prices climb",
        category=["Markets"],
        keywords=["Oil"],
    )

    assert qz_is_relevant(metadata) is False


def test_qz_relevance_is_case_insensitive():
    metadata = _qz_metadata(
        title="A lab update",
        category=["quantum algorithms, quantum simulation"],
    )

    assert qz_is_relevant(metadata) is True
