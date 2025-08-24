"""
Forms Module Initialization

Módulo central para todos los formularios del ecosistema de emprendimiento.
Incluye importaciones, utilidades, validadores globales y configuración.

Author: jusga
Date: 2025
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional, Union, Type, Tuple
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage
from flask import current_app, request, flash, session, g
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, PasswordField, EmailField, 
    TelField, DateField, DateTimeField, TimeField,
    IntegerField, FloatField, DecimalField,
    BooleanField, RadioField, SelectField, SelectMultipleField,
    HiddenField, SubmitField, FormField, FieldList
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange, Optional,
    Regexp, URL, ValidationError, EqualTo, InputRequired
)
from wtforms.widgets import TextArea, Select, CheckboxInput, RadioInput
from babel import Locale
from babel.dates import format_date, format_datetime, format_time
import phonenumbers
from phonenumbers import NumberParseException

from app.core.exceptions import ValidationError as AppValidationError
from app.utils.decorators import rate_limit
from app.models.user import User


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACIÓN GLOBAL DE FORMULARIOS
# =============================================================================

class FormConfig:
    """Configuración global para formularios"""
    
    # Configuración de archivos
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {
        'images': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
        'spreadsheets': {'xls', 'xlsx', 'csv'},
        'presentations': {'ppt', 'pptx'},
        'archives': {'zip', 'rar', '7z'},
        'all': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx', 
               'txt', 'rtf', 'xls', 'xlsx', 'csv', 'ppt', 'pptx', 'zip'}
    }
    
    # Configuración de validación
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 2000
    MAX_COMMENT_LENGTH = 500
    
    # Patrones de validación
    PATTERNS = {
        'phone': r'^\+?[1-9]\d{1,14}$',
        'username': r'^[a-zA-Z0-9_]{3,30}$',
        'slug': r'^[a-z0-9-]+$',
        'tax_id': r'^[0-9]{10,15}$',
        'postal_code': r'^[0-9]{5,10}$'
    }
    
    # Configuración de internacionalización
    SUPPORTED_LOCALES = ['es', 'en', 'pt']
    DEFAULT_LOCALE = 'es'
    
    # Rate limiting para formularios
    RATE_LIMITS = {
        'login': {'limit': 5, 'window': 900},  # 5 intentos por 15 min
        'register': {'limit': 3, 'window': 3600},  # 3 registros por hora
        'contact': {'limit': 5, 'window': 3600},  # 5 mensajes por hora
        'password_reset': {'limit': 3, 'window': 3600}  # 3 resets por hora
    }


# =============================================================================
# CLASE BASE PARA FORMULARIOS
# =============================================================================

class BaseForm(FlaskForm):
    """
    Clase base para todos los formularios del sistema.
    Incluye funcionalidades comunes y utilidades.
    """
    
    class Meta:
        csrf = True
        csrf_time_limit = timedelta(hours=1)
        csrf_secret = lambda: current_app.config.get('SECRET_KEY')
    
    def __init__(self, *args, **kwargs):
        """Inicialización mejorada del formulario"""
        # Configurar locale desde request o usuario
        self._setup_locale()
        
        # Configurar timezone
        self._setup_timezone()
        
        super().__init__(*args, **kwargs)
        
        # Aplicar configuraciones post-inicialización
        self._post_init_setup()
    
    def _setup_locale(self):
        """Configura el locale del formulario"""
        # Intentar obtener locale del usuario autenticado
        if hasattr(g, 'current_user') and g.current_user.is_authenticated:
            self.locale = getattr(g.current_user, 'locale', FormConfig.DEFAULT_LOCALE)
        else:
            # Usar locale de la sesión o por defecto
            self.locale = session.get('locale', FormConfig.DEFAULT_LOCALE)
    
    def _setup_timezone(self):
        """Configura la zona horaria del formulario"""
        if hasattr(g, 'current_user') and g.current_user.is_authenticated:
            self.timezone = getattr(g.current_user, 'timezone', 'UTC')
        else:
            self.timezone = session.get('timezone', 'UTC')
    
    def _post_init_setup(self):
        """Configuración posterior a la inicialización"""
        # Aplicar clases CSS a los campos
        self._apply_field_classes()
        
        # Configurar placeholders dinámicos
        self._setup_placeholders()
        
        # Configurar mensajes de error personalizados
        self._setup_error_messages()
    
    def _apply_field_classes(self):
        """Aplica clases CSS automáticamente a los campos"""
        css_classes = {
            StringField: 'form-control',
            TextAreaField: 'form-control',
            PasswordField: 'form-control',
            EmailField: 'form-control',
            TelField: 'form-control',
            DateField: 'form-control',
            DateTimeField: 'form-control',
            TimeField: 'form-control',
            IntegerField: 'form-control',
            FloatField: 'form-control',
            DecimalField: 'form-control',
            SelectField: 'form-select',
            SelectMultipleField: 'form-select',
            FileField: 'form-control',
            BooleanField: 'form-check-input'
        }
        
        for field in self:
            field_type = type(field)
            css_class = css_classes.get(field_type, 'form-control')
            
            # Agregar clase si no existe
            if hasattr(field.widget, 'html_params'):
                current_class = field.render_kw.get('class', '') if field.render_kw else ''
                if css_class not in current_class:
                    if not field.render_kw:
                        field.render_kw = {}
                    field.render_kw['class'] = f"{current_class} {css_class}".strip()
    
    def _setup_placeholders(self):
        """Configura placeholders dinámicos basados en el locale"""
        placeholder_map = {
            'es': {
                'email': 'ejemplo@correo.com',
                'phone': '+57 300 123 4567',
                'name': 'Ingrese su nombre',
                'password': 'Mínimo 8 caracteres',
                'username': 'Nombre de usuario único'
            },
            'en': {
                'email': 'example@email.com',
                'phone': '+1 555 123 4567',
                'name': 'Enter your name',
                'password': 'Minimum 8 characters',
                'username': 'Unique username'
            }
        }
        
        placeholders = placeholder_map.get(self.locale, placeholder_map['es'])
        
        for field in self:
            field_name = field.name.lower()
            if field_name in placeholders and not field.render_kw.get('placeholder'):
                if not field.render_kw:
                    field.render_kw = {}
                field.render_kw['placeholder'] = placeholders[field_name]
    
    def _setup_error_messages(self):
        """Configura mensajes de error personalizados"""
        error_messages = {
            'es': {
                'required': 'Este campo es obligatorio',
                'email': 'Ingrese un email válido',
                'length': 'Longitud inválida',
                'number_range': 'Número fuera del rango permitido',
                'url': 'URL inválida',
                'regexp': 'Formato inválido'
            },
            'en': {
                'required': 'This field is required',
                'email': 'Enter a valid email',
                'length': 'Invalid length',
                'number_range': 'Number out of valid range',
                'url': 'Invalid URL',
                'regexp': 'Invalid format'
            }
        }
        
        messages = error_messages.get(self.locale, error_messages['es'])
        
        # Aplicar mensajes a validadores
        for field in self:
            for validator in field.validators:
                validator_type = type(validator).__name__.lower()
                if validator_type in messages:
                    if hasattr(validator, 'message') and not validator.message:
                        validator.message = messages[validator_type]
    
    def validate(self, **kwargs):
        """Validación mejorada con logging y rate limiting"""
        # Aplicar rate limiting si está configurado
        form_name = self.__class__.__name__.lower().replace('form', '')
        if form_name in FormConfig.RATE_LIMITS:
            if not self._check_rate_limit(form_name):
                flash('Demasiados intentos. Intente más tarde.', 'error')
                return False
        
        # Validación estándar
        valid = super().validate(**kwargs)
        
        # Log de errores de validación
        if not valid:
            self._log_validation_errors()
        
        return valid
    
    def _check_rate_limit(self, form_name: str) -> bool:
        """Verifica rate limiting para el formulario"""
        from app.utils.cache_utils import CacheManager
        
        cache = CacheManager()
        config = FormConfig.RATE_LIMITS[form_name]
        
        # Usar IP como identificador
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        cache_key = f"form_rate_limit_{form_name}_{client_ip}"
        
        current_count = cache.get(cache_key) or 0
        
        if current_count >= config['limit']:
            return False
        
        cache.set(cache_key, current_count + 1, timeout=config['window'])
        return True
    
    def _log_validation_errors(self):
        """Log de errores de validación para debugging"""
        form_name = self.__class__.__name__
        errors = []
        
        for field_name, field_errors in self.errors.items():
            for error in field_errors:
                errors.append(f"{field_name}: {error}")
        
        logger.info(f"Form validation failed - {form_name}: {'; '.join(errors)}")
    
    def get_errors_dict(self) -> Dict[str, List[str]]:
        """Retorna errores en formato diccionario"""
        return dict(self.errors)
    
    def get_errors_list(self) -> List[str]:
        """Retorna todos los errores como lista plana"""
        errors = []
        for field_errors in self.errors.values():
            errors.extend(field_errors)
        return errors
    
    def has_file_fields(self) -> bool:
        """Verifica si el formulario tiene campos de archivo"""
        return any(isinstance(field, FileField) for field in self)
    
    def get_changed_fields(self, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """Retorna campos que han cambiado respecto a datos originales"""
        changed = {}
        for field in self:
            if field.name in original_data:
                if field.data != original_data[field.name]:
                    changed[field.name] = {
                        'old': original_data[field.name],
                        'new': field.data
                    }
        return changed


# =============================================================================
# VALIDADORES PERSONALIZADOS
# =============================================================================

class PhoneNumber:
    """Validador para números telefónicos internacionales"""
    
    def __init__(self, message=None, region=None):
        self.message = message or 'Número de teléfono inválido'
        self.region = region
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        try:
            phone_number = phonenumbers.parse(field.data, self.region)
            if not phonenumbers.is_valid_number(phone_number):
                raise ValidationError(self.message)
            
            # Formatear número a formato E164
            field.data = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164
            )
            
        except NumberParseException:
            raise ValidationError(self.message)


class TaxID:
    """Validador para números de identificación tributaria"""
    
    def __init__(self, country='CO', message=None):
        self.country = country
        self.message = message or 'Número de identificación tributaria inválido'
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        # Implementar validación específica por país
        if self.country == 'CO':
            self._validate_colombia_nit(field.data)
        elif self.country == 'US':
            self._validate_us_ein(field.data)
        # Agregar más países según necesidad
    
    def _validate_colombia_nit(self, nit: str):
        """Valida NIT colombiano"""
        # Remover puntos y guiones
        nit = re.sub(r'[.-]', '', nit)
        
        if not re.match(r'^\d{8,15}$', nit):
            raise ValidationError(self.message)
        
        # Validar dígito de verificación si está presente
        if len(nit) >= 10:
            self._validate_nit_check_digit(nit)
    
    def _validate_nit_check_digit(self, nit: str):
        """Valida dígito de verificación del NIT"""
        weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        nit_digits = [int(d) for d in nit[:-1]]
        check_digit = int(nit[-1])
        
        total = sum(d * w for d, w in zip(reversed(nit_digits), weights))
        remainder = total % 11
        
        if remainder < 2:
            expected = remainder
        else:
            expected = 11 - remainder
        
        if check_digit != expected:
            raise ValidationError(self.message)
    
    def _validate_us_ein(self, ein: str):
        """Valida EIN estadounidense"""
        ein = re.sub(r'[.-]', '', ein)
        if not re.match(r'^\d{9}$', ein):
            raise ValidationError(self.message)


class SecurePassword:
    """Validador para contraseñas seguras"""
    
    def __init__(self, message=None, min_length=8, require_uppercase=True,
                 require_lowercase=True, require_digits=True, require_symbols=True):
        self.message = message or 'La contraseña no cumple los requisitos de seguridad'
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_symbols = require_symbols
    
    def __call__(self, form, field):
        password = field.data
        if not password:
            return
        
        errors = []
        
        if len(password) < self.min_length:
            errors.append(f'Mínimo {self.min_length} caracteres')
        
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append('Debe contener al menos una mayúscula')
        
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append('Debe contener al menos una minúscula')
        
        if self.require_digits and not re.search(r'\d', password):
            errors.append('Debe contener al menos un número')
        
        if self.require_symbols and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('Debe contener al menos un símbolo especial')
        
        # Verificar contraseñas comunes
        if self._is_common_password(password):
            errors.append('Contraseña muy común, elija otra')
        
        if errors:
            raise ValidationError(f"{self.message}: {'; '.join(errors)}")
    
    def _is_common_password(self, password: str) -> bool:
        """Verifica si es una contraseña común"""
        common_passwords = {
            '12345678', 'password', 'password123', 'admin123', 
            'qwerty123', '123456789', 'colombia123', 'empresa123'
        }
        return password.lower() in common_passwords


class UniqueEmail:
    """Validador para emails únicos en el sistema"""
    
    def __init__(self, model=None, field=None, message=None, user_id=None):
        self.model = model or User
        self.field = field or 'email'
        self.message = message or 'Este email ya está registrado'
        self.user_id = user_id
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        query = self.model.query.filter(
            getattr(self.model, self.field) == field.data
        )
        
        # Excluir el usuario actual en caso de edición
        if self.user_id:
            query = query.filter(self.model.id != self.user_id)
        
        if query.first():
            raise ValidationError(self.message)


class FileSize:
    """Validador para tamaño de archivos"""
    
    def __init__(self, max_size, message=None):
        self.max_size = max_size
        self.message = message or f'El archivo no debe superar {max_size // (1024*1024)}MB'
    
    def __call__(self, form, field):
        if not field.data:
            return
        
        if isinstance(field.data, FileStorage):
            # Para archivos en memory
            if hasattr(field.data, 'content_length') and field.data.content_length:
                if field.data.content_length > self.max_size:
                    raise ValidationError(self.message)
            else:
                # Leer archivo para obtener tamaño
                field.data.seek(0, 2)  # Ir al final
                size = field.data.tell()
                field.data.seek(0)  # Regresar al inicio
                
                if size > self.max_size:
                    raise ValidationError(self.message)


# =============================================================================
# CAMPOS PERSONALIZADOS
# =============================================================================

class CurrencyField(DecimalField):
    """Campo para valores monetarios"""
    
    def __init__(self, currency='USD', **kwargs):
        self.currency = currency
        kwargs.setdefault('places', 2)
        kwargs.setdefault('rounding', None)
        super().__init__(**kwargs)
    
    def process_formdata(self, valuelist):
        if valuelist:
            # Remover símbolos de moneda y comas
            value = valuelist[0]
            value = re.sub(r'[^\d.,\-]', '', value)
            value = value.replace(',', '')
            valuelist = [value]
        
        super().process_formdata(valuelist)


class TagsField(StringField):
    """Campo para tags separados por comas"""
    
    def _value(self):
        if self.data:
            if isinstance(self.data, list):
                return ', '.join(self.data)
            return self.data
        return ''
    
    def process_formdata(self, valuelist):
        if valuelist:
            tags = [tag.strip() for tag in valuelist[0].split(',')]
            self.data = [tag for tag in tags if tag]
        else:
            self.data = []


class PhoneField(TelField):
    """Campo especializado para números telefónicos"""
    
    def __init__(self, region='CO', **kwargs):
        self.region = region
        super().__init__(**kwargs)
        
        # Agregar validador automáticamente
        self.validators.append(PhoneNumber(region=region))
    
    def process_formdata(self, valuelist):
        super().process_formdata(valuelist)
        
        # Formatear número si es válido
        if self.data:
            try:
                phone_number = phonenumbers.parse(self.data, self.region)
                if phonenumbers.is_valid_number(phone_number):
                    self.data = phonenumbers.format_number(
                        phone_number, phonenumbers.PhoneNumberFormat.E164
                    )
            except NumberParseException:
                pass


class DateTimeLocalField(DateTimeField):
    """Campo para datetime con timezone local"""
    
    def __init__(self, timezone='UTC', **kwargs):
        self.timezone = timezone
        super().__init__(**kwargs)
    
    def process_formdata(self, valuelist):
        super().process_formdata(valuelist)
        
        # Ajustar timezone si es necesario
        if self.data and self.timezone != 'UTC':
            # Implementar conversión de timezone
            pass


# =============================================================================
# UTILIDADES PARA FORMULARIOS
# =============================================================================

def get_form_errors(form: FlaskForm) -> Dict[str, List[str]]:
    """Extrae errores de formulario en formato JSON"""
    errors = {}
    for field_name, field_errors in form.errors.items():
        errors[field_name] = field_errors
    return errors


def flash_form_errors(form: FlaskForm, category: str = 'error') -> None:
    """Muestra errores de formulario usando flash messages"""
    for field_name, field_errors in form.errors.items():
        for error in field_errors:
            field_label = getattr(form[field_name], 'label', field_name)
            flash(f"{field_label}: {error}", category)


def populate_form_from_object(form: FlaskForm, obj: Any, 
                            exclude: List[str] = None) -> None:
    """Popula formulario desde objeto con campos excluidos"""
    exclude = exclude or []
    
    for field in form:
        if field.name not in exclude and hasattr(obj, field.name):
            field.data = getattr(obj, field.name)


def form_to_dict(form: FlaskForm, exclude: List[str] = None) -> Dict[str, Any]:
    """Convierte formulario a diccionario"""
    exclude = exclude or ['csrf_token', 'submit']
    
    data = {}
    for field in form:
        if field.name not in exclude:
            data[field.name] = field.data
    
    return data


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Valida extensión de archivo"""
    if not filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return extension in allowed_extensions


