# -*- coding: utf-8 -*-
"""
Project Forms Module
==================

Formularios para la gestión completa de proyectos en el ecosistema de emprendimiento.
Incluye creación, edición, gestión de equipo, financiamiento y seguimiento de progreso.

Author: Ecosistema Emprendimiento Team
Date: 2025
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, FloatField,
    DateField, DateTimeField, BooleanField, FieldList, FormField,
    HiddenField, RadioField, SelectMultipleField
)
from wtforms.validators import (
    DataRequired, Length, Email, NumberRange, Optional,
    ValidationError, URL, Regexp
)
from wtforms.widgets import TextArea, Select

from .base import BaseForm
from .validators import (
    validate_future_date, validate_past_or_today_date,
    validate_positive_number, validate_currency_amount,
    validate_percentage, validate_phone_number,
    UniqueFieldValidator, ConditionalRequired
)
from ..models.project import Project, ProjectStatus, ProjectCategory, ProjectPriority
from ..models.user import User
from ..models.organization import Organization
from ..core.constants import (
    PROJECT_STATUSES, PROJECT_CATEGORIES, PROJECT_PRIORITIES,
    CURRENCIES, FUNDING_TYPES, BUSINESS_MODELS,
    MIN_PROJECT_NAME_LENGTH, MAX_PROJECT_NAME_LENGTH,
    MIN_DESCRIPTION_LENGTH, MAX_DESCRIPTION_LENGTH
)


class CreateProjectForm(BaseForm):
    """Formulario para crear un nuevo proyecto de emprendimiento."""
    
    # Información básica
    name = StringField(
        'Nombre del Proyecto',
        validators=[
            DataRequired(message='El nombre del proyecto es obligatorio'),
            Length(
                min=MIN_PROJECT_NAME_LENGTH,
                max=MAX_PROJECT_NAME_LENGTH,
                message=f'El nombre debe tener entre {MIN_PROJECT_NAME_LENGTH} y {MAX_PROJECT_NAME_LENGTH} caracteres'
            ),
            UniqueFieldValidator(Project, 'name', message='Ya existe un proyecto con este nombre')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Ingresa el nombre de tu proyecto',
            'autocomplete': 'off'
        }
    )
    
    short_description = StringField(
        'Descripción Corta',
        validators=[
            DataRequired(message='La descripción corta es obligatoria'),
            Length(
                min=10,
                max=200,
                message='La descripción corta debe tener entre 10 y 200 caracteres'
            )
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe tu proyecto en una frase',
            'maxlength': '200'
        }
    )
    
    description = TextAreaField(
        'Descripción Detallada',
        validators=[
            DataRequired(message='La descripción detallada es obligatoria'),
            Length(
                min=MIN_DESCRIPTION_LENGTH,
                max=MAX_DESCRIPTION_LENGTH,
                message=f'La descripción debe tener entre {MIN_DESCRIPTION_LENGTH} y {MAX_DESCRIPTION_LENGTH} caracteres'
            )
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe detalladamente tu proyecto, problema que resuelve, propuesta de valor...',
            'rows': '6'
        }
    )
    
    category = SelectField(
        'Categoría',
        choices=PROJECT_CATEGORIES,
        validators=[DataRequired(message='Selecciona una categoría')],
        render_kw={'class': 'form-select'}
    )
    
    priority = SelectField(
        'Prioridad',
        choices=PROJECT_PRIORITIES,
        default='medium',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    # Fechas
    start_date = DateField(
        'Fecha de Inicio',
        validators=[
            DataRequired(message='La fecha de inicio es obligatoria'),
            validate_past_or_today_date
        ],
        render_kw={'class': 'form-control'}
    )
    
    expected_end_date = DateField(
        'Fecha Esperada de Finalización',
        validators=[
            Optional(),
            validate_future_date
        ],
        render_kw={'class': 'form-control'}
    )
    
    # Modelo de negocio y mercado
    business_model = SelectField(
        'Modelo de Negocio',
        choices=BUSINESS_MODELS,
        validators=[DataRequired(message='Selecciona un modelo de negocio')],
        render_kw={'class': 'form-select'}
    )
    
    target_market = TextAreaField(
        'Mercado Objetivo',
        validators=[
            DataRequired(message='Describe tu mercado objetivo'),
            Length(min=50, max=1000, message='Describe tu mercado objetivo en 50-1000 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe tu mercado objetivo, segmento de clientes, tamaño del mercado...',
            'rows': '4'
        }
    )
    
    # Financiamiento
    estimated_budget = FloatField(
        'Presupuesto Estimado',
        validators=[
            DataRequired(message='El presupuesto estimado es obligatorio'),
            validate_positive_number,
            validate_currency_amount
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    currency = SelectField(
        'Moneda',
        choices=CURRENCIES,
        default='COP',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    funding_needed = BooleanField(
        'Requiere Financiamiento Externo',
        render_kw={'class': 'form-check-input'}
    )
    
    funding_amount = FloatField(
        'Monto de Financiamiento Requerido',
        validators=[
            ConditionalRequired('funding_needed'),
            validate_positive_number,
            validate_currency_amount
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    funding_type = SelectField(
        'Tipo de Financiamiento',
        choices=FUNDING_TYPES,
        validators=[ConditionalRequired('funding_needed')],
        render_kw={'class': 'form-select'}
    )
    
    # Equipo y organización
    organization_id = SelectField(
        'Organización',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    team_size = IntegerField(
        'Tamaño del Equipo',
        validators=[
            DataRequired(message='Indica el tamaño del equipo'),
            NumberRange(min=1, max=50, message='El equipo debe tener entre 1 y 50 miembros')
        ],
        render_kw={
            'class': 'form-control',
            'min': '1',
            'max': '50'
        }
    )
    
    # Archivos
    logo = FileField(
        'Logo del Proyecto',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Solo se permiten imágenes')
        ],
        render_kw={'class': 'form-control'}
    )
    
    pitch_deck = FileField(
        'Pitch Deck (PDF)',
        validators=[
            FileAllowed(['pdf'], 'Solo se permiten archivos PDF')
        ],
        render_kw={'class': 'form-control'}
    )
    
    # Configuración y permisos
    is_public = BooleanField(
        'Proyecto Público',
        default=False,
        render_kw={'class': 'form-check-input'}
    )
    
    allows_collaboration = BooleanField(
        'Permite Colaboraciones',
        default=True,
        render_kw={'class': 'form-check-input'}
    )
    
    # Campos de seguimiento
    website_url = StringField(
        'Sitio Web',
        validators=[
            Optional(),
            URL(message='Ingresa una URL válida')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'https://www.ejemplo.com'
        }
    )
    
    social_media = TextAreaField(
        'Redes Sociales',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Enlaces a redes sociales (uno por línea)',
            'rows': '3'
        }
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar organizaciones disponibles
        self.organization_id.choices = [(0, 'Sin organización')] + [
            (org.id, org.name) for org in Organization.query.filter_by(is_active=True).all()
        ]
    
    def validate_expected_end_date(self, field):
        """Validar que la fecha de finalización sea posterior a la de inicio."""
        if field.data and self.start_date.data:
            if field.data <= self.start_date.data:
                raise ValidationError('La fecha de finalización debe ser posterior a la fecha de inicio')
    
    def validate_funding_amount(self, field):
        """Validar que el monto de financiamiento no exceda el presupuesto."""
        if field.data and self.estimated_budget.data:
            if field.data > self.estimated_budget.data:
                raise ValidationError('El financiamiento no puede exceder el presupuesto total')


class EditProjectForm(CreateProjectForm):
    """Formulario para editar un proyecto existente."""
    
    id = HiddenField()
    
    status = SelectField(
        'Estado',
        choices=PROJECT_STATUSES,
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    completion_percentage = IntegerField(
        'Porcentaje de Avance (%)',
        validators=[
            DataRequired(message='El porcentaje de avance es obligatorio'),
            NumberRange(min=0, max=100, message='El porcentaje debe estar entre 0 y 100'),
            validate_percentage
        ],
        render_kw={
            'class': 'form-control',
            'min': '0',
            'max': '100'
        }
    )
    
    actual_end_date = DateField(
        'Fecha Real de Finalización',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    lessons_learned = TextAreaField(
        'Lecciones Aprendidas',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Documenta las lecciones aprendidas durante el desarrollo del proyecto',
            'rows': '4'
        }
    )
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            # Excluir el proyecto actual de la validación de nombre único
            self.name.validators = [v for v in self.name.validators 
                                   if not isinstance(v, UniqueFieldValidator)]
            self.name.validators.append(
                UniqueFieldValidator(
                    Project, 'name', 
                    exclude_id=project.id,
                    message='Ya existe otro proyecto con este nombre'
                )
            )


class ProjectMilestoneForm(BaseForm):
    """Formulario para agregar/editar hitos del proyecto."""
    
    project_id = HiddenField()
    
    title = StringField(
        'Título del Hito',
        validators=[
            DataRequired(message='El título es obligatorio'),
            Length(min=5, max=200, message='El título debe tener entre 5 y 200 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Ej: Lanzamiento del MVP'
        }
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es obligatoria'),
            Length(min=20, max=1000, message='La descripción debe tener entre 20 y 1000 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe detalladamente este hito',
            'rows': '4'
        }
    )
    
    target_date = DateField(
        'Fecha Objetivo',
        validators=[
            DataRequired(message='La fecha objetivo es obligatoria'),
            validate_future_date
        ],
        render_kw={'class': 'form-control'}
    )
    
    is_critical = BooleanField(
        'Hito Crítico',
        render_kw={'class': 'form-check-input'}
    )
    
    budget_allocated = FloatField(
        'Presupuesto Asignado',
        validators=[
            Optional(),
            validate_positive_number,
            validate_currency_amount
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    assigned_to_id = SelectField(
        'Responsable',
        coerce=int,
        validators=[DataRequired(message='Asigna un responsable')],
        render_kw={'class': 'form-select'}
    )
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            # Cargar miembros del equipo del proyecto
            team_members = project.team_members.all()
            self.assigned_to_id.choices = [
                (member.id, f"{member.first_name} {member.last_name}") 
                for member in team_members
            ]


class ProjectTeamForm(BaseForm):
    """Formulario para gestionar miembros del equipo del proyecto."""
    
    project_id = HiddenField()
    
    user_id = SelectField(
        'Usuario',
        coerce=int,
        validators=[DataRequired(message='Selecciona un usuario')],
        render_kw={'class': 'form-select'}
    )
    
    role = StringField(
        'Rol en el Proyecto',
        validators=[
            DataRequired(message='El rol es obligatorio'),
            Length(min=3, max=100, message='El rol debe tener entre 3 y 100 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Ej: Desarrollador Frontend, Diseñador UX, etc.'
        }
    )
    
    responsibilities = TextAreaField(
        'Responsabilidades',
        validators=[
            DataRequired(message='Las responsabilidades son obligatorias'),
            Length(min=20, max=500, message='Las responsabilidades deben tener entre 20 y 500 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe las principales responsabilidades de este miembro',
            'rows': '3'
        }
    )
    
    start_date = DateField(
        'Fecha de Incorporación',
        validators=[DataRequired(message='La fecha de incorporación es obligatoria')],
        render_kw={'class': 'form-control'}
    )
    
    end_date = DateField(
        'Fecha de Finalización',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    hourly_rate = FloatField(
        'Tarifa por Hora',
        validators=[
            Optional(),
            validate_positive_number
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    is_leader = BooleanField(
        'Líder del Equipo',
        render_kw={'class': 'form-check-input'}
    )
    
    can_edit_project = BooleanField(
        'Puede Editar Proyecto',
        render_kw={'class': 'form-check-input'}
    )
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            # Excluir usuarios que ya son miembros del proyecto
            existing_members = [member.id for member in project.team_members.all()]
            available_users = User.query.filter(
                ~User.id.in_(existing_members),
                User.is_active == True
            ).all()
            
            self.user_id.choices = [
                (user.id, f"{user.first_name} {user.last_name} ({user.email})")
                for user in available_users
            ]
    
    def validate_end_date(self, field):
        """Validar que la fecha de finalización sea posterior a la de inicio."""
        if field.data and self.start_date.data:
            if field.data <= self.start_date.data:
                raise ValidationError('La fecha de finalización debe ser posterior a la fecha de incorporación')


class ProjectFundingForm(BaseForm):
    """Formulario para registrar financiamiento del proyecto."""
    
    project_id = HiddenField()
    
    funding_source = StringField(
        'Fuente de Financiamiento',
        validators=[
            DataRequired(message='La fuente de financiamiento es obligatoria'),
            Length(min=3, max=200, message='La fuente debe tener entre 3 y 200 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Ej: Inversionista Ángel, Banco, Capital Semilla, etc.'
        }
    )
    
    funding_type = SelectField(
        'Tipo de Financiamiento',
        choices=FUNDING_TYPES,
        validators=[DataRequired(message='Selecciona el tipo de financiamiento')],
        render_kw={'class': 'form-select'}
    )
    
    amount = FloatField(
        'Monto',
        validators=[
            DataRequired(message='El monto es obligatorio'),
            validate_positive_number,
            validate_currency_amount
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    currency = SelectField(
        'Moneda',
        choices=CURRENCIES,
        default='COP',
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    
    funding_date = DateField(
        'Fecha de Obtención',
        validators=[DataRequired(message='La fecha de obtención es obligatoria')],
        render_kw={'class': 'form-control'}
    )
    
    interest_rate = FloatField(
        'Tasa de Interés (%)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='La tasa debe estar entre 0 y 100%')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.0',
            'step': '0.1',
            'min': '0',
            'max': '100'
        }
    )
    
    equity_percentage = FloatField(
        'Porcentaje de Equity (%)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='El equity debe estar entre 0 y 100%')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.0',
            'step': '0.1',
            'min': '0',
            'max': '100'
        }
    )
    
    repayment_terms = TextAreaField(
        'Términos de Pago',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Describe los términos de pago o devolución',
            'rows': '3'
        }
    )
    
    conditions = TextAreaField(
        'Condiciones Especiales',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Condiciones especiales del financiamiento',
            'rows': '3'
        }
    )
    
    contact_person = StringField(
        'Persona de Contacto',
        validators=[
            Optional(),
            Length(max=200, message='El nombre no puede exceder 200 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Nombre de la persona de contacto'
        }
    )
    
    contact_email = StringField(
        'Email de Contacto',
        validators=[
            Optional(),
            Email(message='Ingresa un email válido')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'email@ejemplo.com'
        }
    )
    
    contact_phone = StringField(
        'Teléfono de Contacto',
        validators=[
            Optional(),
            validate_phone_number
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '+57 300 123 4567'
        }
    )


class ProjectStatusForm(BaseForm):
    """Formulario rápido para actualizar el estado del proyecto."""
    
    project_id = HiddenField()
    
    status = SelectField(
        'Estado',
        choices=PROJECT_STATUSES,
        validators=[DataRequired(message='Selecciona un estado')],
        render_kw={'class': 'form-select'}
    )
    
    completion_percentage = IntegerField(
        'Porcentaje de Avance (%)',
        validators=[
            DataRequired(message='El porcentaje de avance es obligatorio'),
            NumberRange(min=0, max=100, message='El porcentaje debe estar entre 0 y 100')
        ],
        render_kw={
            'class': 'form-control',
            'min': '0',
            'max': '100'
        }
    )
    
    status_notes = TextAreaField(
        'Notas del Estado',
        validators=[
            Optional(),
            Length(max=1000, message='Las notas no pueden exceder 1000 caracteres')
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Comentarios adicionales sobre el cambio de estado',
            'rows': '3'
        }
    )


class ProjectSearchForm(BaseForm):
    """Formulario para buscar y filtrar proyectos."""
    
    search_term = StringField(
        'Buscar',
        validators=[Optional()],
        render_kw={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre, descripción o palabras clave...'
        }
    )
    
    category = SelectField(
        'Categoría',
        choices=[('', 'Todas las categorías')] + PROJECT_CATEGORIES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    status = SelectField(
        'Estado',
        choices=[('', 'Todos los estados')] + PROJECT_STATUSES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    priority = SelectField(
        'Prioridad',
        choices=[('', 'Todas las prioridades')] + PROJECT_PRIORITIES,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    organization_id = SelectField(
        'Organización',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    funding_needed = SelectField(
        'Requiere Financiamiento',
        choices=[('', 'Todos'), ('true', 'Sí'), ('false', 'No')],
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    budget_min = FloatField(
        'Presupuesto Mínimo',
        validators=[
            Optional(),
            validate_positive_number
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    budget_max = FloatField(
        'Presupuesto Máximo',
        validators=[
            Optional(),
            validate_positive_number
        ],
        render_kw={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        }
    )
    
    start_date_from = DateField(
        'Fecha Inicio Desde',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    start_date_to = DateField(
        'Fecha Inicio Hasta',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    is_public = SelectField(
        'Visibilidad',
        choices=[('', 'Todos'), ('true', 'Públicos'), ('false', 'Privados')],
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    sort_by = SelectField(
        'Ordenar por',
        choices=[
            ('created_date_desc', 'Más recientes'),
            ('created_date_asc', 'Más antiguos'),
            ('name_asc', 'Nombre A-Z'),
            ('name_desc', 'Nombre Z-A'),
            ('budget_desc', 'Mayor presupuesto'),
            ('budget_asc', 'Menor presupuesto'),
            ('completion_desc', 'Mayor avance'),
            ('completion_asc', 'Menor avance')
        ],
        default='created_date_desc',
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar organizaciones disponibles
        self.organization_id.choices = [(0, 'Todas las organizaciones')] + [
            (org.id, org.name) for org in Organization.query.filter_by(is_active=True).all()
        ]
    
    def validate_budget_max(self, field):
        """Validar que el presupuesto máximo sea mayor al mínimo."""
        if field.data and self.budget_min.data:
            if field.data < self.budget_min.data:
                raise ValidationError('El presupuesto máximo debe ser mayor al mínimo')
    
    def validate_start_date_to(self, field):
        """Validar que la fecha final sea posterior a la inicial."""
        if field.data and self.start_date_from.data:
            if field.data < self.start_date_from.data:
                raise ValidationError('La fecha final debe ser posterior a la inicial')


class BulkProjectActionForm(BaseForm):
    """Formulario para acciones masivas en proyectos."""
    
    project_ids = FieldList(
        HiddenField(),
        min_entries=1,
        validators=[DataRequired(message='Selecciona al menos un proyecto')]
    )
    
    action = SelectField(
        'Acción',
        choices=[
            ('update_status', 'Actualizar Estado'),
            ('assign_organization', 'Asignar Organización'),
            ('export_data', 'Exportar Datos'),
            ('archive', 'Archivar'),
            ('delete', 'Eliminar')
        ],
        validators=[DataRequired(message='Selecciona una acción')],
        render_kw={'class': 'form-select'}
    )
    
    # Campos condicionales según la acción
    new_status = SelectField(
        'Nuevo Estado',
        choices=PROJECT_STATUSES,
        validators=[ConditionalRequired('action', 'update_status')],
        render_kw={'class': 'form-select'}
    )
    
    organization_id = SelectField(
        'Organización',
        coerce=int,
        validators=[ConditionalRequired('action', 'assign_organization')],
        render_kw={'class': 'form-select'}
    )
    
    confirm_action = BooleanField(
        'Confirmar Acción',
        validators=[DataRequired(message='Debes confirmar la acción')],
        render_kw={'class': 'form-check-input'}
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar organizaciones disponibles
        self.organization_id.choices = [
            (org.id, org.name) for org in Organization.query.filter_by(is_active=True).all()
        ]


# Exportar formularios principales
__all__ = [
    'CreateProjectForm',
    'EditProjectForm', 
    'ProjectMilestoneForm',
    'ProjectTeamForm',
    'ProjectFundingForm',
    'ProjectStatusForm',
    'ProjectSearchForm',
    'BulkProjectActionForm'
]