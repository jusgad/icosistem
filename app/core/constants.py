"""
Constantes globales para el ecosistema de emprendimiento.
Este módulo centraliza todas las constantes utilizadas en la aplicación.
"""

from datetime import timedelta
from enum import Enum
import pytz

# ====================================
# ROLES DEL SISTEMA
# ====================================

# Roles principales
ADMIN_ROLE = 'admin'
ENTREPRENEUR_ROLE = 'entrepreneur'
ALLY_ROLE = 'ally'
CLIENT_ROLE = 'client'

# Diccionario de roles con descripciones
USER_ROLES = {
    ADMIN_ROLE: {
        'name': 'Administrador',
        'description': 'Administrador del sistema con acceso completo',
        'permissions': ['*'],  # Todos los permisos
        'dashboard_route': 'admin.dashboard',
        'icon': 'fas fa-crown',
        'color': 'danger'
    },
    ENTREPRENEUR_ROLE: {
        'name': 'Emprendedor',
        'description': 'Emprendedor desarrollando proyectos',
        'permissions': [
            'view_own_profile', 'edit_own_profile',
            'create_projects', 'manage_own_projects',
            'schedule_meetings', 'upload_documents',
            'view_mentorship', 'request_mentorship'
        ],
        'dashboard_route': 'entrepreneur.dashboard',
        'icon': 'fas fa-rocket',
        'color': 'primary'
    },
    ALLY_ROLE: {
        'name': 'Aliado/Mentor',
        'description': 'Mentor o aliado estratégico del ecosistema',
        'permissions': [
            'view_own_profile', 'edit_own_profile',
            'view_entrepreneurs', 'provide_mentorship',
            'schedule_meetings', 'view_analytics',
            'create_reports', 'manage_hours'
        ],
        'dashboard_route': 'ally.dashboard',
        'icon': 'fas fa-handshake',
        'color': 'success'
    },
    CLIENT_ROLE: {
        'name': 'Cliente/Stakeholder',
        'description': 'Cliente o stakeholder del ecosistema',
        'permissions': [
            'view_own_profile', 'edit_own_profile',
            'view_directory', 'view_public_projects',
            'view_impact_metrics', 'access_reports'
        ],
        'dashboard_route': 'client.dashboard',
        'icon': 'fas fa-building',
        'color': 'info'
    }
}

# Lista de roles válidos
VALID_ROLES = list(USER_ROLES.keys())

# Roles con privilegios administrativos
ADMIN_ROLES = [ADMIN_ROLE]

# Roles que pueden proporcionar mentoría
MENTOR_ROLES = [ALLY_ROLE, ADMIN_ROLE]

# Roles que pueden recibir mentoría
MENTEE_ROLES = [ENTREPRENEUR_ROLE]


# ====================================
# ESTADOS DE PROYECTOS
# ====================================

# Estados individuales
PROJECT_STATUS_IDEA = 'idea'
PROJECT_STATUS_VALIDATION = 'validation'
PROJECT_STATUS_DEVELOPMENT = 'development'
PROJECT_STATUS_LAUNCH = 'launch'
PROJECT_STATUS_GROWTH = 'growth'
PROJECT_STATUS_SCALE = 'scale'
PROJECT_STATUS_EXIT = 'exit'
PROJECT_STATUS_PAUSED = 'paused'
PROJECT_STATUS_CANCELLED = 'cancelled'

