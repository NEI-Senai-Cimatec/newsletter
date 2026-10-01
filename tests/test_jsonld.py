"""TDD coverage for the shared JSON-LD helpers in core.utils.

Written before the helpers exist: every test here fails on import.
"""
import json

from bs4 import BeautifulSoup

from core.utils import (
    collect_ld_nodes,
    extract_article_metadata,
    find_ld_node,
    iter_ld_json,
)

QZ_GRAPH = {
    "@context": "https://rankmath.com/",
    "@graph": [
        {"@type": "Place", "name": "Somewhere"},
        {"@type": "NewsMediaOrganization", "name": "Quantum Zeitgeist"},
        {"@type": "WebSite", "name": "Quantum Zeitgeist"},
        {"@type": "ImageObject", "url": "https://quantumzeitgeist.com/x.png"},
        {"@type": "BreadcrumbList", "itemListElement": []},
        {"@type": "WebPage", "name": "A quantum page"},
        {"@type": "Person", "name": "Editor"},
        {
            "@type": "NewsArticle",
            "headline": "Quantum algorithm speeds up simulation",
            "author": {"@type": "Person", "name": "Jane Doe"},
            "datePublished": "2025-08-13T15:44:00+00:00",
            "dateModified": "2025-08-14T09:00:00+00:00",
            "articleSection": "Quantum Algorithms, Quantum Simulation",
        },
    ],
}


def _soup(payloads):
    """Build a page from (script_class_or_None, raw_text) pairs."""
    parts = []
    for cls, text in payloads:
        attr = f'class="{cls}" ' if cls else ""
        parts.append(f'<script {attr}type="application/ld+json">{text}</script>')
    return BeautifulSoup(
        "<html><head>" + "".join(parts) + "</head><body></body></html>",
        "html.parser",
    )


def test_find_ld_node_locates_article_at_any_position():
    nodes = collect_ld_nodes(_soup([(None, json.dumps(QZ_GRAPH))]))

    node = find_ld_node(nodes, "NewsArticle", "Article")

    assert len(nodes) == 8
    assert node["headline"] == "Quantum algorithm speeds up simulation"


def test_find_ld_node_matches_type_list():
    node = find_ld_node(
        [{"@type": ["Article", "NewsArticle"], "headline": "H"}], "NewsArticle"
    )

    assert node["headline"] == "H"


def test_find_ld_node_respects_type_priority():
    nodes = [
        {"@type": "WebPage", "name": "page"},
        {"@type": "NewsArticle", "headline": "article"},
    ]

    assert find_ld_node(nodes, "NewsArticle", "WebPage")["@type"] == "NewsArticle"
    assert find_ld_node(nodes, "WebPage")["@type"] == "WebPage"


def test_find_ld_node_returns_none_when_absent():
    nodes = [{"@type": "WebSite"}, {"@type": "Organization"}]

    assert find_ld_node(nodes, "NewsArticle", "Article") is None
    assert find_ld_node([], "NewsArticle") is None


def test_collect_ld_nodes_flattens_graph_and_keeps_plain_documents():
    plain = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": "P"}

    nodes = collect_ld_nodes(
        _soup([(None, json.dumps(QZ_GRAPH)), (None, json.dumps(plain))])
    )

    assert len(nodes) == 9
    assert nodes[-1]["headline"] == "P"


def test_iter_ld_json_repairs_malformed_payload():
    broken = '{"@context":"https://schema.org","@type":"NewsArticle","headline":"Fixed",}'

    docs = list(iter_ld_json(_soup([(None, broken)])))

    assert docs == [
        {"@context": "https://schema.org", "@type": "NewsArticle", "headline": "Fixed"}
    ]


def test_iter_ld_json_ignores_non_ld_json_scripts():
    soup = BeautifulSoup(
        '<html><head><script type="text/javascript">{"@graph": []}</script>'
        '<script type="application/ld+json">{"@type": "NewsArticle"}</script>'
        "</head><body></body></html>",
        "html.parser",
    )

    assert len(list(iter_ld_json(soup))) == 1


def test_extract_article_metadata_reads_headline_author_and_dates():
    metadata = extract_article_metadata(_soup([(None, json.dumps(QZ_GRAPH))]))

    assert metadata["title"] == "Quantum algorithm speeds up simulation"
    assert metadata["author"] == "Jane Doe"
    assert metadata["date"] == "2025-08-13"
    assert metadata["datePublished"].startswith("2025-08-13T15:44:00")
    assert metadata["dateModified"].startswith("2025-08-14T09:00:00")
    assert metadata["category"] == ["Quantum Algorithms, Quantum Simulation"]


def test_extract_article_metadata_normalizes_author_variants():
    variants = [
        ({"name": "Dict Author"}, "Dict Author"),
        ([{"name": "List Author"}, {"name": "Second"}], "List Author"),
        ("Plain Author", "Plain Author"),
    ]

    for author, expected in variants:
        doc = {"@type": "NewsArticle", "headline": "H", "author": author}
        soup = _soup([(None, json.dumps(doc))])

        assert extract_article_metadata(soup)["author"] == expected


def test_extract_article_metadata_normalizes_keywords_variants():
    as_string = {"@type": "NewsArticle", "headline": "H", "keywords": "alpha, beta"}
    as_list = {"@type": "NewsArticle", "headline": "H", "keywords": ["alpha", "beta"]}

    assert extract_article_metadata(_soup([(None, json.dumps(as_string))]))["keywords"] == [
        "alpha",
        "beta",
    ]
    assert extract_article_metadata(_soup([(None, json.dumps(as_list))]))["keywords"] == [
        "alpha",
        "beta",
    ]


def test_extract_article_metadata_prefers_script_class():
    other = {"@graph": [{"@type": "NewsArticle", "headline": "Other article"}]}
    mine = {"@graph": [{"@type": "NewsArticle", "headline": "Target article"}]}
    soup = _soup(
        [(None, json.dumps(other)), ("rank-math-schema-pro", json.dumps(mine))]
    )

    metadata = extract_article_metadata(soup, script_class="rank-math-schema-pro")

    assert metadata["title"] == "Target article"


def test_extract_article_metadata_falls_back_to_meta_tags():
    soup = BeautifulSoup(
        '<html><head>'
        '<meta property="og:title" content="Meta title"/>'
        '<meta property="article:published_time" content="2026-01-02T03:04:05+00:00"/>'
        '<meta property="article:modified_time" content="2026-01-03T03:04:05+00:00"/>'
        '<meta name="author" content="Meta Author"/>'
        "</head><body></body></html>",
        "html.parser",
    )

    metadata = extract_article_metadata(soup)

    assert metadata["title"] == "Meta title"
    assert metadata["author"] == "Meta Author"
    assert metadata["date"] == "2026-01-02"
    assert metadata["datePublished"].startswith("2026-01-02T03:04:05")
    assert metadata["dateModified"].startswith("2026-01-03T03:04:05")


def test_extract_article_metadata_returns_empty_strings_not_none():
    bare = {"@context": "https://schema.org", "@type": "NewsArticle"}

    metadata = extract_article_metadata(_soup([(None, json.dumps(bare))]))

    assert metadata == {
        "title": "",
        "author": "",
        "date": "",
        "datePublished": "",
        "dateModified": "",
        "category": [],
        "keywords": [],
    }


def test_extract_article_metadata_returns_none_without_any_source():
    soup = BeautifulSoup("<html><head></head><body></body></html>", "html.parser")

    assert extract_article_metadata(soup) is None
