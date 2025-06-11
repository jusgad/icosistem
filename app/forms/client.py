"""
Client/Stakeholder Forms Module

Formularios específicos para clientes y stakeholders en el ecosistema.
Incluye perfiles, evaluaciones, inversiones, partnerships y reportes.

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
    InternationalPhone, UniqueEmail, SecureFileUpload, ImageValidator,
    ColombianNIT, BusinessEmail, BaseValidator, FutureDate, DateRange
)
from app.models.user import User
from app.models.client import Client
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.investment import Investment
from app.models.assessment import Assessment
from app.models.partnership import Partnership
from app.core.exceptions import ValidationError as AppValidationError
from app.utils.cache_utils import CacheManager


logger = logging.getLogger(__name__)


# =============================================================================
# VALIDADORES ESPECÍFICOS PARA CLIENTES/STAKEHOLDERS
# =============================================================================

class InvestmentRangeValidator(BaseValidator):
    """Validador para rangos de inversión"""
    
    def __init__(self, currency_field: str = 'currency', client_type_field: str = 'client_type', 
                 message: str = None):
        super().__init__(message)
        self.currency_field = currency_field
        self.client_type_field = client_type_field
        
        # Rangos de inversión por tipo de cliente y moneda
        self.investment_ranges = {
            'angel_investor': {
                'USD': {'min': 1000, 'max': 100000},
                'COP': {'min': 4000000, 'max': 400000000}
            },
            'venture_capital': {
                'USD': {'min': 100000, 'max': 50000000},
                'COP': {'min': 400000000, 'max': 200000000000}
            },
            'corporate': {
                'USD': {'min': 10000, 'max': 10000000},
                'COP': {'min': 40000000, 'max': 40000000000}
            },
            'government': {
                'USD': {'min': 5000, 'max': 5000000},
                'COP': {'min': 20000000, 'max': 20000000000}
            }
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        amount = field.data
        currency_field = getattr(form, self.currency_field, None)
        client_type_field = getattr(form, self.client_type_field, None)
        
        if not currency_field or not client_type_field:
            return
        
        currency = currency_field.data
        client_type = client_type_field.data
        
        if client_type in self.investment_ranges and currency in self.investment_ranges[client_type]:
            range_data = self.investment_ranges[client_type][currency]
            min_amount = range_data['min']
            max_amount = range_data['max']
            
            if amount < min_amount:
                raise ValidationError(f'Monto mínimo para {client_type}: {min_amount:,} {currency}')
            
            if amount > max_amount:
                raise ValidationError(f'Monto máximo para {client_type}: {max_amount:,} {currency}')


class AssessmentScoreValidator(BaseValidator):
    """Validador para puntuaciones de evaluación"""
    
    def __init__(self, min_score: int = 1, max_score: int = 10, message: str = None):
        super().__init__(message)
        self.min_score = min_score
        self.max_score = max_score
    
    def validate(self, form, field):
        if field.data is None:
            return
        
        score = field.data
        
        if not self.min_score <= score <= self.max_score:
            raise ValidationError(
                f'Puntuación debe estar entre {self.min_score} y {self.max_score}'
            )


class DueDiligenceValidator(BaseValidator):
    """Validador para procesos de due diligence"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        # Verificar que todos los documentos requeridos estén presentes
        required_sections = [
            'financial_review', 'legal_review', 'technical_review',
            'market_analysis', 'team_assessment'
        ]
        
        missing_sections = []
        for section in required_sections:
            section_field = getattr(form, section, None)
            if not section_field or not section_field.data:
                missing_sections.append(section.replace('_', ' ').title())
        
        if missing_sections:
            raise ValidationError(
                f'Secciones faltantes para completar due diligence: {", ".join(missing_sections)}'
            )


