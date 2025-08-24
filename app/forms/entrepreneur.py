"""
Entrepreneur Forms Module

Formularios específicos para emprendedores en el ecosistema.
Incluye perfil, proyectos, pitch decks, business plans y aplicaciones.

Author: jusga
Date: 2025
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from decimal import Decimal
from flask import current_app, g, flash, request, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, EmailField, TelField,
    SelectField, SelectMultipleField, BooleanField, 
    IntegerField, FloatField, DecimalField, DateField, DateTimeField,
    RadioField, HiddenField, SubmitField, FieldList, FormField
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange, Optional as WTFOptional,
    Regexp, URL, ValidationError, InputRequired
)
from wtforms.widgets import TextArea, Select, NumberInput

from app.forms.base import BaseForm, ModelForm, AuditMixin, CacheableMixin
from app.forms.validators import (
    SecurePassword, InternationalPhone, UniqueEmail, SecureFileUpload,
    ImageValidator, ColombianNIT, BusinessEmail, BudgetRange,
    EntrepreneurCapacity, BaseValidator, FutureDate, DateRange
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.program import Program
from app.models.organization import Organization
from app.models.milestone import Milestone
from app.models.application import Application
from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES ESPECÍFICOS PARA EMPRENDEDORES
# =============================================================================

class ProjectUniqueSlug(BaseValidator):
    """Validador para slug único de proyecto por emprendedor"""
    
    def __init__(self, entrepreneur_id_field: str = 'entrepreneur_id', 
                 project_id: int = None, message: str = None):
        super().__init__(message)
        self.entrepreneur_id_field = entrepreneur_id_field
        self.project_id = project_id
    
    def validate(self, form, field):
        if not field.data:
            return
        
        entrepreneur_id_field = getattr(form, self.entrepreneur_id_field, None)
        entrepreneur_id = entrepreneur_id_field.data if entrepreneur_id_field else g.current_user.id
        
        query = Project.query.filter(
            Project.entrepreneur_id == entrepreneur_id,
            Project.slug == field.data
        )
        
        # Excluir proyecto actual si se está editando
        if self.project_id:
            query = query.filter(Project.id != self.project_id)
        
        if query.first():
            raise ValidationError(
                self.message or 'Ya tiene un proyecto con este nombre'
            )


class ValidIndustryStage(BaseValidator):
    """Validador para combinaciones válidas de industria y etapa"""
    
    def __init__(self, industry_field: str = 'industry', message: str = None):
        super().__init__(message)
        self.industry_field = industry_field
        
        # Etapas válidas por industria
        self.valid_combinations = {
            'fintech': ['idea', 'prototype', 'mvp', 'early_stage', 'growth', 'scale'],
            'healthtech': ['idea', 'prototype', 'mvp', 'early_stage', 'growth'],
            'edtech': ['idea', 'prototype', 'mvp', 'early_stage', 'growth', 'scale'],
            'agtech': ['prototype', 'mvp', 'early_stage', 'growth'],
            'cleantech': ['prototype', 'mvp', 'early_stage', 'growth'],
            'ecommerce': ['mvp', 'early_stage', 'growth', 'scale'],
            'saas': ['prototype', 'mvp', 'early_stage', 'growth', 'scale'],
            'marketplace': ['mvp', 'early_stage', 'growth', 'scale'],
            'social_impact': ['idea', 'prototype', 'mvp', 'early_stage', 'growth']
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        industry_field = getattr(form, self.industry_field, None)
        if not industry_field or not industry_field.data:
            return
        
        industry = industry_field.data
        stage = field.data
        
        valid_stages = self.valid_combinations.get(industry, [])
        
        if stage not in valid_stages:
            stage_names = {
                'idea': 'Idea',
                'prototype': 'Prototipo',
                'mvp': 'MVP',
                'early_stage': 'Etapa Temprana',
                'growth': 'Crecimiento',
                'scale': 'Escalamiento'
            }
            valid_stage_names = [stage_names.get(s, s) for s in valid_stages]
            raise ValidationError(
                f'Para {industry}, las etapas válidas son: {", ".join(valid_stage_names)}'
            )


class RealisticTimeline(BaseValidator):
    """Validador para cronogramas realistas de proyecto"""
    
    def __init__(self, start_date_field: str = 'start_date', 
                 project_type_field: str = 'project_type', message: str = None):
        super().__init__(message)
        self.start_date_field = start_date_field
        self.project_type_field = project_type_field
        
        # Duraciones mínimas por tipo de proyecto (en meses)
        self.min_durations = {
            'mvp': 3,
            'startup': 12,
            'scale_up': 24,
            'social_impact': 6,
            'research': 18
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        start_date_field = getattr(form, self.start_date_field, None)
        project_type_field = getattr(form, self.project_type_field, None)
        
        if not start_date_field or not start_date_field.data:
            return
        if not project_type_field or not project_type_field.data:
            return
        
        start_date = start_date_field.data
        end_date = field.data
        project_type = project_type_field.data
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        duration_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        min_duration = self.min_durations.get(project_type, 6)
        
        if duration_months < min_duration:
            raise ValidationError(
                f'Duración mínima para {project_type}: {min_duration} meses'
            )


class TeamMemberEmail(BaseValidator):
    """Validador para emails de miembros del equipo"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # Verificar que no sea el email del emprendedor actual
        if hasattr(g, 'current_user') and g.current_user.email == field.data:
            raise ValidationError('No puede agregarse a sí mismo como miembro del equipo')
        
        # Verificar formato de email
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', field.data):
            raise ValidationError('Email inválido')


