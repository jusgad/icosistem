"""
Forms Validators Module

Validadores personalizados para el ecosistema de emprendimiento.
Incluye validaciones específicas del dominio, seguridad y compliance.

Author: jusga
Date: 2025
"""

import re
import logging
import hashlib
import mimetypes
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple
from urllib.parse import urlparse
from decimal import Decimal, InvalidOperation
import dns.resolver
import requests
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType
from email_validator import validate_email, EmailNotValidError
from werkzeug.datastructures import FileStorage
from wtforms.validators import ValidationError, StopValidation
from flask import current_app, g
import pycountry

from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.organization import Organization


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES BASE Y UTILIDADES
# =============================================================================

class BaseValidator:
    """Clase base para validadores personalizados"""
    
    def __init__(self, message: str = None, **kwargs):
        self.message = message
        self.cache = CacheManager()
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __call__(self, form, field):
        """Método principal de validación"""
        try:
            self.validate(form, field)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in validator {self.__class__.__name__}: {e}")
            raise ValidationError(self.message or 'Error de validación')
    
    def validate(self, form, field):
        """Método de validación a implementar en subclases"""
        raise NotImplementedError
    
    def get_localized_message(self, key: str, **kwargs) -> str:
        """Obtiene mensaje localizado"""
        locale = getattr(form, 'locale', 'es') if hasattr(self, 'form') else 'es'
        
        messages = {
            'es': {
                'invalid_format': 'Formato inválido',
                'too_short': 'Muy corto',
                'too_long': 'Muy largo',
                'invalid_range': 'Fuera del rango permitido',
                'already_exists': 'Ya existe',
                'not_found': 'No encontrado',
                'invalid_file': 'Archivo inválido',
                'security_error': 'Error de seguridad',
                'business_rule_violation': 'Viola reglas de negocio'
            },
            'en': {
                'invalid_format': 'Invalid format',
                'too_short': 'Too short',
                'too_long': 'Too long', 
                'invalid_range': 'Out of valid range',
                'already_exists': 'Already exists',
                'not_found': 'Not found',
                'invalid_file': 'Invalid file',
                'security_error': 'Security error',
                'business_rule_violation': 'Violates business rules'
            }
        }
        
        message = messages.get(locale, messages['es']).get(key, key)
        return message.format(**kwargs) if kwargs else message


# =============================================================================
# VALIDADORES DE IDENTIDAD Y DOCUMENTOS
# =============================================================================

class ColombianNIT(BaseValidator):
    """Validador para NIT colombiano con dígito verificador"""
    
    def __init__(self, message: str = None, allow_natural_person: bool = True):
        super().__init__(message)
        self.allow_natural_person = allow_natural_person
    
    def validate(self, form, field):
        if not field.data:
            return
        
        nit = self._clean_nit(field.data)
        
        if not self._validate_format(nit):
            raise ValidationError(
                self.message or 'NIT inválido. Formato: 123456789-0'
            )
        
        if not self._validate_check_digit(nit):
            raise ValidationError(
                self.message or 'Dígito verificador del NIT incorrecto'
            )
        
        # Normalizar el campo con formato estándar
        field.data = self._format_nit(nit)
    
    def _clean_nit(self, nit: str) -> str:
        """Limpia el NIT removiendo caracteres no numéricos"""
        return re.sub(r'[^0-9]', '', nit)
    
    def _validate_format(self, nit: str) -> bool:
        """Valida formato básico del NIT"""
        # NIT debe tener entre 8 y 15 dígitos
        if not re.match(r'^\d{8,15}$', nit):
            return False
        
        # Si no permite persona natural, debe tener al menos 9 dígitos
        if not self.allow_natural_person and len(nit) < 9:
            return False
        
        return True
    
    def _validate_check_digit(self, nit: str) -> bool:
        """Valida dígito verificador del NIT"""
        if len(nit) < 9:
            return True  # Personas naturales sin DV
        
        # Separar número base y dígito verificador
        base_number = nit[:-1]
        check_digit = int(nit[-1])
        
        # Tabla de pesos para el cálculo
        weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        
        # Calcular suma ponderada
        total = 0
        for i, digit in enumerate(reversed(base_number)):
            if i < len(weights):
                total += int(digit) * weights[i]
        
        # Calcular dígito verificador esperado
        remainder = total % 11
        expected_digit = 0 if remainder < 2 else 11 - remainder
        
        return check_digit == expected_digit
    
    def _format_nit(self, nit: str) -> str:
        """Formatea NIT con guión antes del dígito verificador"""
        if len(nit) >= 9:
            return f"{nit[:-1]}-{nit[-1]}"
        return nit