# Diccionario de estados con metadatos
PROJECT_STATUSES = {
    PROJECT_STATUS_IDEA: {
        'name': 'Idea',
        'description': 'Proyecto en fase de conceptualización',
        'color': 'light',
        'icon': 'fas fa-lightbulb',
        'progress': 10,
        'next_statuses': [PROJECT_STATUS_VALIDATION, PROJECT_STATUS_PAUSED, PROJECT_STATUS_CANCELLED],
        'requirements': [],
        'deliverables': ['Business Model Canvas', 'Problem Statement']
    },
    PROJECT_STATUS_VALIDATION: {
        'name': 'Validación',
        'description': 'Validando la idea con el mercado',
        'color': 'warning',
        'icon': 'fas fa-search',
        'progress': 25,
        'next_statuses': [PROJECT_STATUS_DEVELOPMENT, PROJECT_STATUS_IDEA, PROJECT_STATUS_PAUSED, PROJECT_STATUS_CANCELLED],
        'requirements': ['Market Research', 'Customer Interviews'],
        'deliverables': ['MVP Requirements', 'Market Analysis']
    },
    PROJECT_STATUS_DEVELOPMENT: {
        'name': 'Desarrollo',
        'description': 'Desarrollando el producto/servicio',
        'color': 'info',
        'icon': 'fas fa-cogs',
        'progress': 50,
        'next_statuses': [PROJECT_STATUS_LAUNCH, PROJECT_STATUS_VALIDATION, PROJECT_STATUS_PAUSED, PROJECT_STATUS_CANCELLED],
        'requirements': ['MVP Specification', 'Development Team'],
        'deliverables': ['MVP', 'Go-to-Market Strategy']
    },
    PROJECT_STATUS_LAUNCH: {
        'name': 'Lanzamiento',
        'description': 'Lanzando al mercado',
        'color': 'primary',
        'icon': 'fas fa-rocket',
        'progress': 70,
        'next_statuses': [PROJECT_STATUS_GROWTH, PROJECT_STATUS_DEVELOPMENT, PROJECT_STATUS_PAUSED, PROJECT_STATUS_CANCELLED],
        'requirements': ['MVP Ready', 'Marketing Strategy'],
        'deliverables': ['Product Launch', 'Initial Customer Base']
    },
    PROJECT_STATUS_GROWTH: {
        'name': 'Crecimiento',
        'description': 'Creciendo y optimizando',
        'color': 'success',
        'icon': 'fas fa-chart-line',
        'progress': 85,
        'next_statuses': [PROJECT_STATUS_SCALE, PROJECT_STATUS_EXIT, PROJECT_STATUS_PAUSED],
        'requirements': ['Market Traction', 'Revenue Generation'],
        'deliverables': ['Growth Metrics', 'Optimization Plan']
    },
    PROJECT_STATUS_SCALE: {
        'name': 'Escalamiento',
        'description': 'Escalando operaciones',
        'color': 'success',
        'icon': 'fas fa-expand-arrows-alt',
        'progress': 95,
        'next_statuses': [PROJECT_STATUS_EXIT, PROJECT_STATUS_GROWTH],
        'requirements': ['Scalable Model', 'Investment/Funding'],
        'deliverables': ['Scale Strategy', 'Expansion Plan']
    },
    PROJECT_STATUS_EXIT: {
        'name': 'Salida',
        'description': 'Proyecto exitoso completado',
        'color': 'success',
        'icon': 'fas fa-trophy',
        'progress': 100,
        'next_statuses': [],
        'requirements': ['Successful Exit Strategy'],
        'deliverables': ['Exit Documentation', 'Impact Report']
    },
    PROJECT_STATUS_PAUSED: {
        'name': 'Pausado',
        'description': 'Proyecto temporalmente pausado',
        'color': 'secondary',
        'icon': 'fas fa-pause',
        'progress': None,
        'next_statuses': [PROJECT_STATUS_IDEA, PROJECT_STATUS_VALIDATION, PROJECT_STATUS_DEVELOPMENT, 
                          PROJECT_STATUS_LAUNCH, PROJECT_STATUS_GROWTH, PROJECT_STATUS_CANCELLED],
        'requirements': [],
        'deliverables': []
    },
    PROJECT_STATUS_CANCELLED: {
        'name': 'Cancelado',
        'description': 'Proyecto cancelado',
        'color': 'danger',
        'icon': 'fas fa-times',
        'progress': None,
        'next_statuses': [],
        'requirements': [],
        'deliverables': ['Cancellation Report', 'Lessons Learned']
    }
}