class ROIExpectationValidator(BaseValidator):
    """Validador para expectativas de ROI"""
    
    def validate(self, form, field):
        if not field.data:
            return
        
        roi_percentage = field.data
        
        # Validar rangos razonables de ROI
        if roi_percentage < 0:
            raise ValidationError('ROI no puede ser negativo')
        
        if roi_percentage > 10000:  # 100x return
            raise ValidationError('ROI expectativa muy alta (máximo 10,000%)')
        
        # Validar coherencia con tipo de inversión
        investment_type_field = getattr(form, 'investment_type', None)
        if investment_type_field and investment_type_field.data:
            investment_type = investment_type_field.data
            
            # Rangos típicos por tipo de inversión
            typical_ranges = {
                'seed': {'min': 500, 'max': 3000},      # 5x-30x
                'series_a': {'min': 300, 'max': 1000},  # 3x-10x
                'series_b': {'min': 200, 'max': 500},   # 2x-5x
                'growth': {'min': 100, 'max': 300}      # 1x-3x
            }
            
            if investment_type in typical_ranges:
                range_data = typical_ranges[investment_type]
                if roi_percentage < range_data['min']:
                    logger.warning(f'ROI bajo para {investment_type}: {roi_percentage}%')
                elif roi_percentage > range_data['max']:
                    logger.warning(f'ROI alto para {investment_type}: {roi_percentage}%')


class PartnershipBudgetValidator(BaseValidator):
    """Validador para presupuestos de partnership"""
    
    def __init__(self, partnership_type_field: str = 'partnership_type', message: str = None):
        super().__init__(message)
        self.partnership_type_field = partnership_type_field
        
        # Rangos de presupuesto por tipo de partnership (USD)
        self.budget_ranges = {
            'technology': {'min': 10000, 'max': 1000000},
            'marketing': {'min': 5000, 'max': 500000},
            'distribution': {'min': 20000, 'max': 2000000},
            'research': {'min': 15000, 'max': 1500000},
            'strategic': {'min': 50000, 'max': 5000000}
        }
    
    def validate(self, form, field):
        if not field.data:
            return
        
        budget = field.data
        partnership_type_field = getattr(form, self.partnership_type_field, None)
        
        if not partnership_type_field or not partnership_type_field.data:
            return
        
        partnership_type = partnership_type_field.data
        
        if partnership_type in self.budget_ranges:
            range_data = self.budget_ranges[partnership_type]
            min_budget = range_data['min']
            max_budget = range_data['max']
            
            if budget < min_budget:
                raise ValidationError(f'Presupuesto mínimo para {partnership_type}: ${min_budget:,} USD')
            
            if budget > max_budget:
                raise ValidationError(f'Presupuesto máximo para {partnership_type}: ${max_budget:,} USD')


# =============================================================================
# SUB-FORMULARIOS REUTILIZABLES
# =============================================================================

class InvestmentCriteriaForm(BaseForm):
    """Sub-formulario para criterios de inversión"""
    
    industry = SelectField(
        'Industria',
        choices=[
            ('fintech', 'Fintech'),
            ('healthtech', 'Healthtech'),
            ('edtech', 'Edtech'),
            ('agtech', 'Agtech'),
            ('cleantech', 'Cleantech'),
            ('ecommerce', 'E-commerce'),
            ('saas', 'SaaS'),
            ('marketplace', 'Marketplace'),
            ('ai_ml', 'IA/ML'),
            ('blockchain', 'Blockchain'),
            ('any', 'Cualquier Industria')
        ],
        validators=[DataRequired()]
    )
    
    stage = SelectMultipleField(
        'Etapas de Interés',
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
    
    min_investment = DecimalField(
        'Inversión Mínima',
        validators=[NumberRange(min=0)],
        places=0
    )
    
    max_investment = DecimalField(
        'Inversión Máxima',
        validators=[NumberRange(min=0)],
        places=0
    )
    
    geographic_focus = SelectMultipleField(
        'Enfoque Geográfico',
        choices=[
            ('local', 'Local'),
            ('national', 'Nacional'),
            ('latam', 'Latinoamérica'),
            ('global', 'Global')
        ],
        render_kw={'size': '4'}
    )
    
    required_metrics = TextAreaField(
        'Métricas Requeridas',
        validators=[Length(max=1000)],
        render_kw={
            'rows': 3,
            'placeholder': 'ARR, usuarios activos, crecimiento mensual, etc.'
        }
    )


class AssessmentCriteriaForm(BaseForm):
    """Sub-formulario para criterios de evaluación"""
    
    criteria_name = StringField(
        'Criterio',
        validators=[
            DataRequired(),
            Length(min=3, max=100)
        ]
    )
    
    weight = IntegerField(
        'Peso (%)',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100)
        ],
        render_kw={'min': 1, 'max': 100}
    )
    
    description = TextAreaField(
        'Descripción',
        validators=[Length(max=500)],
        render_kw={'rows': 3}
    )
    
    scoring_method = SelectField(
        'Método de Puntuación',
        choices=[
            ('1-5', 'Escala 1-5'),
            ('1-10', 'Escala 1-10'),
            ('percentage', 'Porcentaje'),
            ('binary', 'Sí/No')
        ],
        default='1-10'
    )


