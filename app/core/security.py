"""
Utilidades de seguridad para el ecosistema de emprendimiento.
Este módulo centraliza todas las funciones relacionadas con seguridad, encriptación y validación.
"""

import os
import re
import hashlib
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urlparse
import bleach
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app, request, session
from flask_login import current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import redis
from email_validator import validate_email, EmailNotValidError

# Configurar logger de seguridad
security_logger = logging.getLogger('ecosistema.security')


# ====================================
# CONFIGURACIÓN DE ENCRIPTACIÓN
# ====================================

class SecurityConfig:
    """Configuración centralizada de seguridad."""
    
    @staticmethod
    def get_encryption_key():
        """Obtener clave de encriptación desde configuración."""
        key = current_app.config.get('ENCRYPTION_KEY')
        if not key:
            # Generar clave temporal para desarrollo
            if current_app.debug:
                security_logger.warning("Usando clave de encriptación temporal en desarrollo")
                return Fernet.generate_key()
            else:
                raise ValueError("ENCRYPTION_KEY no configurada en producción")
        return key.encode() if isinstance(key, str) else key
    
    @staticmethod
    def get_jwt_secret():
        """Obtener secreto JWT."""
        return current_app.config.get('JWT_SECRET_KEY') or current_app.config['SECRET_KEY']
    
    @staticmethod
    def get_password_config():
        """Obtener configuración de contraseñas."""
        return {
            'min_length': current_app.config.get('MIN_PASSWORD_LENGTH', 8),
            'require_uppercase': current_app.config.get('REQUIRE_PASSWORD_UPPERCASE', True),
            'require_lowercase': current_app.config.get('REQUIRE_PASSWORD_LOWERCASE', True),
            'require_digits': current_app.config.get('REQUIRE_PASSWORD_DIGITS', True),
            'require_special': current_app.config.get('REQUIRE_PASSWORD_SPECIAL', True),
            'forbidden_patterns': current_app.config.get('FORBIDDEN_PASSWORD_PATTERNS', [])
        }


# ====================================
# ENCRIPTACIÓN Y HASHING
# ====================================

def encrypt_sensitive_data(data: str) -> str:
    """
    Encriptar datos sensibles usando Fernet.
    
    Args:
        data: Datos a encriptar
        
    Returns:
        Datos encriptados como string base64
    """
    try:
        if not data:
            return ""
        
        key = SecurityConfig.get_encryption_key()
        fernet = Fernet(key)
        
        # Convertir a bytes si es necesario
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted_data = fernet.encrypt(data)
        return encrypted_data.decode('utf-8')
        
    except Exception as e:
        security_logger.error(f"Error encriptando datos: {str(e)}")
        raise


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """
    Desencriptar datos sensibles.
    
    Args:
        encrypted_data: Datos encriptados
        
    Returns:
        Datos desencriptados como string
    """
    try:
        if not encrypted_data:
            return ""
        
        key = SecurityConfig.get_encryption_key()
        fernet = Fernet(key)
        
        # Convertir a bytes
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode('utf-8')
        
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode('utf-8')
        
    except Exception as e:
        security_logger.error(f"Error desencriptando datos: {str(e)}")
        raise


