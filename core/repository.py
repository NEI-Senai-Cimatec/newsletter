# core/repository.py
"""Pure document queries over lists of documents-data.json records."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.scoring import DEFAULT_WEIGHTS, area_of, relevance

AREAS = ("Negócio/Economia", "Tecnológico", "Científico", "Outros")

ISO3_PTBR: dict[str, str] = {
    "USA": "Estados Unidos", "BRA": "Brasil", "CHN": "China", "JPN": "Japão",
    "DEU": "Alemanha", "FRA": "França", "GBR": "Reino Unido", "CAN": "Canadá",
    "CHE": "Suíça", "NLD": "Países Baixos", "SWE": "Suécia", "FIN": "Finlândia",
    "DNK": "Dinamarca", "NOR": "Noruega", "IRL": "Irlanda", "AUT": "Áustria",
    "BEL": "Bélgica", "ESP": "Espanha", "ITA": "Itália", "PRT": "Portugal",
    "POL": "Polônia", "CZE": "Chéquia", "HUN": "Hungria", "GRC": "Grécia",
    "IND": "Índia", "KOR": "Coreia do Sul", "TWN": "Taiwan", "SGP": "Singapura",
    "AUS": "Austrália", "NZL": "Nova Zelândia", "ISR": "Israel", "ARE": "Emirados Árabes Unidos",
    "SAU": "Arábia Saudita", "QAT": "Catar", "TUR": "Turquia", "ZAF": "África do Sul",
    "MEX": "México", "ARG": "Argentina", "CHL": "Chile", "COL": "Colômbia",
    "RUS": "Rússia", "UKR": "Ucrânia", "EGY": "Egito", "NGA": "Nigéria",
    "KEN": "Quênia", "MYS": "Malásia", "THA": "Tailândia", "VNM": "Vietnã",
    "IDN": "Indonésia", "PHL": "Filipinas", "PAK": "Paquistão", "BGD": "Bangladesh",
    "LUX": "Luxemburgo", "ISL": "Islândia", "EST": "Estônia", "LVA": "Letônia",
    "LTU": "Lituânia", "SVN": "Eslovênia", "SVK": "Eslováquia", "ROU": "Romênia",
    "BGR": "Bulgária", "HRV": "Croácia", "URY": "Uruguai", "PER": "Peru",
}


def load_documents(path: str | Path) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _haystack(doc: dict) -> str:
    parts = [doc.get("title", ""), doc.get("summary", "")]
    parts.extend(doc.get("key_points") or [])
    for org in doc.get("organization") or []:
        parts.append((org or {}).get("name", ""))
    for event in doc.get("event") or []:
        parts.append((event or {}).get("name", ""))
    return "\n".join(parts).casefold()


def search(docs: list[dict], query: str) -> list[dict]:
    needle = (query or "").strip().casefold()
    if not needle:
        return list(docs)
    return [d for d in docs if needle in _haystack(d)]


def _month_key(doc: dict) -> str | None:
    for field in ("date", "published", "modified"):
        raw = (doc.get(field) or "")[:7]
        if len(raw) == 7 and raw[4] == "-":
            return raw
    return None


def stats_monthly(docs: list[dict], areas: list[str]) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {}
    for doc in docs:
        month = _month_key(doc)
        if month is None:
            continue
        table.setdefault(month, {a: 0 for a in areas})
        table[month][area_of(doc)] += 1
    recent = sorted(table)[-6:]
    return {month: table[month] for month in recent}


def stats_area_share(docs: list[dict]) -> dict[str, float]:
    counts = Counter(area_of(d) for d in docs)
    total = sum(counts.values())
    if total == 0:
        return {a: 0.0 for a in AREAS}
    return {a: round(100.0 * counts.get(a, 0) / total, 1) for a in AREAS}


def stats_countries(docs: list[dict], top: int = 5) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for doc in docs:
        for code in doc.get("related_country") or []:
            counts[code] += 1
    return [(ISO3_PTBR.get(code, code), n) for code, n in counts.most_common(top)]


def _sort_value(doc: dict, key: str, weights: dict) -> tuple:
    if key == "relevance":
        return (relevance(doc, weights),)
    if key == "area":
        return (area_of(doc),)
    return (doc.get("date") or doc.get("published") or "",)


def sort_documents(docs: list[dict], key: str, desc: bool = True,
                   weights: dict | None = None) -> list[dict]:
    if key not in ("date", "area", "relevance"):
        raise ValueError(f"sort key must be date/area/relevance, got {key!r}")
    active = weights or DEFAULT_WEIGHTS
    return sorted(docs, key=lambda d: _sort_value(d, key, active), reverse=desc)


AREA_TO_WEIGHT = {
    "Negócio/Economia": {"Business": 35, "Technological": 0, "Scientific": 0, "Others": 0},
    "Tecnológico": {"Business": 0, "Technological": 35, "Scientific": 0, "Others": 0},
    "Científico": {"Business": 0, "Technological": 0, "Scientific": 15, "Others": 0},
    "Outros": {"Business": 0, "Technological": 0, "Scientific": 0, "Others": 15},
}


def add_manual_news(fields: dict) -> dict:
    url = fields.get("url", "") or fields.get("title", "")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return {
        "url": fields.get("url", ""),
        "title": fields.get("title", ""),
        "category": ["Manual"],
        "author": "",
        "date": fields.get("date", datetime.now().strftime("%Y-%m-%d")),
        "published": fields.get("date", ""),
        "modified": "",
        "timestamp": datetime.now().isoformat(),
        "keywords": [],
        "hash": digest,
        "source": "Manual",
        "newsletter": fields.get("title", ""),
        "summary": fields.get("summary", ""),
        "overview": fields.get("summary", ""),
        "key_points": [],
        "classification_weight": dict(AREA_TO_WEIGHT.get(fields.get("area", "Outros"),
                                                         AREA_TO_WEIGHT["Outros"])),
        "organization": [],
        "event": [],
        "breakthrough": [],
        "financial_activity": [],
        "related_country": [],
    }
