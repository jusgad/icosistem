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
    URLField,
    FieldList,
    FormField
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
from datetime import datetime, time

class AllyProfileForm(FlaskForm):
    """Formulario para el perfil del aliado/mentor."""
    
    # Información Personal
    profile_image = FileField('Foto de Perfil', validators=[
        Optional(),
        FileAllowed(['jpg', 'png'], 'Solo imágenes JPG o PNG')
    ])
    
    phone = StringField('Teléfono', validators=[
        DataRequired(message="El teléfono es requerido"),
        Length(min=10, max=15)
    ])
    
    linkedin_profile = URLField('Perfil de LinkedIn', validators=[
        DataRequired(message="El perfil de LinkedIn es requerido"),
        URL(message="Ingrese una URL válida")
    ])
    
    expertise_areas = SelectMultipleField('Áreas de Experiencia', validators=[
        DataRequired(message="Seleccione al menos un área de experiencia")
    ], choices=[
        ('business_strategy', 'Estrategia de Negocio'),
        ('marketing', 'Marketing'),
        ('finance', 'Finanzas'),
        ('operations', 'Operaciones'),
        ('technology', 'Tecnología'),
        ('sales', 'Ventas'),
        ('legal', 'Legal'),
        ('hr', 'Recursos Humanos')
    ])
    
    industries = SelectMultipleField('Industrias', validators=[
        DataRequired(message="Seleccione al menos una industria")
    ], choices=[
        ('technology', 'Tecnología'),
        ('health', 'Salud'),
        ('education', 'Educación'),
        ('retail', 'Comercio'),
        ('manufacturing', 'Manufactura'),
        ('services', 'Servicios'),
        ('fintech', 'Fintech'),
        ('other', 'Otro')
    ])
    
    years_experience = IntegerField('Años de Experiencia', validators=[
        DataRequired(),
        NumberRange(min=1, max=50)
    ])
    
    bio = TextAreaField('Biografía', validators=[
        DataRequired(),
        Length(min=100, max=1000)
    ])
    
    languages = SelectMultipleField('Idiomas', validators=[DataRequired()], choices=[
        ('es', 'Español'),
        ('en', 'Inglés'),
        ('pt', 'Portugués'),
        ('fr', 'Francés'),
        ('other', 'Otro')
    ])
    
    submit = SubmitField('Actualizar Perfil')

class AvailabilitySlotForm(FlaskForm):
    """Subformulario para slots de disponibilidad."""
    
    day = SelectField('Día', validators=[DataRequired()], choices=[
        ('monday', 'Lunes'),
        ('tuesday', 'Martes'),
        ('wednesday', 'Miércoles'),
        ('thursday', 'Jueves'),
        ('friday', 'Viernes')
    ])
    
    start_time = TimeField('Hora Inicio', validators=[DataRequired()])
    end_time = TimeField('Hora Fin', validators=[DataRequired()])
    
    def validate_end_time(self, field):
        if self.start_time.data >= field.data:
            raise ValidationError('La hora de fin debe ser posterior a la hora de inicio')

class AvailabilityForm(FlaskForm):
    """Formulario para gestionar disponibilidad."""
    
    timezone = SelectField('Zona Horaria', validators=[DataRequired()])
    
    slots = FieldList(
        FormField(AvailabilitySlotForm),
        min_entries=1,
        max_entries=10
    )
    
    max_weekly_hours = IntegerField('Máximo de Horas Semanales', validators=[
        DataRequired(),
        NumberRange(min=1, max=40)
    ])
    
    available_for_emergency = BooleanField('Disponible para Emergencias')
    
    submit = SubmitField('Guardar Disponibilidad')