def hash_password(password: str) -> str:
    """
    Generar hash seguro de contraseña.
    
    Args:
        password: Contraseña en texto plano
        
    Returns:
        Hash de la contraseña
    """
    return generate_password_hash(
        password,
        method='pbkdf2:sha256',
        salt_length=16
    )


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verificar contraseña contra su hash.
    
    Args:
        password: Contraseña en texto plano
        password_hash: Hash almacenado
        
    Returns:
        True si la contraseña es correcta
    """
    return check_password_hash(password_hash, password)


def generate_secure_token(length: int = 32) -> str:
    """
    Generar token seguro aleatorio.
    
    Args:
        length: Longitud del token
        
    Returns:
        Token aleatorio seguro
    """
    return secrets.token_urlsafe(length)


def generate_secure_password(length: int = 16) -> str:
    """
    Generar contraseña segura aleatoria.
    
    Args:
        length: Longitud de la contraseña
        
    Returns:
        Contraseña segura
    """
    # Caracteres permitidos
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"
    
    # Asegurar al menos un carácter de cada tipo
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Completar con caracteres aleatorios
    all_chars = lowercase + uppercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Mezclar la contraseña
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def hash_data(data: str, algorithm: str = 'sha256') -> str:
    """
    Generar hash de datos usando algoritmo especificado.
    
    Args:
        data: Datos a hashear
        algorithm: Algoritmo de hash (sha256, sha512, md5)
        
    Returns:
        Hash hexadecimal
    """
    if algorithm == 'sha256':
        return hashlib.sha256(data.encode()).hexdigest()
    elif algorithm == 'sha512':
        return hashlib.sha512(data.encode()).hexdigest()
    elif algorithm == 'md5':
        return hashlib.md5(data.encode()).hexdigest()
    else:
        raise ValueError(f"Algoritmo de hash no soportado: {algorithm}")


# ====================================
# VALIDACIONES DE SEGURIDAD
# ====================================

def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validar fortaleza de contraseña según configuración.
    
    Args:
        password: Contraseña a validar
        
    Returns:
        Diccionario con resultado de validación
    """
    config = SecurityConfig.get_password_config()
    errors = []
    score = 0
    
    # Verificar longitud mínima
    if len(password) < config['min_length']:
        errors.append(f"Debe tener al menos {config['min_length']} caracteres")
    else:
        score += 20
    
    # Verificar mayúsculas
    if config['require_uppercase'] and not re.search(r'[A-Z]', password):
        errors.append("Debe contener al menos una letra mayúscula")
    else:
        score += 20
    
    # Verificar minúsculas
    if config['require_lowercase'] and not re.search(r'[a-z]', password):
        errors.append("Debe contener al menos una letra minúscula")
    else:
        score += 20
    
    # Verificar dígitos
    if config['require_digits'] and not re.search(r'\d', password):
        errors.append("Debe contener al menos un número")
    else:
        score += 20
    
    # Verificar caracteres especiales
    if config['require_special'] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Debe contener al menos un carácter especial")
    else:
        score += 20
    
    # Verificar patrones prohibidos
    for pattern in config.get('forbidden_patterns', []):
        if re.search(pattern, password, re.IGNORECASE):
            errors.append("Contiene un patrón no permitido")
            score -= 30
    
    # Penalizar patrones comunes
    common_patterns = [
        r'123', r'abc', r'qwerty', r'password', r'admin'
    ]
    for pattern in common_patterns:
        if re.search(pattern, password, re.IGNORECASE):
            score -= 10
    
    # Bonus por longitud extra
    if len(password) > 12:
        score += min(10, len(password) - 12)
    
    # Determinar fortaleza
    if score >= 80:
        strength = 'muy_fuerte'
    elif score >= 60:
        strength = 'fuerte'
    elif score >= 40:
        strength = 'media'
    elif score >= 20:
        strength = 'debil'
    else:
        strength = 'muy_debil'
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'score': max(0, score),
        'strength': strength
    }


def validate_email_format(email: str) -> Dict[str, Any]:
    """
    Validar formato de email usando email-validator.
    
    Args:
        email: Email a validar
        
    Returns:
        Diccionario con resultado de validación
    """
    try:
        # Validar formato
        valid = validate_email(email)
        
        # Verificar dominios sospechosos
        suspicious_domains = current_app.config.get('SUSPICIOUS_EMAIL_DOMAINS', [])
        domain = email.split('@')[1].lower()
        
        is_suspicious = domain in suspicious_domains
        
        return {
            'is_valid': True,
            'normalized_email': valid.email,
            'local_part': valid.local,
            'domain': valid.domain,
            'is_suspicious': is_suspicious
        }
        
    except EmailNotValidError as e:
        return {
            'is_valid': False,
            'error': str(e)
        }


def sanitize_input(input_data: str, allowed_tags: List[str] = None) -> str:
    """
    Sanitizar entrada del usuario para prevenir XSS.
    
    Args:
        input_data: Datos de entrada
        allowed_tags: Tags HTML permitidos
        
    Returns:
        Datos sanitizados
    """
    if not input_data:
        return ""
    
    # Tags permitidos por defecto (muy restrictivos)
    if allowed_tags is None:
        allowed_tags = ['b', 'i', 'u', 'strong', 'em']
    
    # Atributos permitidos
    allowed_attributes = {
        '*': ['class'],
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'width', 'height']
    }
    
    # Sanitizar usando bleach
    cleaned = bleach.clean(
        input_data,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )
    
    return cleaned


