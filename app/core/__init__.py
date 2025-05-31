"""
Módulo Core del Ecosistema de Emprendimiento.
Este módulo contiene la lógica de negocio central, excepciones, constantes y utilidades de seguridad.
"""

from flask import current_app

# === IMPORTACIONES DE EXCEPCIONES ===
from .exceptions import (
    # Excepciones base
    EcosistemaException,
    ValidationError,
    BusinessLogicError,
    AuthenticationError,
    AuthorizationError,
    
    # Excepciones específicas de usuarios
    UserNotFoundError,
    UserAlreadyExistsError,
    UserInactiveError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    
    # Excepciones de emprendedores
    EntrepreneurNotFoundError,
    ProjectNotFoundError,
    ProjectStatusError,
    MaxProjectsReachedError,
    
    # Excepciones de aliados/mentores
    AllyNotFoundError,
    MentorshipSessionError,
    MaxEntrepreneursReachedError,
    SessionConflictError,
    
    # Excepciones de reuniones
    MeetingNotFoundError,
    MeetingConflictError,
    InvalidMeetingTimeError,
    
    # Excepciones de archivos
    FileNotFoundError,
    InvalidFileTypeError,
    FileSizeExceededError,
    FileUploadError,
    
    # Excepciones de integración
    IntegrationError,
    GoogleCalendarError,
    EmailServiceError,
    SMSServiceError,
    
    # Manejador global de errores
    register_error_handlers
)

# === IMPORTACIONES DE CONSTANTES ===
from .constants import (
    # Roles del sistema
    USER_ROLES,
    ADMIN_ROLE,
    ENTREPRENEUR_ROLE,
    ALLY_ROLE,
    CLIENT_ROLE,
    
    # Estados de proyectos
    PROJECT_STATUSES,
    PROJECT_STATUS_IDEA,
    PROJECT_STATUS_VALIDATION,
    PROJECT_STATUS_DEVELOPMENT,
    PROJECT_STATUS_LAUNCH,
    PROJECT_STATUS_GROWTH,
    PROJECT_STATUS_SCALE,
    PROJECT_STATUS_EXIT,
    
    # Estados de reuniones
    MEETING_STATUSES,
    MEETING_STATUS_SCHEDULED,
    MEETING_STATUS_IN_PROGRESS,
    MEETING_STATUS_COMPLETED,
    MEETING_STATUS_CANCELLED,
    MEETING_STATUS_NO_SHOW,
    
    # Tipos de archivos
    ALLOWED_FILE_EXTENSIONS,
    IMAGE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    SPREADSHEET_EXTENSIONS,
    
    # Límites del sistema
    MAX_FILE_SIZE,
    MAX_PROJECTS_PER_ENTREPRENEUR,
    MAX_ENTREPRENEURS_PER_ALLY,
    MAX_MEETING_DURATION,
    
    # Configuraciones de negocio
    BUSINESS_CONSTANTS,
    KPI_THRESHOLDS,
    NOTIFICATION_TYPES,
    
    # Configuraciones de tiempo
    TIMEZONE_BOGOTA,
    DATE_FORMAT,
    DATETIME_FORMAT,
    TIME_FORMAT
)

# === IMPORTACIONES DE SEGURIDAD ===
from .security import (
    # Utilidades de encriptación
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    hash_password,
    verify_password,
    generate_secure_token,
    verify_token,
    
    # Validaciones de seguridad
    validate_password_strength,
    validate_email_format,
    sanitize_input,
    validate_file_security,
    
    # Rate limiting
    check_rate_limit,
    increment_rate_limit,
    reset_rate_limit,
    
    # Audit logging
    log_security_event,
    log_user_action,
    
    # JWT utilities
    generate_jwt_token,
    verify_jwt_token,
    blacklist_jwt_token,
    
    # Session management
    create_user_session,
    validate_user_session,
    invalidate_user_session,
    cleanup_expired_sessions
)

# === IMPORTACIONES DE PERMISOS ===
from .permissions import (
    # Decoradores de permisos
    require_role,
    require_permission,
    require_admin,
    require_entrepreneur,
    require_ally,
    require_client,
    
    # Verificadores de permisos
    has_role,
    has_permission,
    can_access_resource,
    can_modify_resource,
    can_delete_resource,
    
    # Permisos específicos
    can_view_user_profile,
    can_edit_user_profile,
    can_manage_projects,
    can_schedule_meetings,
    can_access_analytics,
    
    # Context processors
    permission_context_processor,
    
    # Utilidades de permisos
    get_user_permissions,
    check_resource_ownership,
    filter_by_permissions
)

