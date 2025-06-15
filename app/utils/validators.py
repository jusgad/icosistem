"""
Validadores del Sistema - Ecosistema de Emprendimiento
=====================================================

Este módulo proporciona un conjunto completo de validadores para datos de entrada,
formularios, documentos colombianos, archivos y lógica de negocio específica
del ecosistema de emprendimiento.

Características principales:
- Validadores básicos (email, teléfono, URL, etc.)
- Validadores específicos para Colombia (cédula, NIT, RUT)
- Validadores de contraseñas con políticas de seguridad
- Validadores de archivos y uploads
- Validadores de negocio (sectores, presupuestos, etc.)
- Sistema de sanitización de datos
- Clases de validación avanzadas

Uso básico:
-----------
    from app.utils.validators import is_valid_email, validate_password_strength
    
    if is_valid_email('usuario@ejemplo.com'):
        print("Email válido")
    
    result = validate_password_strength('MiContraseña123!')
    if result['is_valid']:
        print("Contraseña segura")
"""

import re
import json
import uuid
import logging
import mimetypes
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, date
from urllib.parse import urlparse
from pathlib import Path

# Configurar logger
logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES Y PATRONES DE VALIDACIÓN
# ==============================================================================

# Patrones regex para validaciones básicas
VALIDATION_PATTERNS = {
    # Email - RFC 5322 compliant pero más práctico
    'email': re.compile(
        r'^[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*'
        r'@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$'
    ),
    
    # Teléfonos colombianos
    'phone_colombia': re.compile(r'^(\+57\s?)?([1-8]\d{6,7}|3\d{9})$'),
    'mobile_colombia': re.compile(r'^(\+57\s?)?(3\d{9})$'),
    'landline_colombia': re.compile(r'^(\+57\s?)?([1-8]\d{6,7})$'),
    
    # Documentos colombianos
    'cedula': re.compile(r'^[1-9]\d{6,9}$'),  # 7-10 dígitos, no inicia en 0
    'nit': re.compile(r'^[1-9]\d{8}-[0-9]$'),  # 9 dígitos + dígito verificador
    'passport': re.compile(r'^[A-Z]{2}\d{6}$'),  # Formato pasaporte colombiano
    
    # URLs
    'url': re.compile(
        r'^https?://'  # protocolo
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # dominio
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # puerto opcional
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    ),
    
    # Códigos postales colombianos
    'postal_code': re.compile(r'^\d{6}$'),
    
    # Números de tarjeta de crédito (Luhn algorithm)
    'credit_card': re.compile(r'^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})$'),
    
    # Coordenadas geográficas
    'latitude': re.compile(r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)$'),
    'longitude': re.compile(r'^[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$'),
    
    # Códigos de color hexadecimal
    'hex_color': re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'),
    
    # Nombres de usuario
    'username': re.compile(r'^[a-zA-Z0-9_-]{3,20}$'),
    
    # Slugs para URLs
    'slug': re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$'),
}

# Sectores económicos válidos en Colombia
VALID_BUSINESS_SECTORS = {
    'tecnologia': 'Tecnología e Innovación',
    'agricultura': 'Agricultura y Ganadería',
    'manufactura': 'Manufactura e Industria',
    'servicios': 'Servicios Profesionales',
    'comercio': 'Comercio y Retail',
    'turismo': 'Turismo y Hospitalidad',
    'educacion': 'Educación y Capacitación',
    'salud': 'Salud y Bienestar',
    'construccion': 'Construcción e Inmobiliaria',
    'transporte': 'Transporte y Logística',
    'energia': 'Energía y Sostenibilidad',
    'finanzas': 'Servicios Financieros',
    'alimentario': 'Industria Alimentaria',
    'textil': 'Textil y Confección',
    'creativos': 'Industrias Creativas',
    'mineria': 'Minería y Recursos',
    'telecomunicaciones': 'Telecomunicaciones',
    'consultoria': 'Consultoría y Asesoría',
    'otro': 'Otro'
}