class HoursLogForm(FlaskForm):
    """Formulario para registrar horas de mentoría."""
    
    entrepreneur = SelectField('Emprendedor', validators=[DataRequired()])
    
    date = DateField('Fecha', validators=[DataRequired()])
    
    hours = DecimalField('Horas', validators=[
        DataRequired(),
        NumberRange(min=0.5, max=8)
    ])
    
    activity_type = SelectField('Tipo de Actividad', validators=[DataRequired()], choices=[
        ('mentoring', 'Mentoría'),
        ('review', 'Revisión'),
        ('planning', 'Planificación'),
        ('documentation', 'Documentación'),
        ('other', 'Otro')
    ])
    
    description = TextAreaField('Descripción', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    achievements = TextAreaField('Logros', validators=[
        Optional(),
        Length(max=500)
    ])
    
    next_steps = TextAreaField('Próximos Pasos', validators=[
        Optional(),
        Length(max=500)
    ])
    
    submit = SubmitField('Registrar Horas')
    
    def validate_date(self, field):
        if field.data > datetime.now().date():
            raise ValidationError('No se pueden registrar horas futuras')

class EntrepreneurFeedbackForm(FlaskForm):
    """Formulario para proporcionar feedback a emprendedores."""
    
    entrepreneur = SelectField('Emprendedor', validators=[DataRequired()])
    
    period = SelectField('Período', validators=[DataRequired()], choices=[
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral')
    ])
    
    progress_rating = SelectField('Calificación de Progreso', validators=[DataRequired()],
        choices=[('5', '5'), ('4', '4'), ('3', '3'), ('2', '2'), ('1', '1')]
    )
    
    commitment_rating = SelectField('Calificación de Compromiso', validators=[DataRequired()],
        choices=[('5', '5'), ('4', '4'), ('3', '3'), ('2', '2'), ('1', '1')]
    )
    
    achievements = TextAreaField('Logros del Período', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    areas_of_improvement = TextAreaField('Áreas de Mejora', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    recommendations = TextAreaField('Recomendaciones', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    next_period_goals = TextAreaField('Objetivos Próximo Período', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    submit = SubmitField('Enviar Feedback')

class MentorshipPlanForm(FlaskForm):
    """Formulario para crear/editar plan de mentoría."""
    
    entrepreneur = SelectField('Emprendedor', validators=[DataRequired()])
    
    start_date = DateField('Fecha de Inicio', validators=[DataRequired()])
    end_date = DateField('Fecha de Fin', validators=[DataRequired()])
    
    objectives = TextAreaField('Objetivos', validators=[
        DataRequired(),
        Length(min=100, max=1000)
    ])
    
    key_results = TextAreaField('Resultados Clave', validators=[
        DataRequired(),
        Length(min=100, max=1000)
    ])
    
    methodology = TextAreaField('Metodología', validators=[
        DataRequired(),
        Length(min=100, max=1000)
    ])
    
    meeting_frequency = SelectField('Frecuencia de Reuniones', validators=[DataRequired()],
        choices=[
            ('weekly', 'Semanal'),
            ('biweekly', 'Quincenal'),
            ('monthly', 'Mensual')
        ]
    )
    
    resources_needed = TextAreaField('Recursos Necesarios', validators=[
        Optional(),
        Length(max=500)
    ])
    
    success_criteria = TextAreaField('Criterios de Éxito', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    submit = SubmitField('Guardar Plan')
    
    def validate_end_date(self, field):
        if field.data <= self.start_date.data:
            raise ValidationError('La fecha de fin debe ser posterior a la fecha de inicio')

class ResourceRecommendationForm(FlaskForm):
    """Formulario para recomendar recursos a emprendedores."""
    
    entrepreneur = SelectField('Emprendedor', validators=[DataRequired()])
    
    resource_type = SelectField('Tipo de Recurso', validators=[DataRequired()], choices=[
        ('article', 'Artículo'),
        ('video', 'Video'),
        ('book', 'Libro'),
        ('course', 'Curso'),
        ('tool', 'Herramienta'),
        ('contact', 'Contacto'),
        ('other', 'Otro')
    ])
    
    title = StringField('Título', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    description = TextAreaField('Descripción', validators=[
        DataRequired(),
        Length(min=50, max=500)
    ])
    
    url = URLField('URL', validators=[Optional(), URL()])
    
    priority = SelectField('Prioridad', validators=[DataRequired()], choices=[
        ('high', 'Alta'),
        ('medium', 'Media'),
        ('low', 'Baja')
    ])
    
    notes = TextAreaField('Notas Adicionales', validators=[
        Optional(),
        Length(max=500)
    ])
    
    submit = SubmitField('Recomendar Recurso')