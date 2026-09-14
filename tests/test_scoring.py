# tests/test_scoring.py
import pytest

from core.scoring import (
    DEFAULT_WEIGHTS, area_of, indicators, relevance, validate_weights,
)

FULL_DOC = {
    "classification_weight": {"Business": 35, "Technological": 35, "Scientific": 15, "Others": 0},
    "financial_activity": [{"description": "x" * 200, "currency": "Real Brasileiro (BRL), Brasil"}],
    "event": [{"name": "E", "location": "São Paulo, Brasil", "type": "Evento", "description": "y" * 200}],
    "breakthrough": ["avanço relevante"],
}

def test_full_doc_scores_100_with_default_weights():
    assert relevance(FULL_DOC, DEFAULT_WEIGHTS) == 100

def test_missing_weights_yield_zero():
    doc = {}
    assert indicators(doc) == {"negocios": 0.0, "mercado": 0.0, "cientifica": 0.0, "tecnologica": 0.0}
    assert relevance(doc, DEFAULT_WEIGHTS) == 0

def test_default_weights_validate():
    assert validate_weights(DEFAULT_WEIGHTS) is True

def test_area_tiebreak_prefers_business():
    doc = {"classification_weight": {"Business": 20, "Technological": 20, "Scientific": 0, "Others": 0}}
    assert area_of(doc) == "Negócio/Economia"


def test_weights_sum_not_100_rejected():
    with pytest.raises(ValueError):
        validate_weights({"negocios": 35, "mercado": 35, "cientifica": 15, "tecnologica": 14})


def test_partial_doc_proportional():
    doc = {"classification_weight": {"Business": 17, "Technological": 0, "Scientific": 0, "Others": 0}}
    assert relevance(doc, DEFAULT_WEIGHTS) == round(100 * 0.35 * (17 / 35))


def test_scoring_reproducible_three_runs():
    doc = {"classification_weight": {"Business": 18, "Technological": 32, "Scientific": 7, "Others": 13},
           "event": [], "breakthrough": ["b1", "b2"], "financial_activity": []}
    assert relevance(doc, DEFAULT_WEIGHTS) == relevance(doc, DEFAULT_WEIGHTS) == relevance(doc, dict(DEFAULT_WEIGHTS))
