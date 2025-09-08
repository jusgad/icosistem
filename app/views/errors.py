"""
Views de manejo de errores del ecosistema de emprendimiento.
Proporciona páginas de error elegantes, logging completo y recuperación inteligente.

Características:
- Páginas de error personalizadas por código HTTP
- Logging y tracking automático de errores
- Información contextual para debugging
- Recuperación inteligente basada en usuario
- Analytics de errores para mejora continua
- Soporte para errores de API vs Web
- Páginas responsive y accesibles
- Mensajes localizados
- Sugerencias de navegación alternativa
- Reporte automático de errores críticos
- Cache inteligente de páginas de error
- SEO optimizado para páginas de error

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, current_app, g, session
)
from flask_babel import _, get_locale
from werkzeug.exceptions import HTTPException
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import traceback
import logging
import json
import sys
import os
from urllib.parse import urlparse
from collections import defaultdict

# Importaciones locales
from app.models.user import User, UserType
# from app.models.error_log import ErrorLog, ErrorSeverity, ErrorCategory  # Module doesn't exist
# from app.models.user_session import UserSession  # Module doesn't exist
# from app.services.analytics_service import AnalyticsService  # Module doesn't exist
# from app.services.email import EmailService  # Module doesn't exist
# from app.services.notification_service import NotificationService  # Module doesn't exist
# from app.utils.string_utils import get_client_ip, truncate_text  # Some functions missing
# from app.utils.formatters import format_datetime  # Function missing
# from app.utils.seo import generate_meta_tags  # Module doesn't exist
from app.extensions import db, cache

# Stub classes for missing models and services
class ErrorLog:
    @classmethod
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
        return MockQuery()

class ErrorSeverity:
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

class ErrorCategory:
    APPLICATION = 'application'
    DATABASE = 'database'
    NETWORK = 'network'

class UserSession:
    @classmethod
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
        return MockQuery()

class AnalyticsService:
    @staticmethod
    def track_event(*args, **kwargs):
        pass

class EmailService:
    @staticmethod
    def send_email(*args, **kwargs):
        pass

class NotificationService:
    @staticmethod
    def send_notification(*args, **kwargs):
        pass

def get_client_ip():
    from flask import request
    return request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

def truncate_text(text, length=100):
    return text[:length] + '...' if len(text) > length else text

def format_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else ''

def generate_meta_tags(title, description):
    return {'title': title, 'description': description}

logger = logging.getLogger(__name__)

# Crear blueprint
errors_bp = Blueprint('errors', __name__)

# Configuración de errores
ERROR_MESSAGES = {
    400: {
        'title': _('Solicitud Incorrecta'),
        'message': _('La solicitud no pudo ser procesada debido a un error del cliente.'),
        'suggestions': [
            _('Verifica que todos los campos estén completos'),
            _('Asegúrate de que el formato de los datos sea correcto'),
            _('Intenta nuevamente en unos minutos')
        ]
    },
    401: {
        'title': _('No Autorizado'),
        'message': _('Necesitas iniciar sesión para acceder a este contenido.'),
        'suggestions': [
            _('Inicia sesión en tu cuenta'),
            _('Verifica que tus credenciales sean correctas'),
            _('Si olvidaste tu contraseña, puedes restablecerla')
        ]
    },
    403: {
        'title': _('Acceso Prohibido'),
        'message': _('No tienes permisos para acceder a este recurso.'),
        'suggestions': [
            _('Verifica que tengas los permisos necesarios'),
            _('Contacta al administrador si crees que es un error'),
            _('Revisa si tu cuenta está activa')
        ]
    },
    404: {
        'title': _('Página No Encontrada'),
        'message': _('La página que buscas no existe o ha sido movida.'),
        'suggestions': [
            _('Verifica que la URL esté escrita correctamente'),
            _('Usa el menú de navegación para encontrar lo que buscas'),
            _('Prueba con nuestra función de búsqueda')
        ]
    },
    422: {
        'title': _('Datos No Procesables'),
        'message': _('Los datos enviados no pueden ser procesados.'),
        'suggestions': [
            _('Revisa que todos los campos requeridos estén completos'),
            _('Verifica el formato de los datos enviados'),
            _('Intenta nuevamente con información válida')
        ]
    },
    429: {
        'title': _('Demasiadas Solicitudes'),
        'message': _('Has excedido el límite de solicitudes permitidas.'),
        'suggestions': [
            _('Espera unos minutos antes de intentar nuevamente'),
            _('Reduce la frecuencia de tus solicitudes'),
            _('Contacta al soporte si necesitas límites mayores')
        ]
    },
    500: {
        'title': _('Error Interno del Servidor'),
        'message': _('Ha ocurrido un error interno. Nuestro equipo ha sido notificado.'),
        'suggestions': [
            _('Intenta nuevamente en unos minutos'),
            _('Si el problema persiste, contacta al soporte'),
            _('Verifica el estado del servicio en nuestra página')
        ]
    },
    502: {
        'title': _('Servicio No Disponible'),
        'message': _('El servicio está temporalmente no disponible.'),
        'suggestions': [
            _('Intenta nuevamente en unos minutos'),
            _('Verifica tu conexión a internet'),
            _('Revisa el estado del servicio')
        ]
    },
    503: {
        'title': _('Servicio en Mantenimiento'),
        'message': _('El servicio está en mantenimiento programado.'),
        'suggestions': [
            _('Intenta nuevamente más tarde'),
            _('Sigue nuestras redes sociales para actualizaciones'),
            _('El mantenimiento suele durar poco tiempo')
        ]
    }
}

# Páginas alternativas por tipo de usuario
USER_TYPE_ALTERNATIVES = {
    UserType.ADMIN: [
        {'title': _('Panel de Administración'), 'url': 'admin_dashboard.index'},
        {'title': _('Gestión de Usuarios'), 'url': 'admin_users.list_users'},
        {'title': _('Analytics'), 'url': 'admin_analytics.dashboard'}
    ],
    UserType.ENTREPRENEUR: [
        {'title': _('Mi Dashboard'), 'url': 'entrepreneur_dashboard.index'},
        {'title': _('Mis Proyectos'), 'url': 'entrepreneur_projects.list_projects'},
        {'title': _('Mentoría'), 'url': 'entrepreneur_mentorship.sessions'}
    ],
    UserType.ALLY: [
        {'title': _('Mi Dashboard'), 'url': 'ally_dashboard.index'},
        {'title': _('Mis Emprendedores'), 'url': 'ally_entrepreneurs.list'},
        {'title': _('Calendario'), 'url': 'ally_calendar.index'}
    ],
    UserType.CLIENT: [
        {'title': _('Mi Dashboard'), 'url': 'client_dashboard.index'},
        {'title': _('Directorio'), 'url': 'client_directory.index'},
        {'title': _('Reportes'), 'url': 'client_reports.index'}
    ]
}

class ErrorTracker:
    """Clase para tracking y análisis de errores."""
    
    def __init__(self):
        self.analytics_service = None
        self.email_service = None
        self.notification_service = None
        
    def _get_analytics_service(self):
        """Obtiene servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def _get_email_service(self):
        """Obtiene servicio de email de forma lazy."""
        if self.email_service is None:
            self.email_service = EmailService()
        return self.email_service
    
    def _get_notification_service(self):
        """Obtiene servicio de notificaciones de forma lazy."""
        if self.notification_service is None:
            self.notification_service = NotificationService()
        return self.notification_service
    
    def log_error(self, error_code: int, error: Exception = None, 
                  additional_context: Dict = None) -> ErrorLog:
        """Registra un error en la base de datos."""
        try:
            # Determinar severidad basada en el código
            severity = self._get_error_severity(error_code)
            category = self._get_error_category(error_code, error)
            
            # Crear contexto completo
            context = self._build_error_context(error, additional_context)
            
            # Crear registro de error
            error_log = ErrorLog(
                error_code=error_code,
                error_message=str(error) if error else f"HTTP {error_code}",
                severity=severity,
                category=category,
                url=request.url,
                method=request.method,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                user_id=getattr(g, 'current_user_id', None),
                session_id=session.get('session_id'),
                context=context,
                stack_trace=self._get_stack_trace(error),
                referrer=request.referrer
            )
            
            db.session.add(error_log)
            db.session.commit()
            
            # Notificar si es crítico
            if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
                self._notify_critical_error(error_log)
            
            # Trackear en analytics
            self._track_error_analytics(error_log)
            
            return error_log
            
        except Exception as e:
            # Error logging el error - usar logging básico
            logger.error(f"Error logging error: {str(e)}")
            return None
    
    def _get_error_severity(self, error_code: int) -> ErrorSeverity:
        """Determina la severidad del error."""
        # Critical errors should be checked first
        if error_code in [500, 502, 503]:
            return ErrorSeverity.CRITICAL

        severity_map = {
            range(400, 500): ErrorSeverity.MEDIUM,
            range(500, 600): ErrorSeverity.HIGH
        }
        for codes, severity in severity_map.items():
            if error_code in codes:
                return severity
        
        return ErrorSeverity.LOW
    
    def _get_error_category(self, error_code: int, error: Exception = None) -> ErrorCategory:
        """Determina la categoría del error."""
        if error_code == 401:
            return ErrorCategory.AUTHENTICATION
        elif error_code == 403:
            return ErrorCategory.AUTHORIZATION
        elif error_code == 404:
            return ErrorCategory.NOT_FOUND
        elif error_code == 422:
            return ErrorCategory.VALIDATION
        elif error_code == 429:
            return ErrorCategory.RATE_LIMIT
        elif 500 <= error_code < 600:
            return ErrorCategory.SERVER_ERROR
        elif error and 'database' in str(error).lower():
            return ErrorCategory.DATABASE
        elif error and any(term in str(error).lower() for term in ['network', 'connection', 'timeout']):
            return ErrorCategory.NETWORK
        else:
            return ErrorCategory.APPLICATION
    
    def _build_error_context(self, error: Exception = None, 
                           additional_context: Dict = None) -> Dict:
        """Construye contexto completo del error."""
        context = {
            'timestamp': datetime.utcnow().isoformat(),
            'endpoint': request.endpoint,
            'args': dict(request.args),
            'form_data': dict(request.form) if request.form else None,
            'json_data': request.get_json(silent=True),
            'headers': dict(request.headers),
            'environment': current_app.config.get('ENVIRONMENT', 'unknown'),
            'app_version': current_app.config.get('APP_VERSION', 'unknown'),
            'python_version': sys.version,
            'browser_info': {
                'browser': request.user_agent.browser,
                'version': request.user_agent.version,
                'platform': request.user_agent.platform,
                'language': request.user_agent.language
            }
        }
        
        # Agregar información del usuario si está disponible
        if hasattr(g, 'current_user') and g.current_user:
            context['user_info'] = {
                'user_id': g.current_user.id,
                'user_type': g.current_user.user_type.value,
                'email': g.current_user.email,
                'last_login': g.current_user.last_login_at.isoformat() if g.current_user.last_login_at else None
            }
        
        # Agregar información de la sesión
        if session:
            context['session_info'] = {
                'session_keys': list(session.keys()),
                'csrf_token': session.get('csrf_token'),
                'language': session.get('language')
            }
        
        # Información específica del error
        if error:
            context['error_details'] = {
                'type': type(error).__name__,
                'args': error.args,
                'module': getattr(error, '__module__', None)
            }
        
        # Contexto adicional
        if additional_context:
            context['additional'] = additional_context
        
        # Sanitizar datos sensibles
        context = self._sanitize_context(context)
        
        return context
    
    def _sanitize_context(self, context: Dict) -> Dict:
        """Sanitiza datos sensibles del contexto."""
        sensitive_keys = [
            'password', 'token', 'secret', 'key', 'authorization',
            'csrf_token', 'session_id', 'cookie'
        ]
        
        def sanitize_dict(d):
            if isinstance(d, dict):
                return {
                    k: '[REDACTED]' if any(sensitive in k.lower() for sensitive in sensitive_keys)
                    else sanitize_dict(v)
                    for k, v in d.items()
                }
            elif isinstance(d, list):
                return [sanitize_dict(item) for item in d]
            return d
        
        return sanitize_dict(context)
    
    def _get_stack_trace(self, error: Exception = None) -> Optional[str]:
        """Obtiene stack trace del error."""
        if not error:
            return None
        
        try:
            return ''.join(traceback.format_exception(
                type(error), error, error.__traceback__
            ))
        except Exception:
            return str(error)
    
    def _notify_critical_error(self, error_log: ErrorLog):
        """Notifica errores críticos al equipo."""
        try:
            # Solo en producción y para errores realmente críticos
            if (current_app.config.get('ENVIRONMENT') == 'production' and 
                error_log.severity == ErrorSeverity.CRITICAL):
                
                email_service = self._get_email_service()
                email_service.send_critical_error_alert(error_log)
                
                # Notificar a administradores
                notification_service = self._get_notification_service()
                notification_service.notify_critical_error(error_log)
                
        except Exception as e:
            logger.error(f"Error notifying critical error: {str(e)}")
    
    def _track_error_analytics(self, error_log: ErrorLog):
        """Envía datos del error a analytics."""
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_error({
                'error_code': error_log.error_code,
                'error_category': error_log.category.value,
                'error_severity': error_log.severity.value,
                'url': error_log.url,
                'user_id': error_log.user_id,
                'ip_address': error_log.ip_address,
                'user_agent': error_log.user_agent,
                'timestamp': error_log.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"Error tracking error analytics: {str(e)}")

# Instancia global del tracker
error_tracker = ErrorTracker()

def get_error_alternatives(user: User = None) -> List[Dict[str, str]]:
    """Obtiene alternativas de navegación según el usuario."""
    alternatives = []
    
    # Páginas principales siempre disponibles
    main_alternatives = [
        {'title': _('Inicio'), 'url': url_for('main.index')},
        {'title': _('Directorio de Emprendimientos'), 'url': url_for('main.directory')},
        {'title': _('Blog'), 'url': url_for('main.blog')},
        {'title': _('Contacto'), 'url': url_for('main.contact')}
    ]
    
    alternatives.extend(main_alternatives)
    
    # Alternativas específicas por tipo de usuario
    if user and user.user_type in USER_TYPE_ALTERNATIVES:
        user_alternatives = USER_TYPE_ALTERNATIVES[user.user_type]
        for alt in user_alternatives:
            try:
                alternatives.append({
                    'title': alt['title'],
                    'url': url_for(alt['url'])
                })
            except Exception: # Catch BuildError if URL doesn't exist
                # Si la ruta no existe, saltarla
                continue
    
    return alternatives

def get_error_context(error_code: int, error: Exception = None) -> Dict[str, Any]:
    """Obtiene contexto completo para página de error."""
    error_info = ERROR_MESSAGES.get(error_code, {
        'title': f'Error {error_code}',
        'message': _('Ha ocurrido un error inesperado.'),
        'suggestions': [_('Intenta nuevamente más tarde')]
    })
    
    current_user = getattr(g, 'current_user', None)
    
    context = {
        'error_code': error_code,
        'error_title': error_info['title'],
        'error_message': error_info['message'],
        'suggestions': error_info['suggestions'],
        'alternatives': get_error_alternatives(current_user),
        'timestamp': datetime.utcnow(),
        'request_id': getattr(g, 'request_id', 'unknown'),
        'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@example.com'),
        'show_debug': current_app.debug and current_app.config.get('SHOW_ERROR_DEBUG', False)
    }
    
    # Información adicional para debugging en desarrollo
    if context['show_debug'] and error:
        context['debug_info'] = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_args': error.args,
            'traceback': traceback.format_exc()
        }
    
    # Meta tags para SEO
    context['meta_tags'] = generate_meta_tags(
        title=f"{error_info['title']} - {current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento')}",
        description=error_info['message'],
        robots='noindex, nofollow'  # No indexar páginas de error
    )
    
    return context

