"""
Forms Base Module

Clases base y mixins reutilizables para todos los formularios del ecosistema.
Incluye funcionalidades avanzadas, validaciones y utilidades comunes.

Author: jusga
Date: 2025
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, date, time
from typing import Any, Optional, Union, Type, Callable
from functools import wraps
from werkzeug.datastructures import FileStorage
from flask import current_app, request, flash, session, g, url_for
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
    DataRequired, Email, Length, NumberRange, Optional as WTFOptional,
    Regexp, URL, ValidationError, EqualTo, InputRequired, StopValidation
)
from wtforms.widgets import TextArea, Select, CheckboxInput, RadioInput, Input
from wtforms.meta import DefaultMeta
from babel import Locale
from babel.dates import format_date, format_datetime, format_time
import bleach
from markupsafe import Markup

from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager
from app.utils.decorators import retry_on_failure
from app.models.user import User


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACIÓN Y CONSTANTES
# =============================================================================

class FormConstants:
    """Constantes para formularios"""
    
    # Límites de longitud
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 2000
    MAX_COMMENT_LENGTH = 1000
    MAX_TITLE_LENGTH = 200
    
    # Patrones de validación
    USERNAME_PATTERN = r'^[a-zA-Z0-9_.-]{3,50}$'
    SLUG_PATTERN = r'^[a-z0-9-]+$'
    PHONE_PATTERN = r'^\+?[1-9]\d{1,14}$'
    TAX_ID_PATTERN = r'^[0-9]{8,15}$'
    
    # Configuración de archivos
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB
    
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'}
    ALLOWED_SPREADSHEET_EXTENSIONS = {'xls', 'xlsx', 'csv', 'ods'}
    ALLOWED_PRESENTATION_EXTENSIONS = {'ppt', 'pptx', 'odp'}
    ALLOWED_ARCHIVE_EXTENSIONS = {'zip', 'rar', '7z', 'tar', 'gz'}
    
    # Configuración HTML
    ALLOWED_HTML_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'i', 'b', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'
    ]
    
    ALLOWED_HTML_ATTRIBUTES = {
        '*': ['class', 'id'],
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height']
    }


# =============================================================================
# META CLASES PERSONALIZADAS
# =============================================================================

class SecureFormMeta(DefaultMeta):
    """Meta clase para formularios con seguridad mejorada"""
    
    def bind_field(self, form, unbound_field, options):
        """Vincula campo con validaciones de seguridad adicionales"""
        # Aplicar sanitización automática a campos de texto
        if isinstance(unbound_field, (StringField, TextAreaField)):
            if 'filters' not in options:
                options['filters'] = []
            options['filters'].append(self._sanitize_input)
        
        return unbound_field.bind(form=form, **options)
    
    def _sanitize_input(self, value):
        """Sanitiza entrada de texto"""
        if not value:
            return value
        
        # Remover caracteres de control
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
        
        # Limitar longitud
        if len(value) > 10000:  # Límite global
            value = value[:10000]
        
        return value.strip()


# =============================================================================
# CLASES BASE PARA FORMULARIOS
# =============================================================================

class BaseForm(FlaskForm):
    """
    Clase base para todos los formularios del sistema.
    Incluye funcionalidades comunes, validaciones y utilidades.
    """
    
    Meta = SecureFormMeta
    
    def __init__(self, formdata=None, obj=None, prefix='', data=None, meta=None, **kwargs):
        """Inicialización mejorada del formulario"""
        # Configurar contexto del formulario
        self._setup_context()
        
        # Configurar configuración regional
        self._setup_locale()
        
        # Configurar timezone
        self._setup_timezone()
        
        super().__init__(formdata, obj, prefix, data, meta, **kwargs)
        
        # Aplicar configuraciones post-inicialización
        self._post_init_setup()
    
    def _setup_context(self):
        """Configura el contexto del formulario"""
        self.user = getattr(g, 'current_user', None)
        self.request_method = request.method if request else 'GET'
        self.is_api_request = request.is_json if request else False
        self.client_ip = self._get_client_ip()
        
    def _setup_locale(self):
        """Configura el locale del formulario"""
        # Prioridad: usuario autenticado > sesión > configuración > default
        if self.user and hasattr(self.user, 'locale'):
            self.locale = self.user.locale
        elif session.get('locale'):
            self.locale = session['locale']
        elif current_app.config.get('BABEL_DEFAULT_LOCALE'):
            self.locale = current_app.config['BABEL_DEFAULT_LOCALE']
        else:
            self.locale = 'es'
    
    def _setup_timezone(self):
        """Configura la zona horaria del formulario"""
        if self.user and hasattr(self.user, 'timezone'):
            self.timezone = self.user.timezone
        elif session.get('timezone'):
            self.timezone = session['timezone']
        else:
            self.timezone = 'America/Bogota'  # Default para Colombia
    
    def _post_init_setup(self):
        """Configuración posterior a la inicialización"""
        # Aplicar clases CSS automáticamente
        self._apply_bootstrap_classes()
        
        # Configurar placeholders dinámicos
        self._setup_dynamic_placeholders()
        
        # Configurar mensajes de error personalizados
        self._setup_error_messages()
        
        # Aplicar configuraciones específicas del dispositivo
        self._setup_device_specific_config()
    
    def _apply_bootstrap_classes(self):
        """Aplica clases Bootstrap automáticamente"""
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
            if field.type == 'CSRFTokenField':
                continue
                
            field_type = type(field)
            css_class = css_classes.get(field_type, 'form-control')
            
            # Obtener clases existentes
            current_class = ''
            if field.render_kw and 'class' in field.render_kw:
                current_class = field.render_kw['class']
            elif hasattr(field.widget, 'html_params'):
                current_class = field.widget.html_params().get('class', '')
            
            # Agregar clase Bootstrap si no existe
            if css_class not in current_class:
                if not field.render_kw:
                    field.render_kw = {}
                field.render_kw['class'] = f"{current_class} {css_class}".strip()
    
    def _setup_dynamic_placeholders(self):
        """Configura placeholders dinámicos basados en el locale"""
        placeholders = self._get_locale_placeholders()
        
        for field in self:
            field_name = field.name.lower()
            
            # Buscar placeholder específico o genérico
            placeholder = None
            if field_name in placeholders:
                placeholder = placeholders[field_name]
            elif 'email' in field_name:
                placeholder = placeholders.get('email')
            elif 'phone' in field_name or 'telefono' in field_name:
                placeholder = placeholders.get('phone')
            elif 'password' in field_name or 'contraseña' in field_name:
                placeholder = placeholders.get('password')
            elif 'name' in field_name or 'nombre' in field_name:
                placeholder = placeholders.get('name')
            
            if placeholder and not (field.render_kw and field.render_kw.get('placeholder')):
                if not field.render_kw:
                    field.render_kw = {}
                field.render_kw['placeholder'] = placeholder
    
    def _get_locale_placeholders(self) -> dict[str, str]:
        """Obtiene placeholders según el locale"""
        placeholders_map = {
            'es': {
                'email': 'ejemplo@correo.com',
                'phone': '+57 300 123 4567',
                'name': 'Ingrese su nombre',
                'first_name': 'Nombre',
                'last_name': 'Apellido', 
                'password': 'Mínimo 8 caracteres',
                'username': 'Nombre de usuario',
                'company': 'Nombre de la empresa',
                'title': 'Título',
                'description': 'Descripción detallada...',
                'website': 'https://ejemplo.com',
                'linkedin': 'https://linkedin.com/in/usuario',
                'budget': '1000000',
                'tax_id': '123456789-0'
            },
            'en': {
                'email': 'example@email.com',
                'phone': '+1 555 123 4567',
                'name': 'Enter your name',
                'first_name': 'First name',
                'last_name': 'Last name',
                'password': 'Minimum 8 characters',
                'username': 'Username',
                'company': 'Company name',
                'title': 'Title',
                'description': 'Detailed description...',
                'website': 'https://example.com',
                'linkedin': 'https://linkedin.com/in/username',
                'budget': '10000',
                'tax_id': '123-45-6789'
            }
        }
        
        return placeholders_map.get(self.locale, placeholders_map['es'])
    
    def _setup_error_messages(self):
        """Configura mensajes de error personalizados"""
        error_messages = self._get_locale_error_messages()
        
        for field in self:
            for validator in field.validators:
                validator_name = type(validator).__name__.lower()
                
                if validator_name in error_messages:
                    if not hasattr(validator, 'message') or not validator.message:
                        validator.message = error_messages[validator_name]
    
    def _get_locale_error_messages(self) -> dict[str, str]:
        """Obtiene mensajes de error según el locale"""
        messages_map = {
            'es': {
                'datarequired': 'Este campo es obligatorio',
                'inputrequired': 'Este campo es obligatorio',
                'email': 'Ingrese un email válido',
                'length': 'Longitud inválida',
                'numberrange': 'Número fuera del rango permitido',
                'url': 'URL inválida',
                'regexp': 'Formato inválido',
                'equalto': 'Los campos no coinciden',
                'optional': 'Campo opcional'
            },
            'en': {
                'datarequired': 'This field is required',
                'inputrequired': 'This field is required',
                'email': 'Enter a valid email address',
                'length': 'Invalid length',
                'numberrange': 'Number out of valid range',
                'url': 'Invalid URL',
                'regexp': 'Invalid format',
                'equalto': 'Fields do not match',
                'optional': 'Optional field'
            }
        }
        
        return messages_map.get(self.locale, messages_map['es'])
    
    def _setup_device_specific_config(self):
        """Configura opciones específicas según el dispositivo"""
        if not request:
            return
            
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone'])
        
        if is_mobile:
            # Configuraciones para dispositivos móviles
            for field in self:
                if isinstance(field, (DateField, DateTimeField, TimeField)):
                    if not field.render_kw:
                        field.render_kw = {}
                    field.render_kw['data-mobile'] = 'true'
                
                elif isinstance(field, EmailField):
                    if not field.render_kw:
                        field.render_kw = {}
                    field.render_kw['inputmode'] = 'email'
                    field.render_kw['autocomplete'] = 'email'
                
                elif isinstance(field, TelField):
                    if not field.render_kw:
                        field.render_kw = {}
                    field.render_kw['inputmode'] = 'tel'
                    field.render_kw['autocomplete'] = 'tel'
    
    def _get_client_ip(self) -> str:
        """Obtiene la IP del cliente"""
        if not request:
            return '127.0.0.1'
        
        # Verificar headers de proxy
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr or '127.0.0.1'
    
    def validate(self, **kwargs) -> bool:
        """Validación mejorada con logging y rate limiting"""
        # Verificar rate limiting
        if not self._check_rate_limit():
            self._add_form_error('Demasiados intentos. Intente más tarde.')
            return False
        
        # Validación de CSRF mejorada
        if not self._validate_csrf_enhanced():
            return False
        
        # Validación estándar
        valid = super().validate(**kwargs)
        
        # Validaciones adicionales
        if valid:
            valid = self._validate_business_rules()
        
        # Logging de errores
        if not valid:
            self._log_validation_errors()
        
        # Sanitización final de datos
        if valid:
            self._sanitize_validated_data()
        
        return valid
    
    def _check_rate_limit(self) -> bool:
        """Verifica rate limiting específico del formulario"""
        form_name = self.__class__.__name__.lower().replace('form', '')
        
        # Configuración de rate limits por formulario
        rate_limits = {
            'login': {'limit': 5, 'window': 900},      # 5 intentos por 15 min
            'register': {'limit': 3, 'window': 3600},  # 3 registros por hora  
            'contact': {'limit': 5, 'window': 3600},   # 5 mensajes por hora
            'password_reset': {'limit': 3, 'window': 3600},
            'feedback': {'limit': 10, 'window': 3600}
        }
        
        if form_name not in rate_limits:
            return True
        
        cache = CacheManager()
        config = rate_limits[form_name]
        cache_key = f"form_rate_limit_{form_name}_{self.client_ip}"
        
        current_count = cache.get(cache_key) or 0
        
        if current_count >= config['limit']:
            logger.warning(f"Rate limit exceeded for {form_name} from {self.client_ip}")
            return False
        
        cache.set(cache_key, current_count + 1, timeout=config['window'])
        return True
    
    def _validate_csrf_enhanced(self) -> bool:
        """Validación CSRF mejorada"""
        if not current_app.config.get('WTF_CSRF_ENABLED', True):
            return True
        
        # Validación estándar de CSRF
        try:
            self.csrf_token.validate(self)
            return True
        except ValidationError as e:
            logger.warning(f"CSRF validation failed from {self.client_ip}: {e}")
            self._add_form_error('Token de seguridad inválido. Recargue la página.')
            return False
    
    def _validate_business_rules(self) -> bool:
        """Validaciones de reglas de negocio específicas"""
        # Implementar validaciones específicas del dominio
        # Este método puede ser sobrescrito en formularios específicos
        return True
    
    def _sanitize_validated_data(self):
        """Sanitiza datos después de la validación"""
        for field in self:
            if isinstance(field, (StringField, TextAreaField)):
                if field.data:
                    # Limpiar HTML si es necesario
                    if hasattr(field, 'allow_html') and field.allow_html:
                        field.data = self._clean_html(field.data)
                    else:
                        # Escapar HTML básico
                        field.data = field.data.strip()
    
    def _clean_html(self, text: str) -> str:
        """Limpia HTML usando bleach"""
        return bleach.clean(
            text,
            tags=FormConstants.ALLOWED_HTML_TAGS,
            attributes=FormConstants.ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    
    def _log_validation_errors(self):
        """Log detallado de errores de validación"""
        form_name = self.__class__.__name__
        errors = []
        
        for field_name, field_errors in self.errors.items():
            for error in field_errors:
                errors.append(f"{field_name}: {error}")
        
        logger.info(
            f"Form validation failed - {form_name} from {self.client_ip}: "
            f"{'; '.join(errors)}"
        )
    
    def _add_form_error(self, message: str):
        """Agrega error general al formulario"""
        if not hasattr(self, '_form_errors'):
            self._form_errors = []
        self._form_errors.append(message)
    
    def get_form_errors(self) -> list[str]:
        """Obtiene errores generales del formulario"""
        return getattr(self, '_form_errors', [])
    
    def populate_obj(self, obj):
        """Popula objeto con validaciones adicionales"""
        # Guardar valores originales para auditoría
        original_values = {}
        for field in self:
            if hasattr(obj, field.name):
                original_values[field.name] = getattr(obj, field.name)
        
        # Populación estándar
        super().populate_obj(obj)
        
        # Log de cambios para auditoría
        self._log_object_changes(obj, original_values)
    
    def _log_object_changes(self, obj, original_values: dict[str, Any]):
        """Log de cambios en el objeto para auditoría"""
        changes = []
        for field_name, original_value in original_values.items():
            current_value = getattr(obj, field_name, None)
            if original_value != current_value:
                changes.append(f"{field_name}: {original_value} → {current_value}")
        
        if changes:
            logger.info(
                f"Object modified via {self.__class__.__name__}: "
                f"{'; '.join(changes)}"
            )
    
    def to_dict(self, exclude: list[str] = None) -> dict[str, Any]:
        """Convierte formulario a diccionario"""
        exclude = exclude or ['csrf_token', 'submit']
        
        data = {}
        for field in self:
            if field.name not in exclude:
                if isinstance(field.data, datetime):
                    data[field.name] = field.data.isoformat()
                elif isinstance(field.data, date):
                    data[field.name] = field.data.isoformat()
                elif isinstance(field.data, time):
                    data[field.name] = field.data.isoformat()
                else:
                    data[field.name] = field.data
        
        return data
    
    def from_dict(self, data: dict[str, Any], exclude: list[str] = None):
        """Carga datos desde diccionario"""
        exclude = exclude or ['csrf_token', 'submit']
        
        for field_name, value in data.items():
            if field_name not in exclude and hasattr(self, field_name):
                field = getattr(self, field_name)
                field.data = value
    
    def get_changed_fields(self, original_data: dict[str, Any]) -> dict[str, Any]:
        """Retorna campos que han cambiado"""
        changed = {}
        current_data = self.to_dict()
        
        for field_name, current_value in current_data.items():
            original_value = original_data.get(field_name)
            if original_value != current_value:
                changed[field_name] = {
                    'old': original_value,
                    'new': current_value
                }
        
        return changed
    
    def has_file_fields(self) -> bool:
        """Verifica si el formulario contiene campos de archivo"""
        return any(isinstance(field, FileField) for field in self)
    
    def validate_file_uploads(self) -> bool:
        """Valida archivos subidos"""
        for field in self:
            if isinstance(field, FileField) and field.data:
                if not self._validate_file(field, field.data):
                    return False
        return True
    
    def _validate_file(self, field: FileField, file_data: FileStorage) -> bool:
        """Valida un archivo específico"""
        if not file_data.filename:
            return True
        
        # Validar extensión
        allowed_extensions = getattr(field, 'allowed_extensions', None)
        if allowed_extensions:
            extension = file_data.filename.rsplit('.', 1)[1].lower()
            if extension not in allowed_extensions:
                field.errors.append(f'Extensión no permitida: {extension}')
                return False
        
        # Validar tamaño
        max_size = getattr(field, 'max_file_size', FormConstants.MAX_FILE_SIZE)
        if file_data.content_length and file_data.content_length > max_size:
            size_mb = max_size // (1024 * 1024)
            field.errors.append(f'Archivo muy grande. Máximo: {size_mb}MB')
            return False
        
        return True


# =============================================================================
# MIXINS REUTILIZABLES
# =============================================================================

class TimezoneMixin:
    """Mixin para manejo de zonas horarias en formularios"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_timezone_fields()
    
    def _setup_timezone_fields(self):
        """Configura campos de fecha/hora con timezone"""
        for field in self:
            if isinstance(field, (DateTimeField, TimeField)):
                if not hasattr(field, 'timezone'):
                    field.timezone = getattr(self, 'timezone', 'UTC')


