"""TDD coverage for per-portal scraper parsing (pure functions).

Each portal's metadata/relevance logic is extracted into a pure function so it
can be exercised against captured pages without any network access.
"""
import json
from pathlib import Path

from bs4 import BeautifulSoup

from scrapers.insidequantumtechnology import (
    iqt_extract_metadata,
    iqt_find_content_container,
    iqt_parse_sitemap_xml,
)
from scrapers.quantamagazine import qm_extract_metadata, qm_is_relevant
from scrapers.quantumzeitgeist import qz_extract_metadata, qz_is_relevant
from scrapers.thequantuminsider import tqi_extract_metadata

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


def _soup(payloads) -> BeautifulSoup:
    """Build a page from (script_class_or_None, raw_text) pairs."""
    parts = []
    for cls, text in payloads:
        attr = f'class="{cls}" ' if cls else ""
        parts.append(f'<script {attr}type="application/ld+json">{text}</script>')
    return BeautifulSoup(
        "<html><head>" + "".join(parts) + "</head><body></body></html>",
        "html.parser",
    )


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


def test_iqt_sitemap_keeps_full_url_and_parses_cdata_date():
    entries = iqt_parse_sitemap_xml(
        (FIXTURES / "iqt_sitemap.xml").read_text(encoding="utf-8")
    )

    assert [entry["url"] for entry in entries] == [
        "https://www.insidequantumtechnology.com/news-archive/iqt-sunday-edition-5/",
        "https://www.insidequantumtechnology.com/news-archive/only-one-month-to-go/",
    ]
    assert entries[0]["date"] == "2026-09-27 11:00 +0000"


def test_iqt_sitemap_skips_entries_with_unparseable_dates():
    xml = (
        '<?xml version="1.0"?><urlset>'
        '<url><loc><![CDATA[https://www.insidequantumtechnology.com/good/]]></loc>'
        "<lastmod><![CDATA[2026-09-27T11:00:43+00:00]]></lastmod></url>"
        '<url><loc><![CDATA[https://www.insidequantumtechnology.com/bad/]]></loc>'
        "<lastmod><![CDATA[not-a-date]]></lastmod></url>"
        '<url><loc><![CDATA[https://www.insidequantumtechnology.com/no-date/]]></loc>'
        "</url></urlset>"
    )

    entries = iqt_parse_sitemap_xml(xml)

    assert [entry["url"] for entry in entries] == [
        "https://www.insidequantumtechnology.com/good/"
    ]


def test_iqt_metadata_from_aioseo_graph():
    metadata = iqt_extract_metadata(_load("iqt_article.html"))

    assert metadata["title"] == "IQT Sunday Edition - Inside Quantum Technology"
    assert metadata["author"] == "Brian Siegelwax"
    assert metadata["date"] == "2026-09-27"
    assert metadata["datePublished"].startswith("2026-09-27T07:00:43")
    assert metadata["category"] == []


def test_iqt_content_container_found_when_entry_content_absent():
    container = iqt_find_content_container(_load("iqt_article.html"))

    assert container is not None
    assert "single_post_article" in (container.get("class") or [])
    paragraphs = [paragraph.get_text(strip=True) for paragraph in container.find_all("p")]
    assert any(len(paragraph) > 100 for paragraph in paragraphs)


def test_iqt_keywords_missing_tags_section_does_not_raise():
    metadata = iqt_extract_metadata(_load("iqt_article.html"))

    assert metadata["keywords"] == []


def test_iqt_metadata_falls_back_to_meta_tags():
    soup = _load("iqt_article.html")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        script.decompose()

    metadata = iqt_extract_metadata(soup)

    assert metadata["title"] == "IQT Sunday Edition - Inside Quantum Technology"
    assert metadata["author"] == "Brian Siegelwax"
    assert metadata["datePublished"].startswith("2026-09-27T11:00:43")