class MilestoneProgress(BaseValidator):
    """Validador para progreso de hitos"""
    
    def __init__(self, message: str = None):
        super().__init__(message)
    
    def validate(self, form, field):
        if field.data is None:
            return
        
        progress = field.data
        
        if not 0 <= progress <= 100:
            raise ValidationError('El progreso debe estar entre 0 y 100%')
        
        # Si el progreso es 100%, validar que se haya completado
        if progress == 100:
            completion_date_field = getattr(form, 'completion_date', None)
            if completion_date_field and not completion_date_field.data:
                raise ValidationError('Debe especificar fecha de completado si el progreso es 100%')


# =============================================================================
# SUB-FORMULARIOS REUTILIZABLES
# =============================================================================

class TeamMemberForm(BaseForm):
    """Sub-formulario para miembros del equipo"""
    
    name = StringField(
        'Nombre Completo',
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(),
            Email(),
            TeamMemberEmail()
        ]
    )
    
    role = StringField(
        'Rol en el Proyecto',
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )
    
    linkedin_url = StringField(
        'LinkedIn',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'linkedin\.com/in/', message='URL de LinkedIn inválida')
        ]
    )
    
    skills = StringField(
        'Habilidades Principales',
        validators=[Length(max=300)],
        render_kw={'placeholder': 'Python, Marketing, Finanzas (separadas por comas)'}
    )
    
    is_founder = BooleanField('Es Cofundador')
    equity_percentage = FloatField(
        'Porcentaje de Equity (%)',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=100)
        ]
    )


class MilestoneForm(BaseForm):
    """Sub-formulario para hitos del proyecto"""
    
    title = StringField(
        'Título del Hito',
        validators=[
            DataRequired(),
            Length(min=5, max=150)
        ]
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(),
            Length(min=20, max=1000)
        ],
        render_kw={'rows': 4}
    )
    
    target_date = DateField(
        'Fecha Objetivo',
        validators=[
            DataRequired(),
            FutureDate(min_days=1, max_days=730)  # Máximo 2 años
        ]
    )
    
    completion_date = DateField(
        'Fecha de Completado',
        validators=[WTFOptional()]
    )
    
    progress = IntegerField(
        'Progreso (%)',
        validators=[
            WTFOptional(),
            MilestoneProgress()
        ],
        default=0,
        render_kw={'min': 0, 'max': 100}
    )
    
    priority = SelectField(
        'Prioridad',
        choices=[
            ('low', 'Baja'),
            ('medium', 'Media'),
            ('high', 'Alta'),
            ('critical', 'Crítica')
        ],
        default='medium'
    )
    
    category = SelectField(
        'Categoría',
        choices=[
            ('product', 'Producto'),
            ('marketing', 'Marketing'),
            ('sales', 'Ventas'),
            ('funding', 'Financiamiento'),
            ('legal', 'Legal'),
            ('team', 'Equipo'),
            ('operations', 'Operaciones'),
            ('research', 'Investigación')
        ]
    )


# =============================================================================
# FORMULARIOS PRINCIPALES
# =============================================================================