# Rangos de presupuesto válidos (en COP)
VALID_BUDGET_RANGES = {
    'micro': (0, 5_000_000),          # Hasta 5M
    'pequeno': (5_000_001, 25_000_000),  # 5M - 25M
    'mediano': (25_000_001, 100_000_000), # 25M - 100M
    'grande': (100_000_001, 500_000_000), # 100M - 500M
    'corporativo': (500_000_001, float('inf'))  # Más de 500M
}

# Extensiones de archivo permitidas por categoría
ALLOWED_FILE_EXTENSIONS = {
    'image': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'},
    'document': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
    'spreadsheet': {'xls', 'xlsx', 'csv', 'ods'},
    'presentation': {'ppt', 'pptx', 'odp'},
    'archive': {'zip', 'rar', '7z', 'tar', 'gz'},
    'video': {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'},
    'audio': {'mp3', 'wav', 'ogg', 'flac', 'aac'},
}

# Tipos MIME permitidos
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
    'application/pdf', 'application/msword', 
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv', 'text/plain',
    'application/zip', 'application/x-rar-compressed',
}

# Configuración de contraseñas
PASSWORD_CONFIG = {
    'min_length': 8,
    'max_length': 128,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_numbers': True,
    'require_special': True,
    'special_chars': '!@#$%^&*(),.?":{}|<>',
    'forbidden_patterns': ['123456', 'password', 'admin', 'qwerty', '000000'],
    'max_repeated_chars': 3,
}

# ==============================================================================
# VALIDADORES BÁSICOS
# ==============================================================================

def is_valid_email(email: str) -> bool:
    """
    Valida formato de email.
    
    Args:
        email: Dirección de email a validar
        
    Returns:
        True si el email es válido
        
    Examples:
        >>> is_valid_email('usuario@ejemplo.com')
        True
        >>> is_valid_email('email_invalido')
        False
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip().lower()
    
    # Validar longitud
    if len(email) > 254:  # RFC 5321
        return False
    
    # Validar con regex
    if not VALIDATION_PATTERNS['email'].match(email):
        return False
    
    # Validar partes local y dominio
    try:
        local, domain = email.rsplit('@', 1)
        
        # Parte local no puede exceder 64 caracteres
        if len(local) > 64:
            return False
            
        # Dominio debe tener al menos un punto
        if '.' not in domain:
            return False
            
        return True
        
    except ValueError:
        return False

def is_valid_phone(phone: str, country: str = 'CO') -> bool:
    """
    Valida formato de teléfono.
    
    Args:
        phone: Número de teléfono a validar
        country: Código de país (por defecto Colombia)
        
    Returns:
        True si el teléfono es válido
        
    Examples:
        >>> is_valid_phone('3001234567')
        True
        >>> is_valid_phone('+57 300 123 4567')
        True
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Limpiar número (remover espacios, guiones, paréntesis)
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if country.upper() == 'CO':
        return bool(VALIDATION_PATTERNS['phone_colombia'].match(clean_phone))
    
    # Para otros países, validación básica
    return bool(re.match(r'^\+?[1-9]\d{1,14}$', clean_phone))

def is_valid_mobile_phone(phone: str) -> bool:
    """
    Valida que sea un número móvil colombiano.
    
    Args:
        phone: Número de teléfono
        
    Returns:
        True si es móvil válido
    """
    if not phone:
        return False
    
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(VALIDATION_PATTERNS['mobile_colombia'].match(clean_phone))

def is_valid_url(url: str) -> bool:
    """
    Valida formato de URL.
    
    Args:
        url: URL a validar
        
    Returns:
        True si la URL es válida
        
    Examples:
        >>> is_valid_url('https://www.ejemplo.com')
        True
        >>> is_valid_url('not_a_url')
        False
    """
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    
    # Validar con regex
    if not VALIDATION_PATTERNS['url'].match(url):
        return False
    
    # Validar con urlparse para mayor seguridad
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])
    except Exception:
        return False

