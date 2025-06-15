"""
Sistema de Utilidades - Ecosistema de Emprendimiento
====================================================

Este módulo proporciona un conjunto completo de utilidades para el manejo
de datos, validaciones, formateo, archivos, criptografía y más funcionalidades
comunes en el ecosistema de emprendimiento.

Uso básico:
-----------
    from app.utils import validators, formatters, DateUtils
    
    # Validar email
    if validators.is_valid_email('user@example.com'):
        print("Email válido")
    
    # Formatear moneda
    price = formatters.format_currency(150000, 'COP')
    
    # Trabajar con fechas
    formatted_date = DateUtils.format_relative(datetime.now())

Categorías de utilidades:
------------------------
- Validadores: Validación de datos de entrada
- Formateadores: Formateo de datos para presentación
- Decoradores: Decoradores para funciones y métodos
- Base de datos: Utilidades para manejo de DB
- Fechas: Manipulación y formateo de fechas
- Archivos: Manejo de archivos y almacenamiento
- Strings: Manipulación de cadenas de texto
- Criptografía: Encriptación y hashing
- Cache: Utilidades de cache y memoización
- Exportación: Exportación de datos (PDF, Excel, etc.)
- Importación: Importación de datos desde archivos
- Notificaciones: Sistema de notificaciones
"""

import logging
import warnings
from typing import Any, Dict, List, Optional, Union

# Configurar logger para el módulo
logger = logging.getLogger(__name__)

# Versión del módulo de utilidades
__version__ = '1.0.0'
__author__ = 'Ecosistema de Emprendimiento'

# ==============================================================================
# IMPORTACIONES CORE (Siempre disponibles)
# ==============================================================================

try:
    from .decorators import (
        # Decoradores de autenticación y autorización
        login_required,
        role_required,
        permission_required,
        admin_required,
        entrepreneur_required,
        ally_required,
        
        # Decoradores de performance
        cache_result,
        rate_limit,
        retry,
        timeout,
        
        # Decoradores de validación
        validate_input,
        validate_json,
        validate_content_type,
        
        # Decoradores de logging
        log_execution_time,
        log_function_call,
        audit_action,
        
        # Decoradores de utilidad
        deprecated,
        singleton,
        property_cached,
    )
    
    logger.debug("Decoradores importados exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando decoradores: {e}")
    # Crear decoradores dummy para evitar errores
    def dummy_decorator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if args else decorator
    
    login_required = role_required = permission_required = dummy_decorator
    admin_required = entrepreneur_required = ally_required = dummy_decorator
    cache_result = rate_limit = retry = timeout = dummy_decorator
    validate_input = validate_json = validate_content_type = dummy_decorator
    log_execution_time = log_function_call = audit_action = dummy_decorator
    deprecated = singleton = property_cached = dummy_decorator

try:
    from .validators import (
        # Validadores básicos
        is_valid_email,
        is_valid_phone,
        is_valid_url,
        is_valid_uuid,
        is_valid_json,
        
        # Validadores de documentos colombianos
        is_valid_cedula,
        is_valid_nit,
        is_valid_rut,
        
        # Validadores de contraseñas
        validate_password_strength,
        check_password_requirements,
        
        # Validadores de archivos
        is_valid_file_extension,
        is_valid_file_size,
        is_safe_filename,
        
        # Validadores de negocio
        is_valid_business_name,
        is_valid_sector,
        is_valid_budget_range,
        
        # Validadores de formularios
        validate_form_data,
        clean_input_data,
        sanitize_html,
        
        # Clases de validación
        EmailValidator,
        PhoneValidator,
        DocumentValidator,
        PasswordValidator,
        FileValidator,
    )
    
    logger.debug("Validadores importados exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando validadores: {e}")
    # Crear validadores dummy
    is_valid_email = is_valid_phone = is_valid_url = lambda x: True
    is_valid_uuid = is_valid_json = lambda x: True
    is_valid_cedula = is_valid_nit = is_valid_rut = lambda x: True
    validate_password_strength = check_password_requirements = lambda x: True
    is_valid_file_extension = is_valid_file_size = is_safe_filename = lambda x: True
    is_valid_business_name = is_valid_sector = is_valid_budget_range = lambda x: True
    validate_form_data = clean_input_data = sanitize_html = lambda x: x