# Estados activos (no terminados ni cancelados)
ACTIVE_PROJECT_STATUSES = [
    PROJECT_STATUS_IDEA, PROJECT_STATUS_VALIDATION, PROJECT_STATUS_DEVELOPMENT,
    PROJECT_STATUS_LAUNCH, PROJECT_STATUS_GROWTH, PROJECT_STATUS_SCALE
]

# Estados finales
FINAL_PROJECT_STATUSES = [PROJECT_STATUS_EXIT, PROJECT_STATUS_CANCELLED]

# Estados pausados
PAUSED_PROJECT_STATUSES = [PROJECT_STATUS_PAUSED]


# ====================================
# ESTADOS DE REUNIONES
# ====================================

MEETING_STATUS_SCHEDULED = 'scheduled'
MEETING_STATUS_IN_PROGRESS = 'in_progress'
MEETING_STATUS_COMPLETED = 'completed'
MEETING_STATUS_CANCELLED = 'cancelled'
MEETING_STATUS_NO_SHOW = 'no_show'
MEETING_STATUS_RESCHEDULED = 'rescheduled'

MEETING_STATUSES = {
    MEETING_STATUS_SCHEDULED: {
        'name': 'Programada',
        'description': 'Reunión programada',
        'color': 'info',
        'icon': 'fas fa-calendar',
        'can_edit': True,
        'can_cancel': True
    },
    MEETING_STATUS_IN_PROGRESS: {
        'name': 'En Progreso',
        'description': 'Reunión en curso',
        'color': 'warning',
        'icon': 'fas fa-clock',
        'can_edit': False,
        'can_cancel': False
    },
    MEETING_STATUS_COMPLETED: {
        'name': 'Completada',
        'description': 'Reunión completada exitosamente',
        'color': 'success',
        'icon': 'fas fa-check',
        'can_edit': False,
        'can_cancel': False
    },
    MEETING_STATUS_CANCELLED: {
        'name': 'Cancelada',
        'description': 'Reunión cancelada',
        'color': 'danger',
        'icon': 'fas fa-times',
        'can_edit': False,
        'can_cancel': False
    },
    MEETING_STATUS_NO_SHOW: {
        'name': 'No Asistió',
        'description': 'Una o más partes no asistieron',
        'color': 'warning',
        'icon': 'fas fa-user-times',
        'can_edit': False,
        'can_cancel': False
    },
    MEETING_STATUS_RESCHEDULED: {
        'name': 'Reprogramada',
        'description': 'Reunión reprogramada',
        'color': 'secondary',
        'icon': 'fas fa-calendar-alt',
        'can_edit': True,
        'can_cancel': True
    }
}

# Estados que permiten edición
EDITABLE_MEETING_STATUSES = [MEETING_STATUS_SCHEDULED, MEETING_STATUS_RESCHEDULED]

# Estados finales de reuniones
FINAL_MEETING_STATUSES = [MEETING_STATUS_COMPLETED, MEETING_STATUS_CANCELLED, MEETING_STATUS_NO_SHOW]


# ====================================
# TIPOS DE REUNIONES
# ====================================

MEETING_TYPE_MENTORSHIP = 'mentorship'
MEETING_TYPE_REVIEW = 'review'
MEETING_TYPE_PLANNING = 'planning'
MEETING_TYPE_PITCH = 'pitch'
MEETING_TYPE_FOLLOW_UP = 'follow_up'
MEETING_TYPE_WORKSHOP = 'workshop'
MEETING_TYPE_NETWORKING = 'networking'