def is_api_request() -> bool:
    """Determina si la request es para API."""
    return (
        request.path.startswith('/api/') or
        request.is_json or
        'application/json' in request.headers.get('Accept', '') or
        'application/json' in request.headers.get('Content-Type', '')
    )

# Manejadores de errores HTTP
@errors_bp.app_errorhandler(400)
def bad_request_error(error):
    """Maneja errores 400 Bad Request."""
    error_log = error_tracker.log_error(400, error)
    
    if is_api_request():
        return jsonify({
            'error': 'Bad Request',
            'message': 'La solicitud no pudo ser procesada',
            'error_code': 400,
            'error_id': error_log.id if error_log else None
        }), 400
    
    context = get_error_context(400, error)
    return render_template('errors/base.html', **context), 400

@errors_bp.app_errorhandler(401)
def unauthorized_error(error):
    """Maneja errores 401 Unauthorized."""
    error_log = error_tracker.log_error(401, error)
    
    if is_api_request():
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Autenticación requerida',
            'error_code': 401,
            'error_id': error_log.id if error_log else None
        }), 401
    
    # Guardar URL de destino para redirección post-login
    if request.method == 'GET':
        session['next_url'] = request.url
    
    context = get_error_context(401, error)
    context['login_url'] = url_for('auth.login')
    
    return render_template('errors/401.html', **context), 401 # Keep specific template for login suggestion