try:
    from .formatters import (
        # Formateadores de moneda
        format_currency,
        format_currency_short,
        parse_currency,
        
        # Formateadores de números
        format_number,
        format_percentage,
        format_file_size,
        format_duration,
        
        # Formateadores de texto
        format_phone_number,
        format_document_number,
        format_business_name,
        format_address,
        
        # Formateadores de fechas (básicos)
        format_date_spanish,
        format_datetime_spanish,
        format_time_ago,
        format_business_hours,
        
        # Formateadores de listas
        format_list_to_string,
        format_tags,
        format_enum_value,
        
        # Clases formateadoras
        CurrencyFormatter,
        NumberFormatter,
        TextFormatter,
        DateFormatter,
    )
    
    logger.debug("Formateadores importados exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando formateadores: {e}")
    # Crear formateadores dummy
    format_currency = format_currency_short = parse_currency = lambda x: str(x)
    format_number = format_percentage = format_file_size = lambda x: str(x)
    format_duration = format_phone_number = format_document_number = lambda x: str(x)
    format_business_name = format_address = lambda x: str(x)
    format_date_spanish = format_datetime_spanish = format_time_ago = lambda x: str(x)
    format_business_hours = format_list_to_string = format_tags = lambda x: str(x)
    format_enum_value = lambda x: str(x)

try:
    from .db_utils import (
        # Utilidades de consulta
        get_or_create,
        bulk_create_or_update,
        safe_delete,
        soft_delete,
        restore_deleted,
        
        # Utilidades de paginación
        paginate_query,
        get_page_info,
        
        # Utilidades de filtrado
        apply_filters,
        build_search_query,
        
        # Utilidades de transacciones
        atomic_transaction,
        rollback_on_error,
        
        # Utilidades de backup
        backup_table,
        restore_table,
        
        # Clases de utilidad
        DatabaseManager,
        QueryBuilder,
        MigrationHelper,
    )
    
    logger.debug("Utilidades de BD importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de BD: {e}")

# ==============================================================================
# IMPORTACIONES DE FECHA Y TIEMPO
# ==============================================================================

try:
    from .date_utils import (
        # Funciones básicas de fecha
        now,
        today,
        yesterday,
        tomorrow,
        
        # Parsing y validación
        parse_date,
        is_valid_date,
        validate_date_range,
        
        # Formateo de fechas
        format_date,
        format_datetime,
        format_time,
        format_relative_date,
        
        # Cálculos de fecha
        add_days,
        subtract_days,
        days_between,
        business_days_between,
        
        # Utilidades de rango
        date_range,
        month_range,
        week_range,
        
        # Utilidades de zona horaria
        convert_timezone,
        get_local_timezone,
        
        # Clase principal
        DateUtils,
    )
    
    logger.debug("Utilidades de fecha importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de fecha: {e}")
    from datetime import datetime, date
    now = datetime.now
    today = date.today
    parse_date = lambda x: datetime.strptime(str(x), '%Y-%m-%d').date()
    format_date = str

# ==============================================================================
# IMPORTACIONES DE STRINGS
# ==============================================================================

try:
    from .string_utils import (
        # Limpieza y normalización
        clean_string,
        normalize_string,
        remove_accents,
        slugify,
        
        # Conversiones de caso
        to_snake_case,
        to_camel_case,
        to_pascal_case,
        to_kebab_case,
        
        # Truncado y resumen
        truncate,
        truncate_words,
        smart_truncate,
        summarize_text,
        
        # Búsqueda y reemplazo
        highlight_text,
        replace_variables,
        extract_mentions,
        extract_hashtags,
        
        # Generación
        generate_random_string,
        generate_slug,
        generate_password,
        
        # Clase principal
        StringUtils,
    )
    
    logger.debug("Utilidades de string importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de string: {e}")
    clean_string = normalize_string = remove_accents = slugify = lambda x: str(x)
    to_snake_case = to_camel_case = to_pascal_case = to_kebab_case = lambda x: str(x)
    truncate = truncate_words = smart_truncate = summarize_text = lambda x: str(x)

