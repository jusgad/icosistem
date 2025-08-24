"""
Ally/Mentor Forms Module

Formularios específicos para mentores y aliados en el ecosistema.
Incluye perfil, disponibilidad, sesiones, evaluaciones y reportes.

Author: jusga
Date: 2025
"""

import json
import logging
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from decimal import Decimal
from flask import current_app, g, flash, request, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, EmailField, TelField,
    SelectField, SelectMultipleField, BooleanField, 
    IntegerField, FloatField, DecimalField, DateField, DateTimeField, TimeField,
    RadioField, HiddenField, SubmitField, FieldList, FormField
)
from wtforms.validators import (
    DataRequired, Email, Length, NumberRange, Optional as WTFOptional,
    Regexp, URL, ValidationError, InputRequired
)
from wtforms.widgets import TextArea, Select, NumberInput, TimeInput

from app.forms.base import BaseForm, ModelForm, AuditMixin, CacheableMixin, TimezoneMixin
from app.forms.validators import (
    SecurePassword, InternationalPhone, UniqueEmail, SecureFileUpload,
    ImageValidator, BusinessEmail, BaseValidator, FutureDate, DateRange,
    BusinessHours, MentorAvailability
)
from app.models.user import User
from app.models.ally import Ally
from app.models.entrepreneur import Entrepreneur
from app.models.mentorship import MentorshipSession
from app.models.availability import Availability
from app.models.meeting import Meeting
from app.models.evaluation import Evaluation
from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES ESPECÍFICOS PARA MENTORES/ALIADOS
# =============================================================================

class ExpertiseValidator(BaseValidator):
    """Validador para áreas de expertise"""
    
    def __init__(self, min_areas: int = 1, max_areas: int = 5, message: str = None):
        super().__init__(message)
        self.min_areas = min_areas
        self.max_areas = max_areas
    
    def validate(self, form, field):
        if not field.data:
            if self.min_areas > 0:
                raise ValidationError(f'Debe seleccionar al menos {self.min_areas} área(s) de expertise')
            return
        
        areas_count = len(field.data) if isinstance(field.data, list) else 0
        
        if areas_count < self.min_areas:
            raise ValidationError(f'Debe seleccionar al menos {self.min_areas} área(s) de expertise')
        
        if areas_count > self.max_areas:
            raise ValidationError(f'Máximo {self.max_areas} áreas de expertise permitidas')


class MentorshipCapacity(BaseValidator):
    """Validador para capacidad de mentoría"""
    
    def __init__(self, message: str = None):
        super().__init__(message)
    
    def validate(self, form, field):
        if not field.data:
            return
        
        capacity = field.data
        
        # Validar capacidad razonable
        if capacity < 1:
            raise ValidationError('Debe poder mentorear al menos 1 emprendedor')
        
        if capacity > 20:
            raise ValidationError('Capacidad máxima: 20 emprendedores simultáneos')
        
        # Verificar disponibilidad de tiempo
        hours_per_week_field = getattr(form, 'hours_per_week', None)
        if hours_per_week_field and hours_per_week_field.data:
            hours_per_week = hours_per_week_field.data
            min_hours_needed = capacity * 2  # Mínimo 2 horas por emprendedor
            
            if hours_per_week < min_hours_needed:
                raise ValidationError(
                    f'Necesita al menos {min_hours_needed} horas/semana para {capacity} emprendedores'
                )