def validate_file_security(file_data: bytes, filename: str) -> Dict[str, Any]:
    """
    Validar seguridad de archivos subidos.
    
    Args:
        file_data: Contenido del archivo
        filename: Nombre del archivo
        
    Returns:
        Diccionario con resultado de validación
    """
    errors = []
    
    # Verificar nombre de archivo
    secure_name = secure_filename(filename)
    if not secure_name:
        errors.append("Nombre de archivo inválido")
    
    # Verificar extensión
    extension = secure_name.split('.')[-1].lower() if '.' in secure_name else ''
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    
    if extension not in allowed_extensions:
        errors.append(f"Extensión de archivo no permitida: .{extension}")
    
    # Verificar tamaño
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
    if len(file_data) > max_size:
        errors.append(f"Archivo demasiado grande: {len(file_data)} bytes")
    
    # Verificar contenido malicioso (básico)
    suspicious_patterns = [
        b'<script',
        b'javascript:',
        b'vbscript:',
        b'onload=',
        b'onerror='
    ]
    
    file_lower = file_data.lower()
    for pattern in suspicious_patterns:
        if pattern in file_lower:
            errors.append("Contenido potencialmente malicioso detectado")
            break
    
    # Verificar magic bytes para tipos comunes
    magic_bytes = {
        'pdf': b'%PDF',
        'png': b'\x89PNG',
        'jpg': b'\xff\xd8\xff',
        'gif': b'GIF8',
        'zip': b'PK\x03\x04'
    }
    
    detected_type = None
    for file_type, magic in magic_bytes.items():
        if file_data.startswith(magic):
            detected_type = file_type
            break
    
    # Verificar consistencia de extensión
    if detected_type and extension != detected_type:
        if not (extension in ['jpeg', 'jpg'] and detected_type == 'jpg'):
            errors.append(f"Extensión no coincide con contenido: .{extension} vs {detected_type}")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'secure_filename': secure_name,
        'detected_type': detected_type,
        'file_size': len(file_data)
    }


# ====================================
# JWT TOKEN MANAGEMENT
# ====================================

def generate_jwt_token(user_id: int, role: str, expires_in: int = 3600) -> str:
    """
    Generar token JWT para usuario.
    
    Args:
        user_id: ID del usuario
        role: Rol del usuario
        expires_in: Tiempo de expiración en segundos
        
    Returns:
        Token JWT
    """
    payload = {
        'user_id': user_id,
        'role': role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=expires_in),
        'jti': generate_secure_token(16)  # JWT ID único
    }
    
    secret = SecurityConfig.get_jwt_secret()
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    # Log generación de token
    security_logger.info(f"JWT token generated for user {user_id}")
    
    return token


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verificar y decodificar token JWT.
    
    Args:
        token: Token JWT
        
    Returns:
        Payload decodificado o None si es inválido
    """
    try:
        secret = SecurityConfig.get_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        
        # Verificar si el token está en blacklist
        jti = payload.get('jti')
        if jti and is_token_blacklisted(jti):
            security_logger.warning(f"Blacklisted token attempted: {jti}")
            return {'is_valid': False, 'error': 'Token revocado'}
        
        return {
            'is_valid': True,
            'payload': payload
        }
        
    except jwt.ExpiredSignatureError:
        return {'is_valid': False, 'error': 'Token expirado'}
    except jwt.InvalidTokenError as e:
        security_logger.warning(f"Invalid JWT token: {str(e)}")
        return {'is_valid': False, 'error': 'Token inválido'}


def blacklist_jwt_token(token: str) -> bool:
    """
    Añadir token JWT a la blacklist.
    
    Args:
        token: Token a revocar
        
    Returns:
        True si se añadió exitosamente
    """
    try:
        # Decodificar para obtener JTI
        payload = jwt.decode(token, SecurityConfig.get_jwt_secret(), algorithms=['HS256'])
        jti = payload.get('jti')
        exp = payload.get('exp')
        
        if jti:
            # Añadir a blacklist con expiración
            redis_client = get_redis_client()
            if redis_client:
                ttl = exp - datetime.utcnow().timestamp() if exp else 3600
                redis_client.setex(f"blacklist:{jti}", int(ttl), "1")
            else:
                # Fallback a memoria (no recomendado para producción)
                from app.extensions import jwt_blacklist
                jwt_blacklist.add(jti)
            
            security_logger.info(f"Token blacklisted: {jti}")
            return True
            
    except Exception as e:
        security_logger.error(f"Error blacklisting token: {str(e)}")
    
    return False


def is_token_blacklisted(jti: str) -> bool:
    """
    Verificar si un token está en blacklist.
    
    Args:
        jti: JWT ID
        
    Returns:
        True si está en blacklist
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            return redis_client.exists(f"blacklist:{jti}")
        else:
            # Fallback a memoria
            from app.extensions import jwt_blacklist
            return jti in jwt_blacklist
    except:
        return False


