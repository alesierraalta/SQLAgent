"""Sistema de aprendizaje de patrones de errores SQL (Fase D)."""

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.logger import logger


@dataclass
class ErrorPattern:
    """Patrón de error con su corrección conocida."""
    
    error_hash: str
    original_sql: str
    error_message: str
    error_type: str
    corrected_sql: str
    success_count: int = 1
    first_seen: str = ""
    last_used: str = ""
    
    def __post_init__(self):
        """Inicializar timestamps si no están definidos."""
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat()
        if not self.last_used:
            self.last_used = datetime.now().isoformat()


class ErrorPatternStore:
    """Almacén persistente de patrones de errores y sus correcciones."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Inicializa el almacén de patrones de errores.
        
        Args:
            storage_path: Ruta al archivo JSON de almacenamiento.
                         Si es None, usa .data/error_patterns.json
        """
        if storage_path is None:
            # Usar directorio .data en la raíz del proyecto
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / ".data"
            data_dir.mkdir(exist_ok=True)
            storage_path = str(data_dir / "error_patterns.json")
        
        self.storage_path = storage_path
        self.patterns: Dict[str, ErrorPattern] = {}
        self._load_patterns()
    
    def _compute_error_hash(self, original_sql: str, error_message: str) -> str:
        """
        Calcula un hash único para un par (SQL, error).
        
        Usa solo las partes relevantes del error para permitir matching
        de errores similares con diferentes valores específicos.
        
        Args:
            original_sql: SQL original que falló
            error_message: Mensaje de error
            
        Returns:
            Hash MD5 del patrón de error
        """
        # Normalizar SQL: lowercase, sin espacios extra
        normalized_sql = " ".join(original_sql.lower().split())
        
        # Normalizar error: extraer solo el tipo de error, no valores específicos
        # Ej: "column 'xyz' does not exist" -> "column does not exist"
        normalized_error = error_message.lower()
        
        # Remover valores específicos entre comillas
        import re
        normalized_error = re.sub(r"'[^']*'", "'*'", normalized_error)
        normalized_error = re.sub(r'"[^"]*"', '"*"', normalized_error)
        
        # Remover números específicos
        normalized_error = re.sub(r'\b\d+\b', '*', normalized_error)
        
        # Combinar y hashear
        pattern_key = f"{normalized_sql}|{normalized_error}"
        return hashlib.md5(pattern_key.encode()).hexdigest()
    
    def _load_patterns(self) -> None:
        """Carga patrones desde el archivo JSON."""
        if not os.path.exists(self.storage_path):
            logger.info(f"No se encontró archivo de patrones en {self.storage_path}, iniciando vacío")
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convertir dict a ErrorPattern objects
            self.patterns = {
                error_hash: ErrorPattern(**pattern_data)
                for error_hash, pattern_data in data.items()
            }
            
            logger.info(f"Cargados {len(self.patterns)} patrones de error desde {self.storage_path}")
            
        except Exception as e:
            logger.error(f"Error al cargar patrones de error: {e}")
            self.patterns = {}
    
    def _save_patterns(self) -> None:
        """Guarda patrones al archivo JSON."""
        try:
            # Convertir ErrorPattern objects a dict
            data = {
                error_hash: asdict(pattern)
                for error_hash, pattern in self.patterns.items()
            }
            
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Guardar con formato legible
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Guardados {len(self.patterns)} patrones de error en {self.storage_path}")
            
        except Exception as e:
            logger.error(f"Error al guardar patrones de error: {e}")
    
    def find_correction(
        self,
        original_sql: str,
        error_message: str,
        error_type: str
    ) -> Optional[str]:
        """
        Busca una corrección conocida para un error.
        
        Args:
            original_sql: SQL original que falló
            error_message: Mensaje de error
            error_type: Tipo de error clasificado
            
        Returns:
            SQL corregido si se encuentra un patrón conocido, None en caso contrario
        """
        error_hash = self._compute_error_hash(original_sql, error_message)
        
        if error_hash in self.patterns:
            pattern = self.patterns[error_hash]
            
            # Actualizar estadísticas de uso
            pattern.success_count += 1
            pattern.last_used = datetime.now().isoformat()
            self._save_patterns()
            
            logger.info(
                f"Patrón de error encontrado (hash: {error_hash[:8]}..., "
                f"usado {pattern.success_count} veces)"
            )
            
            return pattern.corrected_sql
        
        logger.debug(f"No se encontró patrón conocido para error (hash: {error_hash[:8]}...)")
        return None
    
    def store_successful_correction(
        self,
        original_sql: str,
        error_message: str,
        error_type: str,
        corrected_sql: str
    ) -> None:
        """
        Almacena una corrección exitosa para aprendizaje futuro.
        
        Args:
            original_sql: SQL original que falló
            error_message: Mensaje de error
            error_type: Tipo de error clasificado
            corrected_sql: SQL corregido que funcionó
        """
        # No almacenar si el SQL corregido es igual al original
        if original_sql.strip() == corrected_sql.strip():
            logger.debug("SQL corregido es igual al original, no se almacena")
            return
        
        error_hash = self._compute_error_hash(original_sql, error_message)
        
        if error_hash in self.patterns:
            # Actualizar patrón existente
            pattern = self.patterns[error_hash]
            pattern.corrected_sql = corrected_sql  # Actualizar con la corrección más reciente
            pattern.success_count += 1
            pattern.last_used = datetime.now().isoformat()
            
            logger.info(
                f"Patrón de error actualizado (hash: {error_hash[:8]}..., "
                f"total usos: {pattern.success_count})"
            )
        else:
            # Crear nuevo patrón
            pattern = ErrorPattern(
                error_hash=error_hash,
                original_sql=original_sql,
                error_message=error_message,
                error_type=error_type,
                corrected_sql=corrected_sql
            )
            self.patterns[error_hash] = pattern
            
            logger.info(f"Nuevo patrón de error almacenado (hash: {error_hash[:8]}...)")
        
        self._save_patterns()
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Obtiene estadísticas sobre los patrones almacenados.
        
        Returns:
            Dict con estadísticas
        """
        if not self.patterns:
            return {
                "total_patterns": 0,
                "total_uses": 0,
                "error_types": {},
                "most_common": []
            }
        
        # Contar por tipo de error
        error_types = {}
        for pattern in self.patterns.values():
            error_type = pattern.error_type
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += pattern.success_count
        
        # Patrones más comunes
        sorted_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.success_count,
            reverse=True
        )
        most_common = [
            {
                "error_type": p.error_type,
                "success_count": p.success_count,
                "original_sql": p.original_sql[:50] + "..." if len(p.original_sql) > 50 else p.original_sql,
                "last_used": p.last_used
            }
            for p in sorted_patterns[:5]
        ]
        
        return {
            "total_patterns": len(self.patterns),
            "total_uses": sum(p.success_count for p in self.patterns.values()),
            "error_types": error_types,
            "most_common": most_common
        }
    
    def clear_old_patterns(self, days: int = 90) -> int:
        """
        Elimina patrones que no se han usado en X días.
        
        Args:
            days: Número de días de inactividad para eliminar
            
        Returns:
            Número de patrones eliminados
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        patterns_to_remove = []
        
        for error_hash, pattern in self.patterns.items():
            last_used = datetime.fromisoformat(pattern.last_used)
            if last_used < cutoff_date:
                patterns_to_remove.append(error_hash)
        
        for error_hash in patterns_to_remove:
            del self.patterns[error_hash]
        
        if patterns_to_remove:
            self._save_patterns()
            logger.info(f"Eliminados {len(patterns_to_remove)} patrones antiguos (>{days} días)")
        
        return len(patterns_to_remove)


# Instancia global del store (singleton)
_error_pattern_store: Optional[ErrorPatternStore] = None


def get_error_pattern_store() -> ErrorPatternStore:
    """
    Obtiene la instancia global del error pattern store.
    
    Returns:
        ErrorPatternStore singleton
    """
    global _error_pattern_store
    if _error_pattern_store is None:
        _error_pattern_store = ErrorPatternStore()
    return _error_pattern_store