def is_valid_uuid(uuid_string: str, version: Optional[int] = None) -> bool:
    """
    Valida formato de UUID.
    
    Args:
        uuid_string: String UUID a validar
        version: Versión específica de UUID (1-5)
        
    Returns:
        True si el UUID es válido
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False
    
    try:
        uuid_obj = uuid.UUID(uuid_string)
        if version and uuid_obj.version != version:
            return False
        return True
    except (ValueError, AttributeError):
        return False

def is_valid_json(json_string: str) -> bool:
    """
    Valida si un string es JSON válido.
    
    Args:
        json_string: String a validar
        
    Returns:
        True si es JSON válido
    """
    if not json_string or not isinstance(json_string, str):
        return False
    
    try:
        json.loads(json_string)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

# ==============================================================================
# VALIDADORES DE DOCUMENTOS COLOMBIANOS
# ==============================================================================

def is_valid_cedula(cedula: str) -> bool:
    """
    Valida número de cédula colombiana.
    
    Args:
        cedula: Número de cédula
        
    Returns:
        True si es válida
        
    Examples:
        >>> is_valid_cedula('12345678')
        True
        >>> is_valid_cedula('0123')
        False
    """
    if not cedula or not isinstance(cedula, str):
        return False
    
    # Limpiar y validar formato básico
    clean_cedula = re.sub(r'[\s\.\-]', '', cedula)
    
    if not VALIDATION_PATTERNS['cedula'].match(clean_cedula):
        return False
    
    # Validar longitud (entre 7 y 10 dígitos)
    if not (7 <= len(clean_cedula) <= 10):
        return False
    
    return True

def is_valid_nit(nit: str) -> bool:
    """
    Valida NIT colombiano con dígito verificador.
    
    Args:
        nit: Número de NIT
        
    Returns:
        True si es válido
        
    Examples:
        >>> is_valid_nit('900123456-1')
        True
    """
    if not nit or not isinstance(nit, str):
        return False
    
    # Limpiar formato
    clean_nit = re.sub(r'[\s\.]', '', nit)
    
    # Validar formato básico
    if not VALIDATION_PATTERNS['nit'].match(clean_nit):
        return False
    
    # Separar número y dígito verificador
    number, check_digit = clean_nit.split('-')
    
    # Calcular dígito verificador
    calculated_check = _calculate_nit_check_digit(number)
    
    return str(calculated_check) == check_digit

def _calculate_nit_check_digit(nit_number: str) -> int:
    """
    Calcula el dígito verificador del NIT.
    
    Args:
        nit_number: Número del NIT sin dígito verificador
        
    Returns:
        Dígito verificador calculado
    """
    multipliers = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    
    # Asegurar que el NIT tenga la longitud correcta
    nit_number = nit_number.zfill(15)
    
    total = 0
    for i, digit in enumerate(nit_number):
        if i < len(multipliers):
            total += int(digit) * multipliers[i]
    
    remainder = total % 11
    
    if remainder < 2:
        return remainder
    else:
        return 11 - remainder

def is_valid_rut(rut: str) -> bool:
    """
    Valida RUT (Registro Único Tributario) colombiano.
    
    Args:
        rut: Número de RUT
        
    Returns:
        True si es válido
    """
    if not rut or not isinstance(rut, str):
        return False
    
    # El RUT en Colombia es equivalente al NIT para personas jurídicas
    return is_valid_nit(rut)

def is_valid_passport(passport: str) -> bool:
    """
    Valida formato de pasaporte colombiano.
    
    Args:
        passport: Número de pasaporte
        
    Returns:
        True si es válido
    """
    if not passport or not isinstance(passport, str):
        return False
    
    clean_passport = passport.strip().upper()
    return bool(VALIDATION_PATTERNS['passport'].match(clean_passport))

# ==============================================================================
# VALIDADORES DE CONTRASEÑAS
# ==============================================================================

def validate_password_strength(password: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Valida la fortaleza de una contraseña según políticas configurables.
    
    Args:
        password: Contraseña a validar
        config: Configuración personalizada (opcional)
        
    Returns:
        Diccionario con resultado de validación y detalles
        
    Examples:
        >>> result = validate_password_strength('MiContraseña123!')
        >>> result['is_valid']
        True
    """
    if config is None:
        config = PASSWORD_CONFIG.copy()
    
    result = {
        'is_valid': True,
        'score': 0,
        'errors': [],
        'suggestions': [],
        'strength': 'weak'
    }
    
    if not password or not isinstance(password, str):
        result['is_valid'] = False
        result['errors'].append('La contraseña es requerida')
        return result
    
    # Validar longitud mínima
    if len(password) < config['min_length']:
        result['is_valid'] = False
        result['errors'].append(f'La contraseña debe tener al menos {config["min_length"]} caracteres')
    else:
        result['score'] += 1
    
    # Validar longitud máxima
    if len(password) > config['max_length']:
        result['is_valid'] = False
        result['errors'].append(f'La contraseña no puede exceder {config["max_length"]} caracteres')
    
    # Validar mayúsculas
    if config['require_uppercase'] and not re.search(r'[A-Z]', password):
        result['is_valid'] = False
        result['errors'].append('La contraseña debe contener al menos una letra mayúscula')
        result['suggestions'].append('Agrega al menos una letra mayúscula')
    else:
        result['score'] += 1
    
    # Validar minúsculas
    if config['require_lowercase'] and not re.search(r'[a-z]', password):
        result['is_valid'] = False
        result['errors'].append('La contraseña debe contener al menos una letra minúscula')
        result['suggestions'].append('Agrega al menos una letra minúscula')
    else:
        result['score'] += 1
    
    # Validar números
    if config['require_numbers'] and not re.search(r'\d', password):
        result['is_valid'] = False
        result['errors'].append('La contraseña debe contener al menos un número')
        result['suggestions'].append('Agrega al menos un número')
    else:
        result['score'] += 1
    
    # Validar caracteres especiales
    if config['require_special']:
        special_pattern = f"[{re.escape(config['special_chars'])}]"
        if not re.search(special_pattern, password):
            result['is_valid'] = False
            result['errors'].append('La contraseña debe contener al menos un carácter especial')
            result['suggestions'].append(f'Agrega al menos uno de estos caracteres: {config["special_chars"]}')
        else:
            result['score'] += 1
    
    # Validar patrones prohibidos
    password_lower = password.lower()
    for forbidden in config['forbidden_patterns']:
        if forbidden in password_lower:
            result['is_valid'] = False
            result['errors'].append(f'La contraseña no puede contener "{forbidden}"')
            result['suggestions'].append('Evita patrones comunes y predecibles')
    
    # Validar caracteres repetidos
    if config['max_repeated_chars']:
        for i in range(len(password) - config['max_repeated_chars']):
            if len(set(password[i:i+config['max_repeated_chars']+1])) == 1:
                result['is_valid'] = False
                result['errors'].append(f'No se permiten más de {config["max_repeated_chars"]} caracteres consecutivos iguales')
                break
    
    # Calcular fortaleza
    if result['score'] >= 5:
        result['strength'] = 'very_strong'
    elif result['score'] >= 4:
        result['strength'] = 'strong'
    elif result['score'] >= 3:
        result['strength'] = 'medium'
    elif result['score'] >= 2:
        result['strength'] = 'weak'
    else:
        result['strength'] = 'very_weak'
    
    return result