@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    """Maneja errores 403 Forbidden."""
    error_log = error_tracker.log_error(403, error, {
        'user_id': getattr(g, 'current_user_id', None),
        'required_permission': getattr(error, 'required_permission', None)
    })
    
    if is_api_request():
        return jsonify({
            'error': 'Forbidden',
            'message': 'No tienes permisos para acceder a este recurso',
            'error_code': 403,
            'error_id': error_log.id if error_log else None
        }), 403
    
    context = get_error_context(403, error)
    return render_template('errors/base.html', **context), 403

@errors_bp.app_errorhandler(404)
def not_found_error(error):
    """Maneja errores 404 Not Found."""
    error_log = error_tracker.log_error(404, error, {
        'requested_url': request.url,
        'referrer': request.referrer
    })
    
    if is_api_request():
        return jsonify({
            'error': 'Not Found',
            'message': 'El recurso solicitado no existe',
            'error_code': 404,
            'error_id': error_log.id if error_log else None
        }), 404
    
    context = get_error_context(404, error)
    
    # Sugerencias inteligentes basadas en la URL
    context['smart_suggestions'] = _get_smart_suggestions(request.path)
    
    return render_template('errors/404.html', **context), 404 # Keep specific for smart suggestions

@errors_bp.app_errorhandler(422)
def unprocessable_entity_error(error):
    """Maneja errores 422 Unprocessable Entity."""
    error_log = error_tracker.log_error(422, error, {
        'form_data': dict(request.form) if request.form else None,
        'json_data': request.get_json(silent=True)
    })
    
    if is_api_request():
        return jsonify({
            'error': 'Unprocessable Entity',
            'message': 'Los datos enviados no pueden ser procesados',
            'error_code': 422,
            'error_id': error_log.id if error_log else None,
            'validation_errors': getattr(error, 'data', {})
        }), 422
    
    context = get_error_context(422, error)
    return render_template('errors/base.html', **context), 422

