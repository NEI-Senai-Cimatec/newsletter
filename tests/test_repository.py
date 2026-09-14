# tests/test_repository.py
from core.repository import add_manual_news, search, sort_documents, stats_area_share
from core.repository import sort_documents, stats_countries


def _doc(title, business, date="2026-09-01"):
    return {"title": title, "summary": "", "key_points": [],
            "organization": [], "event": [],
            "classification_weight": {"Business": business, "Technological": 0, "Scientific": 0, "Others": 0},
            "date": date, "published": date, "related_country": []}


def test_search_case_insensitive():
    docs = [_doc("Quantum startup raises $30M", 20), _doc("Photonic sensors", 5)]
    assert [d["title"] for d in search(docs, "QUANTUM")] == ["Quantum startup raises $30M"]


def test_area_share_sums_100():
    share = stats_area_share([_doc("a", 35), _doc("b", 0)])
    assert abs(sum(share.values()) - 100.0) < 1e-6


def test_manual_news_is_compatible():
    record = add_manual_news({"url": "https://exemplo.test/n1", "title": "N1",
                              "area": "Negócio/Economia", "date": "2026-09-14", "summary": "Resumo."})
    assert record["source"] == "Manual"
    assert len(record["hash"]) == 64


def test_unknown_country_code_falls_back_to_code():
    docs = [{"related_country": ["XX1"]}]
    assert stats_countries(docs) == [("XX1", 1)]


def test_sort_by_relevance_desc():
    def _doc(title, business):
        return {"title": title, "summary": "", "key_points": [], "organization": [],
                "event": [], "date": "2026-09-01",
                "classification_weight": {"Business": business, "Technological": 0,
                                          "Scientific": 0, "Others": 0}}
    ordered = sort_documents([_doc("low", 5), _doc("high", 35)], key="relevance", desc=True)
    assert [d["title"] for d in ordered] == ["high", "low"]