# === IMPORTACIONES DE CONTEXT PROCESSORS ===
from .context_processors import (
    # Context processors principales
    inject_user_context,
    inject_app_context,
    inject_navigation_context,
    inject_notification_context,
    
    # Utilidades de contexto
    get_current_user_data,
    get_navigation_items,
    get_unread_notifications,
    get_system_status,
    
    # Registro de context processors
    register_context_processors
)


# ====================================
# CONFIGURACIÓN DEL MÓDULO CORE
# ====================================

class CoreConfig:
    """Configuración central del módulo core."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializar configuración con la aplicación Flask."""
        
        # Configurar logging para el módulo core
        self._setup_core_logging(app)
        
        # Registrar manejadores de errores
        register_error_handlers(app)
        
        # Registrar context processors
        register_context_processors(app)
        
        # Configurar validaciones de seguridad
        self._setup_security_config(app)
        
        # Configurar límites de negocio
        self._setup_business_limits(app)
        
        app.logger.info("Core module initialized successfully")
    
    def _setup_core_logging(self, app):
        """Configurar logging específico para el módulo core."""
        import logging
        
        # Logger para eventos de seguridad
        security_logger = logging.getLogger('ecosistema.security')
        security_logger.setLevel(logging.INFO)
        
        # Logger para eventos de negocio
        business_logger = logging.getLogger('ecosistema.business')
        business_logger.setLevel(logging.INFO)
        
        # Logger para errores críticos
        critical_logger = logging.getLogger('ecosistema.critical')
        critical_logger.setLevel(logging.ERROR)
        
        # Añadir handlers si no existen
        if not security_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            security_logger.addHandler(handler)
    
    def _setup_security_config(self, app):
        """Configurar parámetros de seguridad."""
        
        # Configurar límites de intentos de login
        app.config.setdefault('MAX_LOGIN_ATTEMPTS', 5)
        app.config.setdefault('LOGIN_LOCKOUT_DURATION', 900)  # 15 minutos
        
        # Configurar validaciones de contraseña
        app.config.setdefault('MIN_PASSWORD_LENGTH', 8)
        app.config.setdefault('REQUIRE_PASSWORD_COMPLEXITY', True)
        
        # Configurar tokens de seguridad
        app.config.setdefault('TOKEN_EXPIRATION_HOURS', 24)
        app.config.setdefault('REFRESH_TOKEN_DAYS', 30)
        
        # Configurar audit logging
        app.config.setdefault('AUDIT_LOG_ENABLED', True)
        app.config.setdefault('AUDIT_LOG_RETENTION_DAYS', 365)
    
    def _setup_business_limits(self, app):
        """Configurar límites de negocio."""
        
        # Límites por defecto si no están configurados
        app.config.setdefault('MAX_PROJECTS_PER_ENTREPRENEUR', MAX_PROJECTS_PER_ENTREPRENEUR)
        app.config.setdefault('MAX_ENTREPRENEURS_PER_ALLY', MAX_ENTREPRENEURS_PER_ALLY)
        app.config.setdefault('MAX_FILE_SIZE', MAX_FILE_SIZE)
        app.config.setdefault('MAX_MEETINGS_PER_DAY', 8)
        app.config.setdefault('MAX_MENTORSHIP_HOURS_PER_MONTH', 40)


# ====================================
# UTILIDADES PRINCIPALES DEL CORE
# ====================================

def get_app_version():
    """Obtener versión de la aplicación."""
    return getattr(current_app, 'version', '1.0.0')


def get_system_info():
    """Obtener información del sistema."""
    import platform
    import sys
    from datetime import datetime
    
    return {
        'app_version': get_app_version(),
        'python_version': sys.version,
        'platform': platform.platform(),
        'timestamp': datetime.utcnow().isoformat(),
        'environment': current_app.config.get('FLASK_ENV', 'unknown')
    }


def validate_business_rules():
    """Validar reglas de negocio del sistema."""
    errors = []
    
    try:
        # Validar configuraciones críticas
        required_configs = [
            'SECRET_KEY', 'SQLALCHEMY_DATABASE_URI', 'MAIL_SERVER'
        ]
        
        for config in required_configs:
            if not current_app.config.get(config):
                errors.append(f"Configuración requerida faltante: {config}")
        
        # Validar límites de negocio
        if current_app.config.get('MAX_PROJECTS_PER_ENTREPRENEUR', 0) <= 0:
            errors.append("MAX_PROJECTS_PER_ENTREPRENEUR debe ser mayor a 0")
        
        if current_app.config.get('MAX_ENTREPRENEURS_PER_ALLY', 0) <= 0:
            errors.append("MAX_ENTREPRENEURS_PER_ALLY debe ser mayor a 0")
        
        # Validar configuraciones de seguridad
        if current_app.config.get('MIN_PASSWORD_LENGTH', 0) < 8:
            errors.append("MIN_PASSWORD_LENGTH debe ser al menos 8")
        
    except Exception as e:
        errors.append(f"Error validando reglas de negocio: {str(e)}")
    
    return errors