MEETING_TYPES = {
    MEETING_TYPE_MENTORSHIP: {
        'name': 'Mentoría',
        'description': 'Sesión de mentoría uno a uno',
        'default_duration': 60,
        'icon': 'fas fa-user-graduate',
        'color': 'primary'
    },
    MEETING_TYPE_REVIEW: {
        'name': 'Revisión',
        'description': 'Revisión de progreso del proyecto',
        'default_duration': 45,
        'icon': 'fas fa-clipboard-check',
        'color': 'info'
    },
    MEETING_TYPE_PLANNING: {
        'name': 'Planificación',
        'description': 'Sesión de planificación estratégica',
        'default_duration': 90,
        'icon': 'fas fa-tasks',
        'color': 'success'
    },
    MEETING_TYPE_PITCH: {
        'name': 'Pitch',
        'description': 'Presentación del proyecto',
        'default_duration': 30,
        'icon': 'fas fa-presentation',
        'color': 'warning'
    },
    MEETING_TYPE_FOLLOW_UP: {
        'name': 'Seguimiento',
        'description': 'Reunión de seguimiento',
        'default_duration': 30,
        'icon': 'fas fa-sync',
        'color': 'secondary'
    },
    MEETING_TYPE_WORKSHOP: {
        'name': 'Taller',
        'description': 'Taller grupal',
        'default_duration': 120,
        'icon': 'fas fa-tools',
        'color': 'primary'
    },
    MEETING_TYPE_NETWORKING: {
        'name': 'Networking',
        'description': 'Evento de networking',
        'default_duration': 120,
        'icon': 'fas fa-network-wired',
        'color': 'success'
    }
}


# ====================================
# TIPOS DE ARCHIVOS PERMITIDOS
# ====================================

# Extensiones por categoría
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'}
DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'}
SPREADSHEET_EXTENSIONS = {'xls', 'xlsx', 'csv', 'ods'}
PRESENTATION_EXTENSIONS = {'ppt', 'pptx', 'odp'}
ARCHIVE_EXTENSIONS = {'zip', 'rar', '7z', 'tar', 'gz'}
VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'}
AUDIO_EXTENSIONS = {'mp3', 'wav', 'flac', 'aac', 'ogg'}

# Todas las extensiones permitidas
ALLOWED_FILE_EXTENSIONS = (
    IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS | SPREADSHEET_EXTENSIONS |
    PRESENTATION_EXTENSIONS | ARCHIVE_EXTENSIONS | VIDEO_EXTENSIONS |
    AUDIO_EXTENSIONS
)

# Configuración por tipo de archivo
FILE_TYPE_CONFIG = {
    'images': {
        'extensions': IMAGE_EXTENSIONS,
        'max_size': 5 * 1024 * 1024,  # 5MB
        'mime_types': ['image/*'],
        'icon': 'fas fa-image'
    },
    'documents': {
        'extensions': DOCUMENT_EXTENSIONS,
        'max_size': 10 * 1024 * 1024,  # 10MB
        'mime_types': ['application/pdf', 'application/msword', 'text/*'],
        'icon': 'fas fa-file-alt'
    },
    'spreadsheets': {
        'extensions': SPREADSHEET_EXTENSIONS,
        'max_size': 10 * 1024 * 1024,  # 10MB
        'mime_types': ['application/vnd.ms-excel', 'text/csv'],
        'icon': 'fas fa-table'
    },
    'presentations': {
        'extensions': PRESENTATION_EXTENSIONS,
        'max_size': 20 * 1024 * 1024,  # 20MB
        'mime_types': ['application/vnd.ms-powerpoint'],
        'icon': 'fas fa-file-powerpoint'
    },
    'archives': {
        'extensions': ARCHIVE_EXTENSIONS,
        'max_size': 50 * 1024 * 1024,  # 50MB
        'mime_types': ['application/zip', 'application/x-rar'],
        'icon': 'fas fa-file-archive'
    },
    'videos': {
        'extensions': VIDEO_EXTENSIONS,
        'max_size': 100 * 1024 * 1024,  # 100MB
        'mime_types': ['video/*'],
        'icon': 'fas fa-video'
    },
    'audio': {
        'extensions': AUDIO_EXTENSIONS,
        'max_size': 25 * 1024 * 1024,  # 25MB
        'mime_types': ['audio/*'],
        'icon': 'fas fa-music'
    }
}


# ====================================
# LÍMITES DEL SISTEMA
# ====================================

# Tamaños de archivo
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB por defecto
MAX_TOTAL_STORAGE_PER_USER = 1024 * 1024 * 1024  # 1GB por usuario

# Límites de entidades
MAX_PROJECTS_PER_ENTREPRENEUR = 5
MAX_ENTREPRENEURS_PER_ALLY = 10
MAX_MEETINGS_PER_DAY = 8
MAX_DOCUMENTS_PER_PROJECT = 50
MAX_TASKS_PER_PROJECT = 100

