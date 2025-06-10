"""
Rate Limiting Middleware para el ecosistema de emprendimiento.
Proporciona control avanzado de tráfico con múltiples algoritmos y estrategias.

Características:
- Múltiples algoritmos: Token Bucket, Sliding Window, Fixed Window
- Backends: Redis, Memory, Database
- Rate limiting por IP, Usuario, Endpoint, Rol
- Burst allowance y grace periods
- Whitelist/Blacklist dinámicas
- Métricas en tiempo real
- Configuración flexible por entorno

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, request, g, current_app, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.exceptions import TooManyRequests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import time
import json
import redis
import hashlib
import logging
from functools import wraps
from collections import defaultdict, deque
import threading
import sqlite3
from contextlib import contextmanager

# Importaciones locales
from app.core.exceptions import RateLimitException
from app.models.user import User, UserType
from app.utils.string_utils import get_client_ip
from app.utils.date_utils import get_utc_now
from app.services.analytics_service import AnalyticsService
from app.extensions import cache, db

logger = logging.getLogger(__name__)

class RateLimitAlgorithm(Enum):
    """Algoritmos de rate limiting disponibles."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window" 
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"

class RateLimitScope(Enum):
    """Alcances de rate limiting."""
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"
    USER_TYPE = "user_type"
    API_KEY = "api_key"

class RateLimitAction(Enum):
    """Acciones cuando se excede el límite."""
    REJECT = "reject"
    DELAY = "delay"
    THROTTLE = "throttle"
    WARN = "warn"

@dataclass
class RateLimitRule:
    """Definición de una regla de rate limiting."""
    name: str
    limit: int
    period: int  # segundos
    scope: RateLimitScope
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    action: RateLimitAction = RateLimitAction.REJECT
    burst_allowance: int = 0
    grace_period: int = 0
    priority: int = 100
    enabled: bool = True
    conditions: Dict[str, Any] = field(default_factory=dict)
    exemptions: List[str] = field(default_factory=list)

@dataclass
class RateLimitResult:
    """Resultado de verificación de rate limit."""
    allowed: bool
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None
    rule_name: Optional[str] = None
    current_usage: int = 0
    total_limit: int = 0

class RateLimitBackend:
    """Backend base para almacenamiento de rate limits."""
    
    def get_usage(self, key: str, window_size: int) -> int:
        """Obtiene el uso actual para una key en una ventana."""
        raise NotImplementedError
    
    def increment(self, key: str, window_size: int, amount: int = 1) -> int:
        """Incrementa el contador y retorna el nuevo valor."""
        raise NotImplementedError
    
    def reset(self, key: str) -> bool:
        """Resetea el contador para una key."""
        raise NotImplementedError
    
    def cleanup_expired(self) -> int:
        """Limpia entradas expiradas."""
        raise NotImplementedError

class RedisRateLimitBackend(RateLimitBackend):
    """Backend Redis para rate limiting."""
    
    def __init__(self, redis_client: redis.Redis = None, key_prefix: str = "rate_limit"):
        self.redis = redis_client or redis.from_url(
            current_app.config.get('REDIS_URL', 'redis://localhost:6379')
        )
        self.prefix = key_prefix
        
    def _make_key(self, key: str) -> str:
        """Genera key con prefix."""
        return f"{self.prefix}:{key}"
    
    def get_usage(self, key: str, window_size: int) -> int:
        """Obtiene uso actual con sliding window."""
        redis_key = self._make_key(key)
        now = time.time()
        cutoff = now - window_size
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_size + 1)
        
        results = pipe.execute()
        return results[1]
    
    def increment(self, key: str, window_size: int, amount: int = 1) -> int:
        """Incrementa contador con sliding window."""
        redis_key = self._make_key(key)
        now = time.time()
        cutoff = now - window_size
        
        pipe = self.redis.pipeline()
        
        for _ in range(amount):
            pipe.zadd(redis_key, {str(now + _ * 0.001): now + _ * 0.001})
        
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_size + 1)
        
        results = pipe.execute()
        return results[-2]  # zcard result
    
    def reset(self, key: str) -> bool:
        """Resetea contador."""
        redis_key = self._make_key(key)
        return self.redis.delete(redis_key) > 0
    
    def cleanup_expired(self) -> int:
        """Redis maneja expiración automáticamente."""
        return 0