def check_password_requirements(password: str) -> bool:
    """
    Verifica si una contraseña cumple los requisitos básicos.
    
    Args:
        password: Contraseña a verificar
        
    Returns:
        True si cumple los requisitos
    """
    result = validate_password_strength(password)
    return result['is_valid']

# ==============================================================================
# VALIDADORES DE ARCHIVOS
# ==============================================================================

def is_valid_file_extension(filename: str, allowed_categories: Optional[List[str]] = None) -> bool:
    """
    Valida la extensión de un archivo.
    
    Args:
        filename: Nombre del archivo
        allowed_categories: Categorías permitidas (image, document, etc.)
        
    Returns:
        True si la extensión es válida
        
    Examples:
        >>> is_valid_file_extension('documento.pdf', ['document'])
        True
    """
    if not filename or not isinstance(filename, str):
        return False
    
    # Obtener extensión
    extension = Path(filename).suffix.lower().lstrip('.')
    
    if not extension:
        return False
    
    # Si no se especifican categorías, usar todas
    if allowed_categories is None:
        allowed_categories = list(ALLOWED_FILE_EXTENSIONS.keys())
    
    # Verificar si la extensión está en alguna categoría permitida
    for category in allowed_categories:
        if category in ALLOWED_FILE_EXTENSIONS:
            if extension in ALLOWED_FILE_EXTENSIONS[category]:
                return True
    
    return False