# ====================================
# RATE LIMITING
# ====================================

def check_rate_limit(key: str, limit: int, window: int) -> Dict[str, Any]:
    """
    Verificar límite de tasa para una clave.
    
    Args:
        key: Clave única (ej: user_id, ip_address)
        limit: Número máximo de requests
        window: Ventana de tiempo en segundos
        
    Returns:
        Información del rate limit
    """
    redis_client = get_redis_client()
    if not redis_client:
        # Sin Redis, permitir todas las requests
        return {'allowed': True, 'remaining': limit}
    
    try:
        # Usar sliding window con múltiples claves
        now = datetime.utcnow().timestamp()
        window_start = now - window
        
        # Limpiar requests antiguos
        redis_client.zremrangebyscore(f"rate_limit:{key}", 0, window_start)
        
        # Contar requests actuales
        current_count = redis_client.zcard(f"rate_limit:{key}")
        
        if current_count >= limit:
            # Calcular tiempo hasta reset
            oldest_request = redis_client.zrange(f"rate_limit:{key}", 0, 0, withscores=True)
            reset_time = oldest_request[0][1] + window if oldest_request else now + window
            
            return {
                'allowed': False,
                'remaining': 0,
                'reset_time': reset_time,
                'retry_after': int(reset_time - now)
            }
        
        # Registrar nueva request
        redis_client.zadd(f"rate_limit:{key}", {str(now): now})
        redis_client.expire(f"rate_limit:{key}", window)
        
        return {
            'allowed': True,
            'remaining': limit - current_count - 1,
            'reset_time': now + window
        }
        
    except Exception as e:
        security_logger.error(f"Error checking rate limit: {str(e)}")
        # En caso de error, permitir la request
        return {'allowed': True, 'remaining': limit}


def increment_rate_limit(key: str, window: int = 3600) -> int:
    """
    Incrementar contador de rate limit.
    
    Args:
        key: Clave única
        window: Ventana de tiempo
        
    Returns:
        Contador actual
    """
    redis_client = get_redis_client()
    if not redis_client:
        return 1
    
    try:
        pipe = redis_client.pipeline()
        pipe.incr(f"counter:{key}")
        pipe.expire(f"counter:{key}", window)
        results = pipe.execute()
        return results[0]
    except:
        return 1


def reset_rate_limit(key: str) -> bool:
    """
    Resetear rate limit para una clave.
    
    Args:
        key: Clave única
        
    Returns:
        True si se reseteó exitosamente
    """
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.delete(f"rate_limit:{key}", f"counter:{key}")
            return True
        except:
            pass
    return False


# ====================================
# AUDIT LOGGING
# ====================================

def log_security_event(event_type: str, details: Dict[str, Any] = None, 
                      user_id: Optional[int] = None, severity: str = 'INFO'):
    """
    Registrar evento de seguridad.
    
    Args:
        event_type: Tipo de evento
        details: Detalles adicionales
        user_id: ID del usuario involucrado
        severity: Severidad del evento
    """
    log_data = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': user_id or getattr(current_user, 'id', None),
        'ip_address': request.remote_addr if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None,
        'endpoint': request.endpoint if request else None,
        'details': details or {}
    }
    
    # Log según severidad
    if severity == 'CRITICAL':
        security_logger.critical(f"SECURITY_EVENT: {event_type}", extra=log_data)
    elif severity == 'ERROR':
        security_logger.error(f"SECURITY_EVENT: {event_type}", extra=log_data)
    elif severity == 'WARNING':
        security_logger.warning(f"SECURITY_EVENT: {event_type}", extra=log_data)
    else:
        security_logger.info(f"SECURITY_EVENT: {event_type}", extra=log_data)