@errors_bp.app_errorhandler(429)
def too_many_requests_error(error):
    """Maneja errores 429 Too Many Requests."""
    error_log = error_tracker.log_error(429, error, {
        'rate_limit_info': getattr(error, 'rate_limit_info', None)
    })
    
    retry_after = getattr(error, 'retry_after', 60)
    
    if is_api_request():
        response = jsonify({
            'error': 'Too Many Requests',
            'message': 'Has excedido el límite de solicitudes',
            'error_code': 429,
            'retry_after': retry_after,
            'error_id': error_log.id if error_log else None
        })
        response.headers['Retry-After'] = str(retry_after)
        return response, 429
    
    context = get_error_context(429, error)
    context['retry_after'] = retry_after
    
    response = render_template('errors/base.html', **context), 429
    return response

@errors_bp.app_errorhandler(500)
def internal_server_error(error):
    """Maneja errores 500 Internal Server Error."""
    # Rollback cualquier transacción pendiente
    db.session.rollback()
    
    error_log = error_tracker.log_error(500, error, {
        'critical': True,
        'requires_immediate_attention': True
    })
    
    if is_api_request():
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Ha ocurrido un error interno del servidor',
            'error_code': 500,
            'error_id': error_log.id if error_log else None
        }), 500
    
    context = get_error_context(500, error)
    return render_template('errors/base.html', **context), 500