class AuditMixin:
    """Mixin para auditoría de formularios"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._audit_data = {
            'form_name': self.__class__.__name__,
            'created_at': datetime.now(timezone.utc),
            'user_id': getattr(self.user, 'id', None) if hasattr(self, 'user') else None,
            'client_ip': getattr(self, 'client_ip', None),
            'user_agent': request.headers.get('User-Agent') if request else None
        }
    
    def validate(self, **kwargs):
        """Validación con auditoría"""
        result = super().validate(**kwargs)
        
        self._audit_data.update({
            'validated_at': datetime.now(timezone.utc),
            'validation_result': result,
            'errors': dict(self.errors) if not result else None
        })
        
        # Guardar auditoría (en producción, enviar a base de datos)
        self._save_audit_log()
        
        return result
    
    def _save_audit_log(self):
        """Guarda log de auditoría"""
        logger.info(f"Form audit: {json.dumps(self._audit_data, default=str)}")


class CacheableMixin:
    """Mixin para formularios con capacidades de cache"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = CacheManager()
    
    def get_cached_choices(self, field_name: str, fetch_function: Callable) -> list[Tuple]:
        """Obtiene opciones de campo desde cache"""
        cache_key = f"form_choices_{self.__class__.__name__}_{field_name}"
        
        choices = self.cache.get(cache_key)
        if choices is None:
            choices = fetch_function()
            self.cache.set(cache_key, choices, timeout=300)  # 5 minutos
        
        return choices
    
    def invalidate_choices_cache(self, field_name: str = None):
        """Invalida cache de opciones"""
        if field_name:
            cache_key = f"form_choices_{self.__class__.__name__}_{field_name}"
            self.cache.delete(cache_key)
        else:
            # Invalidar todo el cache del formulario
            pattern = f"form_choices_{self.__class__.__name__}_*"
            self.cache.clear_pattern(pattern)