def log_user_action(action: str, resource: str = None, resource_id: str = None,
                   details: Dict[str, Any] = None):
    """
    Registrar acción de usuario para auditoría.
    
    Args:
        action: Acción realizada
        resource: Recurso afectado
        resource_id: ID del recurso
        details: Detalles adicionales
    """
    log_data = {
        'action': action,
        'resource': resource,
        'resource_id': resource_id,
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': getattr(current_user, 'id', None),
        'user_email': getattr(current_user, 'email', None),
        'ip_address': request.remote_addr if request else None,
        'details': details or {}
    }
    
    # Log en logger específico de audit
    audit_logger = logging.getLogger('ecosistema.audit')
    audit_logger.info(f"USER_ACTION: {action}", extra=log_data)


# ====================================
# SESSION MANAGEMENT
# ====================================

def create_user_session(user_id: int, remember_me: bool = False) -> str:
    """
    Crear sesión de usuario segura.
    
    Args:
        user_id: ID del usuario
        remember_me: Si mantener sesión persistente
        
    Returns:
        ID de sesión
    """
    session_id = generate_secure_token(32)
    session_data = {
        'user_id': user_id,
        'created_at': datetime.utcnow().isoformat(),
        'ip_address': request.remote_addr if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None,
        'remember_me': remember_me
    }
    
    redis_client = get_redis_client()
    if redis_client:
        # TTL basado en remember_me
        ttl = 30 * 24 * 3600 if remember_me else 24 * 3600  # 30 días o 1 día
        redis_client.setex(f"session:{session_id}", ttl, 
                          encrypt_sensitive_data(str(session_data)))
    
    # También almacenar en Flask session
    session['session_id'] = session_id
    session.permanent = remember_me
    
    log_security_event('SESSION_CREATED', {'session_id': session_id[:8] + '...'}, user_id)
    
    return session_id


def validate_user_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Validar sesión de usuario.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        Datos de la sesión si es válida
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None
    
    try:
        encrypted_data = redis_client.get(f"session:{session_id}")
        if not encrypted_data:
            return None
        
        session_data = eval(decrypt_sensitive_data(encrypted_data))
        
        # Verificar IP si está configurado
        if current_app.config.get('SESSION_VALIDATE_IP', False):
            if session_data.get('ip_address') != request.remote_addr:
                log_security_event('SESSION_IP_MISMATCH', 
                                 {'session_id': session_id[:8] + '...',
                                  'original_ip': session_data.get('ip_address'),
                                  'current_ip': request.remote_addr},
                                 severity='WARNING')
                return None
        
        return session_data
        
    except Exception as e:
        security_logger.error(f"Error validating session: {str(e)}")
        return None


def invalidate_user_session(session_id: str) -> bool:
    """
    Invalidar sesión de usuario.
    
    Args:
        session_id: ID de la sesión
        
    Returns:
        True si se invalidó exitosamente
    """
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.delete(f"session:{session_id}")
            log_security_event('SESSION_INVALIDATED', 
                             {'session_id': session_id[:8] + '...'})
            return True
        except:
            pass
    
    # Limpiar Flask session
    session.pop('session_id', None)
    return False


def cleanup_expired_sessions() -> int:
    """
    Limpiar sesiones expiradas.
    
    Returns:
        Número de sesiones limpiadas
    """
    # Esta función normalmente se ejecutaría como tarea programada
    redis_client = get_redis_client()
    if not redis_client:
        return 0
    
    try:
        # Redis automáticamente expira las claves, pero podemos hacer limpieza adicional
        pattern = "session:*"
        keys = redis_client.keys(pattern)
        expired_count = 0
        
        for key in keys:
            ttl = redis_client.ttl(key)
            if ttl == -2:  # Clave expirada
                redis_client.delete(key)
                expired_count += 1
        
        if expired_count > 0:
            security_logger.info(f"Cleaned up {expired_count} expired sessions")
        
        return expired_count
        
    except Exception as e:
        security_logger.error(f"Error cleaning up sessions: {str(e)}")
        return 0


# ====================================
# UTILIDADES AUXILIARES
# ====================================

def get_redis_client():
    """Obtener cliente Redis si está disponible."""
    try:
        from app.extensions import redis_client
        return redis_client
    except:
        return None