class EntrepreneurProfileForm(ModelForm, CacheableMixin):
    """Formulario de perfil para emprendedores"""
    
    # Información personal adicional
    bio = TextAreaField(
        'Biografía',
        validators=[
            DataRequired(message='Biografía requerida'),
            Length(min=50, max=2000, message='Entre 50 y 2000 caracteres')
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Cuéntanos sobre tu experiencia, motivaciones y visión como emprendedor...'
        }
    )
    
    date_of_birth = DateField(
        'Fecha de Nacimiento',
        validators=[DataRequired()]
    )
    
    gender = SelectField(
        'Género',
        choices=[
            ('', 'Preferir no decir'),
            ('male', 'Masculino'),
            ('female', 'Femenino'),
            ('other', 'Otro'),
            ('non_binary', 'No binario')
        ]
    )
    
    # Información educativa
    education_level = SelectField(
        'Nivel Educativo',
        choices=[
            ('', 'Seleccionar...'),
            ('high_school', 'Bachillerato'),
            ('technical', 'Técnico'),
            ('bachelor', 'Pregrado'),
            ('master', 'Maestría'),
            ('phd', 'Doctorado'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    institution = StringField(
        'Institución Educativa',
        validators=[Length(max=200)]
    )
    
    field_of_study = StringField(
        'Campo de Estudio',
        validators=[Length(max=200)]
    )
    
    graduation_year = IntegerField(
        'Año de Graduación',
        validators=[
            WTFOptional(),
            NumberRange(min=1980, max=2030)
        ]
    )
    
    # Experiencia profesional
    years_of_experience = IntegerField(
        'Años de Experiencia Profesional',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=50)
        ]
    )
    
    previous_companies = TextAreaField(
        'Empresas Anteriores',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Lista las empresas donde has trabajado y tu rol...'
        }
    )
    
    previous_startups = BooleanField('¿Has participado en startups anteriormente?')
    
    startup_experience = TextAreaField(
        'Experiencia en Startups',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe tu experiencia previa en startups...'
        }
    )
    
    # Habilidades y competencias
    technical_skills = StringField(
        'Habilidades Técnicas',
        validators=[Length(max=500)],
        render_kw={'placeholder': 'Python, JavaScript, Marketing Digital, etc.'}
    )
    
    business_skills = StringField(
        'Habilidades de Negocio',
        validators=[Length(max=500)],
        render_kw={'placeholder': 'Ventas, Finanzas, Estrategia, etc.'}
    )
    
    languages = StringField(
        'Idiomas',
        validators=[Length(max=300)],
        render_kw={'placeholder': 'Español (nativo), Inglés (avanzado), etc.'}
    )
    
    # Intereses y motivaciones
    motivation = TextAreaField(
        'Motivación para Emprender',
        validators=[
            DataRequired(),
            Length(min=50, max=1000)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Describe qué te motiva a emprender y qué tipo de impacto quieres generar...'
        }
    )
    
    industries_of_interest = SelectMultipleField(
        'Industrias de Interés',
        choices=[
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
            ('logistics', 'Logística'),
            ('tourism', 'Turismo'),
            ('food_beverage', 'Alimentos y Bebidas'),
            ('fashion', 'Moda'),
            ('real_estate', 'Bienes Raíces'),
            ('other', 'Otro')
        ],
        render_kw={'size': '8'}
    )
    
    # Disponibilidad y compromiso
    time_commitment = SelectField(
        'Dedicación de Tiempo al Emprendimiento',
        choices=[
            ('part_time', 'Medio tiempo (< 20 hrs/semana)'),
            ('three_quarter', 'Tres cuartos (20-35 hrs/semana)'),
            ('full_time', 'Tiempo completo (> 35 hrs/semana)')
        ],
        validators=[DataRequired()]
    )
    
    currently_employed = BooleanField('¿Actualmente empleado?')
    
    current_job_title = StringField(
        'Cargo Actual',
        validators=[Length(max=100)]
    )
    
    current_company = StringField(
        'Empresa Actual',
        validators=[Length(max=100)]
    )
    
    # Redes sociales y presencia online
    website_url = StringField(
        'Sitio Web Personal',
        validators=[
            WTFOptional(),
            URL()
        ]
    )
    
    github_url = StringField(
        'GitHub',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'github\.com/', message='URL de GitHub inválida')
        ]
    )
    
    twitter_url = StringField(
        'Twitter/X',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'(twitter\.com|x\.com)/', message='URL de Twitter/X inválida')
        ]
    )
    
    # Foto de perfil
    profile_photo = FileField(
        'Foto de Perfil',
        validators=[
            ImageValidator(
                max_width=800,
                max_height=800,
                min_width=200,
                min_height=200,
                max_size=3*1024*1024  # 3MB
            )
        ]
    )
    
    # Configuraciones de privacidad
    profile_public = BooleanField('Perfil público', default=True)
    contact_info_public = BooleanField('Información de contacto pública')
    experience_public = BooleanField('Experiencia pública', default=True)
    
    # Preferencias de comunicación
    email_notifications = BooleanField('Notificaciones por email', default=True)
    sms_notifications = BooleanField('Notificaciones por SMS')
    marketing_emails = BooleanField('Emails de marketing')
    
    submit = SubmitField('Actualizar Perfil')
    
    def validate_date_of_birth(self, field):
        """Valida edad mínima"""
        if field.data:
            today = date.today()
            age = today.year - field.data.year - ((today.month, today.day) < (field.data.month, field.data.day))
            if age < 16:
                raise ValidationError('Debe ser mayor de 16 años')
            if age > 80:
                raise ValidationError('Edad inválida')
    
    def validate_graduation_year(self, field):
        """Valida año de graduación"""
        if field.data:
            current_year = datetime.now().year
            if self.date_of_birth.data:
                birth_year = self.date_of_birth.data.year
                if field.data < birth_year + 16:
                    raise ValidationError('Año de graduación inválido')
    
    def _get_model_class(self):
        return Entrepreneur