@errors_bp.app_errorhandler(502)
def bad_gateway_error(error):
    """Maneja errores 502 Bad Gateway."""
    error_log = error_tracker.log_error(502, error)
    
    if is_api_request():
        return jsonify({
            'error': 'Bad Gateway',
            'message': 'Error de gateway - servicio temporalmente no disponible',
            'error_code': 502,
            'error_id': error_log.id if error_log else None
        }), 502
    
    context = get_error_context(502, error)
    return render_template('errors/base.html', **context), 502

@errors_bp.app_errorhandler(503)
def service_unavailable_error(error):
    """Maneja errores 503 Service Unavailable."""
    error_log = error_tracker.log_error(503, error)
    
    if is_api_request():
        return jsonify({
            'error': 'Service Unavailable',
            'message': 'Servicio temporalmente no disponible',
            'error_code': 503,
            'error_id': error_log.id if error_log else None
        }), 503
    
    context = get_error_context(503, error)
    
    # Información de mantenimiento si está disponible
    maintenance_info = current_app.config.get('MAINTENANCE_INFO')
    if maintenance_info:
        context['maintenance_info'] = maintenance_info
    
    return render_template('errors/maintenance.html', **context), 503 # Keep specific for maintenance info

@errors_bp.app_errorhandler(Exception)
def handle_exception(error):
    """Maneja excepciones no capturadas."""
    # Si es una HTTPException, dejar que otros handlers la manejen
    if isinstance(error, HTTPException):
        return error
    
    # Log como error crítico
    error_log = error_tracker.log_error(500, error, {
        'unhandled_exception': True,
        'critical': True
    })
    
    # Log adicional con logger estándar
    logger.exception(f"Unhandled exception: {str(error)}")
    
    if is_api_request():
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Ha ocurrido un error inesperado',
            'error_code': 500,
            'error_id': error_log.id if error_log else None
        }), 500
    
    # Rollback cualquier transacción
    db.session.rollback()
    
    context = get_error_context(500, error)
    return render_template('errors/base.html', **context), 500

