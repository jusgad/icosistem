from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    DecimalField,
    DateField,
    TimeField,
    BooleanField,
    SubmitField,
    SelectMultipleField,
    URLField
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    URL,
    ValidationError,
    Email
)
from datetime import datetime

class EntrepreneurProfileForm(FlaskForm):
    """Formulario para el perfil del emprendedor."""
    
    # Información Personal
    profile_image = FileField('Foto de Perfil', validators=[
        Optional(),
        FileAllowed(['jpg', 'png'], 'Solo imágenes JPG o PNG')
    ])
    
    phone = StringField('Teléfono', validators=[
        DataRequired(message="El teléfono es requerido"),
        Length(min=10, max=15)
    ])
    
    address = StringField('Dirección', validators=[
        Optional(),
        Length(max=200)
    ])
    
    city = StringField('Ciudad', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    country = SelectField('País', validators=[DataRequired()])
    
    linkedin_profile = URLField('Perfil de LinkedIn', validators=[
        Optional(),
        URL(message="Ingrese una URL válida")
    ])
    
    bio = TextAreaField('Biografía', validators=[
        Optional(),
        Length(max=500)
    ])
    
    submit = SubmitField('Actualizar Perfil')

class CompanyInfoForm(FlaskForm):
    """Formulario para la información de la empresa."""
    
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
        ('other', 'Otro')
    ])
    
    stage = SelectField('Etapa del Emprendimiento', validators=[DataRequired()], choices=[
        ('idea', 'Idea'),
        ('mvp', 'Producto Mínimo Viable'),
        ('early', 'Etapa Temprana'),
        ('growth', 'Crecimiento'),
        ('scaling', 'Escalamiento')
    ])
    
    founding_date = DateField('Fecha de Fundación', validators=[Optional()])
    
    website = URLField('Sitio Web', validators=[
        Optional(),
        URL(message="Ingrese una URL válida")
    ])
    
    employee_count = IntegerField('Número de Empleados', validators=[
        DataRequired(),
        NumberRange(min=1)
    ])
    
    company_description = TextAreaField('Descripción de la Empresa', validators=[
        DataRequired(),
        Length(min=100, max=1000)
    ])
    
    problem_statement = TextAreaField('Problema que Resuelve', validators=[
        DataRequired(),
        Length(min=100, max=500)
    ])
    
    solution_description = TextAreaField('Descripción de la Solución', validators=[
        DataRequired(),
        Length(min=100, max=500)
    ])
    
    target_market = TextAreaField('Mercado Objetivo', validators=[
        DataRequired(),
        Length(max=500)
    ])
    
    revenue_model = TextAreaField('Modelo de Ingresos', validators=[
        DataRequired(),
        Length(max=500)
    ])
    
    submit = SubmitField('Guardar Información')