class ProjectCreateForm(ModelForm, AuditMixin):
    """Formulario para crear proyectos de emprendimiento"""
    
    # Información básica del proyecto
    name = StringField(
        'Nombre del Proyecto',
        validators=[
            DataRequired(),
            Length(min=3, max=150),
            ProjectUniqueSlug()
        ]
    )
    
    slug = StringField(
        'URL del Proyecto',
        validators=[
            DataRequired(),
            Length(min=3, max=100),
            Regexp(r'^[a-z0-9-]+$', message='Solo minúsculas, números y guiones'),
            ProjectUniqueSlug()
        ],
        render_kw={'placeholder': 'mi-proyecto-startup'}
    )
    
    tagline = StringField(
        'Tagline',
        validators=[
            DataRequired(),
            Length(min=10, max=200)
        ],
        render_kw={'placeholder': 'Describe tu proyecto en una frase impactante...'}
    )
    
    description = TextAreaField(
        'Descripción del Proyecto',
        validators=[
            DataRequired(),
            Length(min=100, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe detalladamente tu proyecto, el problema que resuelve, tu solución...'
        }
    )
    
    # Categorización
    industry = SelectField(
        'Industria',
        choices=[
            ('', 'Seleccionar industria...'),
            ('fintech', 'Fintech'),
            ('healthtech', 'Healthtech'),
            ('edtech', 'Edtech'),
            ('agtech', 'Agtech'),
            ('cleantech', 'Cleantech'),
            ('ecommerce', 'E-commerce'),
            ('marketplace', 'Marketplace'),
            ('saas', 'Software como Servicio'),
            ('mobile_apps', 'Aplicaciones Móviles'),
            ('iot', 'Internet de las Cosas'),
            ('ai_ml', 'Inteligencia Artificial/ML'),
            ('blockchain', 'Blockchain'),
            ('social_impact', 'Impacto Social'),
            ('logistics', 'Logística'),
            ('tourism', 'Turismo'),
            ('food_beverage', 'Alimentos y Bebidas'),
            ('fashion', 'Moda'),
            ('real_estate', 'Bienes Raíces'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    stage = SelectField(
        'Etapa del Proyecto',
        choices=[
            ('', 'Seleccionar etapa...'),
            ('idea', 'Idea'),
            ('prototype', 'Prototipo'),
            ('mvp', 'MVP'),
            ('early_stage', 'Etapa Temprana'),
            ('growth', 'Crecimiento'),
            ('scale', 'Escalamiento')
        ],
        validators=[
            DataRequired(),
            ValidIndustryStage()
        ]
    )
    
    project_type = SelectField(
        'Tipo de Proyecto',
        choices=[
            ('', 'Seleccionar tipo...'),
            ('mvp', 'MVP'),
            ('startup', 'Startup'),
            ('scale_up', 'Scale-up'),
            ('social_impact', 'Impacto Social'),
            ('research', 'Investigación'),
            ('corporate_innovation', 'Innovación Corporativa')
        ],
        validators=[DataRequired()]
    )
    
    # Problema y solución
    problem_statement = TextAreaField(
        'Declaración del Problema',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Describe claramente el problema que tu proyecto busca resolver...'
        }
    )
    
    solution_description = TextAreaField(
        'Descripción de la Solución',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Explica cómo tu proyecto resuelve el problema identificado...'
        }
    )
    
    target_market = TextAreaField(
        'Mercado Objetivo',
        validators=[
            DataRequired(),
            Length(min=50, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Describe tu mercado objetivo, tamaño, segmentación...'
        }
    )
    
    value_proposition = TextAreaField(
        'Propuesta de Valor',
        validators=[
            DataRequired(),
            Length(min=50, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Explica qué valor único ofreces a tus clientes...'
        }
    )
    
    # Aspectos técnicos
    technology_stack = StringField(
        'Stack Tecnológico',
        validators=[Length(max=500)],
        render_kw={'placeholder': 'React, Node.js, Python, AWS, etc.'}
    )
    
    current_status = TextAreaField(
        'Estado Actual del Desarrollo',
        validators=[
            DataRequired(),
            Length(min=50, max=1000)
        ],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe el estado actual de desarrollo, qué has logrado hasta ahora...'
        }
    )
    
    # Cronograma y recursos
    start_date = DateField(
        'Fecha de Inicio',
        validators=[DataRequired()],
        default=date.today
    )
    
    expected_completion = DateField(
        'Fecha Estimada de Completación',
        validators=[
            DataRequired(),
            RealisticTimeline()
        ]
    )
    
    # Presupuesto
    budget_currency = SelectField(
        'Moneda del Presupuesto',
        choices=[
            ('COP', 'Pesos Colombianos (COP)'),
            ('USD', 'Dólares Americanos (USD)'),
            ('EUR', 'Euros (EUR)')
        ],
        default='COP'
    )
    
    estimated_budget = DecimalField(
        'Presupuesto Estimado',
        validators=[
            DataRequired(),
            NumberRange(min=1000000, max=10000000000),  # 1M a 10B COP
            BudgetRange(project_type_field='project_type')
        ],
        places=0,
        render_kw={'placeholder': '10000000'}
    )
    
    funding_needed = DecimalField(
        'Financiamiento Necesario',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=10000000000)
        ],
        places=0
    )
    
    funding_purpose = TextAreaField(
        'Propósito del Financiamiento',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Explica para qué usarás el financiamiento...'
        }
    )
    
    # Equipo inicial
    team_size = IntegerField(
        'Tamaño del Equipo',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=20)
        ],
        default=1
    )
    
    looking_for_cofounders = BooleanField('¿Buscas cofundadores?')
    
    cofounder_profiles = TextAreaField(
        'Perfiles de Cofundadores Buscados',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe qué tipo de cofundadores buscas...'
        }
    )
    
    # Métricas y validación
    has_customers = BooleanField('¿Ya tienes clientes?')
    
    customer_count = IntegerField(
        'Número de Clientes',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=1000000)
        ]
    )
    
    monthly_revenue = DecimalField(
        'Ingresos Mensuales',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=1000000000)
        ],
        places=0
    )
    
    has_mvp = BooleanField('¿Tienes un MVP?')
    mvp_url = StringField(
        'URL del MVP',
        validators=[
            WTFOptional(),
            URL()
        ]
    )
    
    # Objetivos e impacto
    success_metrics = TextAreaField(
        'Métricas de Éxito',
        validators=[
            DataRequired(),
            Length(min=50, max=1000)
        ],
        render_kw={
            'rows': 4,
            'placeholder': 'Define cómo medirás el éxito de tu proyecto...'
        }
    )
    
    social_impact = TextAreaField(
        'Impacto Social Esperado',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe el impacto social que esperas generar...'
        }
    )
    
    # Archivos
    logo = FileField(
        'Logo del Proyecto',
        validators=[
            ImageValidator(
                max_width=500,
                max_height=500,
                max_size=2*1024*1024  # 2MB
            )
        ]
    )
    
    # Configuraciones
    is_public = BooleanField('Proyecto público', default=True)
    seeking_mentorship = BooleanField('Buscando mentoría', default=True)
    open_to_collaboration = BooleanField('Abierto a colaboración', default=True)
    
    submit = SubmitField('Crear Proyecto')
    
    def validate_funding_needed(self, field):
        """Valida que el financiamiento no supere el presupuesto"""
        if field.data and self.estimated_budget.data:
            if field.data > self.estimated_budget.data:
                raise ValidationError('El financiamiento no puede superar el presupuesto total')
    
    def validate_customer_count(self, field):
        """Valida número de clientes si tiene clientes"""
        if self.has_customers.data and not field.data:
            raise ValidationError('Debe especificar número de clientes')
    
    def validate_mvp_url(self, field):
        """Valida URL del MVP si tiene MVP"""
        if self.has_mvp.data and not field.data:
            raise ValidationError('Debe proporcionar URL del MVP')
    
    def _get_model_class(self):
        return Project
    
    def save(self, commit=True):
        """Guarda proyecto con información adicional"""
        try:
            from app.extensions import db
            
            project = super().save(commit=False)
            
            # Asignar emprendedor actual
            if hasattr(g, 'current_user'):
                entrepreneur = Entrepreneur.query.filter_by(user_id=g.current_user.id).first()
                if entrepreneur:
                    project.entrepreneur_id = entrepreneur.id
            
            # Generar slug si no se proporcionó
            if not project.slug:
                import re
                project.slug = re.sub(r'[^a-z0-9]+', '-', project.name.lower()).strip('-')
            
            # Establecer estado inicial
            project.status = 'draft'
            project.progress = 0
            
            if commit:
                db.session.add(project)
                db.session.commit()
                
                logger.info(f"Project created: {project.name} by entrepreneur {project.entrepreneur_id}")
            
            return project
            
        except Exception as e:
            if commit:
                db.session.rollback()
            logger.error(f"Error creating project: {e}")
            raise


