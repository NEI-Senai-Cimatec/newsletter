# core/scoring.py
"""Pure multicriteria relevance scoring (no I/O except weights helpers)."""
from __future__ import annotations

import json
from pathlib import Path

INDICADORES: tuple[str, ...] = ("negocios", "mercado", "cientifica", "tecnologica")

LABELS: dict[str, str] = {
    "negocios": "Relevância para negócios (Investimentos)",
    "mercado": "Impacto no mercado (Casos de uso)",
    "cientifica": "Produção científica",
    "tecnologica": "Produção tecnológica",
}

DEFAULT_WEIGHTS: dict[str, int] = {"negocios": 35, "mercado": 35, "cientifica": 15, "tecnologica": 15}

WEIGHTS_FILE: Path = Path.home() / ".newsletter_tool" / "weights.json"

AREAS_PTBR = ("Negócio/Economia", "Tecnológico", "Científico", "Outros")


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def indicators(doc: dict) -> dict[str, float]:
    cw = doc.get("classification_weight") or {}
    fin = doc.get("financial_activity") or []
    events = doc.get("event") or []
    breakthroughs = doc.get("breakthrough") or []
    return {
        "negocios": clip01((cw.get("Business", 0)) / 35),
        "mercado": clip01(min(1.0, (len(fin) + len(events) + len(breakthroughs)) / 3)),
        "cientifica": clip01((cw.get("Scientific", 0)) / 15),
        "tecnologica": clip01((cw.get("Technological", 0)) / 35),
    }


def validate_weights(weights: dict[str, int]) -> bool:
    if set(weights) != set(INDICADORES):
        raise ValueError(f"Weights must have exactly {INDICADORES}")
    for key, value in weights.items():
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"Weight {key!r} must be an int in 0..100")
    if sum(weights.values()) != 100:
        raise ValueError(f"Weights must sum to 100, got {sum(weights.values())}")
    return True


def relevance(doc: dict, weights: dict[str, int]) -> int:
    validate_weights(weights)
    inds = indicators(doc)
    return int(round(100 * sum((weights[k] / 100) * inds[k] for k in INDICADORES)))


def area_of(doc: dict) -> str:
    cw = doc.get("classification_weight") or {}
    ranked = [
        ("Negócio/Economia", cw.get("Business", 0)),
        ("Tecnológico", cw.get("Technological", 0)),
        ("Científico", cw.get("Scientific", 0)),
        ("Outros", cw.get("Others", 0)),
    ]
    best_value = max(value for _, value in ranked)
    for label, value in ranked:
        if value == best_value:
            return label
    return "Outros"


def load_weights(path: Path | str = WEIGHTS_FILE) -> dict[str, int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_weights(data)
        return dict(data)
    except (OSError, ValueError):
        return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict[str, int], path: Path | str = WEIGHTS_FILE) -> None:
    validate_weights(weights)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2, ensure_ascii=False)
