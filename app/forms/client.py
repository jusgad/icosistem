from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    SelectMultipleField,
    BooleanField,
    DateField,
    IntegerField,
    DecimalField,
    SubmitField,
    URLField,
    FieldList,
    FormField
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    Email,
    URL,
    NumberRange,
    ValidationError
)
from datetime import datetime

class ClientProfileForm(FlaskForm):
    """Formulario para el perfil del cliente corporativo."""
    
    # Información de la Empresa
    company_name = StringField('Nombre de la Empresa', validators=[
        DataRequired(message="El nombre de la empresa es requerido"),
        Length(max=100)
    ])
    
    company_logo = FileField('Logo de la Empresa', validators=[
        Optional(),
        FileAllowed(['jpg', 'png'], 'Solo imágenes JPG o PNG')
    ])
    
    industry = SelectField('Industria', validators=[DataRequired()], choices=[
        ('technology', 'Tecnología'),
        ('health', 'Salud'),
        ('education', 'Educación'),
        ('retail', 'Comercio'),
        ('manufacturing', 'Manufactura'),
        ('services', 'Servicios'),
        ('finance', 'Finanzas'),
        ('other', 'Otro')
    ])
    
    website = URLField('Sitio Web', validators=[
        DataRequired(),
        URL(message="Ingrese una URL válida")
    ])
    
    # Información de Contacto Principal
    contact_name = StringField('Nombre del Contacto', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    contact_email = StringField('Email del Contacto', validators=[
        DataRequired(),
        Email(message="Ingrese un email válido")
    ])
    
    contact_phone = StringField('Teléfono del Contacto', validators=[
        DataRequired(),
        Length(min=10, max=15)
    ])
    
    # Preferencias de Monitoreo
    monitoring_frequency = SelectField('Frecuencia de Reportes', validators=[DataRequired()],
        choices=[
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral')
        ]
    )
    
    preferred_metrics = SelectMultipleField('Métricas de Interés', choices=[
        ('revenue', 'Ingresos'),
        ('growth', 'Crecimiento'),
        ('impact', 'Impacto Social'),
        ('innovation', 'Innovación'),
        ('market_reach', 'Alcance de Mercado'),
        ('sustainability', 'Sostenibilidad')
    ])
    
    submit = SubmitField('Actualizar Perfil')

class ImpactMetricsForm(FlaskForm):
    """Formulario para configurar métricas de impacto."""
    
    metric_categories = SelectMultipleField('Categorías de Métricas', validators=[DataRequired()],
        choices=[
            ('economic', 'Impacto Económico'),
            ('social', 'Impacto Social'),
            ('environmental', 'Impacto Ambiental'),
            ('innovation', 'Innovación'),
            ('employment', 'Generación de Empleo')
        ]
    )
    
    custom_metrics = FieldList(
        StringField('Métrica Personalizada', validators=[Optional(), Length(max=100)]),
        min_entries=1,
        max_entries=5
    )
    
    target_goals = TextAreaField('Objetivos Meta', validators=[
        Optional(),
        Length(max=500)
    ])
    
    measurement_period = SelectField('Período de Medición', validators=[DataRequired()],
        choices=[
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral'),
            ('yearly', 'Anual')
        ]
    )
    
    submit = SubmitField('Guardar Configuración')

class ReportConfigurationForm(FlaskForm):
    """Formulario para configurar reportes personalizados."""
    
    report_name = StringField('Nombre del Reporte', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    frequency = SelectField('Frecuencia', validators=[DataRequired()],
        choices=[
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral')
        ]
    )
    
    included_metrics = SelectMultipleField('Métricas a Incluir', validators=[DataRequired()])
    
    entrepreneur_categories = SelectMultipleField('Categorías de Emprendimientos',
        choices=[
            ('technology', 'Tecnología'),
            ('social', 'Impacto Social'),
            ('green', 'Sostenibilidad'),
            ('innovation', 'Innovación'),
            ('traditional', 'Tradicional')
        ]
    )
    
    format_type = SelectField('Formato del Reporte', validators=[DataRequired()],
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('dashboard', 'Dashboard en Línea')
        ]
    )
    
    recipients = FieldList(
        StringField('Email', validators=[Optional(), Email()]),
        min_entries=1
    )
    
    include_graphics = BooleanField('Incluir Gráficos', default=True)
    include_summaries = BooleanField('Incluir Resúmenes Ejecutivos', default=True)
    
    submit = SubmitField('Guardar Configuración')

class EntrepreneurFilterForm(FlaskForm):
    """Formulario para filtrar emprendimientos."""
    
    industries = SelectMultipleField('Industrias', choices=[
        ('technology', 'Tecnología'),
        ('health', 'Salud'),
        ('education', 'Educación'),
        ('retail', 'Comercio'),
        ('manufacturing', 'Manufactura'),
        ('services', 'Servicios')
    ])
    
    stages = SelectMultipleField('Etapas', choices=[
        ('idea', 'Idea'),
        ('mvp', 'MVP'),
        ('early', 'Etapa Temprana'),
        ('growth', 'Crecimiento'),
        ('scaling', 'Escalamiento')
    ])
    
    revenue_range = SelectField('Rango de Ingresos', choices=[
        ('0-1000', '$0 - $1,000'),
        ('1000-10000', '$1,000 - $10,000'),
        ('10000-100000', '$10,000 - $100,000'),
        ('100000+', '$100,000+')
    ])
    
    employee_range = SelectField('Número de Empleados', choices=[
        ('1-5', '1-5'),
        ('6-20', '6-20'),
        ('21-50', '21-50'),
        ('50+', '50+')
    ])
    
    impact_areas = SelectMultipleField('Áreas de Impacto', choices=[
        ('social', 'Social'),
        ('environmental', 'Ambiental'),
        ('economic', 'Económico'),
        ('technological', 'Tecnológico')
    ])
    
    location = StringField('Ubicación', validators=[Optional()])
    
    submit = SubmitField('Aplicar Filtros')

class InvestmentInterestForm(FlaskForm):
    """Formulario para registrar interés en inversión."""
    
    entrepreneur_id = SelectField('Emprendimiento', validators=[DataRequired()])
    
    investment_range = SelectField('Rango de Inversión Potencial', validators=[DataRequired()],
        choices=[
            ('10000-50000', '$10,000 - $50,000'),
            ('50000-100000', '$50,000 - $100,000'),
            ('100000-500000', '$100,000 - $500,000'),
            ('500000+', '$500,000+')
        ]
    )
    
    investment_type = SelectMultipleField('Tipo de Inversión', validators=[DataRequired()],
        choices=[
            ('equity', 'Equity'),
            ('debt', 'Deuda'),
            ('convertible', 'Nota Convertible'),
            ('grant', 'Subvención')
        ]
    )
    
    notes = TextAreaField('Notas Adicionales', validators=[
        Optional(),
        Length(max=500)
    ])
    
    preferred_contact_method = SelectField('Método de Contacto Preferido',
        choices=[
            ('email', 'Email'),
            ('phone', 'Teléfono'),
            ('meeting', 'Reunión Presencial')
        ]
    )
    
    submit = SubmitField('Registrar Interés')