# ==============================================================================
# IMPORTACIONES DE ARCHIVOS
# ==============================================================================

try:
    from .file_utils import (
        # Operaciones básicas de archivo
        safe_filename,
        get_file_extension,
        get_file_size,
        get_file_mime_type,
        
        # Validación de archivos
        is_allowed_file,
        is_image_file,
        is_document_file,
        validate_file_upload,
        
        # Procesamiento de imágenes
        resize_image,
        crop_image,
        optimize_image,
        generate_thumbnail,
        
        # Almacenamiento
        save_uploaded_file,
        delete_file,
        move_file,
        copy_file,
        
        # Compresión
        compress_file,
        decompress_file,
        create_zip_archive,
        extract_zip_archive,
        
        # Clase principal
        FileManager,
    )
    
    logger.debug("Utilidades de archivo importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de archivo: {e}")
    safe_filename = get_file_extension = get_file_size = lambda x: str(x)
    is_allowed_file = is_image_file = is_document_file = lambda x: True

# ==============================================================================
# IMPORTACIONES DE CRIPTOGRAFÍA
# ==============================================================================

try:
    from .crypto_utils import (
        # Hashing
        hash_password,
        verify_password,
        generate_salt,
        
        # Encriptación simétrica
        encrypt_data,
        decrypt_data,
        generate_key,
        
        # Tokens y firmas
        generate_token,
        verify_token,
        sign_data,
        verify_signature,
        
        # Utilidades de seguridad
        secure_random_string,
        generate_otp,
        verify_otp,
        
        # Clase principal
        CryptoManager,
    )
    
    logger.debug("Utilidades de criptografía importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de criptografía: {e}")
    import secrets
    import hashlib
    
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(password, hashed):
        return hash_password(password) == hashed
    
    def generate_token(length=32):
        return secrets.token_urlsafe(length)

# ==============================================================================
# IMPORTACIONES DE CACHE
# ==============================================================================

try:
    from .cache_utils import (
        # Cache básico
        cache_get,
        cache_set,
        cache_delete,
        cache_clear,
        
        # Cache con decoradores
        cached,
        cached_property,
        invalidate_cache,
        
        # Cache avanzado
        cache_many,
        cache_increment,
        cache_decrement,
        
        # Clase principal
        CacheManager,
    )
    
    logger.debug("Utilidades de cache importadas exitosamente")
    
except ImportError as e:
    logger.warning(f"Error importando utilidades de cache: {e}")
    cache_get = cache_set = cache_delete = lambda *args, **kwargs: None
    cached = lambda func: func
    CacheManager = type('CacheManager', (), {})

# ==============================================================================
# IMPORTACIONES OPCIONALES (Con manejo de errores)
# ==============================================================================

# Utilidades de exportación (PDF, Excel, etc.)
try:
    from .export_utils import (
        export_to_pdf,
        export_to_excel,
        export_to_csv,
        export_to_json,
        generate_report,
        ExportManager,
    )
    
    from .pdf import (
        PDFGenerator,
        create_pdf_report,
        merge_pdfs,
        split_pdf,
    )
    
    from .excel import (
        ExcelProcessor,
        read_excel_file,
        write_excel_file,
        format_excel_sheet,
    )
    
    EXPORT_AVAILABLE = True
    logger.debug("Utilidades de exportación importadas exitosamente")
    
except ImportError as e:
    logger.info(f"Utilidades de exportación no disponibles: {e}")
    EXPORT_AVAILABLE = False
    export_to_pdf = export_to_excel = export_to_csv = lambda *args: None
    export_to_json = generate_report = lambda *args: None