class ColombianCedula(BaseValidator):
    """Validador para cédula de ciudadanía colombiana"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        cedula = re.sub(r'[^0-9]', '', field.data)
        
        if not re.match(r'^\d{7,11}$', cedula):
            raise ValidationError(
                self.message or 'Cédula inválida. Debe tener entre 7 y 11 dígitos'
            )
        
        # Verificar que no sea una secuencia obvia
        if self._is_obvious_sequence(cedula):
            raise ValidationError(
                self.message or 'Número de cédula inválido'
            )
        
        # Normalizar formato
        field.data = cedula
    
    def _is_obvious_sequence(self, cedula: str) -> bool:
        """Verifica si es una secuencia obvia como 111111111"""
        if len(set(cedula)) == 1:  # Todos los dígitos iguales
            return True
        
        # Secuencias ascendentes/descendentes
        if cedula in ['123456789', '987654321']:
            return True
        
        return False


class TaxID(BaseValidator):
    """Validador universal para IDs tributarios por país"""
    
    def __init__(self, country: str = 'CO', message: str = None):
        super().__init__(message)
        self.country = country.upper()
    
    def validate(self, form, field):
        if not field.data:
            return
        
        if self.country == 'CO':
            validator = ColombianNIT()
            validator.validate(form, field)
        elif self.country == 'US':
            self._validate_us_ein(field)
        elif self.country == 'MX':
            self._validate_mexico_rfc(field)
        elif self.country == 'BR':
            self._validate_brazil_cnpj(field)
        else:
            # Validación genérica
            self._validate_generic(field)
    
    def _validate_us_ein(self, field):
        """Valida EIN estadounidense"""
        ein = re.sub(r'[^0-9]', '', field.data)
        if not re.match(r'^\d{9}$', ein):
            raise ValidationError('EIN inválido. Formato: 12-3456789')
        field.data = f"{ein[:2]}-{ein[2:]}"
    
    def _validate_mexico_rfc(self, field):
        """Valida RFC mexicano"""
        rfc = field.data.upper().replace(' ', '')
        # RFC puede ser persona física (13 caracteres) o moral (12 caracteres)
        if not re.match(r'^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$', rfc):
            raise ValidationError('RFC inválido')
        field.data = rfc
    
    def _validate_brazil_cnpj(self, field):
        """Valida CNPJ brasileño"""
        cnpj = re.sub(r'[^0-9]', '', field.data)
        if not re.match(r'^\d{14}$', cnpj):
            raise ValidationError('CNPJ inválido. Debe tener 14 dígitos')
        # Formatear: 12.345.678/0001-95
        field.data = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    
    def _validate_generic(self, field):
        """Validación genérica para otros países"""
        tax_id = re.sub(r'[^A-Z0-9]', '', field.data.upper())
        if len(tax_id) < 5 or len(tax_id) > 20:
            raise ValidationError('ID tributario inválido')
        field.data = tax_id


# =============================================================================
# VALIDADORES DE COMUNICACIÓN
# =============================================================================

class InternationalPhone(BaseValidator):
    """Validador avanzado para números telefónicos internacionales"""
    
    def __init__(self, regions: List[str] = None, types: List[PhoneNumberType] = None, 
                 message: str = None):
        super().__init__(message)
        self.regions = regions or ['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL']
        self.types = types or [PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE]
    
    def validate(self, form, field):
        if not field.data:
            return
        
        try:
            # Intentar parsear el número
            phone_number = phonenumbers.parse(field.data, None)
            
            # Verificar si es válido
            if not phonenumbers.is_valid_number(phone_number):
                raise ValidationError(
                    self.message or 'Número de teléfono inválido'
                )
            
            # Verificar región si está especificada
            if self.regions:
                region = phonenumbers.region_code_for_number(phone_number)
                if region not in self.regions:
                    raise ValidationError(
                        f'Número de teléfono debe ser de: {", ".join(self.regions)}'
                    )
            
            # Verificar tipo de número si está especificado
            if self.types:
                number_type = phonenumbers.number_type(phone_number)
                if number_type not in self.types:
                    type_names = {
                        PhoneNumberType.MOBILE: 'móvil',
                        PhoneNumberType.FIXED_LINE: 'fijo'
                    }
                    allowed_types = [type_names.get(t, str(t)) for t in self.types]
                    raise ValidationError(
                        f'Debe ser un número {" o ".join(allowed_types)}'
                    )
            
            # Normalizar a formato E164
            field.data = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164
            )
            
        except NumberParseException as e:
            error_messages = {
                NumberParseException.INVALID_COUNTRY_CODE: 'Código de país inválido',
                NumberParseException.NOT_A_NUMBER: 'No es un número válido',
                NumberParseException.TOO_SHORT_NSN: 'Número muy corto',
                NumberParseException.TOO_LONG: 'Número muy largo'
            }
            message = error_messages.get(e.error_type, 'Número de teléfono inválido')
            raise ValidationError(self.message or message)


class BusinessEmail(BaseValidator):
    """Validador para emails corporativos (excluye dominios gratuitos)"""
    
    def __init__(self, message: str = None, allow_free_domains: bool = False,
                 check_mx: bool = True):
        super().__init__(message)
        self.allow_free_domains = allow_free_domains
        self.check_mx = check_mx
        
        # Dominios gratuitos comunes
        self.free_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'live.com', 'aol.com', 'icloud.com', 'protonmail.com',
            'mail.com', 'gmx.com', 'yandex.com', 'zoho.com'
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        try:
            # Validación básica de email
            validated_email = validate_email(field.data)
            normalized_email = validated_email.email
            
            # Verificar dominio gratuito
            if not self.allow_free_domains:
                domain = normalized_email.split('@')[1].lower()
                if domain in self.free_domains:
                    raise ValidationError(
                        self.message or 'Use un email corporativo, no gratuito'
                    )
            
            # Verificar registro MX
            if self.check_mx:
                domain = normalized_email.split('@')[1]
                if not self._has_mx_record(domain):
                    raise ValidationError(
                        self.message or 'Dominio de email no válido'
                    )
            
            field.data = normalized_email
            
        except EmailNotValidError as e:
            raise ValidationError(self.message or f'Email inválido: {str(e)}')
    
    def _has_mx_record(self, domain: str) -> bool:
        """Verifica si el dominio tiene registro MX"""
        try:
            dns.resolver.resolve(domain, 'MX')
            return True
        except:
            return False


class SecureURL(BaseValidator):
    """Validador para URLs con verificaciones de seguridad"""
    
    def __init__(self, require_https: bool = False, allow_localhost: bool = False,
                 check_reachable: bool = False, message: str = None):
        super().__init__(message)
        self.require_https = require_https
        self.allow_localhost = allow_localhost
        self.check_reachable = check_reachable
        
        # Dominios peligrosos conocidos
        self.blocked_domains = {
            'bit.ly', 'tinyurl.com', 'short.link',  # Acortadores
            'malware-test.com', 'phishing-test.com'  # Ejemplos de test
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        url = field.data.strip()
        
        # Agregar esquema si no existe
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        try:
            parsed = urlparse(url)
            
            # Verificar esquema
            if parsed.scheme not in ['http', 'https']:
                raise ValidationError('URL debe usar HTTP o HTTPS')
            
            # Verificar HTTPS requerido
            if self.require_https and parsed.scheme != 'https':
                raise ValidationError('URL debe usar HTTPS')
            
            # Verificar localhost
            if not self.allow_localhost:
                localhost_patterns = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
                if any(pattern in parsed.netloc.lower() for pattern in localhost_patterns):
                    raise ValidationError('URLs localhost no permitidas')
            
            # Verificar dominios bloqueados
            domain = parsed.netloc.lower()
            if domain in self.blocked_domains:
                raise ValidationError('Dominio no permitido')
            
            # Verificar accesibilidad
            if self.check_reachable:
                if not self._is_reachable(url):
                    raise ValidationError('URL no accesible')
            
            field.data = url
            
        except ValueError:
            raise ValidationError(self.message or 'URL inválida')
    
    def _is_reachable(self, url: str) -> bool:
        """Verifica si la URL es accesible"""
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code < 400
        except:
            return False


# =============================================================================
# VALIDADORES DE ARCHIVOS AVANZADOS
# =============================================================================

class SecureFileUpload(BaseValidator):
    """Validador avanzado para subida de archivos con seguridad"""
    
    def __init__(self, allowed_extensions: Set[str], max_size: int = 10 * 1024 * 1024,
                 allowed_mimes: Set[str] = None, scan_viruses: bool = False,
                 message: str = None):
        super().__init__(message)
        self.allowed_extensions = {ext.lower() for ext in allowed_extensions}
        self.max_size = max_size
        self.allowed_mimes = allowed_mimes or set()
        self.scan_viruses = scan_viruses
        
        # Extensiones peligrosas
        self.dangerous_extensions = {
            'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jar',
            'php', 'asp', 'aspx', 'jsp', 'py', 'rb', 'pl', 'cgi'
        }
    
    def validate(self, form, field):
        if not field.data or not isinstance(field.data, FileStorage):
            return
        
        file_data = field.data
        
        # Verificar que tiene nombre
        if not file_data.filename:
            raise ValidationError('Archivo debe tener nombre')
        
        filename = file_data.filename.lower()
        
        # Verificar extensión
        if '.' not in filename:
            raise ValidationError('Archivo debe tener extensión')
        
        extension = filename.rsplit('.', 1)[1]
        
        # Verificar extensión peligrosa
        if extension in self.dangerous_extensions:
            raise ValidationError('Tipo de archivo no permitido por seguridad')
        
        # Verificar extensión permitida
        if self.allowed_extensions and extension not in self.allowed_extensions:
            allowed_list = ', '.join(sorted(self.allowed_extensions))
            raise ValidationError(f'Extensiones permitidas: {allowed_list}')
        
        # Verificar tamaño
        file_size = self._get_file_size(file_data)
        if file_size > self.max_size:
            max_mb = self.max_size // (1024 * 1024)
            raise ValidationError(f'Archivo muy grande. Máximo: {max_mb}MB')
        
        # Verificar MIME type
        if self.allowed_mimes:
            mime_type = self._get_mime_type(file_data)
            if mime_type not in self.allowed_mimes:
                raise ValidationError('Tipo de archivo no válido')
        
        # Verificar contenido vs extensión
        if not self._validate_file_content(file_data, extension):
            raise ValidationError('Contenido del archivo no coincide con extensión')
        
        # Escaneo de virus (si está habilitado)
        if self.scan_viruses:
            if not self._scan_for_viruses(file_data):
                raise ValidationError('Archivo rechazado por seguridad')
    
    def _get_file_size(self, file_data: FileStorage) -> int:
        """Obtiene el tamaño del archivo"""
        if hasattr(file_data, 'content_length') and file_data.content_length:
            return file_data.content_length
        
        # Calcular tamaño leyendo el archivo
        file_data.seek(0, 2)  # Ir al final
        size = file_data.tell()
        file_data.seek(0)  # Regresar al inicio
        return size
    
    def _get_mime_type(self, file_data: FileStorage) -> str:
        """Obtiene el MIME type del archivo"""
        # Primero intentar por extensión
        mime_type, _ = mimetypes.guess_type(file_data.filename)
        if mime_type:
            return mime_type
        
        # Intentar detectar por contenido
        file_data.seek(0)
        header = file_data.read(512)
        file_data.seek(0)
        
        # Firmas de archivos comunes
        signatures = {
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'\xff\xd8\xff': 'image/jpeg',
            b'GIF8': 'image/gif',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip'
        }
        
        for signature, mime in signatures.items():
            if header.startswith(signature):
                return mime
        
        return 'application/octet-stream'
    
    def _validate_file_content(self, file_data: FileStorage, extension: str) -> bool:
        """Valida que el contenido coincida con la extensión"""
        expected_mimes = {
            'pdf': ['application/pdf'],
            'jpg': ['image/jpeg'], 'jpeg': ['image/jpeg'],
            'png': ['image/png'],
            'gif': ['image/gif'],
            'doc': ['application/msword'],
            'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            'xls': ['application/vnd.ms-excel'],
            'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        }
        
        if extension not in expected_mimes:
            return True  # No validamos extensiones desconocidas
        
        detected_mime = self._get_mime_type(file_data)
        return detected_mime in expected_mimes[extension]
    
    def _scan_for_viruses(self, file_data: FileStorage) -> bool:
        """Escanea archivo en busca de virus (integrar con antivirus API)"""
        # En producción, integrar con VirusTotal API, ClamAV, etc.
        # Por ahora, solo verificamos patrones básicos
        
        file_data.seek(0)
        content = file_data.read(1024)  # Leer primer KB
        file_data.seek(0)
        
        # Patrones sospechosos básicos
        suspicious_patterns = [
            b'<script', b'javascript:', b'vbscript:', b'onload=',
            b'eval(', b'exec(', b'system(', b'shell_exec'
        ]
        
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if pattern in content_lower:
                logger.warning(f"Suspicious pattern found in uploaded file: {pattern}")
                return False
        
        return True


class ImageValidator(SecureFileUpload):
    """Validador específico para imágenes con verificaciones adicionales"""
    
    def __init__(self, max_width: int = None, max_height: int = None,
                 min_width: int = None, min_height: int = None,
                 max_size: int = 5 * 1024 * 1024, **kwargs):
        
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        allowed_mimes = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp'
        }
        
        super().__init__(
            allowed_extensions=allowed_extensions,
            allowed_mimes=allowed_mimes,
            max_size=max_size,
            **kwargs
        )
        
        self.max_width = max_width
        self.max_height = max_height
        self.min_width = min_width
        self.min_height = min_height
    
    def validate(self, form, field):
        # Validación básica de archivo
        super().validate(form, field)
        
        if not field.data:
            return
        
        # Validar dimensiones de imagen
        self._validate_image_dimensions(field.data)
    
    def _validate_image_dimensions(self, file_data: FileStorage):
        """Valida dimensiones de la imagen"""
        try:
            from PIL import Image
            
            file_data.seek(0)
            image = Image.open(file_data)
            width, height = image.size
            file_data.seek(0)
            
            if self.min_width and width < self.min_width:
                raise ValidationError(f'Imagen muy angosta. Mínimo: {self.min_width}px')
            
            if self.min_height and height < self.min_height:
                raise ValidationError(f'Imagen muy baja. Mínimo: {self.min_height}px')
            
            if self.max_width and width > self.max_width:
                raise ValidationError(f'Imagen muy ancha. Máximo: {self.max_width}px')
            
            if self.max_height and height > self.max_height:
                raise ValidationError(f'Imagen muy alta. Máximo: {self.max_height}px')
                
        except ImportError:
            logger.warning("PIL not available for image validation")
        except Exception as e:
            logger.error(f"Error validating image dimensions: {e}")
            raise ValidationError('Error al validar imagen')


# =============================================================================
# VALIDADORES DE FECHAS Y TIEMPOS
# =============================================================================

class BusinessHours(BaseValidator):
    """Validador para horarios de negocio"""
    
    def __init__(self, start_hour: int = 6, end_hour: int = 22,
                 allow_weekends: bool = True, timezone: str = 'America/Bogota',
                 message: str = None):
        super().__init__(message)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.allow_weekends = allow_weekends
        self.timezone = timezone
    
    def validate(self, form, field):
        if not field.data:
            return
        
        if isinstance(field.data, datetime):
            dt = field.data
        elif isinstance(field.data, str):
            try:
                dt = datetime.fromisoformat(field.data.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError('Formato de fecha/hora inválido')
        else:
            raise ValidationError('Tipo de fecha/hora inválido')
        
        # Verificar horario de negocio
        if dt.hour < self.start_hour or dt.hour >= self.end_hour:
            raise ValidationError(
                f'Horario debe estar entre {self.start_hour}:00 y {self.end_hour}:00'
            )
        
        # Verificar fin de semana
        if not self.allow_weekends and dt.weekday() >= 5:  # Sábado=5, Domingo=6
            raise ValidationError('No se permiten fechas en fin de semana')


class FutureDate(BaseValidator):
    """Validador para fechas futuras con límites"""
    
    def __init__(self, min_days: int = 1, max_days: int = 365,
                 message: str = None):
        super().__init__(message)
        self.min_days = min_days
        self.max_days = max_days
    
    def validate(self, form, field):
        if not field.data:
            return
        
        if isinstance(field.data, datetime):
            target_date = field.data.date()
        elif isinstance(field.data, date):
            target_date = field.data
        else:
            raise ValidationError('Tipo de fecha inválido')
        
        today = date.today()
        min_date = today + timedelta(days=self.min_days)
        max_date = today + timedelta(days=self.max_days)
        
        if target_date < min_date:
            raise ValidationError(
                f'Fecha debe ser al menos {self.min_days} días en el futuro'
            )
        
        if target_date > max_date:
            raise ValidationError(
                f'Fecha no puede ser más de {self.max_days} días en el futuro'
            )


class DateRange(BaseValidator):
    """Validador para rangos de fechas"""
    
    def __init__(self, start_field: str, end_field: str = None,
                 min_duration: timedelta = None, max_duration: timedelta = None,
                 message: str = None):
        super().__init__(message)
        self.start_field = start_field
        self.end_field = end_field
        self.min_duration = min_duration
        self.max_duration = max_duration
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # Este validador debe aplicarse al campo de fecha final
        end_date = field.data
        start_date = getattr(form, self.start_field).data
        
        if not start_date:
            return  # Si no hay fecha inicial, no validamos
        
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        
        if end_date <= start_date:
            raise ValidationError('Fecha final debe ser posterior a la inicial')
        
        duration = end_date - start_date
        
        if self.min_duration and duration < self.min_duration:
            raise ValidationError(
                f'Duración mínima: {self.min_duration.days} días'
            )
        
        if self.max_duration and duration > self.max_duration:
            raise ValidationError(
                f'Duración máxima: {self.max_duration.days} días'
            )


# =============================================================================
# VALIDADORES DE UNICIDAD Y BASE DE DATOS
# =============================================================================

class Unique(BaseValidator):
    """Validador genérico para unicidad en base de datos"""
    
    def __init__(self, model, field: str, message: str = None,
                 filters: Dict[str, Any] = None, case_sensitive: bool = False,
                 exclude_current: bool = False):
        super().__init__(message)
        self.model = model
        self.field = field
        self.filters = filters or {}
        self.case_sensitive = case_sensitive
        self.exclude_current = exclude_current
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # Construir query
        field_attr = getattr(self.model, self.field)
        
        if self.case_sensitive:
            query = self.model.query.filter(field_attr == field.data)
        else:
            query = self.model.query.filter(field_attr.ilike(field.data))
        
        # Aplicar filtros adicionales
        for filter_field, filter_value in self.filters.items():
            filter_attr = getattr(self.model, filter_field)
            query = query.filter(filter_attr == filter_value)
        
        # Excluir registro actual si está en modo edición
        if self.exclude_current and hasattr(form, 'obj') and form.obj:
            query = query.filter(self.model.id != form.obj.id)
        
        # Verificar si existe
        existing = query.first()
        if existing:
            raise ValidationError(
                self.message or f'{self.field.title()} ya existe'
            )


class UniqueEmail(Unique):
    """Validador específico para emails únicos"""
    
    def __init__(self, model=None, message: str = None, **kwargs):
        model = model or User
        message = message or 'Este email ya está registrado'
        super().__init__(model, 'email', message, case_sensitive=False, **kwargs)


class UniqueUsername(Unique):
    """Validador específico para nombres de usuario únicos"""
    
    def __init__(self, model=None, message: str = None, **kwargs):
        model = model or User
        message = message or 'Nombre de usuario no disponible'
        super().__init__(model, 'username', message, case_sensitive=False, **kwargs)


class ExistsInDB(BaseValidator):
    """Validador para verificar que un registro existe en BD"""
    
    def __init__(self, model, field: str = 'id', message: str = None):
        super().__init__(message)
        self.model = model
        self.field = field
    
    def validate(self, form, field):
        if not field.data:
            return
        
        field_attr = getattr(self.model, self.field)
        existing = self.model.query.filter(field_attr == field.data).first()
        
        if not existing:
            model_name = self.model.__name__.lower()
            raise ValidationError(
                self.message or f'{model_name.title()} no encontrado'
            )


# =============================================================================
# VALIDADORES DE REGLAS DE NEGOCIO
# =============================================================================

class EntrepreneurCapacity(BaseValidator):
    """Validador para capacidad de emprendedores"""
    
    def __init__(self, max_projects: int = 3, message: str = None):
        super().__init__(message)
        self.max_projects = max_projects
    
    def validate(self, form, field):
        if not field.data:  # field.data debería ser entrepreneur_id
            return
        
        from app.models.project import Project
        
        # Contar proyectos activos del emprendedor
        active_projects = Project.query.filter(
            Project.entrepreneur_id == field.data,
            Project.status.in_(['active', 'in_progress', 'pending'])
        ).count()
        
        if active_projects >= self.max_projects:
            raise ValidationError(
                self.message or 
                f'Emprendedor ya tiene el máximo de {self.max_projects} proyectos activos'
            )


class MentorAvailability(BaseValidator):
    """Validador para disponibilidad de mentores"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        mentor_id = field.data
        meeting_date = getattr(form, 'scheduled_date', None)
        
        if not meeting_date or not meeting_date.data:
            return
        
        from app.models.meeting import Meeting
        
        # Verificar conflictos de horario
        conflicts = Meeting.query.filter(
            Meeting.mentor_id == mentor_id,
            Meeting.scheduled_date == meeting_date.data,
            Meeting.status.in_(['scheduled', 'in_progress'])
        ).count()
        
        if conflicts > 0:
            raise ValidationError(
                'Mentor no disponible en esa fecha y hora'
            )