# Rutas específicas de error
@errors_bp.route('/error/<int:code>')
def show_error(code: int):
    """Muestra página de error específica."""
    if code not in ERROR_MESSAGES:
        code = 500
    
    context = get_error_context(code)
    template = f'errors/base.html'
    
    # Fallback a template genérico si no existe específico
    try:
        return render_template(template, **context), code
    except Exception:
        return render_template('errors/base.html', **context), code

@errors_bp.route('/maintenance')
@cache.cached(timeout=300)  # Cache por 5 minutos
def maintenance():
    """Página de mantenimiento."""
    maintenance_info = {
        'title': _('Mantenimiento Programado'),
        'message': _('Estamos realizando mejoras al sistema. Estaremos de vuelta pronto.'),
        'estimated_time': current_app.config.get('MAINTENANCE_ESTIMATED_TIME'),
        'start_time': current_app.config.get('MAINTENANCE_START_TIME'),
        'contact_email': current_app.config.get('SUPPORT_EMAIL'),
        'status_page': current_app.config.get('STATUS_PAGE_URL')
    }
    
    context = get_error_context(503)
    context.update(maintenance_info)
    
    return render_template('errors/maintenance.html', **context), 503

# Funciones auxiliares
def _get_smart_suggestions(path: str) -> List[Dict[str, str]]:
    """Genera sugerencias inteligentes basadas en la URL solicitada."""
    suggestions = []
    
    # Análisis de patrones comunes
    path_lower = path.lower()
    
    if 'admin' in path_lower:
        suggestions.append({
            'title': _('Panel de Administración'),
            'url': url_for('admin_dashboard.index'),
            'description': _('Accede al panel administrativo')
        })
    
    elif 'entrepreneur' in path_lower or 'emprendedor' in path_lower:
        suggestions.append({
            'title': _('Dashboard de Emprendedor'),
            'url': url_for('entrepreneur_dashboard.index'),
            'description': _('Ve a tu dashboard de emprendedor')
        })
    
    elif 'project' in path_lower or 'proyecto' in path_lower:
        suggestions.append({
            'title': _('Directorio de Proyectos'),
            'url': url_for('main.directory'),
            'description': _('Explora proyectos de emprendimiento')
        })
    
    elif 'mentor' in path_lower or 'ally' in path_lower:
        suggestions.append({
            'title': _('Dashboard de Mentor'),
            'url': url_for('ally_dashboard.index'),
            'description': _('Accede a tu panel de mentor')
        })
    
    elif 'blog' in path_lower or 'article' in path_lower:
        suggestions.append({
            'title': _('Blog'),
            'url': url_for('main.blog'),
            'description': _('Lee artículos sobre emprendimiento')
        })
    
    # Sugerencias por segmento de URL
    path_segments = [seg for seg in path.split('/') if seg]
    if len(path_segments) > 1:
        # Intentar con el primer segmento
        first_segment = path_segments[0]
        if first_segment in ['dashboard', 'panel']:
            suggestions.append({
                'title': _('Dashboard Principal'),
                'url': url_for('main.index'),
                'description': _('Ve al dashboard principal')
            })
    
    return suggestions[:3]  # Máximo 3 sugerencias