class ImpactMetricForm(BaseForm):
    """Sub-formulario para métricas de impacto"""
    
    metric_name = StringField(
        'Métrica',
        validators=[
            DataRequired(),
            Length(min=3, max=100)
        ]
    )
    
    target_value = DecimalField(
        'Valor Objetivo',
        validators=[DataRequired()],
        places=2
    )
    
    current_value = DecimalField(
        'Valor Actual',
        validators=[WTFOptional()],
        places=2,
        default=0
    )
    
    unit = StringField(
        'Unidad',
        validators=[
            DataRequired(),
            Length(max=50)
        ],
        render_kw={'placeholder': 'empleos, usuarios, revenue, etc.'}
    )
    
    measurement_frequency = SelectField(
        'Frecuencia de Medición',
        choices=[
            ('weekly', 'Semanal'),
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral'),
            ('annually', 'Anual')
        ],
        default='monthly'
    )


# =============================================================================
# FORMULARIOS PRINCIPALES
# =============================================================================

class ClientProfileForm(ModelForm, CacheableMixin):
    """Formulario de perfil para clientes/stakeholders"""
    
    # Tipo de cliente
    client_type = SelectField(
        'Tipo de Cliente',
        choices=[
            ('angel_investor', 'Inversionista Ángel'),
            ('venture_capital', 'Capital de Riesgo'),
            ('private_equity', 'Private Equity'),
            ('corporate', 'Corporativo'),
            ('government', 'Gubernamental'),
            ('university', 'Universidad'),
            ('accelerator', 'Aceleradora'),
            ('incubator', 'Incubadora'),
            ('media', 'Medios'),
            ('service_provider', 'Proveedor de Servicios'),
            ('strategic_partner', 'Socio Estratégico'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    # Información de la organización
    organization_name = StringField(
        'Nombre de la Organización',
        validators=[
            DataRequired(),
            Length(min=2, max=200)
        ]
    )
    
    organization_type = SelectField(
        'Tipo de Organización',
        choices=[
            ('corporation', 'Corporación'),
            ('fund', 'Fondo'),
            ('foundation', 'Fundación'),
            ('government_agency', 'Agencia Gubernamental'),
            ('university', 'Universidad'),
            ('ngo', 'ONG'),
            ('family_office', 'Family Office'),
            ('individual', 'Individual'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()]
    )
    
    industry_sector = SelectMultipleField(
        'Sectores de Industria',
        choices=[
            ('technology', 'Tecnología'),
            ('finance', 'Finanzas'),
            ('healthcare', 'Salud'),
            ('education', 'Educación'),
            ('agriculture', 'Agricultura'),
            ('energy', 'Energía'),
            ('retail', 'Retail'),
            ('manufacturing', 'Manufactura'),
            ('real_estate', 'Bienes Raíces'),
            ('consulting', 'Consultoría'),
            ('media', 'Medios'),
            ('government', 'Gobierno'),
            ('non_profit', 'Sin Fines de Lucro'),
            ('other', 'Otro')
        ],
        render_kw={'size': '8'}
    )
    
    # Información legal y fiscal
    legal_name = StringField(
        'Razón Social',
        validators=[
            DataRequired(),
            Length(min=2, max=250)
        ]
    )
    
    tax_id = StringField(
        'NIT/ID Tributario',
        validators=[
            DataRequired(),
            ColombianNIT(allow_natural_person=False)
        ]
    )
    
    registration_country = SelectField(
        'País de Registro',
        choices=[
            ('CO', 'Colombia'),
            ('US', 'Estados Unidos'),
            ('CA', 'Canadá'),
            ('MX', 'México'),
            ('BR', 'Brasil'),
            ('AR', 'Argentina'),
            ('PE', 'Perú'),
            ('CL', 'Chile'),
            ('EC', 'Ecuador'),
            ('UY', 'Uruguay'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()],
        default='CO'
    )
    
    # Descripción y propósito
    description = TextAreaField(
        'Descripción de la Organización',
        validators=[
            DataRequired(),
            Length(min=100, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe tu organización, misión, objetivos en el ecosistema...'
        }
    )
    
    investment_thesis = TextAreaField(
        'Tesis de Inversión/Participación',
        validators=[
            DataRequired(),
            Length(min=50, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Describe tu enfoque de inversión o participación en el ecosistema...'
        }
    )
    
    # Capacidad financiera
    total_assets = DecimalField(
        'Activos Totales',
        validators=[
            WTFOptional(),
            NumberRange(min=0, max=1000000000000)  # 1 Trillón
        ],
        places=0,
        render_kw={'placeholder': 'Opcional - solo para contexto'}
    )
    
    annual_investment_budget = DecimalField(
        'Presupuesto Anual de Inversión',
        validators=[
            DataRequired(),
            NumberRange(min=1000, max=100000000000)  # 100 Mil Millones
        ],
        places=0
    )
    
    currency = SelectField(
        'Moneda',
        choices=[
            ('COP', 'Pesos Colombianos (COP)'),
            ('USD', 'Dólares Americanos (USD)'),
            ('EUR', 'Euros (EUR)')
        ],
        validators=[DataRequired()],
        default='USD'
    )
    
    # Criterios de inversión/participación
    investment_criteria = FieldList(
        FormField(InvestmentCriteriaForm),
        min_entries=1,
        max_entries=5,
        label='Criterios de Inversión'
    )
    
    # Información de contacto
    primary_contact_name = StringField(
        'Nombre del Contacto Principal',
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )
    
    primary_contact_title = StringField(
        'Cargo del Contacto Principal',
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )
    
    primary_contact_email = EmailField(
        'Email del Contacto Principal',
        validators=[
            DataRequired(),
            BusinessEmail(allow_free_domains=False)
        ]
    )
    
    primary_contact_phone = TelField(
        'Teléfono del Contacto Principal',
        validators=[
            DataRequired(),
            InternationalPhone(regions=['CO', 'US', 'MX', 'BR', 'AR', 'PE', 'CL'])
        ]
    )
    
    # Dirección
    address = StringField(
        'Dirección',
        validators=[
            DataRequired(),
            Length(min=10, max=300)
        ]
    )
    
    city = StringField(
        'Ciudad',
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
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
            ('other', 'Otro')
        ],
        validators=[DataRequired()],
        default='CO'
    )
    
    # Presencia online
    website_url = StringField(
        'Sitio Web',
        validators=[
            DataRequired(),
            URL()
        ]
    )
    
    linkedin_url = StringField(
        'LinkedIn Corporativo',
        validators=[
            WTFOptional(),
            URL(),
            Regexp(r'linkedin\.com/', message='URL de LinkedIn inválida')
        ]
    )
    
    # Archivos
    logo = FileField(
        'Logo Corporativo',
        validators=[
            ImageValidator(
                max_width=800,
                max_height=800,
                max_size=3*1024*1024  # 3MB
            )
        ]
    )
    
    company_profile = FileField(
        'Perfil Corporativo',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx', 'ppt', 'pptx'},
                max_size=20*1024*1024  # 20MB
            )
        ]
    )
    
    # Preferencias de participación
    participation_interests = SelectMultipleField(
        'Intereses de Participación',
        choices=[
            ('direct_investment', 'Inversión Directa'),
            ('mentorship', 'Mentoría'),
            ('strategic_partnership', 'Partnership Estratégico'),
            ('technology_transfer', 'Transferencia de Tecnología'),
            ('market_access', 'Acceso a Mercados'),
            ('talent_acquisition', 'Adquisición de Talento'),
            ('innovation_scouting', 'Scouting de Innovación'),
            ('pilot_programs', 'Programas Piloto'),
            ('corporate_venture', 'Corporate Venture'),
            ('acquisition', 'Adquisición'),
            ('board_participation', 'Participación en Junta'),
            ('other', 'Otro')
        ],
        validators=[DataRequired()],
        render_kw={'size': '8'}
    )
    
    geographic_focus = SelectMultipleField(
        'Enfoque Geográfico',
        choices=[
            ('local_city', 'Ciudad Local'),
            ('national', 'Nacional'),
            ('latam', 'Latinoamérica'),
            ('north_america', 'Norteamérica'),
            ('europe', 'Europa'),
            ('asia', 'Asia'),
            ('global', 'Global')
        ],
        render_kw={'size': '7'}
    )
    
    # Configuraciones
    profile_public = BooleanField('Perfil Público', default=True)
    accept_proposals = BooleanField('Aceptar Propuestas', default=True)
    verified_investor = BooleanField('Inversionista Verificado')
    
    # Notificaciones
    email_notifications = BooleanField('Notificaciones por Email', default=True)
    weekly_digest = BooleanField('Resumen Semanal', default=True)
    investment_opportunities = BooleanField('Oportunidades de Inversión', default=True)
    
    submit = SubmitField('Actualizar Perfil')
    
    def validate_annual_investment_budget(self, field):
        """Valida presupuesto según tipo de cliente"""
        if field.data and self.client_type.data:
            validator = InvestmentRangeValidator(
                currency_field='currency',
                client_type_field='client_type'
            )
            validator.validate(self, field)
    
    def _get_model_class(self):
        return Client


class ProjectAssessmentForm(BaseForm, AuditMixin):
    """Formulario para evaluación de proyectos"""
    
    project_id = SelectField(
        'Proyecto a Evaluar',
        choices=[],  # Se llena dinámicamente
        validators=[DataRequired()],
        coerce=int
    )
    
    assessment_type = SelectField(
        'Tipo de Evaluación',
        choices=[
            ('initial_screening', 'Screening Inicial'),
            ('due_diligence', 'Due Diligence'),
            ('investment_committee', 'Comité de Inversión'),
            ('post_investment', 'Post-Inversión'),
            ('exit_review', 'Revisión de Salida'),
            ('partnership_evaluation', 'Evaluación de Partnership'),
            ('pilot_assessment', 'Evaluación de Piloto')
        ],
        validators=[DataRequired()]
    )
    
    # Evaluación general
    overall_score = IntegerField(
        'Puntuación General',
        validators=[
            DataRequired(),
            AssessmentScoreValidator(min_score=1, max_score=10)
        ],
        render_kw={'min': 1, 'max': 10}
    )
    
    recommendation = SelectField(
        'Recomendación',
        choices=[
            ('', 'Seleccionar...'),
            ('strong_recommend', 'Recomendar Fuertemente'),
            ('recommend', 'Recomendar'),
            ('consider', 'Considerar'),
            ('pass', 'Rechazar'),
            ('revisit_later', 'Revisar Más Tarde')
        ],
        validators=[DataRequired()]
    )
    
    # Evaluaciones específicas por categoría
    team_score = IntegerField(
        'Equipo',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    product_score = IntegerField(
        'Producto/Solución',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    market_score = IntegerField(
        'Mercado',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    business_model_score = IntegerField(
        'Modelo de Negocio',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    financials_score = IntegerField(
        'Finanzas',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    traction_score = IntegerField(
        'Tracción',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    scalability_score = IntegerField(
        'Escalabilidad',
        validators=[AssessmentScoreValidator()],
        render_kw={'min': 1, 'max': 10}
    )
    
    # Evaluación cualitativa
    strengths = TextAreaField(
        'Fortalezas Identificadas',
        validators=[
            DataRequired(),
            Length(min=50, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Principales fortalezas del proyecto...'
        }
    )
    
    weaknesses = TextAreaField(
        'Debilidades Identificadas',
        validators=[
            DataRequired(),
            Length(min=50, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Áreas de mejora y debilidades...'
        }
    )
    
    opportunities = TextAreaField(
        'Oportunidades',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Oportunidades identificadas...'
        }
    )
    
    threats = TextAreaField(
        'Amenazas/Riesgos',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Riesgos y amenazas identificados...'
        }
    )
    
    # Comentarios detallados
    executive_summary = TextAreaField(
        'Resumen Ejecutivo',
        validators=[
            DataRequired(),
            Length(min=100, max=1500)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Resumen ejecutivo de la evaluación...'
        }
    )
    
    detailed_comments = TextAreaField(
        'Comentarios Detallados',
        validators=[Length(max=5000)],
        render_kw={
            'rows': 10,
            'placeholder': 'Análisis detallado y observaciones...'
        }
    )
    
    next_steps = TextAreaField(
        'Próximos Pasos Recomendados',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Acciones recomendadas para el emprendedor...'
        }
    )
    
    # Información de inversión/partnership
    investment_interest = BooleanField('Interés de Inversión')
    
    proposed_investment_amount = DecimalField(
        'Monto de Inversión Propuesto',
        validators=[WTFOptional()],
        places=0
    )
    
    proposed_valuation = DecimalField(
        'Valuación Propuesta',
        validators=[WTFOptional()],
        places=0
    )
    
    investment_terms = TextAreaField(
        'Términos de Inversión',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Términos específicos de la inversión propuesta...'
        }
    )
    
    # Configuraciones
    share_with_entrepreneur = BooleanField(
        'Compartir con Emprendedor',
        default=True
    )
    
    confidential_notes = TextAreaField(
        'Notas Confidenciales',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Notas internas que no se compartirán...'
        }
    )
    
    submit = SubmitField('Enviar Evaluación')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar proyectos activos
        projects = Project.query.filter(
            Project.status.in_(['active', 'seeking_funding'])
        ).all()
        
        self.project_id.choices = [(0, 'Seleccionar proyecto...')] + [
            (project.id, f"{project.name} - {project.entrepreneur.user.full_name}") 
            for project in projects
        ]
    
    def validate_proposed_investment_amount(self, field):
        """Valida monto de inversión si hay interés"""
        if self.investment_interest.data and not field.data:
            raise ValidationError('Debe especificar monto si hay interés de inversión')


class FeedbackForm(BaseForm, AuditMixin):
    """Formulario para feedback general del ecosistema"""
    
    feedback_type = SelectField(
        'Tipo de Feedback',
        choices=[
            ('platform', 'Plataforma'),
            ('entrepreneur', 'Emprendedor Específico'),
            ('program', 'Programa'),
            ('event', 'Evento'),
            ('service', 'Servicio'),
            ('general', 'General'),
            ('suggestion', 'Sugerencia'),
            ('complaint', 'Queja')
        ],
        validators=[DataRequired()]
    )
    
    subject = StringField(
        'Asunto',
        validators=[
            DataRequired(),
            Length(min=5, max=200)
        ]
    )
    
    # Referencias opcionales
    entrepreneur_id = SelectField(
        'Emprendedor Relacionado',
        choices=[],  # Se llena dinámicamente
        validators=[WTFOptional()],
        coerce=int
    )
    
    project_id = SelectField(
        'Proyecto Relacionado',
        choices=[],  # Se llena dinámicamente
        validators=[WTFOptional()],
        coerce=int
    )
    
    # Contenido del feedback
    description = TextAreaField(
        'Descripción Detallada',
        validators=[
            DataRequired(),
            Length(min=50, max=3000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Describe detalladamente tu feedback...'
        }
    )
    
    # Evaluación si aplica
    rating = SelectField(
        'Calificación',
        choices=[
            ('', 'No aplica'),
            ('5', 'Excelente (5)'),
            ('4', 'Muy Bueno (4)'),
            ('3', 'Bueno (3)'),
            ('2', 'Regular (2)'),
            ('1', 'Malo (1)')
        ],
        coerce=lambda x: int(x) if x else None
    )
    
    # Sugerencias
    suggestions = TextAreaField(
        'Sugerencias de Mejora',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Sugerencias específicas para mejorar...'
        }
    )
    
    # Prioridad
    priority = SelectField(
        'Prioridad',
        choices=[
            ('low', 'Baja'),
            ('medium', 'Media'),
            ('high', 'Alta'),
            ('urgent', 'Urgente')
        ],
        default='medium'
    )
    
    # Configuraciones
    anonymous = BooleanField('Enviar Anónimamente')
    
    follow_up_requested = BooleanField('Solicitar Seguimiento')
    
    submit = SubmitField('Enviar Feedback')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar emprendedores y proyectos
        entrepreneurs = Entrepreneur.query.join(User).filter(User.is_active == True).all()
        self.entrepreneur_id.choices = [(0, 'Ninguno')] + [
            (ent.id, ent.user.full_name) for ent in entrepreneurs
        ]
        
        projects = Project.query.filter_by(status='active').all()
        self.project_id.choices = [(0, 'Ninguno')] + [
            (proj.id, proj.name) for proj in projects
        ]


class PartnershipProposalForm(BaseForm, AuditMixin):
    """Formulario para propuestas de partnership"""
    
    # Información básica
    partnership_type = SelectField(
        'Tipo de Partnership',
        choices=[
            ('technology', 'Tecnológico'),
            ('marketing', 'Marketing'),
            ('distribution', 'Distribución'),
            ('research', 'Investigación y Desarrollo'),
            ('strategic', 'Estratégico'),
            ('financial', 'Financiero'),
            ('operational', 'Operacional'),
            ('talent', 'Talento/RRHH')
        ],
        validators=[DataRequired()]
    )
    
    title = StringField(
        'Título de la Propuesta',
        validators=[
            DataRequired(),
            Length(min=10, max=200)
        ]
    )
    
    target_audience = SelectField(
        'Audiencia Objetivo',
        choices=[
            ('all_entrepreneurs', 'Todos los Emprendedores'),
            ('specific_industry', 'Industria Específica'),
            ('specific_stage', 'Etapa Específica'),
            ('specific_entrepreneurs', 'Emprendedores Específicos'),
            ('program_participants', 'Participantes de Programa')
        ],
        validators=[DataRequired()]
    )
    
    # Descripción de la propuesta
    description = TextAreaField(
        'Descripción de la Propuesta',
        validators=[
            DataRequired(),
            Length(min=200, max=5000)
        ],
        render_kw={
            'rows': 10,
            'placeholder': 'Describe detalladamente la propuesta de partnership...'
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
            'placeholder': 'Qué valor aportas y qué buscas recibir...'
        }
    )
    
    objectives = TextAreaField(
        'Objetivos del Partnership',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Objetivos específicos que buscas lograr...'
        }
    )
    
    # Recursos y compromisos
    resources_offered = TextAreaField(
        'Recursos Ofrecidos',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Recursos, servicios, acceso que ofreces...'
        }
    )
    
    resources_sought = TextAreaField(
        'Recursos Buscados',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Qué esperas recibir de los emprendedores...'
        }
    )
    
    # Aspectos financieros
    budget_allocation = DecimalField(
        'Presupuesto Asignado (USD)',
        validators=[
            DataRequired(),
            PartnershipBudgetValidator()
        ],
        places=0
    )
    
    payment_terms = TextAreaField(
        'Términos de Pago/Compensación',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Estructura de pagos, equity, revenue share, etc.'
        }
    )
    
    # Timeline y estructura
    duration_months = IntegerField(
        'Duración (meses)',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=60)
        ]
    )
    
    start_date = DateField(
        'Fecha de Inicio Propuesta',
        validators=[
            DataRequired(),
            FutureDate(min_days=7, max_days=180)
        ]
    )
    
    milestones = TextAreaField(
        'Hitos y Entregables',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Hitos principales y entregables esperados...'
        }
    )
    
    # Criterios de selección
    selection_criteria = TextAreaField(
        'Criterios de Selección',
        validators=[
            DataRequired(),
            Length(min=100, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Criterios para seleccionar emprendedores participantes...'
        }
    )
    
    max_participants = IntegerField(
        'Máximo Participantes',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=100)
        ]
    )
    
    # Métricas de éxito
    success_metrics = TextAreaField(
        'Métricas de Éxito',
        validators=[
            DataRequired(),
            Length(min=100, max=1500)
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Cómo medirás el éxito del partnership...'
        }
    )
    
    # Documentos de soporte
    proposal_document = FileField(
        'Documento de Propuesta Detallada',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx', 'ppt', 'pptx'},
                max_size=20*1024*1024  # 20MB
            )
        ]
    )
    
    terms_and_conditions = FileField(
        'Términos y Condiciones',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx'},
                max_size=10*1024*1024  # 10MB
            )
        ]
    )
    
    # Configuraciones
    public_proposal = BooleanField('Propuesta Pública', default=True)
    exclusive_partnership = BooleanField('Partnership Exclusivo')
    requires_approval = BooleanField('Requiere Aprobación Administrativa', default=True)
    
    submit = SubmitField('Enviar Propuesta')