def get_file_size_mb(file_storage: FileStorage) -> float:
    """Obtiene tamaño de archivo en MB"""
    if not file_storage:
        return 0
    
    file_storage.seek(0, 2)  # Ir al final
    size = file_storage.tell()
    file_storage.seek(0)  # Regresar al inicio
    
    return size / (1024 * 1024)


# =============================================================================
# DECORADORES PARA FORMULARIOS
# =============================================================================

def form_rate_limit(form_name: str):
    """Decorador para aplicar rate limiting a formularios"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if form_name in FormConfig.RATE_LIMITS:
                config = FormConfig.RATE_LIMITS[form_name]
                
                # Aplicar rate limiting
                from app.utils.decorators import rate_limit
                rate_limited_func = rate_limit(
                    limit=config['limit'],
                    window=config['window'],
                    key_func=lambda: request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                )(func)
                
                return rate_limited_func(*args, **kwargs)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def csrf_exempt(func):
    """Decorador para eximir formularios de CSRF"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Deshabilitar CSRF temporalmente
        old_csrf_enabled = current_app.config.get('WTF_CSRF_ENABLED', True)
        current_app.config['WTF_CSRF_ENABLED'] = False
        
        try:
            return func(*args, **kwargs)
        finally:
            current_app.config['WTF_CSRF_ENABLED'] = old_csrf_enabled
    
    return wrapper