class BudgetRange(BaseValidator):
    """Validador para rangos de presupuesto según tipo de proyecto"""
    
    def __init__(self, project_type_field: str = 'project_type', message: str = None):
        super().__init__(message)
        self.project_type_field = project_type_field
        
        # Rangos de presupuesto por tipo de proyecto (en COP)
        self.budget_ranges = {
            'mvp': {'min': 5000000, 'max': 50000000},       # 5M - 50M
            'startup': {'min': 10000000, 'max': 200000000}, # 10M - 200M
            'scale_up': {'min': 50000000, 'max': 1000000000}, # 50M - 1B
            'enterprise': {'min': 100000000, 'max': 5000000000} # 100M - 5B
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        project_type_field = getattr(form, self.project_type_field, None)
        if not project_type_field or not project_type_field.data:
            return
        
        project_type = project_type_field.data
        budget = field.data
        
        if isinstance(budget, str):
            try:
                budget = Decimal(budget.replace(',', '').replace('$', ''))
            except (ValueError, InvalidOperation):
                raise ValidationError('Presupuesto inválido')
        
        if project_type in self.budget_ranges:
            range_info = self.budget_ranges[project_type]
            min_budget = range_info['min']
            max_budget = range_info['max']
            
            if budget < min_budget:
                min_formatted = f"${min_budget:,.0f}"
                raise ValidationError(
                    f'Presupuesto mínimo para {project_type}: {min_formatted}'
                )
            
            if budget > max_budget:
                max_formatted = f"${max_budget:,.0f}"
                raise ValidationError(
                    f'Presupuesto máximo para {project_type}: {max_formatted}'
                )


class IndustryExpertise(BaseValidator):
    """Validador para expertise en industrias específicas"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        mentor_id = getattr(form, 'mentor_id', None)
        if not mentor_id or not mentor_id.data:
            return
        
        required_industry = field.data
        
        from app.models.ally import Ally
        
        mentor = Ally.query.get(mentor_id.data)
        if not mentor:
            return
        
        # Verificar si el mentor tiene expertise en la industria
        if hasattr(mentor, 'industries') and mentor.industries:
            mentor_industries = [i.strip().lower() for i in mentor.industries]
            if required_industry.lower() not in mentor_industries:
                raise ValidationError(
                    f'Mentor no tiene expertise en {required_industry}'
                )


# =============================================================================
# VALIDADORES CONDICIONALES
# =============================================================================

class ConditionalRequired(BaseValidator):
    """Validador que hace requerido un campo según condiciones"""
    
    def __init__(self, condition_field: str, condition_values: List[Any],
                 message: str = None):
        super().__init__(message)
        self.condition_field = condition_field
        self.condition_values = condition_values
    
    def validate(self, form, field):
        condition_field = getattr(form, self.condition_field, None)
        if not condition_field:
            return
        
        if condition_field.data in self.condition_values:
            if not field.data:
                raise ValidationError(
                    self.message or 'Este campo es requerido'
                )


class ConditionalLength(BaseValidator):
    """Validador de longitud condicional"""
    
    def __init__(self, condition_field: str, condition_value: Any,
                 min_length: int = None, max_length: int = None,
                 message: str = None):
        super().__init__(message)
        self.condition_field = condition_field
        self.condition_value = condition_value
        self.min_length = min_length
        self.max_length = max_length
    
    def validate(self, form, field):
        condition_field = getattr(form, self.condition_field, None)
        if not condition_field or condition_field.data != self.condition_value:
            return
        
        if not field.data:
            return
        
        length = len(field.data)
        
        if self.min_length and length < self.min_length:
            raise ValidationError(
                f'Mínimo {self.min_length} caracteres cuando {self.condition_field} es {self.condition_value}'
            )
        
        if self.max_length and length > self.max_length:
            raise ValidationError(
                f'Máximo {self.max_length} caracteres cuando {self.condition_field} es {self.condition_value}'
            )


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Validadores base
    'BaseValidator',
    
    # Validadores de identidad
    'ColombianNIT',
    'ColombianCedula', 
    'TaxID',
    
    # Validadores de comunicación
    'InternationalPhone',
    'BusinessEmail',
    'SecureURL',
    
    # Validadores de archivos
    'SecureFileUpload',
    'ImageValidator',
    
    # Validadores de fechas
    'BusinessHours',
    'FutureDate',
    'DateRange',
    
    # Validadores de base de datos
    'Unique',
    'UniqueEmail',
    'UniqueUsername',
    'ExistsInDB',
    
    # Validadores de reglas de negocio
    'EntrepreneurCapacity',
    'MentorAvailability',
    'BudgetRange',
    'IndustryExpertise',
    
    # Validadores condicionales
    'ConditionalRequired',
    'ConditionalLength'
]