class ImpactReportForm(BaseForm, AuditMixin):
    """Formulario para reportes de impacto"""
    
    # Información básica
    report_title = StringField(
        'Título del Reporte',
        validators=[
            DataRequired(),
            Length(min=10, max=200)
        ]
    )
    
    report_period_start = DateField(
        'Inicio del Período',
        validators=[DataRequired()]
    )
    
    report_period_end = DateField(
        'Fin del Período',
        validators=[
            DataRequired(),
            DateRange(start_field='report_period_start')
        ]
    )
    
    report_type = SelectField(
        'Tipo de Reporte',
        choices=[
            ('quarterly', 'Trimestral'),
            ('annual', 'Anual'),
            ('project_completion', 'Completación de Proyecto'),
            ('milestone', 'Hito Específico'),
            ('custom', 'Personalizado')
        ],
        validators=[DataRequired()]
    )
    
    # Métricas de impacto
    impact_metrics = FieldList(
        FormField(ImpactMetricForm),
        min_entries=1,
        max_entries=10,
        label='Métricas de Impacto'
    )
    
    # Resumen ejecutivo
    executive_summary = TextAreaField(
        'Resumen Ejecutivo',
        validators=[
            DataRequired(),
            Length(min=200, max=2000)
        ],
        render_kw={
            'rows': 8,
            'placeholder': 'Resumen de los principales logros e impactos del período...'
        }
    )
    
    # Análisis detallado
    key_achievements = TextAreaField(
        'Logros Principales',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Principales logros y hitos alcanzados...'
        }
    )
    
    challenges_faced = TextAreaField(
        'Desafíos Enfrentados',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Principales desafíos y cómo se abordaron...'
        }
    )
    
    lessons_learned = TextAreaField(
        'Lecciones Aprendidas',
        validators=[Length(max=2000)],
        render_kw={
            'rows': 5,
            'placeholder': 'Principales aprendizajes del período...'
        }
    )
    
    # Impacto por categorías
    social_impact = TextAreaField(
        'Impacto Social',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Impacto social generado...'
        }
    )
    
    economic_impact = TextAreaField(
        'Impacto Económico',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Impacto económico generado...'
        }
    )
    
    environmental_impact = TextAreaField(
        'Impacto Ambiental',
        validators=[Length(max=1500)],
        render_kw={
            'rows': 5,
            'placeholder': 'Impacto ambiental (si aplica)...'
        }
    )
    
    # Proyecciones futuras
    future_projections = TextAreaField(
        'Proyecciones Futuras',
        validators=[
            DataRequired(),
            Length(min=100, max=2000)
        ],
        render_kw={
            'rows': 6,
            'placeholder': 'Proyecciones e impacto esperado para el próximo período...'
        }
    )
    
    # Documentos de soporte
    supporting_documents = FileField(
        'Documentos de Soporte',
        validators=[
            SecureFileUpload(
                allowed_extensions={'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'},
                max_size=50*1024*1024  # 50MB
            )
        ]
    )
    
    # Configuraciones
    public_report = BooleanField('Reporte Público')
    share_with_stakeholders = BooleanField('Compartir con Stakeholders', default=True)
    
    submit = SubmitField('Generar Reporte')


# =============================================================================
# EXPORTACIONES
# =============================================================================

__all__ = [
    # Validadores
    'InvestmentRangeValidator',
    'AssessmentScoreValidator',
    'DueDiligenceValidator',
    'ROIExpectationValidator',
    'PartnershipBudgetValidator',
    
    # Sub-formularios
    'InvestmentCriteriaForm',
    'AssessmentCriteriaForm',
    'ImpactMetricForm',
    
    # Formularios principales
    'ClientProfileForm',
    'ProjectAssessmentForm',
    'FeedbackForm',
    'PartnershipProposalForm',
    'ImpactReportForm'
]