def is_safe_url(target: str) -> bool:
    """
    Verificar si una URL es segura para redirección.
    
    Args:
        target: URL de destino
        
    Returns:
        True si es segura
    """
    if not target:
        return False
    
    try:
        parsed = urlparse(target)
        
        # Solo permitir URLs relativas o del mismo dominio
        if parsed.netloc:
            allowed_hosts = current_app.config.get('ALLOWED_REDIRECT_HOSTS', [])
            if parsed.netloc not in allowed_hosts:
                return False
        
        # Verificar esquemas permitidos
        if parsed.scheme and parsed.scheme not in ['http', 'https']:
            return False
        
        return True
        
    except Exception:
        return False


def generate_csrf_token() -> str:
    """Generar token CSRF."""
    if 'csrf_token' not in session:
        session['csrf_token'] = generate_secure_token(32)
    return session['csrf_token']


def validate_csrf_token(token: str) -> bool:
    """Validar token CSRF."""
    return token and session.get('csrf_token') == token


# ====================================
# DECORADORES DE SEGURIDAD
# ====================================

from functools import wraps

def require_csrf_token(f):
    """Decorador para requerir token CSRF válido."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
            if not validate_csrf_token(token):
                log_security_event('CSRF_TOKEN_INVALID', severity='WARNING')
                if request.is_json:
                    from flask import jsonify
                    return jsonify({'error': 'Invalid CSRF token'}), 403
                else:
                    from flask import abort
                    abort(403)
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(key_func=None, limit=60, window=3600, per_user=False):
    """
    Decorador para rate limiting.
    
    Args:
        key_func: Función para generar clave única
        limit: Límite de requests
        window: Ventana de tiempo en segundos
        per_user: Si aplicar límite por usuario
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generar clave para rate limiting
            if key_func:
                key = key_func()
            elif per_user:
                key = f"user_{getattr(current_user, 'id', 'anonymous')}"
            else:
                key = request.remote_addr or 'unknown'
            
            # Añadir prefijo de función
            rate_key = f"{f.__name__}:{key}"
            
            # Verificar rate limit
            result = check_rate_limit(rate_key, limit, window)
            
            if not result['allowed']:
                log_security_event('RATE_LIMIT_EXCEEDED', 
                                 {'function': f.__name__, 'key': key, 'limit': limit})
                
                if request.is_json:
                    from flask import jsonify
                    response = jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': result.get('retry_after', window)
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(result.get('retry_after', window))
                    return response
                else:
                    from flask import abort
                    abort(429)
            
            # Añadir headers de rate limit
            from flask import g
            g.rate_limit_remaining = result.get('remaining', 0)
            g.rate_limit_reset = result.get('reset_time', 0)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_api_key(f):
    """Decorador para requerir API key válida."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            log_security_event('API_KEY_MISSING', severity='WARNING')
            from flask import jsonify
            return jsonify({'error': 'API key required'}), 401
        
        # Validar API key (implementar según necesidades)
        if not validate_api_key(api_key):
            log_security_event('API_KEY_INVALID', {'api_key': api_key[:8] + '...'}, 
                             severity='WARNING')
            from flask import jsonify
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


def validate_api_key(api_key: str) -> bool:
    """
    Validar API key.
    
    Args:
        api_key: Clave API a validar
        
    Returns:
        True si es válida
    """
    # Implementar validación según el sistema usado
    # Ejemplo: buscar en base de datos, verificar firma, etc.
    
    # Para demo, verificar contra configuración
    valid_keys = current_app.config.get('VALID_API_KEYS', [])
    return api_key in valid_keys


def secure_headers(f):
    """Decorador para añadir headers de seguridad."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        
        # Añadir headers de seguridad si la respuesta es un objeto Response
        if hasattr(response, 'headers'):
            # Prevenir clickjacking
            response.headers['X-Frame-Options'] = 'DENY'
            
            # Prevenir MIME type sniffing
            response.headers['X-Content-Type-Options'] = 'nosniff'
            
            # XSS Protection
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # Referrer Policy
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Feature Policy
            response.headers['Permissions-Policy'] = (
                'geolocation=(), microphone=(), camera=()'
            )
        
        return response
    return decorated_function


# ====================================
# VALIDACIONES ESPECÍFICAS DEL DOMINIO
# ====================================

