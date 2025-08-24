"""
Excepciones personalizadas para el ecosistema de emprendimiento.
Este módulo define todas las excepciones específicas del dominio de negocio.
"""

import logging
from datetime import datetime
from flask import jsonify, render_template, request, current_app
from werkzeug.exceptions import HTTPException


# ====================================
# EXCEPCIONES BASE
# ====================================

class EcosistemaException(Exception):
    """
    Excepción base para todas las excepciones del ecosistema.
    Proporciona funcionalidad común para logging y manejo de errores.
    """
    
    def __init__(self, message="Error en el ecosistema", error_code=None, 
                 details=None, user_message=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.user_message = user_message or message
        self.timestamp = datetime.utcnow()

class DuplicateUserError(EcosistemaException):
    """Exception raised when attempting to create a duplicate user."""
    
    def __init__(self, email, message=None):
        self.email = email
        message = message or f"User with email {email} already exists"
        super().__init__(message, error_code="DUPLICATE_USER")

class UserNotFoundError(EcosistemaException):
    """Exception raised when user is not found."""
    
    def __init__(self, user_id=None, email=None):
        self.user_id = user_id
        self.email = email
        if email:
            message = f"User with email {email} not found"
        elif user_id:
            message = f"User with ID {user_id} not found"
        else:
            message = "User not found"
        super().__init__(message, error_code="USER_NOT_FOUND")
        
        # Log automático del error
        self._log_error()
    
    def _log_error(self):
        """Log automático del error con contexto."""
        logger = logging.getLogger('ecosistema.exceptions')
        logger.error(
            f"{self.error_code}: {self.message}",
            extra={
                'error_code': self.error_code,
                'details': self.details,
                'timestamp': self.timestamp.isoformat(),
                'user_id': getattr(request, 'user_id', None) if request else None,
                'endpoint': request.endpoint if request else None,
                'ip_address': request.remote_addr if request else None
            }
        )
    
    def to_dict(self):
        """Convertir excepción a diccionario para APIs."""
        return {
            'error': True,
            'error_code': self.error_code,
            'message': self.user_message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }
    
    def __str__(self):
        return f"{self.error_code}: {self.message}"


class ValidationError(EcosistemaException):
    """Error de validación de datos."""
    
    def __init__(self, message="Error de validación", field=None, value=None, **kwargs):
        self.field = field
        self.value = value
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        
        super().__init__(
            message=message,
            error_code='VALIDATION_ERROR',
            details=details,
            user_message=kwargs.get('user_message', "Los datos proporcionados no son válidos"),
            **kwargs
        )


class BusinessLogicError(EcosistemaException):
    """Error de lógica de negocio."""
    
    def __init__(self, message="Error de lógica de negocio", **kwargs):
        super().__init__(
            message=message,
            error_code='BUSINESS_LOGIC_ERROR',
            user_message=kwargs.get('user_message', "Operación no permitida por reglas de negocio"),
            **kwargs
        )


class AuthenticationError(EcosistemaException):
    """Error de autenticación."""
    
    def __init__(self, message="Error de autenticación", **kwargs):
        super().__init__(
            message=message,
            error_code='AUTHENTICATION_ERROR',
            user_message=kwargs.get('user_message', "Credenciales inválidas"),
            **kwargs
        )


class AuthorizationError(EcosistemaException):
    """Error de autorización/permisos."""
    
    def __init__(self, message="Sin permisos suficientes", required_permission=None, **kwargs):
        details = kwargs.get('details', {})
        if required_permission:
            details['required_permission'] = required_permission
        
        super().__init__(
            message=message,
            error_code='AUTHORIZATION_ERROR',
            details=details,
            user_message=kwargs.get('user_message', "No tienes permisos para realizar esta acción"),
            **kwargs
        )


# ====================================
# EXCEPCIONES DE USUARIOS
# ====================================

class UserNotFoundError(EcosistemaException):
    """Usuario no encontrado."""
    
    def __init__(self, user_id=None, email=None, **kwargs):
        identifier = user_id or email or "unknown"
        details = {'identifier': identifier}
        
        super().__init__(
            message=f"Usuario no encontrado: {identifier}",
            error_code='USER_NOT_FOUND',
            details=details,
            user_message="Usuario no encontrado",
            **kwargs
        )


class UserAlreadyExistsError(EcosistemaException):
    """Usuario ya existe."""
    
    def __init__(self, email=None, **kwargs):
        details = {'email': email} if email else {}
        
        super().__init__(
            message=f"Usuario ya existe: {email or 'unknown'}",
            error_code='USER_ALREADY_EXISTS',
            details=details,
            user_message="Ya existe un usuario con este email",
            **kwargs
        )


class UserInactiveError(EcosistemaException):
    """Usuario inactivo."""
    
    def __init__(self, user_id=None, **kwargs):
        details = {'user_id': user_id} if user_id else {}
        
        super().__init__(
            message=f"Usuario inactivo: {user_id or 'unknown'}",
            error_code='USER_INACTIVE',
            details=details,
            user_message="Tu cuenta está desactivada. Contacta al administrador",
            **kwargs
        )


class InvalidCredentialsError(AuthenticationError):
    """Credenciales inválidas."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="Credenciales inválidas",
            error_code='INVALID_CREDENTIALS',
            user_message="Email o contraseña incorrectos",
            **kwargs
        )


class EmailNotVerifiedError(AuthenticationError):
    """Email no verificado."""
    
    def __init__(self, email=None, **kwargs):
        details = {'email': email} if email else {}
        
        super().__init__(
            message=f"Email no verificado: {email or 'unknown'}",
            error_code='EMAIL_NOT_VERIFIED',
            details=details,
            user_message="Debes verificar tu email antes de continuar",
            **kwargs
        )


class PasswordTooWeakError(ValidationError):
    """Contraseña demasiado débil."""
    
    def __init__(self, requirements=None, **kwargs):
        details = {'requirements': requirements} if requirements else {}
        
        super().__init__(
            message="Contraseña demasiado débil",
            error_code='PASSWORD_TOO_WEAK',
            details=details,
            user_message="La contraseña no cumple con los requisitos de seguridad",
            **kwargs
        )


class TooManyLoginAttemptsError(AuthenticationError):
    """Demasiados intentos de login."""
    
    def __init__(self, lockout_until=None, **kwargs):
        details = {}
        if lockout_until:
            details['lockout_until'] = lockout_until.isoformat()
        
        super().__init__(
            message="Demasiados intentos de login",
            error_code='TOO_MANY_LOGIN_ATTEMPTS',
            details=details,
            user_message="Cuenta temporalmente bloqueada por múltiples intentos fallidos",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE EMPRENDEDORES
# ====================================

class EntrepreneurNotFoundError(EcosistemaException):
    """Emprendedor no encontrado."""
    
    def __init__(self, entrepreneur_id=None, **kwargs):
        details = {'entrepreneur_id': entrepreneur_id} if entrepreneur_id else {}
        
        super().__init__(
            message=f"Emprendedor no encontrado: {entrepreneur_id or 'unknown'}",
            error_code='ENTREPRENEUR_NOT_FOUND',
            details=details,
            user_message="Emprendedor no encontrado",
            **kwargs
        )


class ProjectNotFoundError(EcosistemaException):
    """Proyecto no encontrado."""
    
    def __init__(self, project_id=None, **kwargs):
        details = {'project_id': project_id} if project_id else {}
        
        super().__init__(
            message=f"Proyecto no encontrado: {project_id or 'unknown'}",
            error_code='PROJECT_NOT_FOUND',
            details=details,
            user_message="Proyecto no encontrado",
            **kwargs
        )


class ProjectStatusError(BusinessLogicError):
    """Error de estado de proyecto."""
    
    def __init__(self, current_status=None, target_status=None, **kwargs):
        details = {}
        if current_status:
            details['current_status'] = current_status
        if target_status:
            details['target_status'] = target_status
        
        super().__init__(
            message=f"Transición de estado inválida: {current_status} -> {target_status}",
            error_code='PROJECT_STATUS_ERROR',
            details=details,
            user_message="No se puede cambiar el proyecto a este estado",
            **kwargs
        )


class MaxProjectsReachedError(BusinessLogicError):
    """Máximo de proyectos alcanzado."""
    
    def __init__(self, current_count=None, max_allowed=None, **kwargs):
        details = {}
        if current_count is not None:
            details['current_count'] = current_count
        if max_allowed is not None:
            details['max_allowed'] = max_allowed
        
        super().__init__(
            message=f"Máximo de proyectos alcanzado: {current_count}/{max_allowed}",
            error_code='MAX_PROJECTS_REACHED',
            details=details,
            user_message="Has alcanzado el máximo número de proyectos permitidos",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE ALIADOS/MENTORES
# ====================================

class AllyNotFoundError(EcosistemaException):
    """Aliado/Mentor no encontrado."""
    
    def __init__(self, ally_id=None, **kwargs):
        details = {'ally_id': ally_id} if ally_id else {}
        
        super().__init__(
            message=f"Aliado no encontrado: {ally_id or 'unknown'}",
            error_code='ALLY_NOT_FOUND',
            details=details,
            user_message="Aliado no encontrado",
            **kwargs
        )


class MentorshipSessionError(BusinessLogicError):
    """Error en sesión de mentoría."""
    
    def __init__(self, session_id=None, reason=None, **kwargs):
        details = {}
        if session_id:
            details['session_id'] = session_id
        if reason:
            details['reason'] = reason
        
        super().__init__(
            message=f"Error en sesión de mentoría: {reason or 'unknown'}",
            error_code='MENTORSHIP_SESSION_ERROR',
            details=details,
            user_message="Error en la sesión de mentoría",
            **kwargs
        )


class MaxEntrepreneursReachedError(BusinessLogicError):
    """Máximo de emprendedores por aliado alcanzado."""
    
    def __init__(self, current_count=None, max_allowed=None, **kwargs):
        details = {}
        if current_count is not None:
            details['current_count'] = current_count
        if max_allowed is not None:
            details['max_allowed'] = max_allowed
        
        super().__init__(
            message=f"Máximo de emprendedores alcanzado: {current_count}/{max_allowed}",
            error_code='MAX_ENTREPRENEURS_REACHED',
            details=details,
            user_message="Has alcanzado el máximo número de emprendedores que puedes mentorear",
            **kwargs
        )


class SessionConflictError(BusinessLogicError):
    """Conflicto de horario en sesiones."""
    
    def __init__(self, conflicting_session_id=None, time_slot=None, **kwargs):
        details = {}
        if conflicting_session_id:
            details['conflicting_session_id'] = conflicting_session_id
        if time_slot:
            details['time_slot'] = time_slot
        
        super().__init__(
            message=f"Conflicto de horario en sesión: {time_slot or 'unknown'}",
            error_code='SESSION_CONFLICT',
            details=details,
            user_message="Ya tienes una sesión programada en este horario",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE REUNIONES
# ====================================

class MeetingNotFoundError(EcosistemaException):
    """Reunión no encontrada."""
    
    def __init__(self, meeting_id=None, **kwargs):
        details = {'meeting_id': meeting_id} if meeting_id else {}
        
        super().__init__(
            message=f"Reunión no encontrada: {meeting_id or 'unknown'}",
            error_code='MEETING_NOT_FOUND',
            details=details,
            user_message="Reunión no encontrada",
            **kwargs
        )


class MeetingConflictError(BusinessLogicError):
    """Conflicto de horario en reuniones."""
    
    def __init__(self, conflicting_meeting_id=None, time_slot=None, **kwargs):
        details = {}
        if conflicting_meeting_id:
            details['conflicting_meeting_id'] = conflicting_meeting_id
        if time_slot:
            details['time_slot'] = time_slot
        
        super().__init__(
            message=f"Conflicto de horario: {time_slot or 'unknown'}",
            error_code='MEETING_CONFLICT',
            details=details,
            user_message="Ya tienes una reunión programada en este horario",
            **kwargs
        )


class InvalidMeetingTimeError(ValidationError):
    """Hora de reunión inválida."""
    
    def __init__(self, meeting_time=None, reason=None, **kwargs):
        details = {}
        if meeting_time:
            details['meeting_time'] = str(meeting_time)
        if reason:
            details['reason'] = reason
        
        super().__init__(
            message=f"Hora de reunión inválida: {reason or 'unknown'}",
            error_code='INVALID_MEETING_TIME',
            details=details,
            user_message="La hora seleccionada no es válida",
            **kwargs
        )


class MeetingNotEditableError(BusinessLogicError):
    """Reunión no editable."""
    
    def __init__(self, meeting_id=None, status=None, **kwargs):
        details = {}
        if meeting_id:
            details['meeting_id'] = meeting_id
        if status:
            details['status'] = status
        
        super().__init__(
            message=f"Reunión no editable: {status or 'unknown'}",
            error_code='MEETING_NOT_EDITABLE',
            details=details,
            user_message="Esta reunión no se puede editar",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE ARCHIVOS
# ====================================

class FileNotFoundError(EcosistemaException):
    """Archivo no encontrado."""
    
    def __init__(self, file_path=None, file_id=None, **kwargs):
        details = {}
        if file_path:
            details['file_path'] = file_path
        if file_id:
            details['file_id'] = file_id
        
        super().__init__(
            message=f"Archivo no encontrado: {file_path or file_id or 'unknown'}",
            error_code='FILE_NOT_FOUND',
            details=details,
            user_message="Archivo no encontrado",
            **kwargs
        )


class InvalidFileTypeError(ValidationError):
    """Tipo de archivo inválido."""
    
    def __init__(self, file_type=None, allowed_types=None, **kwargs):
        details = {}
        if file_type:
            details['file_type'] = file_type
        if allowed_types:
            details['allowed_types'] = allowed_types
        
        super().__init__(
            message=f"Tipo de archivo inválido: {file_type}",
            error_code='INVALID_FILE_TYPE',
            details=details,
            user_message="Tipo de archivo no permitido",
            **kwargs
        )


class FileSizeExceededError(ValidationError):
    """Tamaño de archivo excedido."""
    
    def __init__(self, file_size=None, max_size=None, **kwargs):
        details = {}
        if file_size is not None:
            details['file_size'] = file_size
        if max_size is not None:
            details['max_size'] = max_size
        
        super().__init__(
            message=f"Tamaño de archivo excedido: {file_size} > {max_size}",
            error_code='FILE_SIZE_EXCEEDED',
            details=details,
            user_message="El archivo es demasiado grande",
            **kwargs
        )


class FileUploadError(EcosistemaException):
    """Error en subida de archivo."""
    
    def __init__(self, filename=None, reason=None, **kwargs):
        details = {}
        if filename:
            details['filename'] = filename
        if reason:
            details['reason'] = reason
        
        super().__init__(
            message=f"Error subiendo archivo: {reason or 'unknown'}",
            error_code='FILE_UPLOAD_ERROR',
            details=details,
            user_message="Error al subir el archivo",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE INTEGRACIÓN
# ====================================

class IntegrationError(EcosistemaException):
    """Error de integración con servicios externos."""
    
    def __init__(self, service=None, operation=None, **kwargs):
        details = {}
        if service:
            details['service'] = service
        if operation:
            details['operation'] = operation
        
        super().__init__(
            message=f"Error de integración: {service} - {operation}",
            error_code='INTEGRATION_ERROR',
            details=details,
            user_message="Error temporal del servicio. Intenta más tarde",
            **kwargs
        )


class GoogleCalendarError(IntegrationError):
    """Error específico de Google Calendar."""
    
    def __init__(self, operation=None, **kwargs):
        super().__init__(
            service='Google Calendar',
            operation=operation,
            error_code='GOOGLE_CALENDAR_ERROR',
            user_message="Error al sincronizar con Google Calendar",
            **kwargs
        )


class EmailServiceError(IntegrationError):
    """Error del servicio de email."""
    
    def __init__(self, operation=None, recipient=None, **kwargs):
        details = kwargs.get('details', {})
        if recipient:
            details['recipient'] = recipient
        
        super().__init__(
            service='Email Service',
            operation=operation,
            error_code='EMAIL_SERVICE_ERROR',
            details=details,
            user_message="Error al enviar email",
            **kwargs
        )


class SMSServiceError(IntegrationError):
    """Error del servicio de SMS."""
    
    def __init__(self, operation=None, phone_number=None, **kwargs):
        details = kwargs.get('details', {})
        if phone_number:
            details['phone_number'] = phone_number
        
        super().__init__(
            service='SMS Service',
            operation=operation,
            error_code='SMS_SERVICE_ERROR',
            details=details,
            user_message="Error al enviar SMS",
            **kwargs
        )


# ====================================
# EXCEPCIONES DE RATE LIMITING
# ====================================

class RateLimitExceededError(EcosistemaException):
    """Límite de tasa excedido."""
    
    def __init__(self, limit=None, window=None, retry_after=None, **kwargs):
        details = {}
        if limit is not None:
            details['limit'] = limit
        if window:
            details['window'] = window
        if retry_after is not None:
            details['retry_after'] = retry_after
        
        super().__init__(
            message=f"Rate limit exceeded: {limit} per {window}",
            error_code='RATE_LIMIT_EXCEEDED',
            details=details,
            user_message="Demasiadas solicitudes. Intenta más tarde",
            **kwargs
        )


# ====================================
# MANEJADORES DE ERRORES GLOBALES
# ====================================

def handle_ecosistema_exception(error):
    """Manejador para excepciones del ecosistema."""
    
    # Log del error
    current_app.logger.error(f"EcosistemaException: {error}")
    
    # Respuesta según el tipo de request
    if request.is_json or request.path.startswith('/api/'):
        # API Response
        response = jsonify(error.to_dict())
        response.status_code = get_http_status_for_error(error)
        return response
    else:
        # Web Response
        return render_template(
            'errors/error.html',
            error=error,
            title="Error"
        ), get_http_status_for_error(error)


def handle_validation_error(error):
    """Manejador específico para errores de validación."""
    
    current_app.logger.warning(f"ValidationError: {error}")
    
    if request.is_json or request.path.startswith('/api/'):
        response_data = error.to_dict()
        response_data['field_errors'] = getattr(error, 'field_errors', {})
        response = jsonify(response_data)
        response.status_code = 400
        return response
    else:
        return render_template(
            'errors/validation_error.html',
            error=error,
            title="Error de Validación"
        ), 400


def handle_authentication_error(error):
    """Manejador específico para errores de autenticación."""
    
    current_app.logger.warning(f"AuthenticationError: {error}")
    
    if request.is_json or request.path.startswith('/api/'):
        response = jsonify(error.to_dict())
        response.status_code = 401
        return response
    else:
        # Redirigir al login para errores de autenticación web
        from flask import redirect, url_for, flash
        flash(error.user_message, 'error')
        return redirect(url_for('auth.login'))


def handle_authorization_error(error):
    """Manejador específico para errores de autorización."""
    
    current_app.logger.warning(f"AuthorizationError: {error}")
    
    if request.is_json or request.path.startswith('/api/'):
        response = jsonify(error.to_dict())
        response.status_code = 403
        return response
    else:
        return render_template(
            'errors/403.html',
            error=error
        ), 403


def handle_rate_limit_error(error):
    """Manejador específico para errores de rate limiting."""
    
    current_app.logger.warning(f"RateLimitExceededError: {error}")
    
    response_data = error.to_dict()
    response = jsonify(response_data)
    response.status_code = 429
    
    # Añadir headers de rate limiting
    if 'retry_after' in error.details:
        response.headers['Retry-After'] = str(error.details['retry_after'])
    
    return response


def get_http_status_for_error(error):
    """Determinar el código HTTP apropiado para una excepción."""
    
    status_map = {
        'ValidationError': 400,
        'AuthenticationError': 401,
        'AuthorizationError': 403,
        'UserNotFoundError': 404,
        'ProjectNotFoundError': 404,
        'MeetingNotFoundError': 404,
        'FileNotFoundError': 404,
        'AllyNotFoundError': 404,
        'EntrepreneurNotFoundError': 404,
        'BusinessLogicError': 422,
        'RateLimitExceededError': 429,
        'IntegrationError': 502,
        'EcosistemaException': 500
    }
    
    return status_map.get(error.error_code, 500)


def register_error_handlers(app):
    """Registrar todos los manejadores de errores con la aplicación Flask."""
    
    # Manejadores específicos
    app.errorhandler(ValidationError)(handle_validation_error)
    app.errorhandler(AuthenticationError)(handle_authentication_error)
    app.errorhandler(AuthorizationError)(handle_authorization_error)
    app.errorhandler(RateLimitExceededError)(handle_rate_limit_error)
    
    # Manejador general para excepciones del ecosistema
    app.errorhandler(EcosistemaException)(handle_ecosistema_exception)
    
    # Manejadores para errores HTTP estándar
    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        current_app.logger.error(f"Internal server error: {error}")
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    app.logger.info("Error handlers registered successfully")
class PermissionError(EcosistemaException):
    """Exception raised for permission denied errors."""
    
    def __init__(self, action, message=None):
        self.action = action
        message = message or f'Permission denied for action: {action}'
        super().__init__(message, error_code='PERMISSION_DENIED')


class ServiceError(EcosistemaException):
    """Exception raised by service layer errors."""
    
    def __init__(self, service, message=None):
        self.service = service
        message = message or f'Service error in {service}'
        super().__init__(message, error_code='SERVICE_ERROR')

class ValidationError(EcosistemaException):
    """Exception raised for validation errors."""
    
    def __init__(self, field, message=None):
        self.field = field
        message = message or f'Validation error in field: {field}'
        super().__init__(message, error_code='VALIDATION_ERROR')


class NotFoundError(EcosistemaException):
    """Exception raised when resource is not found."""
    
    def __init__(self, resource, message=None):
        self.resource = resource
        message = message or f'{resource} not found'
        super().__init__(message, error_code='NOT_FOUND')

class AuthorizationError(EcosistemaException):
    """Exception raised for authorization errors."""
    
    def __init__(self, message='Authorization required'):
        super().__init__(message, error_code='AUTHORIZATION_ERROR')


class ExternalServiceError(EcosistemaException):
    """Exception raised for externalservice errors."""
    
    def __init__(self, message=None):
        message = message or 'externalservice error occurred'
        super().__init__(message, error_code='EXTERNALSERVICE_ERROR')

class ConfigurationError(EcosistemaException):
    """Exception raised for configuration errors."""
    
    def __init__(self, message=None):
        message = message or 'configuration error occurred'
        super().__init__(message, error_code='CONFIGURATION_ERROR')

class DatabaseError(EcosistemaException):
    """Exception raised for database errors."""
    
    def __init__(self, message=None):
        message = message or 'database error occurred'
        super().__init__(message, error_code='DATABASE_ERROR')

class CacheError(EcosistemaException):
    """Exception raised for cache errors."""
    
    def __init__(self, message=None):
        message = message or 'cache error occurred'
        super().__init__(message, error_code='CACHE_ERROR')

class EmailError(EcosistemaException):
    """Exception raised for email errors."""
    
    def __init__(self, message=None):
        message = message or 'email error occurred'
        super().__init__(message, error_code='EMAIL_ERROR')

class FileError(EcosistemaException):
    """Exception raised for file errors."""
    
    def __init__(self, message=None):
        message = message or 'file error occurred'
        super().__init__(message, error_code='FILE_ERROR')

class APIError(EcosistemaException):
    """Exception raised for api errors."""
    
    def __init__(self, message=None):
        message = message or 'api error occurred'
        super().__init__(message, error_code='API_ERROR')

class RateLimitError(EcosistemaException):
    """Exception raised for ratelimit errors."""
    
    def __init__(self, message=None):
        message = message or 'ratelimit error occurred'
        super().__init__(message, error_code='RATELIMIT_ERROR')

class SecurityError(EcosistemaException):
    """Exception raised for security errors."""
    
    def __init__(self, message=None):
        message = message or 'security error occurred'
        super().__init__(message, error_code='SECURITY_ERROR')

class TokenError(EcosistemaException):
    """Exception raised for token errors."""
    
    def __init__(self, message=None):
        message = message or 'token error occurred'
        super().__init__(message, error_code='TOKEN_ERROR')

class SessionError(EcosistemaException):
    """Exception raised for session errors."""
    
    def __init__(self, message=None):
        message = message or 'session error occurred'
        super().__init__(message, error_code='SESSION_ERROR')

class WebhookError(EcosistemaException):
    """Exception raised for webhook errors."""
    
    def __init__(self, message=None):
        message = message or 'webhook error occurred'
        super().__init__(message, error_code='WEBHOOK_ERROR')

class ExternalAPIError(EcosistemaException):
    """Exception raised for external API errors."""
    
    def __init__(self, message=None):
        message = message or 'external API error occurred'
        super().__init__(message, error_code='EXTERNAL_API_ERROR')


class ResourceNotFoundError(EcosistemaException):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, resource_type=None, resource_id=None, message=None):
        if not message:
            if resource_type and resource_id:
                message = f"{resource_type} with ID {resource_id} not found"
            elif resource_type:
                message = f"{resource_type} not found"
            else:
                message = "Requested resource not found"
        
        super().__init__(
            message=message,
            error_code='RESOURCE_NOT_FOUND',
            details={
                'resource_type': resource_type,
                'resource_id': resource_id
            },
            user_message="El recurso solicitado no fue encontrado"
        )