class ProjectUpdateForm(ProjectCreateForm):
    """Formulario para actualizar proyectos existentes"""
    
    # Campos adicionales para actualización
    status = SelectField(
        'Estado del Proyecto',
        choices=[
            ('draft', 'Borrador'),
            ('active', 'Activo'),
            ('paused', 'Pausado'),
            ('completed', 'Completado'),
            ('cancelled', 'Cancelado')
        ]
    )
    
    progress = IntegerField(
        'Progreso General (%)',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=100)
        ],
        render_kw={'min': 0, 'max': 100}
    )
    
    actual_completion_date = DateField(
        'Fecha Real de Completación',
        validators=[WTFOptional()]
    )
    
    lessons_learned = TextAreaField(
        'Lecciones Aprendidas',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Comparte las principales lecciones aprendidas en el desarrollo del proyecto...'
        }
    )
    
    submit = SubmitField('Actualizar Proyecto')
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(obj=project, *args, **kwargs)
        self.project = project
        
        if project:
            # Excluir proyecto actual de validación de slug
            for validator in self.slug.validators:
                if isinstance(validator, ProjectUniqueSlug):
                    validator.project_id = project.id


class PitchDeckForm(BaseForm, AuditMixin):
    """Formulario para subir y gestionar pitch decks"""
    
    title = StringField(
        'Título del Pitch Deck',
        validators=[
            DataRequired(),
            Length(min=5, max=150)
        ]
    )
    
    version = StringField(
        'Versión',
        validators=[
            DataRequired(),
            Length(min=1, max=20),
            Regexp(r'^[0-9]+\.[0-9]+(\.[0-9]+)?$', message='Formato: 1.0 o 1.0.1')
        ],
        default='1.0'
    )
    
    description = TextAreaField(
        'Descripción del Pitch Deck',
        validators=[
            DataRequired(),
            Length(min=20, max=1000)
        ],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe el contenido y propósito de este pitch deck...'
        }
    )
    
    project_id = SelectField(
        'Proyecto Asociado',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    pitch_file = FileField(
        'Archivo del Pitch Deck',
        validators=[
            FileRequired(message='Debe subir un archivo'),
            SecureFileUpload(
                allowed_extensions={'pdf', 'ppt', 'pptx'},
                max_size=20*1024*1024  # 20MB
            )
        ]
    )
    
    # Información del pitch
    slide_count = IntegerField(
        'Número de Slides',
        validators=[
            DataRequired(),
            NumberRange(min=5, max=50)
        ]
    )
    
    target_audience = SelectField(
        'Audiencia Objetivo',
        choices=[
            ('investors', 'Inversionistas'),
            ('customers', 'Clientes'),
            ('partners', 'Socios'),
            ('internal', 'Uso Interno'),
            ('competition', 'Competencia'),
            ('media', 'Medios'),
            ('general', 'Audiencia General')
        ],
        validators=[DataRequired()]
    )
    
    presentation_duration = IntegerField(
        'Duración de Presentación (minutos)',
        validators=[
            WTFOptional(),
            NumberRange(min=1, max=120)
        ]
    )
    
    # Configuraciones
    is_public = BooleanField('Disponible públicamente')
    allow_download = BooleanField('Permitir descarga')
    
    # Notas
    notes = TextAreaField(
        'Notas Adicionales',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Notas sobre el pitch deck, contexto, etc.'
        }
    )
    
    submit = SubmitField('Subir Pitch Deck')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar proyectos del emprendedor actual
        if hasattr(g, 'current_user'):
            entrepreneur = Entrepreneur.query.filter_by(user_id=g.current_user.id).first()
            if entrepreneur:
                projects = Project.query.filter_by(entrepreneur_id=entrepreneur.id).all()
                self.project_id.choices = [(0, 'Seleccionar proyecto...')] + [
                    (project.id, project.name) for project in projects
                ]


