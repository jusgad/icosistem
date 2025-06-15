"""
Utilidades de Cache para el Ecosistema de Emprendimiento

Este módulo proporciona una capa de abstracción y herramientas para gestionar
el cache en la aplicación, interactuando con Flask-Caching y Redis.

Funcionalidades:
- Generación estandarizada de claves de cache.
- Operaciones comunes de cache (get, set, delete, clear).
- Soporte para invalidación de cache por patrones (si usa Redis).
- Decoradores de memoización (aunque ya existen en decorators.py,
  podrían centralizarse o extenderse aquí).
- Estadísticas básicas de cache.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import logging
import json
import hashlib
from typing import Any, Optional, Callable, List, Dict
from functools import wraps

from flask import current_app

# Importar la instancia de cache de Flask-Caching desde extensions
from app.extensions import cache as app_cache, redis_client

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutos por defecto para nuevas entradas de cache

class CacheManager:
    """
    Gestor de Cache que proporciona una interfaz unificada para operaciones de cache.
    Utiliza Flask-Caching como backend principal.
    """

    def __init__(self, cache_instance=None, redis_instance=None):
        self.cache = cache_instance or app_cache
        self.redis = redis_instance or redis_client
        self.prefix = current_app.config.get('CACHE_KEY_PREFIX', 'ecosistema_cache:')

    def _make_key(self, key_parts: Union[str, List[str]]) -> str:
        """
        Genera una clave de cache estandarizada.
        
        Args:
            key_parts: Una cadena o lista de cadenas para formar la clave.
        
        Returns:
            Clave de cache final.
        """
        if isinstance(key_parts, str):
            return f"{self.prefix}{key_parts}"
        
        # Crear un hash si hay muchas partes o son complejas
        if len(key_parts) > 3 or any(len(str(p)) > 50 for p in key_parts):
            key_string = ":".join(str(p) for p in key_parts)
            hashed_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()
            return f"{self.prefix}{key_parts[0]}:{hashed_key}" # Usar la primera parte como namespace
        
        return f"{self.prefix}{':'.join(str(p) for p in key_parts)}"

    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave del item.
            
        Returns:
            Valor cacheado o None si no existe o ha expirado.
        """
        full_key = self._make_key(key)
        try:
            value = self.cache.get(full_key)
            if value is not None:
                logger.debug(f"Cache HIT para clave: {full_key}")
            else:
                logger.debug(f"Cache MISS para clave: {full_key}")
            return value
        except Exception as e:
            logger.error(f"Error obteniendo de cache ({full_key}): {e}")
            return None

    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Guarda un valor en el cache.
        
        Args:
            key: Clave del item.
            value: Valor a cachear.
            timeout: Tiempo de expiración en segundos. Usa DEFAULT_TIMEOUT si es None.
            
        Returns:
            True si se guardó correctamente, False en caso contrario.
        """
        full_key = self._make_key(key)
        timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        try:
            self.cache.set(full_key, value, timeout=timeout)
            logger.debug(f"Cache SET para clave: {full_key} con timeout: {timeout}s")
            return True
        except Exception as e:
            logger.error(f"Error guardando en cache ({full_key}): {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Elimina un valor del cache.
        
        Args:
            key: Clave del item a eliminar.
            
        Returns:
            True si se eliminó (o no existía), False en caso de error.
        """
        full_key = self._make_key(key)
        try:
            self.cache.delete(full_key)
            logger.debug(f"Cache DELETE para clave: {full_key}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando de cache ({full_key}): {e}")
            return False

    def clear(self) -> bool:
        """
        Limpia todo el cache (solo si el backend lo soporta).
        Precaución: Usar con cuidado en producción.
        
        Returns:
            True si se limpió, False en caso de error o no soportado.
        """
        try:
            self.cache.clear()
            logger.info("Cache limpiado completamente.")
            return True
        except Exception as e:
            logger.error(f"Error limpiando cache: {e}")
            return False

    def has(self, key: str) -> bool:
        """
        Verifica si una clave existe en el cache.
        
        Args:
            key: Clave a verificar.
            
        Returns:
            True si la clave existe, False en caso contrario.
        """
        full_key = self._make_key(key)
        try:
            return self.cache.has(full_key)
        except Exception as e:
            # Algunos backends de Flask-Caching no implementan `has`
            # En ese caso, podemos intentar un get.
            logger.warning(f"Backend de cache no soporta 'has', usando 'get' para {full_key}: {e}")
            return self.cache.get(full_key) is not None

    def get_many(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        """
        Obtiene múltiples valores del cache.
        
        Args:
            keys: Lista de claves.
            
        Returns:
            Diccionario con claves y sus valores cacheados.
        """
        full_keys = [self._make_key(k) for k in keys]
        try:
            # Flask-Caching soporta get_many
            cached_values = self.cache.get_many(*full_keys)
            # Reconstruir el diccionario con las claves originales
            result = {}
            for i, original_key in enumerate(keys):
                result[original_key] = cached_values[i] if i < len(cached_values) else None
            
            logger.debug(f"Cache GET_MANY para claves: {keys}")
            return result
        except Exception as e:
            logger.error(f"Error en get_many de cache: {e}")
            # Fallback a gets individuales
            return {key: self.get(key) for key in keys}

    def set_many(self, mapping: Dict[str, Any], timeout: Optional[int] = None) -> bool:
        """
        Guarda múltiples valores en el cache.
        
        Args:
            mapping: Diccionario de clave-valor.
            timeout: Tiempo de expiración.
            
        Returns:
            True si se guardaron, False en caso de error.
        """
        full_mapping = {self._make_key(k): v for k, v in mapping.items()}
        timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        try:
            self.cache.set_many(full_mapping, timeout=timeout)
            logger.debug(f"Cache SET_MANY para claves: {list(mapping.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error en set_many de cache: {e}")
            # Fallback a sets individuales
            success = True
            for key, value in mapping.items():
                if not self.set(key, value, timeout):
                    success = False
            return success

    def delete_many(self, keys: List[str]) -> bool:
        """
        Elimina múltiples valores del cache.
        
        Args:
            keys: Lista de claves a eliminar.
            
        Returns:
            True si se eliminaron, False en caso de error.
        """
        full_keys = [self._make_key(k) for k in keys]
        try:
            self.cache.delete_many(*full_keys)
            logger.debug(f"Cache DELETE_MANY para claves: {keys}")
            return True
        except Exception as e:
            logger.error(f"Error en delete_many de cache: {e}")
            # Fallback a deletes individuales
            success = True
            for key in keys:
                if not self.delete(key):
                    success = False
            return success

    def clear_pattern(self, pattern: str) -> int:
        """
        Limpia claves que coincidan con un patrón (solo para Redis).
        
        Args:
            pattern: Patrón a buscar (ej. 'user:*:profile').
            
        Returns:
            Número de claves eliminadas.
        """
        if not self.redis:
            logger.warning("clear_pattern solo está soportado para backend Redis.")
            return 0
        
        full_pattern = f"{self.prefix}{pattern}"
        try:
            keys_to_delete = [key.decode('utf-8') for key in self.redis.keys(full_pattern)]
            if keys_to_delete:
                deleted_count = self.redis.delete(*keys_to_delete)
                logger.info(f"{deleted_count} claves eliminadas con patrón: {full_pattern}")
                return deleted_count
            logger.debug(f"No se encontraron claves para el patrón: {full_pattern}")
            return 0
        except Exception as e:
            logger.error(f"Error limpiando patrón de cache ({full_pattern}): {e}")
            return 0

    def memoize(self, timeout: Optional[int] = None, make_name: Optional[Callable] = None):
        """
        Decorador para memoizar resultados de funciones.
        Similar a @cache.memoize de Flask-Caching pero usando este gestor.
        
        Args:
            timeout: Tiempo de expiración.
            make_name: Función para generar nombre de clave (opcional).
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if make_name:
                    cache_key_base = make_name(*args, **kwargs)
                else:
                    # Crear una clave simple basada en el nombre de la función y los argumentos
                    key_parts = [func.__module__, func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key_base = ":".join(key_parts)
                
                cached_value = self.get(cache_key_base)
                if cached_value is not None:
                    return cached_value

                result = func(*args, **kwargs)
                self.set(cache_key_base, result, timeout=timeout)
                return result
            return wrapper
        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas básicas del cache (si el backend lo soporta).
        Principalmente para Redis.
        """
        if not self.redis:
            logger.warning("get_stats solo está bien soportado para backend Redis.")
            return {"error": "Estadísticas no disponibles para el backend actual."}
        
        try:
            info = self.redis.info()
            return {
                'total_keys': self.redis.dbsize(),
                'used_memory': info.get('used_memory_human'),
                'hits': info.get('keyspace_hits'),
                'misses': info.get('keyspace_misses'),
                'hit_rate': (info.get('keyspace_hits', 0) / 
                             (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1))) * 100
                            if (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0)) > 0 else 0,
                'uptime_days': info.get('uptime_in_days'),
                'connected_clients': info.get('connected_clients')
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de cache: {e}")
            return {"error": str(e)}