# =============================================================================
# IMPORTACIONES DE FORMULARIOS ESPECÍFICOS
# =============================================================================

# Importar formularios después de definir clases base para evitar imports circulares
try:
    # Formularios de autenticación
    from .auth import (
        LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm,
        ChangePasswordForm, TwoFactorForm, EmailVerificationForm
    )
    
    # Formularios de administración
    from .admin import (
        AdminUserCreateForm, AdminUserEditForm, AdminOrganizationForm, AdminProgramForm,
        AdminSettingsForm, AdminReportForm, AdminBulkUserForm
    )
    
    # Formularios de emprendedores
    from .entrepreneur import (
        EntrepreneurProfileForm, ProjectCreateForm, ProjectUpdateForm,
        MilestoneForm, PitchDeckForm, BusinessPlanForm
    )
    
    # Formularios de aliados/mentores
    from .ally import (
        AllyProfileForm, MentorshipSessionForm, AvailabilityForm,
        ExpertiseForm, HourLogForm
    )
    
    # Formularios de clientes/stakeholders
    from .client import (
        ClientProfileForm, FeedbackForm, AssessmentForm,
        ImpactReportForm
    )
    
    # Formularios de proyectos
    from .project import (
        ProjectForm, ProjectPhaseForm, ResourceRequestForm,
        TeamMemberForm, InvestmentRequestForm
    )
    
    # Formularios de reuniones
    from .meeting import (
        MeetingScheduleForm, MeetingUpdateForm, MeetingFeedbackForm,
        RecurringMeetingForm, MeetingNotesForm
    )
    
    # Formulario base y validadores
    from .base import BaseForm as ImportedBaseForm
    from .validators import *
    
    logger.info("All forms imported successfully")
    