class BusinessPlanForm(BaseForm, AuditMixin):
    """Formulario para business plans"""
    
    title = StringField(
        'Título del Business Plan',
        validators=[
            DataRequired(),
            Length(min=5, max=150)
        ]
    )
    
    project_id = SelectField(
        'Proyecto Asociado',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    # Secciones del business plan
    executive_summary = TextAreaField(
        'Resumen Ejecutivo',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Resumen conciso del negocio, problema, solución, mercado y proyecciones...'
        }
    )
    
    market_analysis = TextAreaField(
        'Análisis de Mercado',
        validators=[
            DataRequired(),
            Length(min=300, max=5000)
        ],
        render_kw={
            'rows': 10,
            'placeholder': 'Análisis detallado del mercado objetivo, tamaño, competencia, tendencias...'
        }
    )
    
    business_model = TextAreaField(
        'Modelo de Negocio',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe cómo generas ingresos, estructura de costos, canales de distribución...'
        }
    )
    
    marketing_strategy = TextAreaField(
        'Estrategia de Marketing',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Plan de marketing, adquisición de clientes, posicionamiento...'
        }
    )
    
    operations_plan = TextAreaField(
        'Plan de Operaciones',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Operaciones diarias, procesos, tecnología, proveedores...'
        }
    )
    
    financial_projections = TextAreaField(
        'Proyecciones Financieras',
        validators=[
            DataRequired(),
            Length(min=300, max=5000)
        ],
        render_kw={
            'rows': 10,
            'placeholder': 'Proyecciones de ingresos, gastos, flujo de caja, punto de equilibrio...'
        }
    )
    
    # Proyecciones numéricas
    year_1_revenue = DecimalField(
        'Ingresos Proyectados Año 1',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=10000000000)
        ],
        places=0
    )
    
    year_2_revenue = DecimalField(
        'Ingresos Proyectados Año 2',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=10000000000)
        ],
        places=0
    )
    
    year_3_revenue = DecimalField(
        'Ingresos Proyectados Año 3',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=10000000000)
        ],
        places=0
    )
    
    break_even_month = IntegerField(
        'Mes de Punto de Equilibrio',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=60)  # Máximo 5 años
        ]
    )
    
    # Archivo del business plan
    business_plan_file = FileField(
        'Archivo del Business Plan',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx'},
                max_size=50*1024*1024  # 50MB
            )
        ]
    )
    
    # Configuraciones
    is_confidential = BooleanField('Business Plan Confidencial', default=True)
    
    submit = SubmitField('Guardar Business Plan')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar proyectos del emprendedor actual
        if hasattr(g, 'current_user'):
            entrepreneur = Entrepreneur.query.filter_by(user_id=g.current_user.id).first()
            if entrepreneur:
                projects = Project.query.filter_by(entrepreneur_id=entrepreneur.id).all()
                self.project_id.choices = [(0, 'Seleccionar proyecto...')] + [
                    (project.id, project.name) for project in projects
                ]
    
    def validate_year_2_revenue(self, field):
        """Valida que año 2 sea mayor que año 1"""
        if field.data and self.year_1_revenue.data:
            if field.data < self.year_1_revenue.data:
                raise ValidationError('Ingresos año 2 deben ser mayores o iguales a año 1')
    
    def validate_year_3_revenue(self, field):
        """Valida que año 3 sea mayor que año 2"""
        if field.data and self.year_2_revenue.data:
            if field.data < self.year_2_revenue.data:
                raise ValidationError('Ingresos año 3 deben ser mayores o iguales a año 2')