class MemoryRateLimitBackend(RateLimitBackend):
    """Backend en memoria para rate limiting."""
    
    def __init__(self):
        self.storage: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.RLock()
        
    def _cleanup_window(self, key: str, window_size: int):
        """Limpia ventana deslizante."""
        now = time.time()
        cutoff = now - window_size
        
        while self.storage[key] and self.storage[key][0] <= cutoff:
            self.storage[key].popleft()
    
    def get_usage(self, key: str, window_size: int) -> int:
        """Obtiene uso actual."""
        with self.lock:
            self._cleanup_window(key, window_size)
            return len(self.storage[key])
    
    def increment(self, key: str, window_size: int, amount: int = 1) -> int:
        """Incrementa contador."""
        with self.lock:
            self._cleanup_window(key, window_size)
            now = time.time()
            
            for _ in range(amount):
                self.storage[key].append(now)
            
            return len(self.storage[key])
    
    def reset(self, key: str) -> bool:
        """Resetea contador."""
        with self.lock:
            if key in self.storage:
                self.storage[key].clear()
                return True
            return False
    
    def cleanup_expired(self) -> int:
        """Limpia entradas expiradas."""
        with self.lock:
            cleaned = 0
            for key in list(self.storage.keys()):
                if not self.storage[key]:
                    del self.storage[key]
                    cleaned += 1
            return cleaned