class DocumentUploadForm(FlaskForm):
    """Formulario para subir documentos."""
    
    document = FileField('Documento', validators=[
        DataRequired(),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'],
                   'Formato de archivo no permitido')
    ])
    
    title = StringField('Título', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    category = SelectField('Categoría', validators=[DataRequired()], choices=[
        ('business_plan', 'Plan de Negocio'),
        ('pitch_deck', 'Pitch Deck'),
        ('financial', 'Documentos Financieros'),
        ('legal', 'Documentos Legales'),
        ('other', 'Otros')
    ])
    
    description = TextAreaField('Descripción', validators=[
        Optional(),
        Length(max=200)
    ])
    
    is_private = BooleanField('Documento Privado', default=False)
    
    submit = SubmitField('Subir Documento')

class TaskCreateForm(FlaskForm):
    """Formulario para crear tareas."""
    
    title = StringField('Título', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    description = TextAreaField('Descripción', validators=[
        DataRequired(),
        Length(max=500)
    ])
    
    due_date = DateField('Fecha de Vencimiento', validators=[DataRequired()])
    
    priority = SelectField('Prioridad', validators=[DataRequired()], choices=[
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta')
    ])
    
    category = SelectField('Categoría', validators=[DataRequired()], choices=[
        ('business', 'Negocio'),
        ('legal', 'Legal'),
        ('financial', 'Financiero'),
        ('marketing', 'Marketing'),
        ('operations', 'Operaciones'),
        ('other', 'Otro')
    ])
    
    assignee = SelectField('Asignar a', validators=[Optional()])
    
    submit = SubmitField('Crear Tarea')

class MeetingRequestForm(FlaskForm):
    """Formulario para solicitar reuniones."""
    
    title = StringField('Título', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    description = TextAreaField('Descripción', validators=[
        DataRequired(),
        Length(max=500)
    ])
    
    date = DateField('Fecha', validators=[DataRequired()])
    
    time = TimeField('Hora', validators=[DataRequired()])
    
    duration = SelectField('Duración', validators=[DataRequired()], choices=[
        ('30', '30 minutos'),
        ('60', '1 hora'),
        ('90', '1 hora 30 minutos'),
        ('120', '2 horas')
    ])
    
    meeting_type = SelectField('Tipo de Reunión', validators=[DataRequired()], choices=[
        ('mentoring', 'Mentoría'),
        ('follow_up', 'Seguimiento'),
        ('planning', 'Planificación'),
        ('review', 'Revisión'),
        ('other', 'Otro')
    ])
    
    is_virtual = BooleanField('Reunión Virtual', default=True)
    
    location = StringField('Ubicación', validators=[Optional()])
    
    participants = SelectMultipleField('Participantes', validators=[DataRequired()])
    
    submit = SubmitField('Solicitar Reunión')
    
    def validate_date(self, field):
        if field.data < datetime.now().date():
            raise ValidationError('La fecha no puede ser en el pasado')

class MetricsUpdateForm(FlaskForm):
    """Formulario para actualizar métricas del emprendimiento."""
    
    monthly_revenue = DecimalField('Ingresos Mensuales', validators=[Optional()])
    
    customer_count = IntegerField('Número de Clientes', validators=[Optional()])
    
    burn_rate = DecimalField('Tasa de Consumo de Capital', validators=[Optional()])
    
    runway_months = IntegerField('Meses de Runway', validators=[Optional()])
    
    growth_rate = DecimalField('Tasa de Crecimiento (%)', validators=[
        Optional(),
        NumberRange(min=0, max=1000)
    ])
    
    month = SelectField('Mes', validators=[DataRequired()])
    
    year = SelectField('Año', validators=[DataRequired()])
    
    notes = TextAreaField('Notas', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Actualizar Métricas')

class FeedbackForm(FlaskForm):
    """Formulario para enviar feedback sobre el programa."""
    
    satisfaction_level = SelectField('Nivel de Satisfacción', validators=[DataRequired()],
        choices=[
            ('5', 'Muy Satisfecho'),
            ('4', 'Satisfecho'),
            ('3', 'Neutral'),
            ('2', 'Insatisfecho'),
            ('1', 'Muy Insatisfecho')
        ]
    )
    
    mentor_rating = SelectField('Calificación del Mentor', validators=[DataRequired()],
        choices=[('5', '5'), ('4', '4'), ('3', '3'), ('2', '2'), ('1', '1')]
    )
    
    program_rating = SelectField('Calificación del Programa', validators=[DataRequired()],
        choices=[('5', '5'), ('4', '4'), ('3', '3'), ('2', '2'), ('1', '1')]
    )
    
    feedback_text = TextAreaField('Comentarios', validators=[
        DataRequired(),
        Length(min=50, max=1000)
    ])
    
    would_recommend = BooleanField('Recomendaría el Programa')
    
    areas_of_improvement = SelectMultipleField('Áreas de Mejora', choices=[
        ('mentoring', 'Mentoría'),
        ('resources', 'Recursos'),
        ('networking', 'Networking'),
        ('content', 'Contenido'),
        ('platform', 'Plataforma'),
        ('support', 'Soporte')
    ])
    
    submit = SubmitField('Enviar Feedback')