class SearchFormMixin:
    """Mixin para formularios de búsqueda"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_search_fields()
    
    def _setup_search_fields(self):
        """Configura campos de búsqueda"""
        for field in self:
            if isinstance(field, StringField):
                # Agregar autocompletado para campos de búsqueda
                if not field.render_kw:
                    field.render_kw = {}
                field.render_kw['autocomplete'] = 'off'
                field.render_kw['data-search'] = 'true'
    
    def get_search_filters(self) -> dict[str, Any]:
        """Obtiene filtros de búsqueda aplicados"""
        filters = {}
        for field in self:
            if field.data and field.name != 'csrf_token':
                filters[field.name] = field.data
        return filters
    
    def build_query_params(self) -> str:
        """Construye parámetros de query string"""
        filters = self.get_search_filters()
        if not filters:
            return ''
        
        params = []
        for key, value in filters.items():
            if isinstance(value, list):
                for v in value:
                    params.append(f"{key}={v}")
            else:
                params.append(f"{key}={value}")
        
        return '&'.join(params)


# =============================================================================
# FORMULARIOS BASE ESPECIALIZADOS
# =============================================================================

class ModelForm(BaseForm, AuditMixin):
    """Formulario base para operaciones CRUD de modelos"""
    
    def __init__(self, obj=None, *args, **kwargs):
        self.obj = obj
        self.is_edit = obj is not None
        super().__init__(obj=obj, *args, **kwargs)
    
    def validate(self, **kwargs):
        """Validación específica para modelos"""
        valid = super().validate(**kwargs)
        
        if valid:
            # Validaciones específicas del modelo
            valid = self._validate_model_constraints()
        
        return valid
    
    def _validate_model_constraints(self) -> bool:
        """Valida restricciones específicas del modelo"""
        # Implementar en subclases según el modelo
        return True
    
    def save(self, commit=True):
        """Guarda el modelo con el formulario"""
        if self.obj is None:
            # Crear nuevo objeto
            model_class = self._get_model_class()
            self.obj = model_class()
        
        # Poblar objeto
        self.populate_obj(self.obj)
        
        if commit:
            from app.extensions import db
            try:
                db.session.add(self.obj)
                db.session.commit()
                logger.info(f"Saved {self.obj.__class__.__name__} via form")
                return self.obj
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error saving model via form: {e}")
                self._add_form_error('Error al guardar. Intente nuevamente.')
                raise
        
        return self.obj
    
    def _get_model_class(self):
        """Obtiene la clase del modelo (implementar en subclases)"""
        raise NotImplementedError("Subclasses must implement _get_model_class")


class SearchForm(BaseForm, SearchFormMixin, CacheableMixin):
    """Formulario base para búsquedas"""
    
    def __init__(self, *args, **kwargs):
        # Los formularios de búsqueda no requieren CSRF
        kwargs.setdefault('meta', {})['csrf'] = False
        super().__init__(*args, **kwargs)
    
    def validate(self, **kwargs):
        """Validación simplificada para búsquedas"""
        # Saltear validación CSRF
        return FlaskForm.validate(self, **kwargs)


class FileUploadForm(BaseForm):
    """Formulario base para subida de archivos"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configurar enctype automáticamente
        self._enctype = 'multipart/form-data'
    
    def validate(self, **kwargs):
        """Validación con archivos"""
        valid = super().validate(**kwargs)
        
        if valid:
            valid = self.validate_file_uploads()
        
        return valid
    
    def process_files(self) -> dict[str, str]:
        """Procesa archivos subidos"""
        processed_files = {}
        
        for field in self:
            if isinstance(field, FileField) and field.data:
                file_path = self._save_file(field.data)
                if file_path:
                    processed_files[field.name] = file_path
        
        return processed_files
    
    def _save_file(self, file_data: FileStorage) -> Optional[str]:
        """Guarda archivo (implementar según storage utilizado)"""
        # En producción, integrar con servicio de storage
        # (AWS S3, Google Cloud Storage, etc.)
        pass


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    'FormConstants',
    'SecureFormMeta',
    'BaseForm',
    'TimezoneMixin',
    'AuditMixin', 
    'CacheableMixin',
    'SearchFormMixin',
    'ModelForm',
    'SearchForm',
    'FileUploadForm'
]