# Utilidades de importación
try:
    from .import_utils import (
        import_from_csv,
        import_from_excel,
        import_from_json,
        validate_import_data,
        ImportManager,
    )
    
    IMPORT_AVAILABLE = True
    logger.debug("Utilidades de importación importadas exitosamente")
    
except ImportError as e:
    logger.info(f"Utilidades de importación no disponibles: {e}")
    IMPORT_AVAILABLE = False
    import_from_csv = import_from_excel = import_from_json = lambda *args: None

# Utilidades de notificaciones
try:
    from .notifications import (
        send_email_notification,
        send_sms_notification,
        send_push_notification,
        send_slack_notification,
        NotificationManager,
    )
    
    NOTIFICATIONS_AVAILABLE = True
    logger.debug("Utilidades de notificación importadas exitosamente")
    
except ImportError as e:
    logger.info(f"Utilidades de notificación no disponibles: {e}")
    NOTIFICATIONS_AVAILABLE = False
    send_email_notification = send_sms_notification = lambda *args: None
    send_push_notification = send_slack_notification = lambda *args: None

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================

# Configuración por defecto
DEFAULT_CONFIG = {
    'date_format': '%d/%m/%Y',
    'datetime_format': '%d/%m/%Y %H:%M',
    'currency': 'COP',
    'locale': 'es_CO',
    'timezone': 'America/Bogota',
    'file_upload_max_size': 10 * 1024 * 1024,  # 10MB
    'allowed_file_extensions': [
        'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'
    ],
    'cache_timeout': 300,  # 5 minutos
    'password_min_length': 8,
    'max_login_attempts': 5,
}

# Constantes de validación
VALIDATION_PATTERNS = {
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone_colombia': r'^(\+57)?[0-9]{10}$',
    'cedula': r'^[0-9]{8,10}$',
    'nit': r'^[0-9]{9}-[0-9]$',
    'url': r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$',
}

# Constantes de formateo
FORMAT_CONSTANTS = {
    'currency_symbol': '$',
    'decimal_separator': ',',
    'thousands_separator': '.',
    'date_separator': '/',
    'time_separator': ':',
}

# ==============================================================================
# FUNCIONES DE UTILIDAD GLOBALES
# ==============================================================================

def get_version():
    """Obtiene la versión del módulo de utilidades."""
    return __version__

def get_available_features():
    """Obtiene lista de características disponibles."""
    features = {
        'core': True,
        'decorators': 'decorators' in globals(),
        'validators': 'validators' in globals(),
        'formatters': 'formatters' in globals(),
        'db_utils': 'db_utils' in globals(),
        'date_utils': 'DateUtils' in globals(),
        'string_utils': 'StringUtils' in globals(),
        'file_utils': 'FileManager' in globals(),
        'crypto_utils': 'CryptoManager' in globals(),
        'cache_utils': 'CacheManager' in globals(),
        'export': EXPORT_AVAILABLE,
        'import': IMPORT_AVAILABLE,
        'notifications': NOTIFICATIONS_AVAILABLE,
    }
    return features

def configure_utils(config: Dict[str, Any]):
    """
    Configura las utilidades globalmente.
    
    Args:
        config: Diccionario con configuración personalizada
    """
    global DEFAULT_CONFIG
    DEFAULT_CONFIG.update(config)
    logger.info("Configuración de utilidades actualizada")

def get_config(key: str, default: Any = None):
    """
    Obtiene un valor de configuración.
    
    Args:
        key: Clave de configuración
        default: Valor por defecto si no existe
        
    Returns:
        Valor de configuración
    """
    return DEFAULT_CONFIG.get(key, default)

def validate_dependencies():
    """
    Valida que las dependencias necesarias estén instaladas.
    
    Returns:
        Dict con estado de dependencias
    """
    dependencies = {
        'pillow': False,
        'openpyxl': False,
        'reportlab': False,
        'cryptography': False,
        'redis': False,
        'celery': False,
    }
    
    for lib in dependencies.keys():
        try:
            __import__(lib)
            dependencies[lib] = True
        except ImportError:
            pass
    
    return dependencies