class ProgramApplicationForm(BaseForm, AuditMixin):
    """Formulario para aplicar a programas de emprendimiento"""
    
    program_id = HiddenField('Program ID', validators=[DataRequired()])
    
    project_id = SelectField(
        'Proyecto a Postular',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    # Información del equipo
    team_members = FieldList(
        FormField(TeamMemberForm),
        min_entries=1,
        max_entries=10
    )
    
    # Motivación y fit
    motivation = TextAreaField(
        'Motivación para Participar',
        validators=[
            DataRequired(),
            Length(min=200, max=2000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Explica por qué quieres participar en este programa y cómo te ayudará...'
        }
    )
    
    program_fit = TextAreaField(
        'Fit con el Programa',
        validators=[
            DataRequired(),
            Length(min=200, max=2000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe cómo tu proyecto encaja con los objetivos del programa...'
        }
    )
    
    expected_outcomes = TextAreaField(
        'Resultados Esperados',
        validators=[
            DataRequired(),
            Length(min=200, max=2000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Qué esperas lograr al finalizar el programa...'
        }
    )
    
    # Compromiso
    time_commitment_confirmation = BooleanField(
        'Confirmo que puedo dedicar el tiempo requerido por el programa',
        validators=[DataRequired(message='Debe confirmar disponibilidad de tiempo')]
    )
    
    full_participation = BooleanField(
        'Confirmo que participaré en todas las actividades del programa',
        validators=[DataRequired(message='Debe comprometerse a participación completa')]
    )
    
    # Información adicional
    previous_programs = TextAreaField(
        'Programas Anteriores',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Lista programas de emprendimiento en los que has participado anteriormente...'
        }
    )
    
    special_requirements = TextAreaField(
        'Requerimientos Especiales',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Menciona cualquier requerimiento especial o acomodación necesaria...'
        }
    )
    
    # Archivos de soporte
    cv_file = FileField(
        'CV/Hoja de Vida',
        validators=[
            FileRequired(),
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx'},
                max_size=5*1024*1024  # 5MB
            )
        ]
    )
    
    cover_letter = FileField(
        'Carta de Presentación',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx'},
                max_size=5*1024*1024  # 5MB
            )
        ]
    )
    
    submit = SubmitField('Enviar Aplicación')
    
    def __init__(self, program_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if program_id:
            self.program_id.data = str(program_id)
        
        # Cargar proyectos del emprendedor actual
        if hasattr(g, 'current_user'):
            entrepreneur = Entrepreneur.query.filter_by(user_id=g.current_user.id).first()
            if entrepreneur:
                projects = Project.query.filter_by(
                    entrepreneur_id=entrepreneur.id,
                    status__in=['active', 'draft']
                ).all()
                self.project_id.choices = [(0, 'Seleccionar proyecto...')] + [
                    (project.id, project.name) for project in projects
                ]


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Validadores
    'ProjectUniqueSlug',
    'ValidIndustryStage',
    'RealisticTimeline',
    'TeamMemberEmail',
    'MilestoneProgress',
    
    # Sub-formularios
    'TeamMemberForm',
    'MilestoneForm',
    
    # Formularios principales
    'EntrepreneurProfileForm',
    'ProfileForm',  # Alias para EntrepreneurProfileForm
    'ProjectCreateForm',
    'ProjectUpdateForm',
    'PitchDeckForm',
    'BusinessPlanForm',
    'ProgramApplicationForm',
    # Formularios adicionales necesarios
    'PasswordChangeForm', 'PreferencesForm', 'PrivacySettingsForm', 
    'TwoFactorForm', 'SocialLinksForm', 'ProfilePictureForm', 
    'BusinessInfoForm', 'ContactInfoForm'
]