except ImportError as e:
    logger.warning(f"Some forms could not be imported: {e}")


# =============================================================================
# EXPORTACIONES PÚBLICAS
# =============================================================================

__all__ = [
    # Clases base
    'BaseForm',
    'FormConfig',
    
    # Validadores personalizados
    'PhoneNumber',
    'TaxID', 
    'SecurePassword',
    'UniqueEmail',
    'FileSize',
    
    # Campos personalizados
    'CurrencyField',
    'TagsField',
    'PhoneField',
    'DateTimeLocalField',
    
    # Utilidades
    'get_form_errors',
    'flash_form_errors',
    'populate_form_from_object',
    'form_to_dict',
    'validate_file_extension',
    'get_file_size_mb',
    
    # Decoradores
    'form_rate_limit',
    'csrf_exempt',
    
    # Formularios importados (si están disponibles)
    'LoginForm', 'RegisterForm', 'ForgotPasswordForm', 'ResetPasswordForm',
    'AdminUserCreateForm', 'AdminUserEditForm', 'AdminOrganizationForm', 'AdminProgramForm',
    'EntrepreneurProfileForm', 'ProjectCreateForm', 'ProjectUpdateForm',
    'AllyProfileForm', 'MentorshipSessionForm', 'AvailabilityForm',
    'ClientProfileForm', 'FeedbackForm', 'AssessmentForm',
    'ProjectForm', 'ProjectPhaseForm', 'ResourceRequestForm',
    'MeetingScheduleForm', 'MeetingUpdateForm', 'MeetingFeedbackForm'
]


