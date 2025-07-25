"""
Decoradores Utilitarios para el Ecosistema de Emprendimiento

Este módulo proporciona decoradores personalizados para funcionalidades comunes
como validación de JSON, logging de actividad, rate limiting, caching y
estandarización de respuestas de API.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import time
import logging
from functools import wraps
from datetime import datetime

from flask import request, jsonify, current_app, g
from flask_login import current_user

from app.core.exceptions import ValidationError
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.extensions import limiter, cache as app_cache # Renombrar para evitar conflicto con el decorador

logger = logging.getLogger(__name__)

def validate_json(f):
    """
    Decorador para validar que el request contenga JSON.
    Si no es JSON, retorna un error 400.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({"error": "Request debe ser JSON"}), 400
        return f(*args, **kwargs)
    return decorated_function


def log_activity(activity_type: ActivityType, description_template: str, severity: ActivitySeverity = ActivitySeverity.LOW):
    """
    Decorador factory para registrar la actividad de un endpoint o función.

    Args:
        activity_type (ActivityType): El tipo de actividad a registrar.
        description_template (str): Una plantilla para la descripción. Puede usar {kwargs} o {result}.
        severity (ActivitySeverity): La severidad de la actividad.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Intentar obtener el usuario actual
            user = current_user if current_user.is_authenticated else None
            user_id = user.id if user else None
            
            # Ejecutar la función original
            try:
                result = func(*args, **kwargs)
                status = "success"
            except Exception as e:
                status = "failure"
                # Re-lanzar la excepción para que sea manejada por Flask
                raise e
            finally:
                # Formatear la descripción
                try:
                    description = description_template.format(kwargs=kwargs, result=result if status == "success" else None)
                except Exception:
                    description = description_template # Fallback si el formato falla

                # Registrar la actividad
                try:
                    ActivityLog.log_activity(
                        activity_type=activity_type,
                        description=description,
                        user_id=user_id,
                        severity=severity,
                        metadata={
                            'endpoint': func.__name__,
                            'args': str(args) if args else None,
                            'kwargs': str(kwargs) if kwargs else None,
                            'status': status,
                            'ip_address': request.remote_addr,
                            'user_agent': request.headers.get('User-Agent')
                        }
                    )
                except Exception as log_exc:
                    logger.error(f"Error al registrar actividad para {func.__name__}: {log_exc}")
            return result
        return wrapper
    return decorator


def api_response(func):
    """
    Decorador para estandarizar las respuestas de la API.
    Envuelve el resultado en una estructura JSON estándar.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
                # Si la función retorna (data, status_code)
                data, status_code = result
                if isinstance(data, dict) and 'error' in data: # Ya es una respuesta de error formateada
                    return jsonify(data), status_code
                response_data = {
                    'success': True,
                    'data': data,
                    'timestamp': datetime.utcnow().isoformat()
                }
                return jsonify(response_data), status_code
            elif isinstance(result, dict) and 'error' in result: # Ya es una respuesta de error formateada
                 status_code = result.get('status_code', 400) # Asumir 400 si no se especifica
                 if 'status_code' in result:
                     del result['status_code']
                 return jsonify(result), status_code
            else:
                # Respuesta exitosa por defecto
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.utcnow().isoformat()
                }), 200
        except ValidationError as e:
            logger.warning(f"ValidationError en {func.__name__}: {e}")
            return jsonify({
                'success': False,
                'error': 'Validation Error',
                'message': str(e),
                'details': getattr(e, 'details', None),
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        except Exception as e:
            logger.error(f"Error inesperado en API endpoint {func.__name__}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'Ocurrió un error inesperado.',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    return wrapper


def rate_limit(limit_str: str = None, key_func=None, per_method: bool = False, scope: str = None):
    """
    Decorador para aplicar rate limiting a un endpoint.
    Utiliza la extensión Flask-Limiter.

    Args:
        limit_str (str, optional): Límite en formato "count per period" (e.g., "100/hour").
                                   Si es None, usa el límite por defecto de Flask-Limiter.
        key_func (callable, optional): Función para generar la clave de rate limit.
                                       Por defecto usa la IP remota.
        per_method (bool, optional): Si el límite es por método HTTP.
        scope (str, optional): Alcance del límite (e.g., "user", "endpoint").
    """
    def decorator(f):
        # Aplicar el decorador de Flask-Limiter
        # El decorador de Flask-Limiter necesita ser llamado para aplicar los límites.
        # Si limit_str no se proporciona, se usa el default_limits de la extensión.
        if limit_str:
            limited_f = limiter.limit(limit_str, key_func=key_func, per_method=per_method, scope=scope)(f)
        else:
            limited_f = limiter.limit(key_func=key_func, per_method=per_method, scope=scope)(f)
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            return limited_f(*args, **kwargs)
        return wrapper
    return decorator


def cache_response(timeout: int = 300, key_prefix: str = 'view/%s'):
    """
    Decorador para cachear la respuesta de un endpoint.
    Utiliza la extensión Flask-Caching.

    Args:
        timeout (int): Tiempo de expiración del cache en segundos.
        key_prefix (str): Prefijo para la clave de cache.
                          '%s' se reemplaza con la ruta del request.
    """
    def decorator(f):
        # Aplicar el decorador de Flask-Caching
        cached_f = app_cache.cached(timeout=timeout, key_prefix=key_prefix)(f)
        @wraps(f)
        def wrapper(*args, **kwargs):
            return cached_f(*args, **kwargs)
        return wrapper
    return decorator

def cache_result(timeout: int = 300, make_name: Optional[Callable] = None):
    """
    Decorador para cachear el resultado de una función.
    Útil para funciones de servicio o cálculos costosos.

    Args:
        timeout (int): Tiempo de expiración del cache en segundos.
        make_name (callable, optional): Función para generar un nombre de clave único
                                        basado en los argumentos de la función.
                                        Si es None, se usa una representación de los args/kwargs.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if make_name:
                cache_key = make_name(*args, **kwargs)
            else:
                # Crear una clave simple basada en el nombre de la función y los argumentos
                key_parts = [func.__module__, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            cached_value = app_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)
            app_cache.set(cache_key, result, timeout=timeout)
            return result
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0,
                     exceptions: tuple = (Exception,)):
    """
    Decorador para reintentar una función en caso de fallo.

    Args:
        max_retries (int): Número máximo de reintentos.
        delay (float): Retraso inicial en segundos.
        backoff (float): Factor de backoff exponencial.
        exceptions (tuple): Tupla de excepciones a capturar para reintento.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Función {func.__name__} falló después de {max_retries} reintentos: {e}")
                        raise
                    logger.warning(
                        f"Intento {attempt + 1} fallido para {func.__name__}: {e}. "
                        f"Reintentando en {current_delay:.2f} segundos..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