# Límites de tiempo
MAX_MEETING_DURATION = timedelta(hours=4)
MIN_MEETING_DURATION = timedelta(minutes=15)
MEETING_BUFFER_TIME = timedelta(minutes=15)
MAX_ADVANCE_BOOKING_DAYS = 90

# Límites de contenido
MAX_PROJECT_NAME_LENGTH = 100
MAX_PROJECT_DESCRIPTION_LENGTH = 2000
MAX_MESSAGE_LENGTH = 1000
MAX_COMMENT_LENGTH = 500

# Límites de mentoría
MAX_MENTORSHIP_SESSIONS_PER_MONTH = 8
MAX_MENTORSHIP_HOURS_PER_MONTH = 40
MIN_HOURS_BETWEEN_SESSIONS = 24


# ====================================
# TIPOS DE NOTIFICACIONES
# ====================================

NOTIFICATION_TYPE_INFO = 'info'
NOTIFICATION_TYPE_SUCCESS = 'success'
NOTIFICATION_TYPE_WARNING = 'warning'
NOTIFICATION_TYPE_ERROR = 'error'
NOTIFICATION_TYPE_REMINDER = 'reminder'

NOTIFICATION_TYPES = {
    NOTIFICATION_TYPE_INFO: {
        'name': 'Información',
        'icon': 'fas fa-info-circle',
        'color': 'info'
    },
    NOTIFICATION_TYPE_SUCCESS: {
        'name': 'Éxito',
        'icon': 'fas fa-check-circle',
        'color': 'success'
    },
    NOTIFICATION_TYPE_WARNING: {
        'name': 'Advertencia',
        'icon': 'fas fa-exclamation-triangle',
        'color': 'warning'
    },
    NOTIFICATION_TYPE_ERROR: {
        'name': 'Error',
        'icon': 'fas fa-times-circle',
        'color': 'danger'
    },
    NOTIFICATION_TYPE_REMINDER: {
        'name': 'Recordatorio',
        'icon': 'fas fa-bell',
        'color': 'primary'
    }
}

# Categorías de notificaciones
NOTIFICATION_CATEGORY_MEETING = 'meeting'
NOTIFICATION_CATEGORY_PROJECT = 'project'
NOTIFICATION_CATEGORY_MENTORSHIP = 'mentorship'
NOTIFICATION_CATEGORY_SYSTEM = 'system'
NOTIFICATION_CATEGORY_MESSAGE = 'message'

NOTIFICATION_CATEGORIES = {
    NOTIFICATION_CATEGORY_MEETING: 'Reuniones',
    NOTIFICATION_CATEGORY_PROJECT: 'Proyectos',
    NOTIFICATION_CATEGORY_MENTORSHIP: 'Mentoría',
    NOTIFICATION_CATEGORY_SYSTEM: 'Sistema',
    NOTIFICATION_CATEGORY_MESSAGE: 'Mensajes'
}


# ====================================
# CONFIGURACIONES DE TIEMPO
# ====================================

# Zona horaria principal
TIMEZONE_BOGOTA = pytz.timezone('America/Bogota')
TIMEZONE_UTC = pytz.UTC

# Formatos de fecha y hora
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
TIME_FORMAT = '%H:%M'
HUMAN_DATE_FORMAT = '%d de %B de %Y'
HUMAN_DATETIME_FORMAT = '%d de %B de %Y a las %H:%M'

# Horarios de trabajo
BUSINESS_HOURS_START = 8  # 8:00 AM
BUSINESS_HOURS_END = 18   # 6:00 PM
BUSINESS_DAYS = [0, 1, 2, 3, 4]  # Lunes a Viernes (0=Lunes)

# Duraciones comunes
DURATION_15_MIN = timedelta(minutes=15)
DURATION_30_MIN = timedelta(minutes=30)
DURATION_45_MIN = timedelta(minutes=45)
DURATION_1_HOUR = timedelta(hours=1)
DURATION_2_HOURS = timedelta(hours=2)