# Instancia global del gestor de cache
# Se puede inicializar en app/__init__.py o aquí si se pasa la app
# Por ahora, asumimos que se usará con current_app
cache_manager = CacheManager()

# Funciones de utilidad de cache (pueden usar cache_manager o app_cache directamente)

def generate_key_from_args(prefix: str, func: Callable, *args, **kwargs) -> str:
    """
    Genera una clave de cache a partir de un prefijo, nombre de función y argumentos.
    """
    arg_string = hashlib.md5(
        (
            str(args) + str(sorted(kwargs.items()))
        ).encode('utf-8')
    ).hexdigest()
    return f"{prefix}:{func.__module__}:{func.__name__}:{arg_string}"

def invalidate_cache_for_model(model_instance) -> None:
    """
    Invalida claves de cache relacionadas con una instancia de modelo.
    Esto es un ejemplo, la lógica de invalidación puede ser compleja.
    """
    if not hasattr(model_instance, 'id') or not hasattr(model_instance, '__tablename__'):
        logger.warning("Instancia de modelo inválida para invalidación de cache.")
        return

    model_name = model_instance.__tablename__
    model_id = model_instance.id

    # Patrones comunes a invalidar
    patterns_to_clear = [
        f"{model_name}:{model_id}:*",  # Cache de la instancia específica
        f"{model_name}:list:*",        # Cache de listas que podrían incluir la instancia
        f"user:*:related_to_{model_name}:{model_id}" # Cache de usuarios relacionados
    ]

    for pattern in patterns_to_clear:
        cache_manager.clear_pattern(pattern)
    
    logger.info(f"Cache invalidado para {model_name} ID {model_id}")

def get_cached_or_compute(key: str, compute_func: Callable, timeout: Optional[int] = None, *args, **kwargs) -> Any:
    """
    Obtiene un valor del cache. Si no existe, lo calcula usando compute_func,
    lo guarda en cache y lo retorna.
    """
    cached_value = cache_manager.get(key)
    if cached_value is not None:
        return cached_value
    
    new_value = compute_func(*args, **kwargs)
    cache_manager.set(key, new_value, timeout=timeout)
    return new_value

# Exportaciones principales
__all__ = [
    'CacheManager',
    'cache_manager',
    'generate_key_from_args',
    'invalidate_cache_for_model',
    'get_cached_or_compute',
    'DEFAULT_TIMEOUT'
]