"""ML-enhanced query complexity classifier (Phase E)."""

import os
from typing import List, Tuple

from src.utils.logger import logger


# Reference examples by category
SIMPLE_EXAMPLES = [
    "¿Cuántos productos hay?",
    "Total de ventas",
    "Suma de revenue",
    "Lista de clientes",
    "Promedio de precio",
    "Contar registros",
    "Mostrar todas las ventas",
    "¿Cuántas ventas hay por país?",
    "Total de revenue por mes",
    "Promedio de cantidad",
]

COMPLEX_EXAMPLES = [
    "Ventas por país con subconsulta de productos más vendidos",
    "Join entre ventas y productos con filtro de fecha",
    "CTE con ranking de clientes por revenue",
    "Window function para calcular running total",
    "Union de ventas de diferentes años",
    "Subquery con agregación anidada",
    "Case when con múltiples condiciones",
    "Left join con having clause",
    "Partition by para análisis temporal",
    "Query con múltiples joins y agregaciones",
]


class MLQueryClassifier:
    """Query complexity classifier using embeddings."""
    
    def __init__(self):
        """Initializes the ML classifier."""
        self.model = None
        self.simple_embeddings = None
        self.complex_embeddings = None
        self._initialized = False
    
    def _lazy_init(self) -> bool:
        """
        Lazy initialization of the model (only when needed).
        
        Returns:
            True if initialized successfully, False if failed
        """
        if self._initialized:
            return True
        
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            # Use lightweight and fast model
            model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            logger.info(f"Cargando modelo de embeddings: {model_name}")
            
            self.model = SentenceTransformer(model_name)
            
            # Generate embeddings for reference examples
            logger.info("Generando embeddings de ejemplos de referencia...")
            self.simple_embeddings = self.model.encode(SIMPLE_EXAMPLES)
            self.complex_embeddings = self.model.encode(COMPLEX_EXAMPLES)
            
            self._initialized = True
            logger.info("Clasificador ML inicializado correctamente")
            return True
            
        except ImportError:
            logger.warning(
                "sentence-transformers no está instalado. "
                "Instalar con: pip install sentence-transformers"
            )
            return False
        except Exception as e:
            logger.warning(f"Error al inicializar clasificador ML: {e}")
            return False
    
    def classify(self, question: str) -> str:
        """
        Classifies query complexity using embeddings.
        
        Args:
            question: User question in natural language
            
        Returns:
            "simple" or "complex"
        """
        if not self._lazy_init():
            # Fallback to keyword-based classifier
            return None
        
        try:
            import numpy as np
            from scipy.spatial.distance import cosine
            
            # Generate question embedding
            question_embedding = self.model.encode([question])[0]
            
            # Calculate similarity with simple examples
            simple_similarities = [
                1 - cosine(question_embedding, ref_embedding)
                for ref_embedding in self.simple_embeddings
            ]
            avg_simple_similarity = np.mean(simple_similarities)
            max_simple_similarity = np.max(simple_similarities)
            
            # Calculate similarity with complex examples
            complex_similarities = [
                1 - cosine(question_embedding, ref_embedding)
                for ref_embedding in self.complex_embeddings
            ]
            avg_complex_similarity = np.mean(complex_similarities)
            max_complex_similarity = np.max(complex_similarities)
            
            # Decision based on similarities
            # Use both mean and max for better accuracy
            simple_score = (avg_simple_similarity * 0.6) + (max_simple_similarity * 0.4)
            complex_score = (avg_complex_similarity * 0.6) + (max_complex_similarity * 0.4)
            
            # Confidence threshold
            confidence_threshold = 0.05
            
            if simple_score > complex_score + confidence_threshold:
                logger.debug(
                    f"ML Classification: simple (score: {simple_score:.3f} vs {complex_score:.3f})"
                )
                return "simple"
            elif complex_score > simple_score + confidence_threshold:
                logger.debug(
                    f"ML Classification: complex (score: {complex_score:.3f} vs {simple_score:.3f})"
                )
                return "complex"
            else:
                # Too close, use keyword tiebreaker
                logger.debug(
                    f"ML Classification: inconclusive (scores: {simple_score:.3f} vs {complex_score:.3f}), "
                    "using keyword fallback"
                )
                return None
                
        except Exception as e:
            logger.warning(f"Error en clasificación ML: {e}, usando fallback")
            return None


# Global classifier instance (singleton with lazy init)
_ml_classifier: MLQueryClassifier = None


def get_ml_classifier() -> MLQueryClassifier:
    """
    Gets the global instance of the ML classifier.
    
    Returns:
        MLQueryClassifier singleton
    """
    global _ml_classifier
    if _ml_classifier is None:
        _ml_classifier = MLQueryClassifier()
    return _ml_classifier


def classify_query_complexity_ml(question: str) -> str:
    """
    Classifies query complexity using ML + keywords (hybrid).
    
    Strategy:
    1. Attempt classification with ML (embeddings)
    2. If ML is unavailable or inconclusive, use keywords
    
    Args:
        question: User question in natural language
        
    Returns:
        "simple" or "complex"
    """
    # Check if ML is enabled
    use_ml = os.getenv("USE_ML_CLASSIFICATION", "true").lower() in ("true", "1", "yes")
    
    if use_ml:
        classifier = get_ml_classifier()
        ml_result = classifier.classify(question)
        
        if ml_result is not None:
            return ml_result
        
        logger.debug("ML classification inconclusive, using keyword fallback")
    
    # Fallback: keyword-based classifier (original)
    return _classify_with_keywords(question)


def _classify_with_keywords(question: str) -> str:
    """
    Keyword-based classifier (fallback).
    
    Args:
        question: User question
        
    Returns:
        "simple" or "complex"
    """
    question_lower = question.lower()
    words = question_lower.split()
    word_count = len(words)
    
    # Keywords indicating complex queries
    complex_keywords = [
        "join", "inner join", "left join", "right join", "full join",
        "subquery", "sub-query", "with", "cte", "common table expression",
        "union", "intersect", "except", "window", "over", "partition",
        "case when", "coalesce", "nullif", "cast", "convert",
        "distinct on", "array", "json", "jsonb", "having"
    ]
    
    has_complex_keywords = any(
        keyword in question_lower for keyword in complex_keywords
    )
    
    if has_complex_keywords:
        return "complex"
    
    # Basic keywords indicating simple queries
    simple_keywords = [
        "total", "count", "sum", "list", "show", 
        "cuántos", "cuántas", "promedio", "avg"
    ]
    has_simple_keywords = any(keyword in question_lower for keyword in simple_keywords)
    
    # If it has 'por' (by) but also simple keywords and is short, it is a simple GROUP BY
    has_por = "por" in question_lower
    if has_por and has_simple_keywords and word_count <= 12:
        return "simple"
    
    # If it only has simple keywords and is short, it is simple
    if has_simple_keywords and word_count <= 10:
        return "simple"
    
    # If it is very short (<=6 words) and has simple keywords, it is simple
    if word_count <= 6 and has_simple_keywords:
        return "simple"
    
    # Default to complex for safety
    return "complex"