def is_valid_file_size(file_size: int, max_size: Optional[int] = None) -> bool:
    """
    Valida el tamaño de un archivo.
    
    Args:
        file_size: Tamaño del archivo en bytes
        max_size: Tamaño máximo permitido en bytes
        
    Returns:
        True si el tamaño es válido
    """
    if not isinstance(file_size, (int, float)) or file_size < 0:
        return False
    
    if max_size is None:
        max_size = 10 * 1024 * 1024  # 10MB por defecto
    
    return file_size <= max_size

def is_safe_filename(filename: str) -> bool:
    """
    Valida que un nombre de archivo sea seguro.
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        True si el nombre es seguro
    """
    if not filename or not isinstance(filename, str):
        return False
    
    # Verificar caracteres peligrosos
    dangerous_chars = '<>:"/\\|?*'
    if any(char in filename for char in dangerous_chars):
        return False
    
    # Verificar nombres reservados en Windows
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        return False
    
    # Verificar longitud
    if len(filename) > 255:
        return False
    
    # No debe empezar o terminar con punto o espacio
    if filename.startswith('.') or filename.endswith('.') or filename.endswith(' '):
        return False
    
    return True

def validate_file_upload(filename: str, file_size: int, mime_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Validación completa de archivo subido.
    
    Args:
        filename: Nombre del archivo
        file_size: Tamaño en bytes
        mime_type: Tipo MIME del archivo
        
    Returns:
        Diccionario con resultado de validación
    """
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }
    
    # Validar nombre de archivo
    if not is_safe_filename(filename):
        result['is_valid'] = False
        result['errors'].append('Nombre de archivo no seguro')
    
    # Validar extensión
    if not is_valid_file_extension(filename):
        result['is_valid'] = False
        result['errors'].append('Tipo de archivo no permitido')
    
    # Validar tamaño
    if not is_valid_file_size(file_size):
        result['is_valid'] = False
        result['errors'].append('Archivo demasiado grande')
    
    # Validar tipo MIME si se proporciona
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        result['warnings'].append('Tipo MIME no reconocido')
    
    return result

# ==============================================================================
# VALIDADORES DE NEGOCIO
# ==============================================================================

def is_valid_business_name(name: str) -> bool:
    """
    Valida nombre de empresa/emprendimiento.
    
    Args:
        name: Nombre del negocio
        
    Returns:
        True si es válido
    """
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    
    # Longitud mínima y máxima
    if not (2 <= len(name) <= 100):
        return False
    
    # No debe contener solo números
    if name.isdigit():
        return False
    
    # No debe empezar con caracteres especiales
    if name[0] in '!@#$%^&*()[]{}|\\:";\'<>?,./':
        return False
    
    return True

def is_valid_sector(sector: str) -> bool:
    """
    Valida sector económico.
    
    Args:
        sector: Código del sector
        
    Returns:
        True si es válido
    """
    if not sector or not isinstance(sector, str):
        return False
    
    return sector.lower() in VALID_BUSINESS_SECTORS

def is_valid_budget_range(budget_range: str) -> bool:
    """
    Valida rango de presupuesto.
    
    Args:
        budget_range: Código del rango
        
    Returns:
        True si es válido
    """
    if not budget_range or not isinstance(budget_range, str):
        return False
    
    return budget_range.lower() in VALID_BUDGET_RANGES

def validate_budget_amount(amount: Union[int, float], currency: str = 'COP') -> bool:
    """
    Valida monto de presupuesto.
    
    Args:
        amount: Cantidad a validar
        currency: Moneda (por defecto COP)
        
    Returns:
        True si es válido
    """
    if not isinstance(amount, (int, float)) or amount < 0:
        return False
    
    # Para COP, validar rangos razonables
    if currency == 'COP':
        # Entre 100,000 y 10,000,000,000 (10 mil millones)
        return 100_000 <= amount <= 10_000_000_000
    
    # Para otras monedas, validación básica
    return amount > 0

# ==============================================================================
# VALIDADORES DE FORMULARIOS
# ==============================================================================

def validate_form_data(data: Dict[str, Any], rules: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Valida datos de formulario según reglas especificadas.
    
    Args:
        data: Datos del formulario
        rules: Reglas de validación por campo
        
    Returns:
        Diccionario con errores encontrados
        
    Examples:
        >>> rules = {
        ...     'email': {'required': True, 'type': 'email'},
        ...     'name': {'required': True, 'min_length': 2}
        ... }
        >>> errors = validate_form_data({'email': 'test'}, rules)
    """
    errors = {}
    
    for field, field_rules in rules.items():
        field_errors = []
        value = data.get(field)
        
        # Validar campo requerido
        if field_rules.get('required', False):
            if value is None or (isinstance(value, str) and not value.strip()):
                field_errors.append('Este campo es requerido')
                continue
        
        # Si el campo está vacío y no es requerido, saltar otras validaciones
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        
        # Validar tipo
        field_type = field_rules.get('type')
        if field_type == 'email' and not is_valid_email(value):
            field_errors.append('Formato de email inválido')
        elif field_type == 'phone' and not is_valid_phone(value):
            field_errors.append('Formato de teléfono inválido')
        elif field_type == 'url' and not is_valid_url(value):
            field_errors.append('Formato de URL inválido')
        
        # Validar longitud mínima
        min_length = field_rules.get('min_length')
        if min_length and isinstance(value, str) and len(value) < min_length:
            field_errors.append(f'Debe tener al menos {min_length} caracteres')
        
        # Validar longitud máxima
        max_length = field_rules.get('max_length')
        if max_length and isinstance(value, str) and len(value) > max_length:
            field_errors.append(f'No puede exceder {max_length} caracteres')
        
        # Validar valores permitidos
        allowed_values = field_rules.get('allowed_values')
        if allowed_values and value not in allowed_values:
            field_errors.append('Valor no permitido')
        
        # Validar patrón regex
        pattern = field_rules.get('pattern')
        if pattern and isinstance(value, str) and not re.match(pattern, value):
            field_errors.append('Formato inválido')
        
        if field_errors:
            errors[field] = field_errors
    
    return errors

def clean_input_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Limpia y sanitiza datos de entrada.
    
    Args:
        data: Datos a limpiar
        
    Returns:
        Datos limpiados
    """
    cleaned = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            # Remover espacios al inicio y final
            value = value.strip()
            
            # Remover caracteres de control
            value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
            
            # Normalizar espacios múltiples
            value = re.sub(r'\s+', ' ', value)
        
        cleaned[key] = value
    
    return cleaned

def sanitize_html(html_string: str) -> str:
    """
    Sanitiza contenido HTML removiendo elementos peligrosos.
    
    Args:
        html_string: String HTML a sanitizar
        
    Returns:
        HTML sanitizado
    """
    if not html_string or not isinstance(html_string, str):
        return ''
    
    # Lista básica de tags peligrosos
    dangerous_tags = [
        'script', 'style', 'iframe', 'object', 'embed', 'form',
        'input', 'button', 'select', 'textarea', 'link', 'meta'
    ]
    
    # Remover tags peligrosos
    for tag in dangerous_tags:
        pattern = f'<{tag}[^>]*>.*?</{tag}>'
        html_string = re.sub(pattern, '', html_string, flags=re.IGNORECASE | re.DOTALL)
        
        # Remover tags auto-cerrados
        pattern = f'<{tag}[^>]*/?>'
        html_string = re.sub(pattern, '', html_string, flags=re.IGNORECASE)
    
    # Remover atributos de eventos JavaScript
    html_string = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', html_string, flags=re.IGNORECASE)
    
    # Remover javascript: URLs
    html_string = re.sub(r'javascript:', '', html_string, flags=re.IGNORECASE)
    
    return html_string

# ==============================================================================
# CLASES DE VALIDACIÓN AVANZADAS
# ==============================================================================

class EmailValidator:
    """Validador avanzado de emails con configuración personalizable."""
    
    def __init__(self, allow_smtputf8: bool = True, check_deliverability: bool = False):
        self.allow_smtputf8 = allow_smtputf8
        self.check_deliverability = check_deliverability
    
    def validate(self, email: str) -> Dict[str, Any]:
        """
        Validación completa de email.
        
        Args:
            email: Email a validar
            
        Returns:
            Resultado detallado de validación
        """
        result = {
            'is_valid': False,
            'email': email,
            'local': None,
            'domain': None,
            'errors': []
        }
        
        if not email or not isinstance(email, str):
            result['errors'].append('Email requerido')
            return result
        
        email = email.strip().lower()
        result['email'] = email
        
        # Validación básica
        if not is_valid_email(email):
            result['errors'].append('Formato de email inválido')
            return result
        
        # Separar partes
        try:
            local, domain = email.rsplit('@', 1)
            result['local'] = local
            result['domain'] = domain
        except ValueError:
            result['errors'].append('Formato de email inválido')
            return result
        
        # Validaciones adicionales
        if not self.allow_smtputf8 and any(ord(char) > 127 for char in email):
            result['errors'].append('Caracteres no ASCII no permitidos')
        
        if self.check_deliverability:
            # Aquí se podría implementar verificación de DNS/MX
            pass
        
        if not result['errors']:
            result['is_valid'] = True
        
        return result

class PhoneValidator:
    """Validador avanzado de teléfonos."""
    
    def __init__(self, default_country: str = 'CO'):
        self.default_country = default_country
    
    def validate(self, phone: str, country: Optional[str] = None) -> Dict[str, Any]:
        """
        Validación completa de teléfono.
        
        Args:
            phone: Teléfono a validar
            country: Código de país (opcional)
            
        Returns:
            Resultado detallado de validación
        """
        if country is None:
            country = self.default_country
        
        result = {
            'is_valid': False,
            'original': phone,
            'cleaned': None,
            'country': country,
            'type': None,  # mobile, landline
            'errors': []
        }
        
        if not phone:
            result['errors'].append('Teléfono requerido')
            return result
        
        # Limpiar número
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        result['cleaned'] = cleaned
        
        # Validar según país
        if country.upper() == 'CO':
            if is_valid_mobile_phone(cleaned):
                result['type'] = 'mobile'
                result['is_valid'] = True
            elif VALIDATION_PATTERNS['landline_colombia'].match(cleaned):
                result['type'] = 'landline'
                result['is_valid'] = True
            else:
                result['errors'].append('Formato de teléfono colombiano inválido')
        
        return result

class DocumentValidator:
    """Validador de documentos de identidad colombianos."""
    
    def validate_cedula(self, cedula: str) -> Dict[str, Any]:
        """Validación detallada de cédula."""
        result = {
            'is_valid': False,
            'document': cedula,
            'type': 'cedula',
            'errors': []
        }
        
        if not is_valid_cedula(cedula):
            result['errors'].append('Formato de cédula inválido')
        else:
            result['is_valid'] = True
        
        return result
    
    def validate_nit(self, nit: str) -> Dict[str, Any]:
        """Validación detallada de NIT."""
        result = {
            'is_valid': False,
            'document': nit,
            'type': 'nit',
            'check_digit': None,
            'errors': []
        }
        
        if not is_valid_nit(nit):
            result['errors'].append('NIT inválido o dígito verificador incorrecto')
        else:
            result['is_valid'] = True
            # Extraer dígito verificador
            if '-' in nit:
                result['check_digit'] = nit.split('-')[1]
        
        return result

class PasswordValidator:
    """Validador avanzado de contraseñas."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PASSWORD_CONFIG.copy()
    
    def validate(self, password: str) -> Dict[str, Any]:
        """Validación completa de contraseña."""
        return validate_password_strength(password, self.config)
    
    def suggest_improvements(self, password: str) -> List[str]:
        """Genera sugerencias para mejorar la contraseña."""
        result = self.validate(password)
        return result.get('suggestions', [])

class FileValidator:
    """Validador completo de archivos."""
    
    def __init__(self, 
                 allowed_extensions: Optional[List[str]] = None,
                 max_size: int = 10 * 1024 * 1024,
                 allowed_mime_types: Optional[List[str]] = None):
        self.allowed_extensions = allowed_extensions
        self.max_size = max_size
        self.allowed_mime_types = allowed_mime_types or list(ALLOWED_MIME_TYPES)
    
    def validate(self, filename: str, file_size: int, 
                 mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Validación completa de archivo.
        
        Args:
            filename: Nombre del archivo
            file_size: Tamaño en bytes
            mime_type: Tipo MIME
            
        Returns:
            Resultado de validación
        """
        result = {
            'is_valid': True,
            'filename': filename,
            'file_size': file_size,
            'mime_type': mime_type,
            'errors': [],
            'warnings': []
        }
        
        # Validar nombre
        if not is_safe_filename(filename):
            result['is_valid'] = False
            result['errors'].append('Nombre de archivo no seguro')
        
        # Validar extensión
        if self.allowed_extensions:
            extension = Path(filename).suffix.lower().lstrip('.')
            if extension not in self.allowed_extensions:
                result['is_valid'] = False
                result['errors'].append(f'Extensión .{extension} no permitida')
        
        # Validar tamaño
        if not is_valid_file_size(file_size, self.max_size):
            result['is_valid'] = False
            result['errors'].append(f'Archivo demasiado grande (máximo {self.max_size} bytes)')
        
        # Validar tipo MIME
        if mime_type and mime_type not in self.allowed_mime_types:
            result['warnings'].append(f'Tipo MIME {mime_type} no reconocido')
        
        return result

# ==============================================================================
# FUNCIONES DE UTILIDAD
# ==============================================================================

def get_validation_patterns() -> Dict[str, re.Pattern]:
    """Obtiene todos los patrones de validación disponibles."""
    return VALIDATION_PATTERNS.copy()

def get_business_sectors() -> Dict[str, str]:
    """Obtiene lista de sectores económicos válidos."""
    return VALID_BUSINESS_SECTORS.copy()

def get_budget_ranges() -> Dict[str, Tuple[int, float]]:
    """Obtiene rangos de presupuesto válidos."""
    return VALID_BUDGET_RANGES.copy()

def get_allowed_file_extensions() -> Dict[str, set]:
    """Obtiene extensiones de archivo permitidas por categoría."""
    return {k: v.copy() for k, v in ALLOWED_FILE_EXTENSIONS.items()}

# Logging de inicialización
logger.info("Módulo de validadores inicializado correctamente")