def test_tqi_metadata_works_without_yoast_script():
    metadata = tqi_extract_metadata(_load("tqi_article.html"))

    assert metadata["title"] == (
        "Klea Dhmitri (Hamamatsu): Photonics as the hidden backbone of "
        "quantum hardware scaling"
    )
    assert metadata["author"] == "Yuval Boger"
    assert metadata["date"] == "2026-09-12"
    assert metadata["datePublished"].startswith("2026-09-12T08:00:00")
    assert metadata["category"] == ["Daily"]
    assert metadata["keywords"] == ["Klea Dhmitri", "quantum computing", "Yuval Boger"]


def test_tqi_metadata_works_with_yoast_script():
    graph = {
        "@graph": [
            {"@type": "WebSite", "name": "The Quantum Insider"},
            {
                "@type": "NewsArticle",
                "headline": "Yoast headline",
                "author": {"name": "A Author"},
                "datePublished": "2026-09-12T08:00:00+00:00",
                "dateModified": "2026-09-12T09:00:00+00:00",
                "articleSection": "Daily",
                "keywords": ["one", "two"],
            },
        ]
    }
    soup = _soup(
        [
            (None, json.dumps({"@type": "Organization", "name": "Org"})),
            ("yoast-schema-graph", json.dumps(graph)),
        ]
    )

    metadata = tqi_extract_metadata(soup)

    assert metadata["title"] == "Yoast headline"
    assert metadata["author"] == "A Author"
    assert metadata["keywords"] == ["one", "two"]


def test_tqi_metadata_ignores_ld_json_scripts_before_the_article():
    article = {
        "@type": "NewsArticle",
        "headline": "Article after the others",
        "author": {"name": "Later Author"},
        "datePublished": "2026-09-12T08:00:00+00:00",
        "articleSection": "Daily",
    }
    soup = _soup(
        [
            (None, json.dumps({"@type": "BreadcrumbList", "itemListElement": []})),
            (None, json.dumps({"@type": "Organization", "name": "TQI"})),
            (None, json.dumps(article)),
        ]
    )

    metadata = tqi_extract_metadata(soup)

    assert metadata["title"] == "Article after the others"
    assert metadata["author"] == "Later Author"


def test_tqi_keywords_string_is_not_split_into_characters():
    doc = {"@type": "NewsArticle", "headline": "H", "keywords": "alpha, beta"}

    metadata = tqi_extract_metadata(_soup([(None, json.dumps(doc))]))

    assert metadata["keywords"] == ["alpha", "beta"]


def _find_ga4_script(soup: BeautifulSoup):
    return next(s for s in soup.find_all("script") if "ga4Array" in s.text)


def _find_graph_script(soup: BeautifulSoup):
    return next(s for s in soup.find_all("script") if "@graph" in s.text)


def test_qm_metadata_reads_graph_and_ga4():
    metadata = qm_extract_metadata(_load("qm_article.html"))

    assert metadata["title"] == "In Hilbert Space, All Things Are Quantumly Possible"
    assert metadata["author"] == "Charlie Wood"
    assert metadata["date"] == "2026-08-26"
    assert metadata["datePublished"].startswith("2026-08-26T14:30:35")
    assert metadata["dateModified"].startswith("2026-08-26T17:56:55")
    assert metadata["category"] == ["Physics"]
    assert metadata["kicker"] == "quantum physics"
    assert metadata["keywords"] == [
        "explainers",
        "history of science",
        "physics",
        "quantum physics",
    ]


def test_qm_extract_metadata_returns_none_without_graph_script():
    soup = _load("qm_article.html")
    _find_graph_script(soup).extract()

    assert qm_extract_metadata(soup) is None


def test_qm_extract_metadata_returns_none_without_ga4_script():
    soup = _load("qm_article.html")
    _find_ga4_script(soup).extract()

    assert qm_extract_metadata(soup) is None


def test_qm_relevance_filter_still_rejects_non_quantum_kicker():
    assert qm_is_relevant({"kicker": "quantum physics"}) is True
    assert qm_is_relevant({"kicker": "biology"}) is False
    assert qm_is_relevant({}) is False


def test_qm_keywords_empty_when_sidebar_tags_missing():
    soup = _load("qm_article.html")
    for tag_wrap in soup.find_all("div", class_="sidebar__tag-wrap"):
        tag_wrap.extract()

    metadata = qm_extract_metadata(soup)

    assert metadata["keywords"] == []