# ====================================
# CONFIGURACIONES DE NEGOCIO
# ====================================

BUSINESS_CONSTANTS = {
    # Configuraciones de proyectos
    'project': {
        'min_team_size': 1,
        'max_team_size': 10,
        'required_documents': ['business_plan', 'financial_projection'],
        'success_metrics': ['revenue', 'users', 'funding', 'growth_rate']
    },
    
    # Configuraciones de mentoría
    'mentorship': {
        'session_types': ['individual', 'group', 'workshop'],
        'rating_scale': (1, 5),
        'required_feedback': True,
        'max_consecutive_sessions': 3
    },
    
    # Configuraciones de evaluación
    'evaluation': {
        'criteria': ['innovation', 'market_potential', 'team', 'execution'],
        'scoring_scale': (1, 10),
        'passing_score': 6,
        'reviewer_types': ['peer', 'expert', 'mentor']
    },
    
    # Configuraciones de networking
    'networking': {
        'max_connections_per_month': 50,
        'connection_expiry_days': 30,
        'max_event_attendees': 100
    }
}

# KPIs y métricas
KPI_THRESHOLDS = {
    'entrepreneur_engagement': {
        'low': 0.3,
        'medium': 0.6,
        'high': 0.8
    },
    'project_success_rate': {
        'low': 0.2,
        'medium': 0.5,
        'high': 0.7
    },
    'mentor_effectiveness': {
        'low': 3.0,
        'medium': 4.0,
        'high': 4.5
    },
    'user_satisfaction': {
        'low': 3.0,
        'medium': 4.0,
        'high': 4.5
    }
}

# Configuraciones de analytics
ANALYTICS_CONFIG = {
    'retention_periods': {
        'user_activity': 365,  # días
        'session_logs': 90,
        'error_logs': 30,
        'audit_logs': 1095  # 3 años
    },
    'aggregation_intervals': ['daily', 'weekly', 'monthly', 'quarterly'],
    'key_metrics': [
        'active_users', 'project_completion_rate', 'mentorship_hours',
        'meeting_attendance', 'document_uploads', 'user_engagement'
    ]
}


# ====================================
# CONFIGURACIONES DE SISTEMA
# ====================================

# Paginación
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
VALID_PAGE_SIZES = [10, 20, 50, 100]

# Cache
CACHE_TIMEOUT_SHORT = 300      # 5 minutos
CACHE_TIMEOUT_MEDIUM = 1800    # 30 minutos
CACHE_TIMEOUT_LONG = 3600      # 1 hora
CACHE_TIMEOUT_DAILY = 86400    # 24 horas

# Rate limiting
RATE_LIMIT_DEFAULT = '100 per hour'
RATE_LIMIT_AUTH = '5 per minute'
RATE_LIMIT_API = '1000 per hour'
RATE_LIMIT_UPLOAD = '10 per minute'

# Configuraciones de email
EMAIL_TEMPLATES = {
    'welcome': 'Bienvenido al Ecosistema',
    'password_reset': 'Recuperación de Contraseña',
    'email_verification': 'Verificación de Email',
    'meeting_reminder': 'Recordatorio de Reunión',
    'project_update': 'Actualización de Proyecto',
    'mentorship_request': 'Solicitud de Mentoría'
}


# ====================================
# ESTADOS Y CONFIGURACIONES REGIONALES
# ====================================

# Configuración para Colombia
COLOMBIA_CONFIG = {
    'currency': 'COP',
    'currency_symbol': '$',
    'phone_country_code': '+57',
    'timezone': 'America/Bogota',
    'business_registration_types': [
        'SAS', 'LTDA', 'SA', 'Persona Natural', 'ESAL'
    ],
    'tax_id_types': ['NIT', 'CC', 'CE', 'RUT']
}

