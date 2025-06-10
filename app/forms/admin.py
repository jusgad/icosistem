"""
Admin Forms Module

Formularios administrativos para el ecosistema de emprendimiento.
Incluye gestión de usuarios, organizaciones, programas y configuraciones.

Author: Senior Developer
Date: 2025
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from decimal import Decimal
from flask import current_app, g, flash, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, PasswordField, EmailField,
    SelectField, SelectMultipleField, BooleanField, IntegerField,
    FloatField, DecimalField, DateField, DateTimeField,
    RadioField, HiddenField, SubmitField, FieldList, FormField
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange, Optional as WTFOptional,
    Regexp, URL, ValidationError, InputRequired
)
from wtforms.widgets import TextArea, Select, CheckboxInput

from app.forms.base import BaseForm, ModelForm, AuditMixin, CacheableMixin
from app.forms.validators import (
    SecurePassword, InternationalPhone, UniqueEmail, UniqueUsername,
    ColombianNIT, BusinessEmail, SecureFileUpload, ImageValidator,
    Unique, ExistsInDB, BaseValidator
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.admin import Admin
from app.models.organization import Organization
from app.models.program import Program
from app.models.project import Project
from app.models.meeting import Meeting
from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES ESPECÍFICOS DE ADMINISTRACIÓN
# =============================================================================

class AdminPermissionRequired(BaseValidator):
    """Validador que requiere permisos específicos de administrador"""
    
    def __init__(self, required_permissions: List[str], message: str = None):
        super().__init__(message)
        self.required_permissions = required_permissions
    
    def validate(self, form, field):
        if not hasattr(g, 'current_user') or not g.current_user.is_authenticated:
            raise ValidationError('Autenticación requerida')
        
        if not g.current_user.is_admin:
            raise ValidationError('Permisos de administrador requeridos')
        
        admin = Admin.query.filter_by(user_id=g.current_user.id).first()
        if not admin:
            raise ValidationError('Perfil de administrador no encontrado')
        
        user_permissions = admin.permissions or []
        missing_permissions = set(self.required_permissions) - set(user_permissions)
        
        if missing_permissions:
            raise ValidationError(
                f'Permisos insuficientes. Requeridos: {", ".join(missing_permissions)}'
            )


class BulkActionLimit(BaseValidator):
    """Validador para limitar operaciones en lote"""
    
    def __init__(self, max_items: int = 100, message: str = None):
        super().__init__(message)
        self.max_items = max_items
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # field.data debería ser una lista de IDs
        if isinstance(field.data, str):
            items = field.data.split(',')
        elif isinstance(field.data, list):
            items = field.data
        else:
            raise ValidationError('Formato de datos inválido')
        
        if len(items) > self.max_items:
            raise ValidationError(
                f'Máximo {self.max_items} elementos permitidos en operación masiva'
            )


class DateRangeLimit(BaseValidator):
    """Validador para limitar rangos de fechas en reportes"""
    
    def __init__(self, max_days: int = 365, message: str = None):
        super().__init__(message)
        self.max_days = max_days
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # Obtener fecha de inicio del formulario
        start_date_field = getattr(form, 'start_date', None)
        if not start_date_field or not start_date_field.data:
            return
        
        start_date = start_date_field.data
        end_date = field.data
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if end_date <= start_date:
            raise ValidationError('Fecha final debe ser posterior a la inicial')
        
        delta = end_date - start_date
        if delta.days > self.max_days:
            raise ValidationError(
                f'Rango máximo permitido: {self.max_days} días'
            )


# =============================================================================
# FORMULARIOS DE GESTIÓN DE USUARIOS
# =============================================================================

class AdminUserCreateForm(ModelForm, CacheableMixin):
    """Formulario para crear usuarios desde el panel administrativo"""
    
    # Información básica
    user_type = SelectField(
        'Tipo de Usuario',
        choices=[
            ('entrepreneur', 'Emprendedor'),
            ('ally', 'Mentor/Aliado'),
            ('client', 'Cliente/Stakeholder'),
            ('admin', 'Administrador')
        ],
        validators=[DataRequired()],
        default='entrepreneur'
    )
    
    first_name = StringField(
        'Nombre',
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='Solo letras y espacios')
        ]
    )
    
    last_name = StringField(
        'Apellido',
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='Solo letras y espacios')
        ]
    )
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(),
            Email(),
            UniqueEmail()
        ]
    )
    
    username = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(),
            Length(min=3, max=30),
            Regexp(r'^[a-zA-Z0-9_.-]+$'),
            UniqueUsername()
        ]
    )
    
    phone = StringField(
        'Teléfono',
        validators=[
            DataRequired(),
            InternationalPhone(regions=['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL'])
        ]
    )
    
    # Contraseña temporal
    password = PasswordField(
        'Contraseña Temporal',
        validators=[
            DataRequired(),
            SecurePassword(min_length=8)
        ]
    )
    
    send_welcome_email = BooleanField(
        'Enviar email de bienvenida',
        default=True
    )
    
    force_password_change = BooleanField(
        'Forzar cambio de contraseña en primer login',
        default=True
    )
    
    # Información adicional
    organization = StringField(
        'Organización',
        validators=[Length(max=100)]
    )
    
    linkedin_url = StringField(
        'LinkedIn',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'linkedin\.com/in/', message='URL de LinkedIn inválida')
        ]
    )
    
    # Estado de la cuenta
    is_active = BooleanField('Cuenta Activa', default=True)
    email_verified = BooleanField('Email Verificado', default=False)
    
    # Configuraciones específicas para administradores
    admin_permissions = SelectMultipleField(
        'Permisos de Administrador',
        choices=[],  # Se llenan dinámicamente
        validators=[],
        render_kw={'class': 'form-control', 'size': '8'}
    )
    
    # Notas administrativas
    admin_notes = TextAreaField(
        'Notas Administrativas',
        validators=[Length(max=1000)],
        render_kw={'rows': 4, 'placeholder': 'Notas internas sobre el usuario...'}
    )
    
    submit = SubmitField('Crear Usuario')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar permisos dinámicamente
        self.admin_permissions.choices = self._get_admin_permissions()
    
    def _get_admin_permissions(self) -> List[Tuple[str, str]]:
        """Obtiene lista de permisos disponibles"""
        permissions = [
            ('users_manage', 'Gestionar Usuarios'),
            ('users_delete', 'Eliminar Usuarios'),
            ('organizations_manage', 'Gestionar Organizaciones'),
            ('programs_manage', 'Gestionar Programas'),
            ('reports_view', 'Ver Reportes'),
            ('reports_export', 'Exportar Reportes'),
            ('system_config', 'Configuración del Sistema'),
            ('bulk_operations', 'Operaciones Masivas'),
            ('analytics_advanced', 'Analytics Avanzados'),
            ('integrations_manage', 'Gestionar Integraciones'),
            ('content_manage', 'Gestionar Contenido'),
            ('notifications_manage', 'Gestionar Notificaciones')
        ]
        return permissions
    
    def validate_admin_permissions(self, field):
        """Valida permisos de administrador"""
        if self.user_type.data == 'admin' and not field.data:
            raise ValidationError('Administradores deben tener al menos un permiso')
    
    def _get_model_class(self):
        return User
    
    def save(self, commit=True):
        """Guarda usuario con perfil específico"""
        try:
            from app.extensions import db
            
            # Crear usuario base
            user = super().save(commit=False)
            
            # Configurar contraseña
            user.set_password(self.password.data)
            
            # Configurar flags especiales
            if self.force_password_change.data:
                user.force_password_change = True
            
            # Configurar tokens de verificación si es necesario
            if not self.email_verified.data:
                import secrets
                user.email_verification_token = secrets.token_urlsafe(32)
                user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
            
            db.session.add(user)
            db.session.flush()  # Para obtener el ID
            
            # Crear perfil específico
            profile = self._create_user_profile(user)
            if profile:
                db.session.add(profile)
            
            if commit:
                db.session.commit()
                
                # Enviar email de bienvenida si se solicitó
                if self.send_welcome_email.data:
                    self._send_welcome_email(user)
            
            logger.info(f"Admin created user: {user.email} ({user.user_type})")
            return user
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating user via admin: {e}")
            raise
    
    def _create_user_profile(self, user: User):
        """Crea perfil específico según tipo de usuario"""
        if user.user_type == 'entrepreneur':
            return Entrepreneur(user_id=user.id)
        elif user.user_type == 'ally':
            return Ally(user_id=user.id)
        elif user.user_type == 'admin':
            return Admin(
                user_id=user.id,
                permissions=self.admin_permissions.data,
                notes=self.admin_notes.data
            )
        return None
    
    def _send_welcome_email(self, user: User):
        """Envía email de bienvenida"""
        try:
            from app.services.email import EmailService
            
            email_service = EmailService()
            email_service.send_admin_created_user_email(
                user=user,
                temporary_password=self.password.data,
                created_by=g.current_user
            )
        except Exception as e:
            logger.error(f"Error sending welcome email: {e}")


class AdminUserEditForm(ModelForm):
    """Formulario para editar usuarios existentes"""
    
    # Campos editables básicos
    first_name = StringField(
        'Nombre',
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$')
        ]
    )
    
    last_name = StringField(
        'Apellido',
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$')
        ]
    )
    
    email = EmailField(
        'Email',
        validators=[DataRequired(), Email()]
    )
    
    phone = StringField(
        'Teléfono',
        validators=[
            DataRequired(),
            InternationalPhone(regions=['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL'])
        ]
    )
    
    organization = StringField(
        'Organización',
        validators=[Length(max=100)]
    )
    
    linkedin_url = StringField(
        'LinkedIn',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'linkedin\.com/in/')
        ]
    )
    
    # Estados de cuenta
    is_active = BooleanField('Cuenta Activa')
    email_verified = BooleanField('Email Verificado')
    two_factor_enabled = BooleanField('2FA Habilitado')
    
    # Acciones administrativas
    force_password_change = BooleanField('Forzar Cambio de Contraseña')
    suspend_account = BooleanField('Suspender Cuenta')
    
    suspension_reason = SelectField(
        'Razón de Suspensión',
        choices=[
            ('', 'Seleccionar...'),
            ('policy_violation', 'Violación de Políticas'),
            ('spam', 'Actividad de Spam'),
            ('fraud', 'Actividad Fraudulenta'),
            ('security', 'Razones de Seguridad'),
            ('admin_request', 'Solicitud Administrativa'),
            ('other', 'Otra Razón')
        ],
        validators=[WTFOptional()]
    )
    
    # Notas administrativas
    admin_notes = TextAreaField(
        'Notas Administrativas',
        validators=[Length(max=2000)],
        render_kw={'rows': 6}
    )
    
    # Campos de solo lectura (información)
    created_at = StringField('Fecha de Creación', render_kw={'readonly': True})
    last_login = StringField('Último Login', render_kw={'readonly': True})
    login_count = IntegerField('Total Logins', render_kw={'readonly': True})
    
    submit = SubmitField('Actualizar Usuario')
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(obj=user, *args, **kwargs)
        self.user = user
        
        if user:
            # Llenar campos de solo lectura
            self.created_at.data = user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else ''
            self.last_login.data = user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Nunca'
            self.login_count.data = user.login_count or 0
    
    def validate_email(self, field):
        """Valida unicidad de email excluyendo usuario actual"""
        if self.user and field.data != self.user.email:
            existing = User.query.filter(User.email == field.data).first()
            if existing:
                raise ValidationError('Este email ya está en uso')
    
    def validate_suspension_reason(self, field):
        """Valida razón de suspensión si se suspende la cuenta"""
        if self.suspend_account.data and not field.data:
            raise ValidationError('Debe especificar razón de suspensión')
    
    def _get_model_class(self):
        return User
    
    def save(self, commit=True):
        """Guarda cambios del usuario"""
        try:
            from app.extensions import db
            
            user = super().save(commit=False)
            
            # Procesar suspensión
            if self.suspend_account.data:
                user.is_active = False
                user.suspended_at = datetime.utcnow()
                user.suspended_by = g.current_user.id
                user.suspension_reason = self.suspension_reason.data
            elif not self.suspend_account.data and user.suspended_at:
                # Reactivar cuenta
                user.suspended_at = None
                user.suspended_by = None
                user.suspension_reason = None
                user.is_active = self.is_active.data
            
            # Actualizar notas administrativas
            admin_profile = Admin.query.filter_by(user_id=user.id).first()
            if admin_profile:
                admin_profile.notes = self.admin_notes.data
            
            if commit:
                db.session.commit()
            
            logger.info(f"Admin updated user: {user.email}")
            return user
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating user via admin: {e}")
            raise


class AdminBulkUserForm(BaseForm):
    """Formulario para operaciones masivas en usuarios"""
    
    action = SelectField(
        'Acción',
        choices=[
            ('', 'Seleccionar acción...'),
            ('activate', 'Activar Usuarios'),
            ('deactivate', 'Desactivar Usuarios'),
            ('verify_email', 'Verificar Emails'),
            ('force_password_change', 'Forzar Cambio de Contraseña'),
            ('export', 'Exportar Datos'),
            ('send_notification', 'Enviar Notificación'),
            ('delete', 'Eliminar Usuarios')
        ],
        validators=[
            DataRequired(message='Seleccione una acción'),
            AdminPermissionRequired(['bulk_operations'])
        ]
    )
    
    user_ids = HiddenField(
        'IDs de Usuarios',
        validators=[
            DataRequired(message='Seleccione al menos un usuario'),
            BulkActionLimit(max_items=100)
        ]
    )
    
    # Campos condicionales
    notification_subject = StringField(
        'Asunto de Notificación',
        validators=[Length(max=200)]
    )
    
    notification_message = TextAreaField(
        'Mensaje de Notificación',
        validators=[Length(max=1000)],
        render_kw={'rows': 4}
    )
    
    export_format = SelectField(
        'Formato de Exportación',
        choices=[
            ('csv', 'CSV'),
            ('excel', 'Excel'),
            ('json', 'JSON')
        ]
    )
    
    confirm_action = BooleanField(
        'Confirmo que deseo ejecutar esta acción',
        validators=[DataRequired(message='Debe confirmar la acción')]
    )
    
    submit = SubmitField('Ejecutar Acción Masiva')
    
    def validate_notification_subject(self, field):
        """Valida asunto si la acción es enviar notificación"""
        if self.action.data == 'send_notification' and not field.data:
            raise ValidationError('Asunto requerido para enviar notificación')
    
    def validate_notification_message(self, field):
        """Valida mensaje si la acción es enviar notificación"""
        if self.action.data == 'send_notification' and not field.data:
            raise ValidationError('Mensaje requerido para enviar notificación')
    
    def get_selected_users(self) -> List[User]:
        """Obtiene usuarios seleccionados"""
        user_ids = self.user_ids.data.split(',') if self.user_ids.data else []
        return User.query.filter(User.id.in_(user_ids)).all()
    
    def execute_bulk_action(self) -> Dict[str, Any]:
        """Ejecuta la acción masiva seleccionada"""
        from app.services.admin import AdminService
        
        admin_service = AdminService()
        users = self.get_selected_users()
        
        if self.action.data == 'activate':
            return admin_service.bulk_activate_users(users)
        elif self.action.data == 'deactivate':
            return admin_service.bulk_deactivate_users(users)
        elif self.action.data == 'verify_email':
            return admin_service.bulk_verify_emails(users)
        elif self.action.data == 'force_password_change':
            return admin_service.bulk_force_password_change(users)
        elif self.action.data == 'export':
            return admin_service.export_users(users, self.export_format.data)
        elif self.action.data == 'send_notification':
            return admin_service.bulk_send_notification(
                users, self.notification_subject.data, self.notification_message.data
            )
        elif self.action.data == 'delete':
            return admin_service.bulk_delete_users(users)
        
        return {'success': False, 'message': 'Acción no válida'}


# =============================================================================
# FORMULARIOS DE GESTIÓN DE ORGANIZACIONES
# =============================================================================

class AdminOrganizationForm(ModelForm):
    """Formulario para gestionar organizaciones"""
    
    # Información básica
    name = StringField(
        'Nombre de la Organización',
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Unique(Organization, 'name', case_sensitive=False)
        ]
    )
    
    slug = StringField(
        'Slug (URL)',
        validators=[
            DataRequired(),
            Length(min=2, max=50),
            Regexp(r'^[a-z0-9-]+$', message='Solo minúsculas, números y guiones'),
            Unique(Organization, 'slug')
        ],
        render_kw={'placeholder': 'organizacion-ejemplo'}
    )
    
    organization_type = SelectField(
        'Tipo de Organización',
        choices=[
            ('incubator', 'Incubadora'),
            ('accelerator', 'Aceleradora'),
            ('university', 'Universidad'),
            ('corporation', 'Corporación'),
            ('government', 'Entidad Gubernamental'),
            ('ngo', 'ONG'),
            ('foundation', 'Fundación'),
            ('venture_capital', 'Capital de Riesgo'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(),
            Length(min=10, max=2000)
        ],
        render_kw={'rows': 6}
    )
    
    # Información de contacto
    email = EmailField(
        'Email Principal',
        validators=[
            DataRequired(),
            BusinessEmail(allow_free_domains=False)
        ]
    )
    
    phone = StringField(
        'Teléfono',
        validators=[
            DataRequired(),
            InternationalPhone(regions=['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL'])
        ]
    )
    
    website = StringField(
        'Sitio Web',
        validators=[
            DataRequired(),
            URL(),
            Regexp(r'^https?://', message='URL debe incluir http:// o https://')
        ]
    )
    
    # Dirección
    address = StringField(
        'Dirección',
        validators=[DataRequired(), Length(max=200)]
    )
    
    city = StringField(
        'Ciudad',
        validators=[DataRequired(), Length(max=100)]
    )
    
    country = SelectField(
        'País',
        choices=[
            ('CO', 'Colombia'),
            ('US', 'Estados Unidos'),
            ('MX', 'México'),
            ('BR', 'Brasil'),
            ('AR', 'Argentina'),
            ('PE', 'Perú'),
            ('CL', 'Chile'),
            ('EC', 'Ecuador'),
            ('UY', 'Uruguay'),
            ('PY', 'Paraguay')
        ],
        validators=[DataRequired()],
        default='CO'
    )
    
    # Información legal
    tax_id = StringField(
        'NIT/ID Tributario',
        validators=[
            DataRequired(),
            ColombianNIT(allow_natural_person=False)
        ]
    )
    
    legal_name = StringField(
        'Razón Social',
        validators=[DataRequired(), Length(max=200)]
    )
    
    # Configuraciones
    is_active = BooleanField('Organización Activa', default=True)
    is_verified = BooleanField('Organización Verificada', default=False)
    
    max_programs = IntegerField(
        'Máximo Programas Permitidos',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100)
        ],
        default=5
    )
    
    max_entrepreneurs = IntegerField(
        'Máximo Emprendedores por Programa',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=1000)
        ],
        default=50
    )
    
    # Archivos
    logo = FileField(
        'Logo',
        validators=[
            ImageValidator(
                max_width=500,
                max_height=500,
                max_size=2*1024*1024  # 2MB
            )
        ]
    )
    
    # Configuraciones avanzadas
    features_enabled = SelectMultipleField(
        'Características Habilitadas',
        choices=[
            ('mentorship', 'Mentoría'),
            ('funding', 'Financiamiento'),
            ('workspace', 'Espacio de Trabajo'),
            ('events', 'Eventos'),
            ('networking', 'Networking'),
            ('legal_support', 'Soporte Legal'),
            ('marketing', 'Marketing'),
            ('technology', 'Tecnología'),
            ('analytics', 'Analytics Avanzados')
        ],
        render_kw={'size': '9'}
    )
    
    # Notas administrativas
    admin_notes = TextAreaField(
        'Notas Administrativas',
        validators=[Length(max=2000)],
        render_kw={'rows': 4}
    )
    
    submit = SubmitField('Guardar Organización')
    
    def _get_model_class(self):
        return Organization


# =============================================================================
# FORMULARIOS DE GESTIÓN DE PROGRAMAS
# =============================================================================

class AdminProgramForm(ModelForm):
    """Formulario para gestionar programas de emprendimiento"""
    
    # Información básica
    name = StringField(
        'Nombre del Programa',
        validators=[
            DataRequired(),
            Length(min=3, max=150)
        ]
    )
    
    slug = StringField(
        'Slug (URL)',
        validators=[
            DataRequired(),
            Length(min=3, max=100),
            Regexp(r'^[a-z0-9-]+$', message='Solo minúsculas, números y guiones')
        ]
    )
    
    organization_id = SelectField(
        'Organización',
        choices=[],  # Se llena dinámicamente
        validators=[
            DataRequired(),
            ExistsInDB(Organization, 'id')
        ],
        coerce=int
    )
    
    program_type = SelectField(
        'Tipo de Programa',
        choices=[
            ('incubation', 'Incubación'),
            ('acceleration', 'Aceleración'),
            ('pre_acceleration', 'Pre-aceleración'),
            ('mentorship', 'Mentoría'),
            ('bootcamp', 'Bootcamp'),
            ('competition', 'Competencia'),
            ('workshop_series', 'Serie de Talleres'),
            ('online_course', 'Curso Online'),
            ('hybrid', 'Híbrido')
        ],
        validators=[DataRequired()]
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(),
            Length(min=50, max=3000)
        ],
        render_kw={'rows': 8}
    )
    
    # Fechas y duración
    start_date = DateField(
        'Fecha de Inicio',
        validators=[DataRequired()]
    )
    
    end_date = DateField(
        'Fecha de Finalización',
        validators=[DataRequired()]
    )
    
    application_deadline = DateField(
        'Fecha Límite de Aplicaciones',
        validators=[DataRequired()]
    )
    
    duration_weeks = IntegerField(
        'Duración (semanas)',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=104)  # Máximo 2 años
        ]
    )
    
    # Capacidad y requisitos
    max_participants = IntegerField(
        'Máximo Participantes',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=500)
        ]
    )
    
    min_team_size = IntegerField(
        'Tamaño Mínimo de Equipo',
        validators=[
            NumberRange(min=1, max=10)
        ],
        default=1
    )
    
    max_team_size = IntegerField(
        'Tamaño Máximo de Equipo',
        validators=[
            NumberRange(min=1, max=20)
        ],
        default=5
    )
    
    # Requisitos de aplicación
    requirements = TextAreaField(
        'Requisitos de Aplicación',
        validators=[Length(max=2000)],
        render_kw={'rows': 6}
    )
    
    target_industries = SelectMultipleField(
        'Industrias Objetivo',
        choices=[
            ('technology', 'Tecnología'),
            ('fintech', 'Fintech'),
            ('healthtech', 'Healthtech'),
            ('edtech', 'Edtech'),
            ('agtech', 'Agtech'),
            ('cleantech', 'Cleantech'),
            ('ecommerce', 'E-commerce'),
            ('marketplace', 'Marketplace'),
            ('saas', 'SaaS'),
            ('mobile_apps', 'Apps Móviles'),
            ('iot', 'IoT'),
            ('ai_ml', 'IA/ML'),
            ('blockchain', 'Blockchain'),
            ('social_impact', 'Impacto Social'),
            ('other', 'Otro')
        ],
        render_kw={'size': '10'}
    )
    
    target_stages = SelectMultipleField(
        'Etapas Objetivo',
        choices=[
            ('idea', 'Idea'),
            ('prototype', 'Prototipo'),
            ('mvp', 'MVP'),
            ('early_stage', 'Etapa Temprana'),
            ('growth', 'Crecimiento'),
            ('scale', 'Escalamiento')
        ],
        render_kw={'size': '6'}
    )
    
    # Beneficios y recursos
    funding_amount = DecimalField(
        'Monto de Financiamiento (COP)',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=10000000000)  # 10 mil millones
        ],
        places=0
    )
    
    equity_percentage = FloatField(
        'Porcentaje de Equity (%)',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=50)
        ]
    )
    
    benefits = TextAreaField(
        'Beneficios del Programa',
        validators=[Length(max=2000)],
        render_kw={'rows': 6}
    )
    
    # Configuraciones
    is_active = BooleanField('Programa Activo', default=True)
    is_public = BooleanField('Visible Públicamente', default=True)
    applications_open = BooleanField('Aplicaciones Abiertas', default=True)
    
    # Modalidad
    modality = SelectField(
        'Modalidad',
        choices=[
            ('presential', 'Presencial'),
            ('virtual', 'Virtual'),
            ('hybrid', 'Híbrido')
        ],
        validators=[DataRequired()],
        default='hybrid'
    )
    
    location = StringField(
        'Ubicación',
        validators=[Length(max=200)],
        render_kw={'placeholder': 'Ciudad, País o "Virtual"'}
    )
    
    # Archivos
    banner_image = FileField(
        'Imagen Banner',
        validators=[
            ImageValidator(
                max_width=1200,
                max_height=600,
                max_size=3*1024*1024  # 3MB
            )
        ]
    )
    
    submit = SubmitField('Guardar Programa')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar organizaciones activas
        organizations = Organization.query.filter_by(is_active=True).all()
        self.organization_id.choices = [(0, 'Seleccionar...')] + [
            (org.id, org.name) for org in organizations
        ]
    
    def validate_end_date(self, field):
        """Valida que fecha final sea posterior a inicial"""
        if field.data <= self.start_date.data:
            raise ValidationError('Fecha final debe ser posterior a la fecha de inicio')
    
    def validate_application_deadline(self, field):
        """Valida que deadline sea antes del inicio"""
        if field.data >= self.start_date.data:
            raise ValidationError('Fecha límite debe ser anterior al inicio del programa')
    
    def validate_max_team_size(self, field):
        """Valida que tamaño máximo sea mayor al mínimo"""
        if field.data < self.min_team_size.data:
            raise ValidationError('Tamaño máximo debe ser mayor al mínimo')
    
    def _get_model_class(self):
        return Program


# =============================================================================
# FORMULARIOS DE REPORTES Y ANALYTICS
# =============================================================================

class AdminReportForm(BaseForm):
    """Formulario para generar reportes administrativos"""
    
    report_type = SelectField(
        'Tipo de Reporte',
        choices=[
            ('', 'Seleccionar tipo...'),
            ('users_overview', 'Resumen de Usuarios'),
            ('users_activity', 'Actividad de Usuarios'),
            ('organizations_performance', 'Rendimiento Organizaciones'),
            ('programs_analytics', 'Analytics de Programas'),
            ('projects_status', 'Estado de Proyectos'),
            ('meetings_analytics', 'Analytics de Reuniones'),
            ('financial_overview', 'Resumen Financiero'),
            ('engagement_metrics', 'Métricas de Engagement'),
            ('conversion_funnel', 'Embudo de Conversión'),
            ('custom_query', 'Consulta Personalizada')
        ],
        validators=[
            DataRequired(),
            AdminPermissionRequired(['reports_view'])
        ]
    )
    
    # Rango de fechas
    start_date = DateField(
        'Fecha de Inicio',
        validators=[DataRequired()],
        default=lambda: date.today() - timedelta(days=30)
    )
    
    end_date = DateField(
        'Fecha de Fin',
        validators=[
            DataRequired(),
            DateRangeLimit(max_days=365)
        ],
        default=date.today
    )
    
    # Filtros
    organization_filter = SelectMultipleField(
        'Filtrar por Organización',
        choices=[],  # Se llena dinámicamente
        render_kw={'size': '5'}
    )
    
    user_type_filter = SelectMultipleField(
        'Filtrar por Tipo de Usuario',
        choices=[
            ('entrepreneur', 'Emprendedores'),
            ('ally', 'Mentores/Aliados'),
            ('client', 'Clientes'),
            ('admin', 'Administradores')
        ],
        render_kw={'size': '4'}
    )
    
    program_filter = SelectMultipleField(
        'Filtrar por Programa',
        choices=[],  # Se llena dinámicamente
        render_kw={'size': '5'}
    )
    
    status_filter = SelectMultipleField(
        'Filtrar por Estado',
        choices=[
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
            ('pending', 'Pendiente'),
            ('completed', 'Completado'),
            ('cancelled', 'Cancelado')
        ],
        render_kw={'size': '5'}
    )
    
    # Opciones de agrupación
    group_by = SelectField(
        'Agrupar por',
        choices=[
            ('', 'Sin agrupación'),
            ('day', 'Día'),
            ('week', 'Semana'),
            ('month', 'Mes'),
            ('quarter', 'Trimestre'),
            ('organization', 'Organización'),
            ('program', 'Programa'),
            ('user_type', 'Tipo de Usuario'),
            ('country', 'País'),
            ('industry', 'Industria')
        ]
    )
    
    # Formato de salida
    output_format = SelectField(
        'Formato de Salida',
        choices=[
            ('table', 'Tabla HTML'),
            ('csv', 'CSV'),
            ('excel', 'Excel'),
            ('json', 'JSON'),
            ('pdf', 'PDF'),
            ('chart', 'Gráfico')
        ],
        default='table'
    )
    
    # Opciones avanzadas
    include_deleted = BooleanField('Incluir Registros Eliminados')
    include_inactive = BooleanField('Incluir Registros Inactivos', default=True)
    
    # Consulta personalizada (para reportes custom)
    custom_query = TextAreaField(
        'Consulta SQL Personalizada',
        validators=[
            Length(max=5000)
        ],
        render_kw={
            'rows': 10,
            'placeholder': 'SELECT ... FROM ... WHERE ...'
        }
    )
    
    # Configuraciones de gráficos
    chart_type = SelectField(
        'Tipo de Gráfico',
        choices=[
            ('bar', 'Barras'),
            ('line', 'Líneas'),
            ('pie', 'Circular'),
            ('area', 'Área'),
            ('scatter', 'Dispersión'),
            ('heatmap', 'Mapa de Calor')
        ],
        default='bar'
    )
    
    submit = SubmitField('Generar Reporte')
    export = SubmitField('Exportar Datos')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar opciones dinámicas
        self._load_filter_choices()
    
    def _load_filter_choices(self):
        """Carga opciones de filtros dinámicamente"""
        # Organizaciones activas
        organizations = Organization.query.filter_by(is_active=True).all()
        self.organization_filter.choices = [
            (str(org.id), org.name) for org in organizations
        ]
        
        # Programas activos
        programs = Program.query.filter_by(is_active=True).all()
        self.program_filter.choices = [
            (str(prog.id), prog.name) for prog in programs
        ]
    
    def validate_custom_query(self, field):
        """Valida consulta personalizada"""
        if self.report_type.data == 'custom_query':
            if not field.data:
                raise ValidationError('Consulta personalizada requerida')
            
            # Validaciones básicas de seguridad SQL
            dangerous_keywords = [
                'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
                'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE'
            ]
            
            query_upper = field.data.upper()
            for keyword in dangerous_keywords:
                if keyword in query_upper:
                    raise ValidationError(f'Palabra clave no permitida: {keyword}')
    
    def generate_report(self) -> Dict[str, Any]:
        """Genera el reporte solicitado"""
        from app.services.admin import AdminReportService
        
        report_service = AdminReportService()
        
        filters = {
            'start_date': self.start_date.data,
            'end_date': self.end_date.data,
            'organizations': self.organization_filter.data,
            'user_types': self.user_type_filter.data,
            'programs': self.program_filter.data,
            'statuses': self.status_filter.data,
            'include_deleted': self.include_deleted.data,
            'include_inactive': self.include_inactive.data,
            'group_by': self.group_by.data
        }
        
        if self.report_type.data == 'custom_query':
            return report_service.execute_custom_query(
                self.custom_query.data, 
                self.output_format.data
            )
        else:
            return report_service.generate_report(
                self.report_type.data,
                filters,
                self.output_format.data,
                self.chart_type.data if self.output_format.data == 'chart' else None
            )


# =============================================================================
# FORMULARIOS DE CONFIGURACIÓN DEL SISTEMA
# =============================================================================

class AdminSettingsForm(BaseForm):
    """Formulario para configuraciones del sistema"""
    
    # Configuraciones generales
    app_name = StringField(
        'Nombre de la Aplicación',
        validators=[
            DataRequired(),
            Length(min=3, max=100)
        ]
    )
    
    app_description = TextAreaField(
        'Descripción de la Aplicación',
        validators=[Length(max=500)],
        render_kw={'rows': 3}
    )
    
    maintenance_mode = BooleanField('Modo de Mantenimiento')
    
    maintenance_message = TextAreaField(
        'Mensaje de Mantenimiento',
        validators=[Length(max=1000)],
        render_kw={'rows': 4}
    )
    
    # Configuraciones de registro
    registration_enabled = BooleanField('Registro Habilitado', default=True)
    email_verification_required = BooleanField('Verificación de Email Requerida', default=True)
    admin_approval_required = BooleanField('Aprobación de Admin Requerida')
    
    allowed_domains = TextAreaField(
        'Dominios de Email Permitidos',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 4,
            'placeholder': 'example.com\ncompany.org\n(uno por línea, vacío = todos)'
        }
    )
    
    # Configuraciones de seguridad
    session_timeout_minutes = IntegerField(
        'Timeout de Sesión (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=5, max=1440)  # 5 min a 24 horas
        ],
        default=120
    )
    
    max_login_attempts = IntegerField(
        'Máximo Intentos de Login',
        validators=[
            DataRequired(),
            NumberRange(min=3, max=20)
        ],
        default=5
    )
    
    password_min_length = IntegerField(
        'Longitud Mínima de Contraseña',
        validators=[
            DataRequired(),
            NumberRange(min=6, max=50)
        ],
        default=8
    )
    
    force_2fa_for_admins = BooleanField('Forzar 2FA para Administradores')
    
    # Configuraciones de archivos
    max_file_size_mb = IntegerField(
        'Tamaño Máximo de Archivo (MB)',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100)
        ],
        default=10
    )
    
    allowed_file_types = SelectMultipleField(
        'Tipos de Archivo Permitidos',
        choices=[
            ('pdf', 'PDF'),
            ('doc', 'Word (.doc)'),
            ('docx', 'Word (.docx)'),
            ('xls', 'Excel (.xls)'),
            ('xlsx', 'Excel (.xlsx)'),
            ('ppt', 'PowerPoint (.ppt)'),
            ('pptx', 'PowerPoint (.pptx)'),
            ('jpg', 'JPEG'),
            ('png', 'PNG'),
            ('gif', 'GIF'),
            ('zip', 'ZIP'),
            ('csv', 'CSV')
        ],
        render_kw={'size': '10'}
    )
    
    # Configuraciones de notificaciones
    email_notifications_enabled = BooleanField('Notificaciones por Email', default=True)
    sms_notifications_enabled = BooleanField('Notificaciones por SMS')
    push_notifications_enabled = BooleanField('Notificaciones Push')
    
    # Configuraciones de integración
    google_analytics_id = StringField(
        'Google Analytics ID',
        validators=[
            WTFOptional(),
            Regexp(r'^(G-|GA_MEASUREMENT_ID|UA-)', message='ID de Analytics inválido')
        ]
    )
    
    recaptcha_enabled = BooleanField('reCAPTCHA Habilitado')
    recaptcha_site_key = StringField('reCAPTCHA Site Key')
    recaptcha_secret_key = PasswordField('reCAPTCHA Secret Key')
    
    # Configuraciones de contenido
    default_language = SelectField(
        'Idioma por Defecto',
        choices=[
            ('es', 'Español'),
            ('en', 'English'),
            ('pt', 'Português')
        ],
        default='es'
    )
    
    default_timezone = SelectField(
        'Zona Horaria por Defecto',
        choices=[
            ('America/Bogota', 'Colombia (UTC-5)'),
            ('America/Mexico_City', 'México (UTC-6)'),
            ('America/Sao_Paulo', 'Brasil (UTC-3)'),
            ('America/Argentina/Buenos_Aires', 'Argentina (UTC-3)'),
            ('America/Lima', 'Perú (UTC-5)'),
            ('America/Santiago', 'Chile (UTC-3)'),
            ('UTC', 'UTC')
        ],
        default='America/Bogota'
    )
    
    # Configuraciones de backup
    auto_backup_enabled = BooleanField('Backup Automático')
    backup_frequency_hours = IntegerField(
        'Frecuencia de Backup (horas)',
        validators=[NumberRange(min=1, max=168)],  # 1 hora a 1 semana
        default=24
    )
    
    submit = SubmitField('Guardar Configuraciones')
    
    def validate_allowed_domains(self, field):
        """Valida formato de dominios permitidos"""
        if field.data:
            domains = [d.strip() for d in field.data.split('\n') if d.strip()]
            for domain in domains:
                if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                    raise ValidationError(f'Dominio inválido: {domain}')
    
    def save_settings(self) -> bool:
        """Guarda las configuraciones del sistema"""
        try:
            from app.services.admin import AdminConfigService
            
            config_service = AdminConfigService()
            settings_data = self.to_dict(exclude=['csrf_token', 'submit'])
            
            return config_service.update_system_settings(settings_data)
            
        except Exception as e:
            logger.error(f"Error saving system settings: {e}")
            return False


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Validadores
    'AdminPermissionRequired',
    'BulkActionLimit',
    'DateRangeLimit',
    
    # Formularios de usuarios
    'AdminUserCreateForm',
    'AdminUserEditForm', 
    'AdminBulkUserForm',
    
    # Formularios de organizaciones
    'AdminOrganizationForm',
    
    # Formularios de programas
    'AdminProgramForm',
    
    # Formularios de reportes
    'AdminReportForm',
    
    # Formularios de configuración
    'AdminSettingsForm'
]