class HourlyRateValidator(BaseValidator):
    """Validador para tarifas por hora"""
    
    def __init__(self, currency_field: str = 'currency', message: str = None):
        super().__init__(message)
        self.currency_field = currency_field
        
        # Rangos por moneda (valores aproximados)
        self.rate_ranges = {
            'COP': {'min': 50000, 'max': 500000},     # $50K-500K COP
            'USD': {'min': 25, 'max': 500},           # $25-500 USD
            'EUR': {'min': 20, 'max': 400}            # €20-400 EUR
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        rate = field.data
        currency_field = getattr(form, self.currency_field, None)
        currency = currency_field.data if currency_field else 'USD'
        
        if currency in self.rate_ranges:
            min_rate = self.rate_ranges[currency]['min']
            max_rate = self.rate_ranges[currency]['max']
            
            if rate < min_rate:
                raise ValidationError(f'Tarifa mínima: {min_rate} {currency}')
            
            if rate > max_rate:
                raise ValidationError(f'Tarifa máxima: {max_rate} {currency}')


class AvailabilityValidator(BaseValidator):
    """Validador para horarios de disponibilidad"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # field.data debería ser una lista de horarios
        if not isinstance(field.data, list):
            return
        
        total_hours = 0
        for slot in field.data:
            if isinstance(slot, dict) and 'start_time' in slot and 'end_time' in slot:
                try:
                    start = datetime.strptime(slot['start_time'], '%H:%M').time()
                    end = datetime.strptime(slot['end_time'], '%H:%M').time()
                    
                    # Validar que end > start
                    if end <= start:
                        raise ValidationError('Hora de fin debe ser posterior a hora de inicio')
                    
                    # Calcular duración
                    start_minutes = start.hour * 60 + start.minute
                    end_minutes = end.hour * 60 + end.minute
                    duration_hours = (end_minutes - start_minutes) / 60
                    total_hours += duration_hours
                    
                except ValueError:
                    raise ValidationError('Formato de hora inválido')
        
        # Validar total de horas razonable
        if total_hours > 80:  # Más de 80 horas por semana
            raise ValidationError('Total de horas disponibles excesivo')


class SessionRatingValidator(BaseValidator):
    """Validador para calificaciones de sesiones"""
    
    def validate(self, form, field):
        if field.data is None:
            return
        
        rating = field.data
        
        if not 1 <= rating <= 5:
            raise ValidationError('Calificación debe estar entre 1 y 5')


class ExperienceYearsValidator(BaseValidator):
    """Validador para años de experiencia"""
    
    def __init__(self, min_years: int = 1, max_years: int = 50, message: str = None):
        super().__init__(message)
        self.min_years = min_years
        self.max_years = max_years
    
    def validate(self, form, field):
        if not field.data:
            return
        
        years = field.data
        
        if years < self.min_years:
            raise ValidationError(f'Mínimo {self.min_years} año(s) de experiencia requerido(s)')
        
        if years > self.max_years:
            raise ValidationError(f'Máximo {self.max_years} años de experiencia')


# =============================================================================
# SUB-FORMULARIOS REUTILIZABLES
# =============================================================================

class AvailabilitySlotForm(BaseForm):
    """Sub-formulario para slots de disponibilidad"""
    
    day_of_week = SelectField(
        'Día de la Semana',
        choices=[
            ('monday', 'Lunes'),
            ('tuesday', 'Martes'),
            ('wednesday', 'Miércoles'),
            ('thursday', 'Jueves'),
            ('friday', 'Viernes'),
            ('saturday', 'Sábado'),
            ('sunday', 'Domingo')
        ],
        validators=[DataRequired()]
    )
    
    start_time = TimeField(
        'Hora de Inicio',
        validators=[DataRequired()],
        widget=TimeInput()
    )
    
    end_time = TimeField(
        'Hora de Fin',
        validators=[DataRequired()],
        widget=TimeInput()
    )
    
    is_recurring = BooleanField('Recurrente', default=True)
    
    def validate_end_time(self, field):
        """Valida que hora de fin sea posterior a inicio"""
        if field.data and self.start_time.data:
            if field.data <= self.start_time.data:
                raise ValidationError('Hora de fin debe ser posterior a hora de inicio')


class ExpertiseAreaForm(BaseForm):
    """Sub-formulario para áreas de expertise"""
    
    area = SelectField(
        'Área',
        choices=[
            ('business_strategy', 'Estrategia de Negocio'),
            ('marketing_digital', 'Marketing Digital'),
            ('sales', 'Ventas'),
            ('finance', 'Finanzas'),
            ('operations', 'Operaciones'),
            ('technology', 'Tecnología'),
            ('product_development', 'Desarrollo de Producto'),
            ('user_experience', 'Experiencia de Usuario'),
            ('legal', 'Legal'),
            ('fundraising', 'Recaudación de Fondos'),
            ('scaling', 'Escalamiento'),
            ('leadership', 'Liderazgo'),
            ('team_building', 'Construcción de Equipos'),
            ('innovation', 'Innovación'),
            ('international_expansion', 'Expansión Internacional')
        ],
        validators=[DataRequired()]
    )
    
    proficiency_level = SelectField(
        'Nivel de Competencia',
        choices=[
            ('beginner', 'Principiante'),
            ('intermediate', 'Intermedio'),
            ('advanced', 'Avanzado'),
            ('expert', 'Experto')
        ],
        validators=[DataRequired()],
        default='intermediate'
    )
    
    years_of_experience = IntegerField(
        'Años de Experiencia',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=50)
        ]
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[Length(max=500)],
        render_kw={'rows': 3}
    )


class EvaluationCriteriaForm(BaseForm):
    """Sub-formulario para criterios de evaluación"""
    
    criteria = StringField(
        'Criterio',
        validators=[
            DataRequired(),
            Length(min=5, max=100)
        ]
    )
    
    score = IntegerField(
        'Puntuación',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=10)
        ],
        render_kw={'min': 1, 'max': 10}
    )
    
    comments = TextAreaField(
        'Comentarios',
        validators=[Length(max=500)],
        render_kw={'rows': 3}
    )


# =============================================================================
# FORMULARIOS PRINCIPALES
# =============================================================================

class AllyProfileForm(ModelForm, CacheableMixin, TimezoneMixin):
    """Formulario de perfil para mentores/aliados"""
    
    # Información profesional
    professional_title = StringField(
        'Título Profesional',
        validators=[
            DataRequired(),
            Length(min=5, max=150)
        ],
        render_kw={'placeholder': 'CEO, CTO, Director de Marketing, etc.'}
    )
    
    company = StringField(
        'Empresa Actual',
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )
    
    company_website = StringField(
        'Sitio Web de la Empresa',
        validators=[
            WTFOptional(),
            URL()
        ]
    )
    
    industry_experience = SelectMultipleField(
        'Experiencia por Industria',
        choices=[
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
            ('consulting', 'Consultoría'),
            ('banking', 'Banca'),
            ('insurance', 'Seguros'),
            ('retail', 'Retail'),
            ('manufacturing', 'Manufactura'),
            ('other', 'Otro')
        ],
        validators=[
            ExpertiseValidator(min_areas=1, max_areas=5)
        ],
        render_kw={'size': '8'}
    )
    
    # Experiencia y trayectoria
    total_experience_years = IntegerField(
        'Años Totales de Experiencia',
        validators=[
            DataRequired(),
            ExperienceYearsValidator(min_years=3, max_years=50)
        ]
    )
    
    startup_experience_years = IntegerField(
        'Años de Experiencia en Startups',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=50)
        ]
    )
    
    companies_founded = IntegerField(
        'Empresas Fundadas',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=20)
        ],
        default=0
    )
    
    successful_exits = IntegerField(
        'Exits Exitosos',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=10)
        ],
        default=0
    )
    
    # Biografía y motivación
    bio = TextAreaField(
        'Biografía Profesional',
        validators=[
            DataRequired(),
            Length(min=100, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe tu trayectoria profesional, experiencias relevantes y motivación para ser mentor...'
        }
    )
    
    mentoring_motivation = TextAreaField(
        'Motivación para Mentorear',
        validators=[
            DataRequired(),
            Length(min=50, max=1500)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Explica por qué quieres ser mentor y qué valor puedes aportar...'
        }
    )
    
    # Áreas de expertise
    expertise_areas = FieldList(
        FormField(ExpertiseAreaForm),
        min_entries=1,
        max_entries=8,
        label='Áreas de Expertise'
    )
    
    # Logros y reconocimientos
    achievements = TextAreaField(
        'Logros y Reconocimientos',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Premios, reconocimientos, logros destacados en tu carrera...'
        }
    )
    
    # Educación
    education_background = TextAreaField(
        'Formación Académica',
        validators=[
            DataRequired(),
            Length(min=50, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Universidades, títulos, certificaciones relevantes...'
        }
    )
    
    certifications = StringField(
        'Certificaciones',
        validators=[Length(max=500)],
        render_kw={'placeholder': 'PMP, MBA, CPA, etc. (separadas por comas)'}
    )
    
    # Configuración de mentoría
    mentoring_type = SelectMultipleField(
        'Tipo de Mentoría',
        choices=[
            ('one_on_one', 'Uno a Uno'),
            ('group', 'Grupal'),
            ('workshop', 'Talleres'),
            ('advisory', 'Asesoría'),
            ('board_member', 'Miembro de Junta'),
            ('investment', 'Investor/Advisor')
        ],
        validators=[DataRequired()],
        render_kw={'size': '6'}
    )
    
    mentoring_style = SelectField(
        'Estilo de Mentoría',
        choices=[
            ('directive', 'Directivo'),
            ('coaching', 'Coaching'),
            ('supportive', 'De Apoyo'),
            ('collaborative', 'Colaborativo'),
            ('challenge_based', 'Basado en Retos')
        ],
        validators=[DataRequired()]
    )
    
    max_mentees = IntegerField(
        'Máximo Emprendedores Simultáneos',
        validators=[
            DataRequired(),
            MentorshipCapacity()
        ],
        default=3
    )
    
    # Disponibilidad general
    hours_per_week = IntegerField(
        'Horas Disponibles por Semana',
        validators=[
            DataRequired(),
            NumberRange(min=2, max=40)
        ]
    )
    
    preferred_session_duration = IntegerField(
        'Duración Preferida de Sesión (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=30, max=180)
        ],
        default=60
    )
    
    # Tarifas (opcional para mentores voluntarios)
    is_paid_mentor = BooleanField('Mentor Remunerado')
    
    hourly_rate = DecimalField(
        'Tarifa por Hora',
        validators=[
            WTFOptional(),
            HourlyRateValidator()
        ],
        places=2
    )
    
    currency = SelectField(
        'Moneda',
        choices=[
            ('COP', 'Pesos Colombianos (COP)'),
            ('USD', 'Dólares Americanos (USD)'),
            ('EUR', 'Euros (EUR)')
        ],
        default='USD'
    )
    
    payment_methods = SelectMultipleField(
        'Métodos de Pago',
        choices=[
            ('bank_transfer', 'Transferencia Bancaria'),
            ('paypal', 'PayPal'),
            ('stripe', 'Stripe'),
            ('crypto', 'Criptomonedas'),
            ('invoice', 'Facturación')
        ],
        render_kw={'size': '5'}
    )
    
    # Presencia online
    linkedin_url = StringField(
        'LinkedIn',
        validators=[
            DataRequired(),
            URL(),
            Regexp(r'linkedin\.com/in/', message='URL de LinkedIn inválida')
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
    
    personal_website = StringField(
        'Sitio Web Personal',
        validators=[
            WTFOptional(),
            URL()
        ]
    )
    
    # Archivos
    profile_photo = FileField(
        'Foto de Perfil',
        validators=[
            ImageValidator(
                max_width=800,
                max_height=800,
                min_width=300,
                min_height=300,
                max_size=3*1024*1024  # 3MB
            )
        ]
    )
    
    resume_cv = FileField(
        'CV/Hoja de Vida',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx'},
                max_size=5*1024*1024  # 5MB
            )
        ]
    )
    
    # Preferencias
    preferred_communication = SelectMultipleField(
        'Métodos de Comunicación Preferidos',
        choices=[
            ('video_call', 'Videollamada'),
            ('phone_call', 'Llamada Telefónica'),
            ('in_person', 'Presencial'),
            ('email', 'Email'),
            ('messaging', 'Mensajería')
        ],
        validators=[DataRequired()],
        render_kw={'size': '5'}
    )
    
    languages = StringField(
        'Idiomas',
        validators=[
            DataRequired(),
            Length(max=300)
        ],
        render_kw={'placeholder': 'Español (nativo), Inglés (avanzado), etc.'}
    )
    
    time_zone = SelectField(
        'Zona Horaria',
        choices=[
            ('America/Bogota', 'Colombia (UTC-5)'),
            ('America/Mexico_City', 'México (UTC-6)'),
            ('America/Sao_Paulo', 'Brasil (UTC-3)'),
            ('America/Argentina/Buenos_Aires', 'Argentina (UTC-3)'),
            ('America/Lima', 'Perú (UTC-5)'),
            ('America/Santiago', 'Chile (UTC-3)'),
            ('America/New_York', 'Nueva York (UTC-5/-4)'),
            ('Europe/Madrid', 'Madrid (UTC+1/+2)'),
            ('UTC', 'UTC')
        ],
        default='America/Bogota'
    )
    
    # Configuraciones de privacidad
    profile_public = BooleanField('Perfil Público', default=True)
    contact_info_public = BooleanField('Información de Contacto Pública')
    show_hourly_rate = BooleanField('Mostrar Tarifa Pública')
    
    # Notificaciones
    email_notifications = BooleanField('Notificaciones por Email', default=True)
    sms_notifications = BooleanField('Notificaciones por SMS')
    calendar_sync = BooleanField('Sincronización de Calendario', default=True)
    
    submit = SubmitField('Actualizar Perfil')
    
    def validate_startup_experience_years(self, field):
        """Valida que experiencia en startups no supere experiencia total"""
        if field.data and self.total_experience_years.data:
            if field.data > self.total_experience_years.data:
                raise ValidationError('Experiencia en startups no puede superar experiencia total')
    
    def validate_hourly_rate(self, field):
        """Valida tarifa si es mentor remunerado"""
        if self.is_paid_mentor.data and not field.data:
            raise ValidationError('Debe especificar tarifa por hora para mentores remunerados')
    
    def validate_payment_methods(self, field):
        """Valida métodos de pago si es mentor remunerado"""
        if self.is_paid_mentor.data and not field.data:
            raise ValidationError('Debe especificar al menos un método de pago')
    
    def _get_model_class(self):
        return Ally


class AvailabilityForm(BaseForm, TimezoneMixin):
    """Formulario para gestionar disponibilidad del mentor"""
    
    # Configuración general
    default_session_duration = IntegerField(
        'Duración por Defecto (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=15, max=240)
        ],
        default=60
    )
    
    buffer_time = IntegerField(
        'Tiempo de Buffer (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=0, max=60)
        ],
        default=15,
        render_kw={'title': 'Tiempo entre sesiones'}
    )
    
    advance_booking_days = IntegerField(
        'Días de Anticipación para Reservar',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=90)
        ],
        default=7
    )
    
    max_sessions_per_day = IntegerField(
        'Máximo Sesiones por Día',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=12)
        ],
        default=4
    )
    
    # Horarios recurrentes
    recurring_availability = FieldList(
        FormField(AvailabilitySlotForm),
        min_entries=0,
        max_entries=21,  # 3 slots por día * 7 días
        label='Disponibilidad Recurrente'
    )
    
    # Fechas específicas no disponibles
    unavailable_dates = TextAreaField(
        'Fechas No Disponibles',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Una fecha por línea (YYYY-MM-DD), ej: 2025-12-25'
        }
    )
    
    # Configuraciones especiales
    allow_weekend_sessions = BooleanField('Permitir Sesiones en Fin de Semana')
    
    emergency_sessions = BooleanField('Disponible para Sesiones de Emergencia')
    
    auto_approve_sessions = BooleanField(
        'Aprobación Automática de Sesiones',
        default=True
    )
    
    require_session_notes = BooleanField(
        'Requerir Notas de Sesión',
        default=True
    )
    
    # Preferencias de tipo de sesión
    preferred_session_types = SelectMultipleField(
        'Tipos de Sesión Preferidos',
        choices=[
            ('strategy', 'Estrategia'),
            ('product_review', 'Revisión de Producto'),
            ('pitch_practice', 'Práctica de Pitch'),
            ('problem_solving', 'Resolución de Problemas'),
            ('networking', 'Networking'),
            ('technical_review', 'Revisión Técnica'),
            ('business_model', 'Modelo de Negocio'),
            ('fundraising', 'Fundraising'),
            ('team_building', 'Team Building'),
            ('market_analysis', 'Análisis de Mercado')
        ],
        render_kw={'size': '8'}
    )
    
    # Instrucciones para emprendedores
    booking_instructions = TextAreaField(
        'Instrucciones para Reservar',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Instrucciones especiales para emprendedores que quieran reservar sesiones...'
        }
    )
    
    preparation_requirements = TextAreaField(
        'Requisitos de Preparación',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Qué deben preparar los emprendedores antes de la sesión...'
        }
    )
    
    submit = SubmitField('Guardar Disponibilidad')
    
    def validate_unavailable_dates(self, field):
        """Valida formato de fechas no disponibles"""
        if not field.data:
            return
        
        dates = [d.strip() for d in field.data.split('\n') if d.strip()]
        for date_str in dates:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise ValidationError(f'Fecha inválida: {date_str}. Use formato YYYY-MM-DD')


class MentorshipSessionForm(BaseForm, AuditMixin, TimezoneMixin):
    """Formulario para programar y gestionar sesiones de mentoría"""
    
    # Información básica
    entrepreneur_id = SelectField(
        'Emprendedor',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    session_type = SelectField(
        'Tipo de Sesión',
        choices=[
            ('initial_consultation', 'Consulta Inicial'),
            ('strategy_planning', 'Planificación Estratégica'),
            ('product_review', 'Revisión de Producto'),
            ('pitch_practice', 'Práctica de Pitch'),
            ('problem_solving', 'Resolución de Problemas'),
            ('business_model_review', 'Revisión de Modelo de Negocio'),
            ('market_analysis', 'Análisis de Mercado'),
            ('fundraising_prep', 'Preparación para Fundraising'),
            ('technical_guidance', 'Orientación Técnica'),
            ('leadership_coaching', 'Coaching de Liderazgo'),
            ('team_dynamics', 'Dinámicas de Equipo'),
            ('follow_up', 'Seguimiento'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    title = StringField(
        'Título de la Sesión',
        validators=[
            DataRequired(),
            Length(min=5, max=200)
        ]
    )
    
    description = TextAreaField(
        'Descripción y Objetivos',
        validators=[
            DataRequired(),
            Length(min=20, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Describe los objetivos de la sesión y temas a tratar...'
        }
    )
    
    # Programación
    scheduled_date = DateField(
        'Fecha',
        validators=[
            DataRequired(),
            FutureDate(min_days=1, max_days=90)
        ]
    )
    
    start_time = TimeField(
        'Hora de Inicio',
        validators=[
            DataRequired(),
            BusinessHours(start_hour=6, end_hour=22)
        ]
    )
    
    duration = IntegerField(
        'Duración (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=15, max=240)
        ],
        default=60
    )
    
    # Modalidad
    modality = SelectField(
        'Modalidad',
        choices=[
            ('video_call', 'Videollamada'),
            ('phone_call', 'Llamada Telefónica'),
            ('in_person', 'Presencial'),
            ('mixed', 'Mixta')
        ],
        validators=[DataRequired()],
        default='video_call'
    )
    
    meeting_link = StringField(
        'Link de Reunión',
        validators=[
            WTFOptional(),
            URL()
        ],
        render_kw={'placeholder': 'https://meet.google.com/...'}
    )
    
    location = StringField(
        'Ubicación',
        validators=[Length(max=200)],
        render_kw={'placeholder': 'Dirección para sesiones presenciales'}
    )
    
    # Preparación
    entrepreneur_preparation = TextAreaField(
        'Preparación Requerida del Emprendedor',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Qué debe preparar el emprendedor para la sesión...'
        }
    )
    
    materials_needed = StringField(
        'Materiales Necesarios',
        validators=[Length(max=500)],
        render_kw={'placeholder': 'Pitch deck, business plan, documentos específicos...'}
    )
    
    # Estado y seguimiento
    status = SelectField(
        'Estado',
        choices=[
            ('scheduled', 'Programada'),
            ('confirmed', 'Confirmada'),
            ('in_progress', 'En Progreso'),
            ('completed', 'Completada'),
            ('cancelled', 'Cancelada'),
            ('no_show', 'No Se Presentó'),
            ('rescheduled', 'Reprogramada')
        ],
        default='scheduled'
    )
    
    priority = SelectField(
        'Prioridad',
        choices=[
            ('low', 'Baja'),
            ('normal', 'Normal'),
            ('high', 'Alta'),
            ('urgent', 'Urgente')
        ],
        default='normal'
    )
    
    # Recordatorios
    send_reminder = BooleanField('Enviar Recordatorio', default=True)
    
    reminder_time = SelectField(
        'Tiempo de Recordatorio',
        choices=[
            ('1_hour', '1 Hora Antes'),
            ('2_hours', '2 Horas Antes'),
            ('4_hours', '4 Horas Antes'),
            ('1_day', '1 Día Antes'),
            ('2_days', '2 Días Antes')
        ],
        default='1_day'
    )
    
    # Notas privadas del mentor
    mentor_notes = TextAreaField(
        'Notas Privadas del Mentor',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Notas privadas para tu referencia...'
        }
    )
    
    submit = SubmitField('Programar Sesión')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar emprendedores del mentor actual
        if hasattr(g, 'current_user'):
            ally = Ally.query.filter_by(user_id=g.current_user.id).first()
            if ally:
                # Obtener emprendedores asignados o todos si es mentor general
                entrepreneurs = Entrepreneur.query.join(User).filter(User.is_active == True).all()
                self.entrepreneur_id.choices = [(0, 'Seleccionar emprendedor...')] + [
                    (ent.id, f"{ent.user.full_name} - {ent.user.email}") for ent in entrepreneurs
                ]
    
    def validate_meeting_link(self, field):
        """Valida link de reunión según modalidad"""
        if self.modality.data == 'video_call' and not field.data:
            raise ValidationError('Link de reunión requerido para videollamadas')
    
    def validate_location(self, field):
        """Valida ubicación para sesiones presenciales"""
        if self.modality.data == 'in_person' and not field.data:
            raise ValidationError('Ubicación requerida para sesiones presenciales')


class SessionFeedbackForm(BaseForm, AuditMixin):
    """Formulario para feedback de sesiones de mentoría"""
    
    session_id = HiddenField('Session ID', validators=[DataRequired()])
    
    # Evaluación general
    overall_rating = SelectField(
        'Calificación General',
        choices=[
            ('', 'Seleccionar...'),
            ('5', 'Excelente (5)'),
            ('4', 'Muy Bueno (4)'),
            ('3', 'Bueno (3)'),
            ('2', 'Regular (2)'),
            ('1', 'Malo (1)')
        ],
        validators=[
            DataRequired(),
            SessionRatingValidator()
        ],
        coerce=int
    )
    
    # Evaluación por criterios
    preparation_rating = SelectField(
        'Preparación del Emprendedor',
        choices=[
            ('', 'N/A'),
            ('5', 'Excelente'),
            ('4', 'Muy Buena'),
            ('3', 'Buena'),
            ('2', 'Regular'),
            ('1', 'Mala')
        ],
        coerce=int
    )
    
    engagement_rating = SelectField(
        'Nivel de Participación',
        choices=[
            ('', 'N/A'),
            ('5', 'Muy Alto'),
            ('4', 'Alto'),
            ('3', 'Medio'),
            ('2', 'Bajo'),
            ('1', 'Muy Bajo')
        ],
        coerce=int
    )
    
    progress_rating = SelectField(
        'Progreso Observado',
        choices=[
            ('', 'N/A'),
            ('5', 'Excelente'),
            ('4', 'Muy Bueno'),
            ('3', 'Bueno'),
            ('2', 'Limitado'),
            ('1', 'Nulo')
        ],
        coerce=int
    )
    
    # Feedback cualitativo
    session_summary = TextAreaField(
        'Resumen de la Sesión',
        validators=[
            DataRequired(),
            Length(min=50, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Resumen de los temas tratados y resultados de la sesión...'
        }
    )
    
    key_insights = TextAreaField(
        'Insights Principales',
        validators=[
            DataRequired(),
            Length(min=30, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Principales insights y aprendizajes de la sesión...'
        }
    )
    
    challenges_identified = TextAreaField(
        'Desafíos Identificados',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 4,
            'placeholder': 'Principales desafíos o problemas identificados...'
        }
    )
    
    # Recomendaciones y próximos pasos
    action_items = TextAreaField(
        'Acciones Recomendadas',
        validators=[
            DataRequired(),
            Length(min=30, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Lista de acciones específicas recomendadas para el emprendedor...'
        }
    )
    
    next_session_topics = TextAreaField(
        'Temas para Próxima Sesión',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Temas sugeridos para abordar en la próxima sesión...'
        }
    )
    
    recommended_resources = TextAreaField(
        'Recursos Recomendados',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Libros, artículos, cursos, contactos u otros recursos recomendados...'
        }
    )
    
    # Evaluación del emprendedor
    entrepreneur_strengths = TextAreaField(
        'Fortalezas del Emprendedor',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Principales fortalezas observadas...'
        }
    )
    
    areas_for_improvement = TextAreaField(
        'Áreas de Mejora',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Áreas donde el emprendedor puede mejorar...'
        }
    )
    
    # Configuraciones
    share_with_entrepreneur = BooleanField(
        'Compartir con Emprendedor',
        default=True,
        render_kw={'title': 'Permitir que el emprendedor vea este feedback'}
    )
    
    confidential_notes = TextAreaField(
        'Notas Confidenciales',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 4,
            'placeholder': 'Notas privadas que no se compartirán con el emprendedor...'
        }
    )
    
    submit = SubmitField('Enviar Feedback')


class HourLogForm(BaseForm, AuditMixin):
    """Formulario para registro de horas de mentoría"""
    
    # Información básica
    date = DateField(
        'Fecha',
        validators=[DataRequired()],
        default=date.today
    )
    
    entrepreneur_id = SelectField(
        'Emprendedor',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    activity_type = SelectField(
        'Tipo de Actividad',
        choices=[
            ('mentoring_session', 'Sesión de Mentoría'),
            ('preparation', 'Preparación'),
            ('follow_up', 'Seguimiento'),
            ('research', 'Investigación'),
            ('networking', 'Networking'),
            ('email_communication', 'Comunicación por Email'),
            ('document_review', 'Revisión de Documentos'),
            ('event_attendance', 'Asistencia a Eventos'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    # Tiempo
    start_time = TimeField(
        'Hora de Inicio',
        validators=[DataRequired()]
    )
    
    end_time = TimeField(
        'Hora de Fin',
        validators=[DataRequired()]
    )
    
    total_hours = FloatField(
        'Total Horas',
        validators=[
            DataRequired(),
            NumberRange(min=0.25, max=12)
        ],
        render_kw={'step': '0.25', 'readonly': True}
    )
    
    # Descripción
    description = TextAreaField(
        'Descripción de la Actividad',
        validators=[
            DataRequired(),
            Length(min=20, max=1000)
        ],
        render_kw={
            'rows': 4,
            'placeholder': 'Describe las actividades realizadas...'
        }
    )
    
    outcomes = TextAreaField(
        'Resultados',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 3,
            'placeholder': 'Resultados o logros de la actividad...'
        }
    )
    
    # Información financiera (para mentores remunerados)
    is_billable = BooleanField('Tiempo Facturable')
    
    hourly_rate = DecimalField(
        'Tarifa por Hora',
        validators=[WTFOptional()],
        places=2
    )
    
    total_amount = DecimalField(
        'Monto Total',
        validators=[WTFOptional()],
        places=2,
        render_kw={'readonly': True}
    )
    
    # Referencias
    session_id = SelectField(
        'Sesión Relacionada',
        choices=[],  # Se llena dinámicamente
        validators=[WTFOptional()],
        coerce=int
    )
    
    # Archivos de soporte
    supporting_documents = FileField(
        'Documentos de Soporte',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx', 'jpg', 'png'},
                max_size=10*1024*1024  # 10MB
            )
        ]
    )
    
    submit = SubmitField('Registrar Horas')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar emprendedores y sesiones del mentor actual
        if hasattr(g, 'current_user'):
            ally = Ally.query.filter_by(user_id=g.current_user.id).first()
            if ally:
                entrepreneurs = Entrepreneur.query.join(User).filter(User.is_active == True).all()
                self.entrepreneur_id.choices = [(0, 'Seleccionar emprendedor...')] + [
                    (ent.id, f"{ent.user.full_name}") for ent in entrepreneurs
                ]
                
                # Cargar sesiones recientes
                recent_sessions = MentorshipSession.query.filter_by(
                    mentor_id=ally.id
                ).order_by(MentorshipSession.scheduled_date.desc()).limit(20).all()
                
                self.session_id.choices = [(0, 'Sin sesión relacionada')] + [
                    (session.id, f"{session.title} - {session.scheduled_date}") 
                    for session in recent_sessions
                ]
    
    def validate_end_time(self, field):
        """Valida que hora de fin sea posterior a inicio"""
        if field.data and self.start_time.data:
            if field.data <= self.start_time.data:
                raise ValidationError('Hora de fin debe ser posterior a hora de inicio')
            
            # Calcular horas automáticamente
            start_minutes = self.start_time.data.hour * 60 + self.start_time.data.minute
            end_minutes = field.data.hour * 60 + field.data.minute
            hours = (end_minutes - start_minutes) / 60
            self.total_hours.data = round(hours, 2)
    
    def validate_total_amount(self, field):
        """Calcula monto total automáticamente"""
        if self.is_billable.data and self.hourly_rate.data and self.total_hours.data:
            self.total_amount.data = round(self.hourly_rate.data * self.total_hours.data, 2)


class AllyApplicationForm(BaseForm, AuditMixin):
    """Formulario para aplicar a ser mentor/aliado"""
    
    # Motivación
    motivation = TextAreaField(
        'Motivación para ser Mentor',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Explica por qué quieres ser mentor en nuestro ecosistema...'
        }
    )
    
    value_proposition = TextAreaField(
        'Propuesta de Valor',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Qué valor único puedes aportar a los emprendedores...'
        }
    )
    
    # Experiencia relevante
    relevant_experience = TextAreaField(
        'Experiencia Relevante',
        validators=[
            DataRequired(),
            Length(min=200, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe tu experiencia más relevante para mentoría...'
        }
    )
    
    success_stories = TextAreaField(
        'Casos de Éxito',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 6,
            'placeholder': 'Comparte casos de éxito en mentoría o desarrollo de equipos...'
        }
    )
    
    # Compromisos
    time_commitment = SelectField(
        'Compromiso de Tiempo',
        choices=[
            ('2-4_hours', '2-4 horas por semana'),
            ('4-8_hours', '4-8 horas por semana'),
            ('8-15_hours', '8-15 horas por semana'),
            ('15+_hours', 'Más de 15 horas por semana')
        ],
        validators=[DataRequired()]
    )
    
    long_term_commitment = BooleanField(
        'Compromiso a Largo Plazo (mínimo 1 año)',
        validators=[DataRequired(message='Debe comprometerse a largo plazo')]
    )
    
    # Referencias
    references = TextAreaField(
        'Referencias',
        validators=[
            DataRequired(),
            Length(min=100, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Proporciona al menos 2 referencias profesionales...'
        }
    )
    
    # Archivos requeridos
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
    
    # Términos y condiciones
    accept_terms = BooleanField(
        'Acepto los términos y condiciones del programa de mentores',
        validators=[DataRequired(message='Debe aceptar los términos y condiciones')]
    )
    
    accept_code_of_conduct = BooleanField(
        'Acepto el código de conducta para mentores',
        validators=[DataRequired(message='Debe aceptar el código de conducta')]
    )
    
    submit = SubmitField('Enviar Aplicación')


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Validadores
    'ExpertiseValidator',
    'MentorshipCapacity',
    'HourlyRateValidator',
    'AvailabilityValidator',
    'SessionRatingValidator',
    'ExperienceYearsValidator',
    
    # Sub-formularios
    'AvailabilitySlotForm',
    'ExpertiseAreaForm',
    'EvaluationCriteriaForm',
    
    # Formularios principales
    'AllyProfileForm',
    'AvailabilityForm',
    'MentorshipSessionForm',
    'SessionFeedbackForm',
    'HourLogForm',
    'AllyApplicationForm',
    'ExpertiseForm'
]


# ====================================
# FORMULARIOS ADICIONALES PARA COMPATIBILIDAD
# ====================================

class ExpertiseForm(BaseForm):
    """Formulario para gestión de expertise de aliado"""
    
    expertise_areas = SelectMultipleField(
        'Áreas de Expertise',
        choices=[
            ('technology', 'Tecnología'),
            ('marketing', 'Marketing'),
            ('finance', 'Finanzas'),
            ('operations', 'Operaciones'),
            ('strategy', 'Estrategia'),
            ('legal', 'Legal'),
            ('hr', 'Recursos Humanos'),
            ('sales', 'Ventas')
        ],
        validators=[DataRequired()]
    )
    
    expertise_description = TextAreaField(
        'Descripción de Expertise',
        validators=[WTFOptional(), Length(max=500)],
        render_kw={'rows': 4}
    )
    
    years_experience = IntegerField(
        'Años de Experiencia',
        validators=[WTFOptional(), NumberRange(min=0, max=50)],
        default=0
    )