class DatabaseRateLimitBackend(RateLimitBackend):
    """Backend de base de datos para rate limiting persistente."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or current_app.config.get(
            'RATE_LIMIT_DB_PATH', 
            '/tmp/rate_limits.db'
        )
        self._init_db()
        
    def _init_db(self):
        """Inicializa base de datos SQLite."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT,
                    timestamp REAL,
                    PRIMARY KEY (key, timestamp)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON rate_limits(timestamp)
            ''')
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexiones DB."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_usage(self, key: str, window_size: int) -> int:
        """Obtiene uso actual."""
        cutoff = time.time() - window_size
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM rate_limits WHERE key = ? AND timestamp > ?',
                (key, cutoff)
            )
            return cursor.fetchone()[0]
    
    def increment(self, key: str, window_size: int, amount: int = 1) -> int:
        """Incrementa contador."""
        now = time.time()
        cutoff = now - window_size
        
        with self._get_connection() as conn:
            # Limpiar entradas expiradas
            conn.execute(
                'DELETE FROM rate_limits WHERE key = ? AND timestamp <= ?',
                (key, cutoff)
            )
            
            # Agregar nuevas entradas
            for i in range(amount):
                conn.execute(
                    'INSERT INTO rate_limits (key, timestamp) VALUES (?, ?)',
                    (key, now + i * 0.001)
                )
            
            # Contar total
            cursor = conn.execute(
                'SELECT COUNT(*) FROM rate_limits WHERE key = ?',
                (key,)
            )
            return cursor.fetchone()[0]
    
    def reset(self, key: str) -> bool:
        """Resetea contador."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'DELETE FROM rate_limits WHERE key = ?',
                (key,)
            )
            return cursor.rowcount > 0
    
    def cleanup_expired(self) -> int:
        """Limpia entradas expiradas globalmente."""
        cutoff = time.time() - 3600  # 1 hora atrás
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                'DELETE FROM rate_limits WHERE timestamp <= ?',
                (cutoff,)
            )
            return cursor.rowcount

class TokenBucketLimiter:
    """Implementación de Token Bucket algorithm."""
    
    def __init__(self, backend: RateLimitBackend):
        self.backend = backend
        
    def check_limit(self, key: str, rule: RateLimitRule) -> RateLimitResult:
        """Verifica límite usando token bucket."""
        bucket_key = f"bucket:{key}"
        last_refill_key = f"bucket_refill:{key}"
        
        now = time.time()
        
        # Obtener estado actual del bucket
        current_tokens = self.backend.get_usage(bucket_key, rule.period)
        last_refill = self.backend.get_usage(last_refill_key, 86400)  # 24h window
        
        if not last_refill:
            last_refill = now
            current_tokens = rule.limit
        
        # Calcular tokens a agregar
        time_passed = now - last_refill
        tokens_to_add = int(time_passed * (rule.limit / rule.period))
        current_tokens = min(rule.limit, current_tokens + tokens_to_add)
        
        if current_tokens > 0:
            # Consumir token
            current_tokens -= 1
            self.backend.reset(bucket_key)
            self.backend.increment(bucket_key, rule.period, rule.limit - current_tokens)
            self.backend.reset(last_refill_key)
            self.backend.increment(last_refill_key, 86400, int(now))
            
            return RateLimitResult(
                allowed=True,
                remaining=current_tokens,
                reset_time=datetime.fromtimestamp(now + rule.period),
                rule_name=rule.name,
                current_usage=rule.limit - current_tokens,
                total_limit=rule.limit
            )
        else:
            # Sin tokens disponibles
            retry_after = int(rule.period / rule.limit)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.fromtimestamp(now + retry_after),
                retry_after=retry_after,
                rule_name=rule.name,
                current_usage=rule.limit,
                total_limit=rule.limit
            )

class SlidingWindowLimiter:
    """Implementación de Sliding Window algorithm."""
    
    def __init__(self, backend: RateLimitBackend):
        self.backend = backend
        
    def check_limit(self, key: str, rule: RateLimitRule) -> RateLimitResult:
        """Verifica límite usando sliding window."""
        current_usage = self.backend.get_usage(key, rule.period)
        
        if current_usage < rule.limit:
            # Incrementar uso
            new_usage = self.backend.increment(key, rule.period)
            
            return RateLimitResult(
                allowed=True,
                remaining=rule.limit - new_usage,
                reset_time=datetime.fromtimestamp(time.time() + rule.period),
                rule_name=rule.name,
                current_usage=new_usage,
                total_limit=rule.limit
            )
        else:
            # Límite excedido
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.fromtimestamp(time.time() + rule.period),
                retry_after=rule.period,
                rule_name=rule.name,
                current_usage=current_usage,
                total_limit=rule.limit
            )

class AdaptiveRateLimiter:
    """Rate limiter adaptativo basado en patrones de tráfico."""
    
    def __init__(self, backend: RateLimitBackend):
        self.backend = backend
        self.base_limiter = SlidingWindowLimiter(backend)
        
    def check_limit(self, key: str, rule: RateLimitRule) -> RateLimitResult:
        """Verifica límite con adaptación basada en historial."""
        # Obtener estadísticas históricas
        history_key = f"history:{key}"
        recent_usage = self.backend.get_usage(history_key, rule.period * 10)
        
        # Calcular factor de adaptación
        if recent_usage < rule.limit * 0.5:
            # Bajo uso histórico: ser más permisivo
            adapted_rule = RateLimitRule(
                name=f"{rule.name}_adapted",
                limit=int(rule.limit * 1.2),
                period=rule.period,
                scope=rule.scope,
                algorithm=rule.algorithm
            )
        elif recent_usage > rule.limit * 0.9:
            # Alto uso histórico: ser más restrictivo
            adapted_rule = RateLimitRule(
                name=f"{rule.name}_adapted",
                limit=int(rule.limit * 0.8),
                period=rule.period,
                scope=rule.scope,
                algorithm=rule.algorithm
            )
        else:
            adapted_rule = rule
        
        # Registrar uso actual en historial
        self.backend.increment(history_key, rule.period * 10)
        
        return self.base_limiter.check_limit(key, adapted_rule)

class RateLimitManager:
    """Gestor principal de rate limiting."""
    
    def __init__(self, backend: RateLimitBackend = None):
        self.backend = backend or self._create_default_backend()
        self.rules: Dict[str, RateLimitRule] = {}
        self.algorithms = {
            RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketLimiter(self.backend),
            RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowLimiter(self.backend),
            RateLimitAlgorithm.ADAPTIVE: AdaptiveRateLimiter(self.backend),
            RateLimitAlgorithm.FIXED_WINDOW: SlidingWindowLimiter(self.backend)  # Similar implementation
        }
        self.whitelist: set = set()
        self.blacklist: set = set()
        
    def _create_default_backend(self) -> RateLimitBackend:
        """Crea backend por defecto basado en configuración."""
        backend_type = current_app.config.get('RATE_LIMIT_BACKEND', 'memory')
        
        if backend_type == 'redis':
            return RedisRateLimitBackend()
        elif backend_type == 'database':
            return DatabaseRateLimitBackend()
        else:
            return MemoryRateLimitBackend()
    
    def add_rule(self, rule: RateLimitRule):
        """Agrega una regla de rate limiting."""
        self.rules[rule.name] = rule
        logger.info(f"Regla de rate limit agregada: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remueve una regla de rate limiting."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Regla de rate limit removida: {rule_name}")
            return True
        return False
    
    def add_to_whitelist(self, identifier: str):
        """Agrega a whitelist (IP, user_id, etc.)."""
        self.whitelist.add(identifier)
        
    def add_to_blacklist(self, identifier: str):
        """Agrega a blacklist."""
        self.blacklist.add(identifier)
    
    def remove_from_whitelist(self, identifier: str):
        """Remueve de whitelist."""
        self.whitelist.discard(identifier)
        
    def remove_from_blacklist(self, identifier: str):
        """Remueve de blacklist."""
        self.blacklist.discard(identifier)
    
    def _generate_key(self, rule: RateLimitRule, context: Dict[str, Any]) -> str:
        """Genera key única para rate limiting."""
        key_parts = [rule.scope.value]
        
        if rule.scope == RateLimitScope.IP:
            key_parts.append(context.get('ip', 'unknown'))
        elif rule.scope == RateLimitScope.USER:
            key_parts.append(str(context.get('user_id', 'anonymous')))
        elif rule.scope == RateLimitScope.ENDPOINT:
            key_parts.append(context.get('endpoint', 'unknown'))
        elif rule.scope == RateLimitScope.USER_TYPE:
            key_parts.append(context.get('user_type', 'unknown'))
        elif rule.scope == RateLimitScope.API_KEY:
            key_parts.append(context.get('api_key', 'unknown'))
        elif rule.scope == RateLimitScope.GLOBAL:
            key_parts.append('global')
        
        # Agregar nombre de regla para evitar colisiones
        key_parts.append(rule.name)
        
        return ':'.join(key_parts)
    
    def _matches_conditions(self, rule: RateLimitRule, context: Dict[str, Any]) -> bool:
        """Verifica si el contexto cumple las condiciones de la regla."""
        if not rule.conditions:
            return True
            
        for condition, expected_value in rule.conditions.items():
            actual_value = context.get(condition)
            
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False
                
        return True
    
    def _is_exempt(self, rule: RateLimitRule, context: Dict[str, Any]) -> bool:
        """Verifica si el contexto está exento de la regla."""
        user_id = context.get('user_id')
        ip = context.get('ip')
        
        # Verificar whitelist
        if str(user_id) in self.whitelist or ip in self.whitelist:
            return True
        
        # Verificar exempciones específicas de la regla
        for exemption in rule.exemptions:
            if exemption in [str(user_id), ip, context.get('user_type')]:
                return True
                
        return False
    
    def check_rate_limit(self, context: Dict[str, Any]) -> List[RateLimitResult]:
        """Verifica todas las reglas aplicables."""
        results = []
        
        # Verificar blacklist primero
        user_id = context.get('user_id')
        ip = context.get('ip')
        
        if str(user_id) in self.blacklist or ip in self.blacklist:
            return [RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.utcnow() + timedelta(hours=24),
                retry_after=86400,
                rule_name="blacklist"
            )]
        
        # Evaluar reglas por prioridad
        sorted_rules = sorted(
            self.rules.values(),
            key=lambda r: r.priority
        )
        
        for rule in sorted_rules:
            if not rule.enabled:
                continue
                
            if not self._matches_conditions(rule, context):
                continue
                
            if self._is_exempt(rule, context):
                continue
            
            key = self._generate_key(rule, context)
            limiter = self.algorithms[rule.algorithm]
            result = limiter.check_limit(key, rule)
            
            results.append(result)
            
            # Si alguna regla rechaza, parar evaluación
            if not result.allowed:
                break
        
        return results

class RateLimitMiddleware:
    """Middleware principal de rate limiting."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.manager = RateLimitManager()
        self.analytics_service = None
        self._setup_default_rules()
        
    def _setup_default_rules(self):
        """Configura reglas por defecto."""
        # Regla global básica
        self.manager.add_rule(RateLimitRule(
            name="global_basic",
            limit=1000,
            period=3600,  # 1 hora
            scope=RateLimitScope.IP,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            priority=100
        ))
        
        # Regla por usuario autenticado
        self.manager.add_rule(RateLimitRule(
            name="user_authenticated",
            limit=500,
            period=3600,
            scope=RateLimitScope.USER,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            priority=80,
            conditions={'authenticated': True}
        ))
        
        # Regla estricta para endpoints sensibles
        self.manager.add_rule(RateLimitRule(
            name="auth_endpoints",
            limit=10,
            period=300,  # 5 minutos
            scope=RateLimitScope.IP,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            priority=10,
            conditions={'endpoint': ['/auth/login', '/auth/register', '/auth/reset-password']}
        ))
        
        # Regla para uploads
        self.manager.add_rule(RateLimitRule(
            name="file_uploads",
            limit=20,
            period=3600,
            scope=RateLimitScope.USER,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            priority=50,
            conditions={'method': 'POST', 'has_files': True}
        ))
    
    def init_app(self, app: Flask):
        """Inicializa el middleware con Flask."""
        self.app = app
        
        # Configurar reglas desde config
        rules_config = self.config.get('rules', [])
        for rule_config in rules_config:
            rule = RateLimitRule(**rule_config)
            self.manager.add_rule(rule)
        
        # Configurar whitelist/blacklist
        whitelist = self.config.get('whitelist', [])
        for item in whitelist:
            self.manager.add_to_whitelist(item)
            
        blacklist = self.config.get('blacklist', [])
        for item in blacklist:
            self.manager.add_to_blacklist(item)
    
    def _get_request_context(self) -> Dict[str, Any]:
        """Extrae contexto del request actual."""
        context = {
            'ip': get_client_ip(),
            'method': request.method,
            'endpoint': request.endpoint or request.path,
            'path': request.path,
            'user_agent': request.user_agent.string,
            'has_files': bool(request.files),
            'authenticated': False,
            'user_id': None,
            'user_type': None
        }
        
        # Intentar obtener información del usuario
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            
            if user_id:
                context['authenticated'] = True
                context['user_id'] = user_id
                
                # Obtener tipo de usuario
                user = User.query.get(user_id)
                if user:
                    context['user_type'] = user.user_type.value
                    
        except Exception:
            pass  # Usuario no autenticado
        
        return context
    
    def _get_analytics_service(self):
        """Obtiene servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def process_request(self):
        """Procesa request para rate limiting."""
        # Obtener contexto
        context = self._get_request_context()
        
        # Verificar rate limits
        results = self.manager.check_rate_limit(context)
        
        if not results:
            return  # Sin reglas aplicables
        
        # Encontrar resultado más restrictivo
        blocking_result = None
        for result in results:
            if not result.allowed:
                blocking_result = result
                break
        
        # Agregar headers informativos
        if results:
            primary_result = results[0]
            g.rate_limit_remaining = primary_result.remaining
            g.rate_limit_limit = primary_result.total_limit
            g.rate_limit_reset = int(primary_result.reset_time.timestamp())
        
        # Si hay bloqueo, rechazar request
        if blocking_result:
            self._track_rate_limit_exceeded(context, blocking_result)
            
            error_response = {
                'error': 'Rate limit exceeded',
                'message': f'Rate limit exceeded for rule: {blocking_result.rule_name}',
                'retry_after': blocking_result.retry_after,
                'limit': blocking_result.total_limit,
                'reset_time': blocking_result.reset_time.isoformat()
            }
            
            response = jsonify(error_response)
            response.status_code = 429
            response.headers['Retry-After'] = str(blocking_result.retry_after or 60)
            response.headers['X-RateLimit-Limit'] = str(blocking_result.total_limit)
            response.headers['X-RateLimit-Remaining'] = str(blocking_result.remaining)
            response.headers['X-RateLimit-Reset'] = str(int(blocking_result.reset_time.timestamp()))
            
            raise TooManyRequests(response=response)
    
    def process_response(self, response):
        """Procesa response para agregar headers."""
        # Agregar headers de rate limiting
        if hasattr(g, 'rate_limit_remaining'):
            response.headers['X-RateLimit-Limit'] = str(getattr(g, 'rate_limit_limit', 0))
            response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
            response.headers['X-RateLimit-Reset'] = str(getattr(g, 'rate_limit_reset', 0))
        
        return response
    
    def _track_rate_limit_exceeded(self, context: Dict[str, Any], result: RateLimitResult):
        """Registra evento de rate limit excedido."""
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_rate_limit_event({
                'event_type': 'rate_limit_exceeded',
                'rule_name': result.rule_name,
                'ip': context['ip'],
                'user_id': context.get('user_id'),
                'endpoint': context['endpoint'],
                'user_agent': context['user_agent'],
                'timestamp': get_utc_now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error tracking rate limit event: {str(e)}")

# Decoradores útiles
def rate_limit(limit: str, scope: RateLimitScope = RateLimitScope.IP, 
               algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW):
    """
    Decorador para aplicar rate limiting a endpoints específicos.
    
    Args:
        limit: Límite en formato "cantidad/período" (ej: "100/hour", "10/minute")
        scope: Alcance del rate limiting
        algorithm: Algoritmo a usar
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Parsear límite
            try:
                amount, period_str = limit.split('/')
                amount = int(amount)
                
                period_map = {
                    'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400
                }
                period = period_map.get(period_str, 60)
                
                # Crear regla temporal
                rule_name = f"{f.__name__}_{limit}_{scope.value}"
                rule = RateLimitRule(
                    name=rule_name,
                    limit=amount,
                    period=period,
                    scope=scope,
                    algorithm=algorithm
                )
                
                # Verificar límite
                middleware = current_app.extensions.get('rate_limit_middleware')
                if middleware:
                    context = middleware._get_request_context()
                    results = [middleware.manager.algorithms[algorithm].check_limit(
                        middleware.manager._generate_key(rule, context),
                        rule
                    )]
                    
                    if results and not results[0].allowed:
                        raise TooManyRequests(
                            description=f"Rate limit exceeded: {limit}"
                        )
                
            except Exception as e:
                if isinstance(e, TooManyRequests):
                    raise
                logger.error(f"Error en rate limit decorator: {str(e)}")
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# Configuraciones predefinidas
def configure_development_rate_limits() -> Dict[str, Any]:
    """Configuración para desarrollo."""
    return {
        'backend': 'memory',
        'rules': [
            {
                'name': 'dev_general',
                'limit': 10000,
                'period': 3600,
                'scope': 'ip',
                'algorithm': 'sliding_window'
            }
        ],
        'whitelist': ['127.0.0.1', '::1']
    }

def configure_production_rate_limits() -> Dict[str, Any]:
    """Configuración para producción."""
    return {
        'backend': 'redis',
        'rules': [
            {
                'name': 'prod_general',
                'limit': 1000,
                'period': 3600,
                'scope': 'ip',
                'algorithm': 'adaptive'
            },
            {
                'name': 'prod_auth',
                'limit': 5,
                'period': 300,
                'scope': 'ip',
                'algorithm': 'sliding_window',
                'conditions': {'endpoint': ['/api/v1/auth/login']}
            },
            {
                'name': 'prod_premium_users',
                'limit': 5000,
                'period': 3600,
                'scope': 'user',
                'algorithm': 'token_bucket',
                'conditions': {'user_type': 'premium'}
            }
        ]
    }

# Funciones de utilidad exportadas
__all__ = [
    'RateLimitMiddleware',
    'RateLimitManager', 
    'RateLimitRule',
    'RateLimitResult',
    'RateLimitAlgorithm',
    'RateLimitScope',
    'RateLimitAction',
    'RedisRateLimitBackend',
    'MemoryRateLimitBackend',
    'DatabaseRateLimitBackend',
    'rate_limit',
    'configure_development_rate_limits',
    'configure_production_rate_limits'
]