def setup_logging(level: str = 'INFO'):
    """
    Configura el logging para las utilidades.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.setLevel(numeric_level)

# ==============================================================================
# EXPORTACIONES PRINCIPALES
# ==============================================================================

# Exportar todas las funciones y clases principales
__all__ = [
    # Información del módulo
    '__version__',
    'get_version',
    'get_available_features',
    'configure_utils',
    'get_config',
    'validate_dependencies',
    'setup_logging',
    
    # Constantes
    'DEFAULT_CONFIG',
    'VALIDATION_PATTERNS',
    'FORMAT_CONSTANTS',
    
    # Decoradores
    'login_required',
    'role_required',
    'permission_required',
    'admin_required',
    'entrepreneur_required',
    'ally_required',
    'cache_result',
    'rate_limit',
    'retry',
    'timeout',
    'validate_input',
    'validate_json',
    'log_execution_time',
    'audit_action',
    'deprecated',
    
    # Validadores
    'is_valid_email',
    'is_valid_phone',
    'is_valid_url',
    'is_valid_cedula',
    'is_valid_nit',
    'validate_password_strength',
    'is_valid_file_extension',
    'is_safe_filename',
    'validate_form_data',
    'clean_input_data',
    'sanitize_html',
    
    # Formateadores
    'format_currency',
    'format_number',
    'format_percentage',
    'format_file_size',
    'format_phone_number',
    'format_date_spanish',
    'format_time_ago',
    
    # Utilidades de fecha
    'DateUtils',
    'now',
    'today',
    'yesterday',
    'tomorrow',
    'parse_date',
    'format_date',
    'format_relative_date',
    'days_between',
    
    # Utilidades de string
    'StringUtils',
    'clean_string',
    'slugify',
    'truncate',
    'to_snake_case',
    'generate_random_string',
    
    # Utilidades de archivo
    'FileManager',
    'safe_filename',
    'get_file_extension',
    'is_allowed_file',
    'save_uploaded_file',
    
    # Utilidades de criptografía
    'CryptoManager',
    'hash_password',
    'verify_password',
    'generate_token',
    'encrypt_data',
    'decrypt_data',
    
    # Utilidades de cache
    'CacheManager',
    'cached',
    'cache_get',
    'cache_set',
    'cache_delete',
    
    # Utilidades de base de datos
    'get_or_create',
    'paginate_query',
    'atomic_transaction',
]

# Agregar exportaciones condicionales
if EXPORT_AVAILABLE:
    __all__.extend([
        'export_to_pdf',
        'export_to_excel',
        'export_to_csv',
        'generate_report',
        'PDFGenerator',
        'ExcelProcessor',
    ])

if IMPORT_AVAILABLE:
    __all__.extend([
        'import_from_csv',
        'import_from_excel',
        'validate_import_data',
        'ImportManager',
    ])

if NOTIFICATIONS_AVAILABLE:
    __all__.extend([
        'send_email_notification',
        'send_sms_notification',
        'NotificationManager',
    ])

# ==============================================================================
# INICIALIZACIÓN
# ==============================================================================

# Log de inicialización
logger.info(f"Módulo de utilidades v{__version__} inicializado")
logger.debug(f"Características disponibles: {get_available_features()}")

# Validar dependencias críticas en modo debug
try:
    if logger.isEnabledFor(logging.DEBUG):
        deps = validate_dependencies()
        missing_deps = [k for k, v in deps.items() if not v]
        if missing_deps:
            logger.debug(f"Dependencias opcionales no disponibles: {missing_deps}")
except Exception as e:
    logger.warning(f"Error validando dependencias: {e}")

# Configurar warnings para dependencias faltantes
warnings.filterwarnings('ignore', category=ImportWarning)
warnings.filterwarnings('ignore', message='.*No module named.*')