# =============================================================================
# CONFIGURACIÓN DE INICIALIZACIÓN
# =============================================================================

def init_forms(app):
    """Inicializa configuración de formularios para la aplicación"""
    
    # Configurar CSRF
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Configurar opciones de formularios
    app.config.setdefault('WTF_CSRF_ENABLED', True)
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)  # 1 hora
    app.config.setdefault('MAX_CONTENT_LENGTH', FormConfig.MAX_FILE_SIZE)
    
    # Registrar filtros Jinja2 para formularios
    @app.template_filter('form_errors')
    def form_errors_filter(form):
        """Filtro para mostrar errores de formulario"""
        return get_form_errors(form)
    
    @app.template_filter('field_class')
    def field_class_filter(field, additional_classes=''):
        """Filtro para agregar clases CSS a campos"""
        base_class = 'form-control'
        if hasattr(field, 'errors') and field.errors:
            base_class += ' is-invalid'
        
        if additional_classes:
            base_class += f' {additional_classes}'
        
        return base_class
    
    # Registrar funciones globales para templates
    @app.template_global()
    def render_field(field, **kwargs):
        """Función global para renderizar campos con clases automáticas"""
        css_class = kwargs.get('class', '')
        
        if hasattr(field, 'errors') and field.errors:
            css_class += ' is-invalid'
        
        kwargs['class'] = css_class.strip()
        return field(**kwargs)
    
    logger.info("Forms module initialized successfully")


# Configuración automática si se importa directamente
if __name__ != '__main__':
    logger.info(f"Forms module loaded - {len(__all__)} exports available")