def init_core_module(app):
    """
    Inicializar completamente el módulo core.
    Esta función debe ser llamada desde app/__init__.py
    """
    
    # Inicializar configuración core
    core_config = CoreConfig(app)
    
    # Validar reglas de negocio
    validation_errors = validate_business_rules()
    if validation_errors:
        app.logger.warning("Errores de validación encontrados:")
        for error in validation_errors:
            app.logger.warning(f"  - {error}")
    
    # Registrar funciones utilitarias en el contexto de la app
    app.jinja_env.globals.update({
        'get_app_version': get_app_version,
        'get_system_info': get_system_info,
        'USER_ROLES': USER_ROLES,
        'PROJECT_STATUSES': PROJECT_STATUSES,
        'MEETING_STATUSES': MEETING_STATUSES
    })
    
    app.logger.info("Core module fully initialized")
    return core_config


# ====================================
# HEALTH CHECK DEL MÓDULO CORE
# ====================================

def core_health_check():
    """
    Verificar la salud del módulo core.
    Retorna un diccionario con el estado de los componentes.
    """
    
    health_status = {
        'status': 'healthy',
        'components': {},
        'timestamp': None
    }
    
    try:
        from datetime import datetime
        health_status['timestamp'] = datetime.utcnow().isoformat()
        
        # Verificar constantes
        try:
            assert len(USER_ROLES) > 0
            assert len(PROJECT_STATUSES) > 0
            health_status['components']['constants'] = 'ok'
        except Exception as e:
            health_status['components']['constants'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Verificar excepciones
        try:
            test_exception = EcosistemaException("Test")
            assert isinstance(test_exception, Exception)
            health_status['components']['exceptions'] = 'ok'
        except Exception as e:
            health_status['components']['exceptions'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Verificar seguridad
        try:
            test_token = generate_secure_token()
            assert len(test_token) > 0
            health_status['components']['security'] = 'ok'
        except Exception as e:
            health_status['components']['security'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Verificar permisos
        try:
            assert callable(require_role)
            assert callable(has_permission)
            health_status['components']['permissions'] = 'ok'
        except Exception as e:
            health_status['components']['permissions'] = f'error: {str(e)}'
            health_status['status'] = 'unhealthy'
    
    except Exception as e:
        health_status['status'] = 'critical'
        health_status['error'] = str(e)
    
    return health_status


# ====================================
# EXPORTACIONES PRINCIPALES
# ====================================

__all__ = [
    # Configuración
    'CoreConfig',
    'init_core_module',
    
    # Excepciones
    'EcosistemaException',
    'ValidationError',
    'BusinessLogicError',
    'AuthenticationError',
    'AuthorizationError',
    'UserNotFoundError',
    'UserAlreadyExistsError',
    'ProjectNotFoundError',
    'MeetingNotFoundError',
    'register_error_handlers',
    
    # Constantes
    'USER_ROLES',
    'PROJECT_STATUSES',
    'MEETING_STATUSES',
    'BUSINESS_CONSTANTS',
    'MAX_PROJECTS_PER_ENTREPRENEUR',
    'MAX_ENTREPRENEURS_PER_ALLY',
    
    # Seguridad
    'encrypt_sensitive_data',
    'decrypt_sensitive_data',
    'generate_secure_token',
    'validate_password_strength',
    'log_security_event',
    'generate_jwt_token',
    'verify_jwt_token',
    
    # Permisos
    'require_role',
    'require_permission',
    'has_role',
    'has_permission',
    'can_access_resource',
    'get_user_permissions',
    
    # Context processors
    'inject_user_context',
    'inject_app_context',
    'register_context_processors',
    
    # Utilidades
    'get_app_version',
    'get_system_info',
    'validate_business_rules',
    'core_health_check'
]


# ====================================
# METADATA DEL MÓDULO
# ====================================

__version__ = '1.0.0'
__author__ = 'Ecosistema de Emprendimiento Team'
__description__ = 'Módulo core con lógica de negocio central'
__license__ = 'MIT'