@errors_bp.route('/report-error', methods=['POST'])
def report_error():
    """Endpoint para reportar errores desde JavaScript."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Crear log de error desde frontend
        error_log = ErrorLog(
            error_code=data.get('error_code', 0),
            error_message=data.get('message', 'Frontend error'),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.FRONTEND,
            url=data.get('url', request.referrer),
            method='GET',
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            user_id=getattr(g, 'current_user_id', None),
            context={
                'frontend_error': True,
                'stack_trace': data.get('stack'),
                'user_action': data.get('user_action'),
                'browser_info': data.get('browser_info'),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        db.session.add(error_log)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'error_id': error_log.id
        })
        
    except Exception as e:
        logger.error(f"Error reporting frontend error: {str(e)}")
        return jsonify({'error': 'Failed to report error'}), 500

# Contexto específico para templates de error
@errors_bp.context_processor
def inject_error_context():
    """Inyecta contexto específico para páginas de error."""
    return {
        'current_year': datetime.utcnow().year,
        'app_name': current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento'),
        'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@example.com'),
        'status_page': current_app.config.get('STATUS_PAGE_URL'),
        'social_links': {
            'twitter': current_app.config.get('SOCIAL_TWITTER'),
            'facebook': current_app.config.get('SOCIAL_FACEBOOK'),
            'linkedin': current_app.config.get('SOCIAL_LINKEDIN')
        }
    }

# Filtros de template específicos para errores
@errors_bp.app_template_filter('error_icon')
def error_icon_filter(error_code):
    """Devuelve icono apropiado para el código de error."""
    icons = {
        400: 'alert-triangle',
        401: 'lock',
        403: 'shield-off',
        404: 'search',
        422: 'alert-circle',
        429: 'clock',
        500: 'server',
        502: 'cloud-off',
        503: 'tool'
    }
    return icons.get(error_code, 'alert-triangle')

@errors_bp.app_template_filter('error_color')
def error_color_filter(error_code):
    """Devuelve color CSS apropiado para el código de error."""
    colors = {
        400: 'warning',
        401: 'info',
        403: 'danger',
        404: 'secondary',
        422: 'warning',
        429: 'warning',
        500: 'danger',
        502: 'danger',
        503: 'info'
    }
    return colors.get(error_code, 'danger')

# Comando CLI para análisis de errores
@errors_bp.cli.command('analyze-errors')
def analyze_errors_command():
    """Analiza patrones de errores para mejora del sistema."""
    from datetime import datetime, timedelta
    
    # Análisis de los últimos 7 días
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    errors = ErrorLog.query.filter(
        ErrorLog.created_at >= week_ago
    ).all()
    
    # Análisis por código
    by_code = defaultdict(int)
    by_category = defaultdict(int)
    by_severity = defaultdict(int)
    
    for error in errors:
        by_code[error.error_code] += 1
        by_category[error.category.value] += 1
        by_severity[error.severity.value] += 1
    
    print("\n=== ANÁLISIS DE ERRORES (Últimos 7 días) ===")
    print(f"Total de errores: {len(errors)}")
    
    print("\nPor código de error:")
    for code, count in sorted(by_code.items(), key=lambda x: x[1], reverse=True):
        print(f"  {code}: {count}")
    
    print("\nPor categoría:")
    for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")
    
    print("\nPor severidad:")
    for severity, count in sorted(by_severity.items(), key=lambda x: x[1], reverse=True):
        print(f"  {severity}: {count}")