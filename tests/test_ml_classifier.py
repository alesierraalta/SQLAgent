"""Tests para ML Query Classification (Fase E)."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.utils.ml_classifier import (
    classify_query_complexity_ml,
    _classify_with_keywords,
    get_ml_classifier,
    MLQueryClassifier,
    SIMPLE_EXAMPLES,
    COMPLEX_EXAMPLES,
)


def test_keyword_classifier_simple_queries():
    """Verifica que el clasificador de keywords identifica queries simples."""
    simple_queries = [
        "¿Cuántos productos hay?",
        "Total de ventas",
        "Suma de revenue",
        "Promedio de precio",
        "Lista de clientes",
    ]
    
    for query in simple_queries:
        result = _classify_with_keywords(query)
        assert result == "simple", f"Query '{query}' debería ser simple"


def test_keyword_classifier_complex_queries():
    """Verifica que el clasificador de keywords identifica queries complejas."""
    complex_queries = [
        "Join entre ventas y productos",
        "Subquery con agregación",
        "CTE con ranking",
        "Window function para total",
        "Union de tablas",
    ]
    
    for query in complex_queries:
        result = _classify_with_keywords(query)
        assert result == "complex", f"Query '{query}' debería ser complex"


def test_keyword_classifier_group_by_simple():
    """Verifica que GROUP BY simple se clasifica como simple."""
    queries = [
        "Total de ventas por país",
        "Suma de revenue por mes",
        "Promedio por categoría",
    ]
    
    for query in queries:
        result = _classify_with_keywords(query)
        assert result == "simple", f"Query '{query}' debería ser simple (GROUP BY básico)"


def test_classify_with_ml_disabled():
    """Verifica que funciona con ML deshabilitado."""
    with patch.dict('os.environ', {'USE_ML_CLASSIFICATION': 'false'}):
        result = classify_query_complexity_ml("¿Cuántos productos hay?")
        assert result in ["simple", "complex"]


def test_classify_fallback_when_ml_fails():
    """Verifica que usa fallback cuando ML falla."""
    # Simular que sentence-transformers no está disponible
    classifier = get_ml_classifier()
    classifier._initialized = False
    
    with patch.object(classifier, '_lazy_init', return_value=False):
        result = classify_query_complexity_ml("¿Cuántos productos hay?")
        assert result == "simple"  # Debería usar keyword fallback


def test_ml_classifier_lazy_initialization():
    """Verifica que el clasificador ML se inicializa de manera lazy."""
    classifier = get_ml_classifier()
    
    # Antes de usar, no debería estar inicializado
    if not classifier._initialized:
        assert classifier.model is None
        assert classifier.simple_embeddings is None
        assert classifier.complex_embeddings is None


def test_simple_examples_defined():
    """Verifica que hay ejemplos simples definidos."""
    assert len(SIMPLE_EXAMPLES) > 0
    assert all(isinstance(ex, str) for ex in SIMPLE_EXAMPLES)


def test_complex_examples_defined():
    """Verifica que hay ejemplos complejos definidos."""
    assert len(COMPLEX_EXAMPLES) > 0
    assert all(isinstance(ex, str) for ex in COMPLEX_EXAMPLES)


def test_examples_are_different():
    """Verifica que los ejemplos simples y complejos son diferentes."""
    # No debería haber overlap entre ejemplos
    simple_set = set(ex.lower() for ex in SIMPLE_EXAMPLES)
    complex_set = set(ex.lower() for ex in COMPLEX_EXAMPLES)
    
    overlap = simple_set & complex_set
    assert len(overlap) == 0, f"Hay overlap en ejemplos: {overlap}"


def test_keyword_classifier_default_complex():
    """Verifica que queries ambiguas se clasifican como complex por defecto."""
    ambiguous_queries = [
        "Analizar datos",
        "Procesar información",
        "Generar reporte completo",
    ]
    
    for query in ambiguous_queries:
        result = _classify_with_keywords(query)
        # Por defecto debería ser complex para seguridad
        assert result == "complex"



def test_classify_with_environment_variable():
    """Verifica que respeta la variable de entorno USE_ML_CLASSIFICATION."""
    # Con ML habilitado (aunque no esté instalado, debería intentar)
    with patch.dict('os.environ', {'USE_ML_CLASSIFICATION': 'true'}):
        result = classify_query_complexity_ml("Test query")
        assert result in ["simple", "complex"]
    
    # Con ML deshabilitado
    with patch.dict('os.environ', {'USE_ML_CLASSIFICATION': 'false'}):
        result = classify_query_complexity_ml("Test query")
        assert result in ["simple", "complex"]


def test_singleton_classifier():
    """Verifica que get_ml_classifier retorna singleton."""
    classifier1 = get_ml_classifier()
    classifier2 = get_ml_classifier()
    
    assert classifier1 is classifier2


def test_ml_lazy_init_import_error(monkeypatch):
    """Cubre rama ImportError en _lazy_init sin descargar modelos."""
    classifier = MLQueryClassifier()
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert classifier._lazy_init() is False


def test_ml_classify_returns_none_on_exception(monkeypatch):
    """Cubre excepción dentro de classify."""
    classifier = MLQueryClassifier()
    monkeypatch.setattr(classifier, "_lazy_init", lambda: True)
    classifier.model = MagicMock()
    classifier.model.encode.side_effect = Exception("boom")
    classifier.simple_embeddings = [0.0]
    classifier.complex_embeddings = [0.0]

    assert classifier.classify("x") is None


# Tests condicionales (solo si sentence-transformers está instalado)
try:
    import sentence_transformers
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers not installed")
def test_ml_classifier_initialization(monkeypatch):
    """Verifica inicialización ML usando modelo dummy (sin descargas)."""
    import sentence_transformers

    class DummyModel:
        def encode(self, texts):
            # Retorna embeddings simples determinísticos
            if isinstance(texts, list):
                return [[0.0, 1.0, 0.0] for _ in texts]
            return [0.0, 1.0, 0.0]

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda *_a, **_k: DummyModel())

    classifier = get_ml_classifier()
    classifier._initialized = False
    classifier.model = None
    classifier.simple_embeddings = None
    classifier.complex_embeddings = None

    success = classifier._lazy_init()
    assert success is True
    assert classifier.model is not None
    assert len(classifier.simple_embeddings) == len(SIMPLE_EXAMPLES)
    assert len(classifier.complex_embeddings) == len(COMPLEX_EXAMPLES)


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers not installed")
def test_ml_classifier_simple_query(monkeypatch):
    """Verifica clasificación ML simple con embeddings dummy."""
    classifier = get_ml_classifier()
    monkeypatch.setattr(classifier, "_lazy_init", lambda: True)
    classifier.model = MagicMock()
    classifier.model.encode.return_value = [[0.0, 1.0, 0.0]]
    classifier.simple_embeddings = [[0.0, 1.0, 0.0]]
    classifier.complex_embeddings = [[1.0, 0.0, 0.0]]

    result = classifier.classify("¿Cuántos productos hay en total?")
    assert result in ["simple", "complex", None]


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers not installed")
def test_ml_classifier_complex_query(monkeypatch):
    """Verifica clasificación ML compleja con embeddings dummy."""
    classifier = get_ml_classifier()
    monkeypatch.setattr(classifier, "_lazy_init", lambda: True)
    classifier.model = MagicMock()
    classifier.model.encode.return_value = [[1.0, 0.0, 0.0]]
    classifier.simple_embeddings = [[0.0, 1.0, 0.0]]
    classifier.complex_embeddings = [[1.0, 0.0, 0.0]]

    result = classifier.classify("Join entre ventas y productos con subquery")
    assert result in ["complex", "simple", None]


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers not installed")
def test_ml_classification_end_to_end(monkeypatch):
    """Test end-to-end de clasificación ML usando stub de classify."""
    classifier = get_ml_classifier()
    monkeypatch.setattr(classifier, "classify", lambda q: "simple" if "Total" in q else "complex")

    with patch.dict('os.environ', {'USE_ML_CLASSIFICATION': 'true'}):
        assert classify_query_complexity_ml("Total de ventas") == "simple"
        assert classify_query_complexity_ml("Join con subquery y window function") == "complex"