def validate_user_input(input_type: str, value: str) -> Dict[str, Any]:
    """
    Validar entrada de usuario según tipo específico.
    
    Args:
        input_type: Tipo de entrada (phone, tax_id, etc.)
        value: Valor a validar
        
    Returns:
        Resultado de validación
    """
    validators = {
        'phone_colombia': validate_colombia_phone,
        'tax_id_colombia': validate_colombia_tax_id,
        'company_name': validate_company_name,
        'project_name': validate_project_name,
        'url': validate_url
    }
    
    validator = validators.get(input_type)
    if not validator:
        return {'is_valid': False, 'error': f'Validator not found: {input_type}'}
    
    return validator(value)


def validate_colombia_phone(phone: str) -> Dict[str, Any]:
    """Validar número telefónico colombiano."""
    # Limpiar número
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Patrones válidos para Colombia
    patterns = [
        r'^\+57[13][0-9]{9},  # +57 + código área + número
        r'^[13][0-9]{9},       # Sin código país
        r'^3[0-9]{9}           # Celular
    ]
    
    for pattern in patterns:
        if re.match(pattern, clean_phone):
            return {
                'is_valid': True,
                'normalized_phone': clean_phone,
                'type': 'mobile' if clean_phone.startswith('3') else 'landline'
            }
    
    return {
        'is_valid': False,
        'error': 'Formato de teléfono colombiano inválido'
    }


def validate_colombia_tax_id(tax_id: str) -> Dict[str, Any]:
    """Validar NIT colombiano."""
    # Limpiar NIT
    clean_nit = re.sub(r'[^\d]', '', tax_id)
    
    if len(clean_nit) < 8 or len(clean_nit) > 15:
        return {'is_valid': False, 'error': 'Longitud de NIT inválida'}
    
    # Algoritmo de validación de NIT colombiano
    def calculate_check_digit(nit_digits):
        weights = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
        total = sum(int(digit) * weight for digit, weight in zip(nit_digits[::-1], weights))
        remainder = total % 11
        if remainder < 2:
            return remainder
        return 11 - remainder
    
    # Verificar dígito de control si está presente
    if len(clean_nit) > 8:
        main_digits = clean_nit[:-1]
        check_digit = int(clean_nit[-1])
        calculated_check = calculate_check_digit(main_digits)
        
        if check_digit != calculated_check:
            return {'is_valid': False, 'error': 'Dígito de verificación inválido'}
    
    return {
        'is_valid': True,
        'normalized_nit': clean_nit,
        'check_digit': calculate_check_digit(clean_nit[:-1]) if len(clean_nit) > 8 else None
    }


def validate_company_name(name: str) -> Dict[str, Any]:
    """Validar nombre de empresa."""
    if not name or len(name.strip()) < 2:
        return {'is_valid': False, 'error': 'Nombre muy corto'}
    
    if len(name) > 100:
        return {'is_valid': False, 'error': 'Nombre muy largo'}
    
    # Verificar caracteres permitidos
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\s\.\-&]+, name):
        return {'is_valid': False, 'error': 'Caracteres no permitidos en nombre'}
    
    return {
        'is_valid': True,
        'normalized_name': name.strip().title()
    }


def validate_project_name(name: str) -> Dict[str, Any]:
    """Validar nombre de proyecto."""
    if not name or len(name.strip()) < 3:
        return {'is_valid': False, 'error': 'Nombre de proyecto muy corto'}
    
    if len(name) > 100:
        return {'is_valid': False, 'error': 'Nombre de proyecto muy largo'}
    
    # Verificar caracteres permitidos
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\s\.\-_]+, name):
        return {'is_valid': False, 'error': 'Caracteres no permitidos en nombre de proyecto'}
    
    return {
        'is_valid': True,
        'normalized_name': name.strip()
    }


def validate_url(url: str) -> Dict[str, Any]:
    """Validar URL."""
    if not url:
        return {'is_valid': False, 'error': 'URL vacía'}
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            url = 'https://' + url
            parsed = urlparse(url)
        
        if parsed.scheme not in ['http', 'https']:
            return {'is_valid': False, 'error': 'Esquema de URL no permitido'}
        
        if not parsed.netloc:
            return {'is_valid': False, 'error': 'Dominio inválido'}
        
        return {
            'is_valid': True,
            'normalized_url': url,
            'domain': parsed.netloc
        }
        
    except Exception as e:
        return {'is_valid': False, 'error': f'URL inválida: {str(e)}'}