# Sectores económicos
ECONOMIC_SECTORS = {
    'technology': 'Tecnología',
    'healthcare': 'Salud',
    'education': 'Educación',
    'finance': 'Finanzas',
    'retail': 'Retail',
    'manufacturing': 'Manufactura',
    'agriculture': 'Agricultura',
    'energy': 'Energía',
    'transportation': 'Transporte',
    'construction': 'Construcción',
    'tourism': 'Turismo',
    'media': 'Medios',
    'consulting': 'Consultoría',
    'other': 'Otro'
}

# Etapas de financiación
FUNDING_STAGES = {
    'pre_seed': 'Pre-semilla',
    'seed': 'Semilla',
    'series_a': 'Serie A',
    'series_b': 'Serie B',
    'series_c': 'Serie C',
    'growth': 'Crecimiento',
    'ipo': 'IPO',
    'bootstrap': 'Autofinanciado'
}


# ====================================
# UTILIDADES DE CONSTANTES
# ====================================

def get_status_choices(status_dict):
    """Obtener choices para formularios Django/WTForms."""
    return [(key, value['name']) for key, value in status_dict.items()]

def get_status_info(status_dict, status_key):
    """Obtener información completa de un estado."""
    return status_dict.get(status_key, {})

def is_valid_transition(status_dict, current_status, target_status):
    """Verificar si una transición de estado es válida."""
    current_info = status_dict.get(current_status, {})
    next_statuses = current_info.get('next_statuses', [])
    return target_status in next_statuses

def get_role_permissions(role):
    """Obtener permisos de un rol específico."""
    return USER_ROLES.get(role, {}).get('permissions', [])

def has_role_permission(role, permission):
    """Verificar si un rol tiene un permiso específico."""
    permissions = get_role_permissions(role)
    return '*' in permissions or permission in permissions


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    # Roles
    'USER_ROLES', 'VALID_ROLES', 'ADMIN_ROLES', 'MENTOR_ROLES', 'MENTEE_ROLES',
    'ADMIN_ROLE', 'ENTREPRENEUR_ROLE', 'ALLY_ROLE', 'CLIENT_ROLE',
    
    # Estados de proyectos
    'PROJECT_STATUSES', 'ACTIVE_PROJECT_STATUSES', 'FINAL_PROJECT_STATUSES',
    'PROJECT_STATUS_IDEA', 'PROJECT_STATUS_VALIDATION', 'PROJECT_STATUS_DEVELOPMENT',
    'PROJECT_STATUS_LAUNCH', 'PROJECT_STATUS_GROWTH', 'PROJECT_STATUS_SCALE', 'PROJECT_STATUS_EXIT',
    
    # Estados de reuniones
    'MEETING_STATUSES', 'EDITABLE_MEETING_STATUSES', 'FINAL_MEETING_STATUSES',
    'MEETING_TYPES',
    
    # Archivos
    'ALLOWED_FILE_EXTENSIONS', 'IMAGE_EXTENSIONS', 'DOCUMENT_EXTENSIONS',
    'FILE_TYPE_CONFIG',
    
    # Límites
    'MAX_FILE_SIZE', 'MAX_PROJECTS_PER_ENTREPRENEUR', 'MAX_ENTREPRENEURS_PER_ALLY',
    'MAX_MEETING_DURATION', 'MIN_MEETING_DURATION',
    
    # Notificaciones
    'NOTIFICATION_TYPES', 'NOTIFICATION_CATEGORIES',
    
    # Tiempo
    'TIMEZONE_BOGOTA', 'DATE_FORMAT', 'DATETIME_FORMAT', 'TIME_FORMAT',
    'BUSINESS_HOURS_START', 'BUSINESS_HOURS_END',
    
    # Negocio
    'BUSINESS_CONSTANTS', 'KPI_THRESHOLDS', 'ANALYTICS_CONFIG',
    'ECONOMIC_SECTORS', 'FUNDING_STAGES', 'COLOMBIA_CONFIG',
    
    # Sistema
    'DEFAULT_PAGE_SIZE', 'CACHE_TIMEOUT_SHORT', 'RATE_LIMIT_DEFAULT',
    
    # Utilidades
    'get_status_choices', 'get_status_info', 'is_valid_transition',
    'get_role_permissions', 'has_role_permission'
]