# ====================================
# FORMULARIOS ADICIONALES PARA COMPATIBILIDAD
# ====================================

class PasswordChangeForm(BaseForm):
    """Formulario para cambio de contraseña de emprendedor"""
    
    current_password = StringField(
        'Contraseña Actual',
        validators=[DataRequired()],
        render_kw={'type': 'password', 'autocomplete': 'current-password'}
    )
    
    new_password = StringField(
        'Nueva Contraseña',
        validators=[DataRequired(), Length(min=8)],
        render_kw={'type': 'password', 'autocomplete': 'new-password'}
    )
    
    confirm_password = StringField(
        'Confirmar Nueva Contraseña',
        validators=[DataRequired()],
        render_kw={'type': 'password', 'autocomplete': 'new-password'}
    )


class PreferencesForm(BaseForm):
    """Formulario de preferencias del emprendedor"""
    
    email_notifications = BooleanField('Notificaciones por Email', default=True)
    sms_notifications = BooleanField('Notificaciones por SMS', default=False)
    newsletter = BooleanField('Recibir Newsletter', default=True)
    marketing_emails = BooleanField('Emails de Marketing', default=False)


class PrivacySettingsForm(BaseForm):
    """Formulario de configuración de privacidad"""
    
    profile_visibility = SelectField(
        'Visibilidad del Perfil',
        choices=[
            ('public', 'Público'),
            ('private', 'Privado'),
            ('connections', 'Solo Conexiones')
        ],
        default='public'
    )
    
    show_contact_info = BooleanField('Mostrar Información de Contacto', default=False)
    show_social_links = BooleanField('Mostrar Enlaces Sociales', default=True)


class TwoFactorForm(BaseForm):
    """Formulario de configuración de autenticación de dos factores"""
    
    enable_2fa = BooleanField('Habilitar 2FA', default=False)
    backup_codes = HiddenField('Códigos de Respaldo')


class SocialLinksForm(BaseForm):
    """Formulario para enlaces sociales del emprendedor"""
    
    linkedin_url = StringField(
        'LinkedIn',
        validators=[WTFOptional(), URL()],
        render_kw={'placeholder': 'https://linkedin.com/in/usuario'}
    )
    
    twitter_url = StringField(
        'Twitter',
        validators=[WTFOptional(), URL()],
        render_kw={'placeholder': 'https://twitter.com/usuario'}
    )
    
    website_url = StringField(
        'Sitio Web',
        validators=[WTFOptional(), URL()],
        render_kw={'placeholder': 'https://misitio.com'}
    )


class ProfilePictureForm(BaseForm):
    """Formulario para foto de perfil"""
    
    profile_picture = FileField(
        'Foto de Perfil',
        validators=[WTFOptional(), FileAllowed(['jpg', 'png', 'gif'], 'Solo imágenes')]
    )


class BusinessInfoForm(BaseForm):
    """Formulario de información de negocio"""
    
    business_name = StringField(
        'Nombre del Negocio',
        validators=[WTFOptional(), Length(max=100)]
    )
    
    business_type = SelectField(
        'Tipo de Negocio',
        choices=[
            ('', 'Seleccionar...'),
            ('startup', 'Startup'),
            ('small_business', 'Pequeño Negocio'),
            ('corporation', 'Corporación'),
            ('nonprofit', 'Sin Fines de Lucro')
        ]
    )
    
    business_stage = SelectField(
        'Etapa del Negocio',
        choices=[
            ('', 'Seleccionar...'),
            ('idea', 'Idea'),
            ('prototype', 'Prototipo'),
            ('mvp', 'MVP'),
            ('growth', 'Crecimiento'),
            ('mature', 'Maduro')
        ]
    )


class ContactInfoForm(BaseForm):
    """Formulario de información de contacto"""
    
    phone = TelField(
        'Teléfono',
        validators=[WTFOptional()],
        render_kw={'placeholder': '+57 300 123 4567'}
    )
    
    alternative_email = EmailField(
        'Email Alternativo',
        validators=[WTFOptional(), Email()]
    )
    
    address = TextAreaField(
        'Dirección',
        validators=[WTFOptional(), Length(max=200)],
        render_kw={'rows': 3}
    )


# Alias para compatibilidad
ProfileForm = EntrepreneurProfileForm