# ====================================
# UTILIDADES DE MONITOREO
# ====================================

def monitor_suspicious_activity():
    """Monitorear actividad sospechosa en tiempo real."""
    # Esta función se ejecutaría periódicamente
    
    try:
        redis_client = get_redis_client()
        if not redis_client:
            return
        
        # Verificar patrones sospechosos
        suspicious_patterns = [
            ('failed_logins', 'login_failed:*', 5),  # 5+ logins fallidos
            ('rapid_requests', 'rate_limit:*', 100),  # 100+ requests rápidos
            ('multiple_ips', 'session:*', None),      # Múltiples IPs por sesión
        ]
        
        alerts = []
        
        for pattern_name, redis_pattern, threshold in suspicious_patterns:
            keys = redis_client.keys(redis_pattern)
            
            if pattern_name == 'failed_logins':
                for key in keys:
                    count = int(redis_client.get(key) or 0)
                    if count >= threshold:
                        user_info = key.replace('login_failed:', '')
                        alerts.append({
                            'type': 'multiple_failed_logins',
                            'user': user_info,
                            'count': count,
                            'severity': 'HIGH'
                        })
            
            elif pattern_name == 'rapid_requests':
                for key in keys:
                    count = redis_client.zcard(key)
                    if count >= threshold:
                        alerts.append({
                            'type': 'rapid_requests',
                            'source': key.replace('rate_limit:', ''),
                            'count': count,
                            'severity': 'MEDIUM'
                        })
        
        # Procesar alertas
        for alert in alerts:
            log_security_event('SUSPICIOUS_ACTIVITY', alert, severity=alert['severity'])
            
            # Acciones automáticas según severidad
            if alert['severity'] == 'HIGH':
                # Bloquear temporalmente
                if alert['type'] == 'multiple_failed_logins':
                    block_user_temporarily(alert['user'])
        
        return alerts
        
    except Exception as e:
        security_logger.error(f"Error monitoring suspicious activity: {str(e)}")
        return []


def block_user_temporarily(identifier: str, duration: int = 900):
    """
    Bloquear usuario temporalmente.
    
    Args:
        identifier: Identificador del usuario (email, IP, etc.)
        duration: Duración del bloqueo en segundos
    """
    redis_client = get_redis_client()
    if redis_client:
        redis_client.setex(f"blocked:{identifier}", duration, "1")
        log_security_event('USER_BLOCKED_TEMPORARILY', 
                         {'identifier': identifier, 'duration': duration},
                         severity='WARNING')


def is_user_blocked(identifier: str) -> bool:
    """Verificar si un usuario está bloqueado."""
    redis_client = get_redis_client()
    if redis_client:
        return redis_client.exists(f"blocked:{identifier}")
    return False


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    # Configuración
    'SecurityConfig',
    
    # Encriptación y hashing
    'encrypt_sensitive_data',
    'decrypt_sensitive_data',
    'hash_password',
    'verify_password',
    'generate_secure_token',
    'generate_secure_password',
    'hash_data',
    
    # Validaciones
    'validate_password_strength',
    'validate_email_format',
    'sanitize_input',
    'validate_file_security',
    'validate_user_input',
    'validate_colombia_phone',
    'validate_colombia_tax_id',
    'validate_company_name',
    'validate_project_name',
    'validate_url',
    
    # JWT
    'generate_jwt_token',
    'verify_jwt_token',
    'blacklist_jwt_token',
    'is_token_blacklisted',
    
    # Rate limiting
    'check_rate_limit',
    'increment_rate_limit',
    'reset_rate_limit',
    
    # Audit logging
    'log_security_event',
    'log_user_action',
    
    # Session management
    'create_user_session',
    'validate_user_session',
    'invalidate_user_session',
    'cleanup_expired_sessions',
    
    # Utilidades
    'is_safe_url',
    'generate_csrf_token',
    'validate_csrf_token',
    'validate_api_key',
    
    # Decoradores
    'require_csrf_token',
    'rate_limit',
    'require_api_key',
    'secure_headers',
    
    # Monitoreo
    'monitor_suspicious_activity',
    'block_user_temporarily',
    'is_user_blocked'
]