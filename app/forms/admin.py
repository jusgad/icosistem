from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    DecimalField,
    BooleanField,
    DateField,
    SubmitField,
    EmailField,
    SelectMultipleField,
    PasswordField
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    ValidationError,
    EqualTo
)
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.utils.validators import password_strength

class UserCreateForm(FlaskForm):
    """Formulario para crear nuevos usuarios desde el panel de administración."""
    
    email = EmailField('Email', validators=[
        DataRequired(message="Email es requerido"),
        Email(message="Por favor ingrese un email válido")
    ])
    
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="Contraseña es requerida"),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres"),
        password_strength()
    ])
    
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message="Por favor confirme la contraseña"),
        EqualTo('password', message="Las contraseñas deben coincidir")
    ])
    
    first_name = StringField('Nombre', validators=[
        DataRequired(message="Nombre es requerido"),
        Length(min=2, max=64)
    ])
    
    last_name = StringField('Apellido', validators=[
        DataRequired(message="Apellido es requerido"),
        Length(min=2, max=64)
    ])
    
    role = SelectField('Rol', validators=[DataRequired()], choices=[
        ('admin', 'Administrador'),
        ('entrepreneur', 'Emprendedor'),
        ('ally', 'Aliado'),
        ('client', 'Cliente')
    ])
    
    is_active = BooleanField('Usuario Activo', default=True)
    
    submit = SubmitField('Crear Usuario')
    
    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('Este email ya está registrado.')

class UserEditForm(FlaskForm):
    """Formulario para editar usuarios existentes."""
    
    email = EmailField('Email', validators=[
        DataRequired(message="Email es requerido"),
        Email(message="Por favor ingrese un email válido")
    ])
    
    first_name = StringField('Nombre', validators=[
        DataRequired(message="Nombre es requerido"),
        Length(min=2, max=64)
    ])
    
    last_name = StringField('Apellido', validators=[
        DataRequired(message="Apellido es requerido"),
        Length(min=2, max=64)
    ])
    
    is_active = BooleanField('Usuario Activo')
    
    role = SelectField('Rol', validators=[DataRequired()], choices=[
        ('admin', 'Administrador'),
        ('entrepreneur', 'Emprendedor'),
        ('ally', 'Aliado'),
        ('client', 'Cliente')
    ])
    
    submit = SubmitField('Actualizar Usuario')
    
    def __init__(self, original_email, *args, **kwargs):
        super(UserEditForm, self).__init__(*args, **kwargs)
        self.original_email = original_email
    
    def validate_email(self, field):
        if field.data.lower() != self.original_email.lower():
            if User.query.filter_by(email=field.data.lower()).first():
                raise ValidationError('Este email ya está registrado.')

class EntrepreneurApprovalForm(FlaskForm):
    """Formulario para aprobar o rechazar solicitudes de emprendedores."""
    
    status = SelectField('Estado', validators=[DataRequired()], choices=[
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('pending', 'Pendiente')
    ])
    
    notes = TextAreaField('Notas de Revisión', validators=[
        Optional(),
        Length(max=500)
    ])
    
    assigned_ally = SelectField('Aliado Asignado', validators=[Optional()])
    
    submit = SubmitField('Actualizar Estado')
    
    def __init__(self, *args, **kwargs):
        super(EntrepreneurApprovalForm, self).__init__(*args, **kwargs)
        self.assigned_ally.choices = [
            (ally.id, f"{ally.first_name} {ally.last_name}")
            for ally in Ally.query.filter_by(is_active=True).all()
        ]

class AllyAssignmentForm(FlaskForm):
    """Formulario para asignar emprendedores a aliados."""
    
    entrepreneur = SelectField('Emprendedor', validators=[DataRequired()])
    ally = SelectField('Aliado', validators=[DataRequired()])
    start_date = DateField('Fecha de Inicio', validators=[DataRequired()])
    notes = TextAreaField('Notas', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Asignar')
    
    def __init__(self, *args, **kwargs):
        super(AllyAssignmentForm, self).__init__(*args, **kwargs)
        self.entrepreneur.choices = [
            (e.id, f"{e.first_name} {e.last_name} - {e.company_name}")
            for e in Entrepreneur.query.filter_by(is_active=True).all()
        ]
        self.ally.choices = [
            (a.id, f"{a.first_name} {a.last_name}")
            for a in Ally.query.filter_by(is_active=True).all()
        ]

class GlobalSettingsForm(FlaskForm):
    """Formulario para configuraciones globales del sistema."""
    
    platform_name = StringField('Nombre de la Plataforma', validators=[
        DataRequired(),
        Length(max=100)
    ])
    
    max_entrepreneurs_per_ally = IntegerField(
        'Máximo de Emprendedores por Aliado',
        validators=[
            DataRequired(),
            NumberRange(min=1, max=20)
        ]
    )
    
    default_session_duration = IntegerField(
        'Duración Predeterminada de Sesiones (minutos)',
        validators=[
            DataRequired(),
            NumberRange(min=30, max=180)
        ]
    )
    
    enable_chat = BooleanField('Habilitar Chat', default=True)
    enable_video_calls = BooleanField('Habilitar Videollamadas', default=True)
    
    submit = SubmitField('Guardar Configuración')

class BulkUserImportForm(FlaskForm):
    """Formulario para importación masiva de usuarios."""
    
    file = FileField('Archivo CSV', validators=[
        DataRequired(),
        FileAllowed(['csv'], 'Solo archivos CSV son permitidos')
    ])
    
    role = SelectField('Rol para Usuarios Importados', validators=[DataRequired()],
        choices=[
            ('entrepreneur', 'Emprendedores'),
            ('ally', 'Aliados'),
            ('client', 'Clientes')
        ]
    )
    
    send_welcome_email = BooleanField('Enviar Email de Bienvenida', default=True)
    
    submit = SubmitField('Importar Usuarios')

class MetricsConfigurationForm(FlaskForm):
    """Formulario para configurar métricas y KPIs del sistema."""
    
    available_metrics = SelectMultipleField('Métricas Disponibles',
        choices=[
            ('revenue', 'Ingresos'),
            ('employees', 'Empleados'),
            ('meetings', 'Reuniones Realizadas'),
            ('tasks', 'Tareas Completadas'),
            ('satisfaction', 'Satisfacción'),
            ('growth', 'Crecimiento')
        ]
    )
    
    default_dashboard_metrics = SelectMultipleField('Métricas en Dashboard',
        choices=[
            ('revenue', 'Ingresos'),
            ('employees', 'Empleados'),
            ('meetings', 'Reuniones Realizadas'),
            ('tasks', 'Tareas Completadas')
        ]
    )
    
    custom_metric_name = StringField('Nombre de Métrica Personalizada',
        validators=[Optional(), Length(max=50)]
    )
    
    custom_metric_description = TextAreaField('Descripción',
        validators=[Optional(), Length(max=200)]
    )
    
    submit = SubmitField('Guardar Configuración de Métricas')

class NotificationSettingsForm(FlaskForm):
    """Formulario para configurar notificaciones del sistema."""
    
    enable_email_notifications = BooleanField('Habilitar Notificaciones por Email',
        default=True
    )
    
    enable_sms_notifications = BooleanField('Habilitar Notificaciones SMS')
    
    notification_types = SelectMultipleField('Tipos de Notificaciones',
        choices=[
            ('new_user', 'Nuevo Usuario Registrado'),
            ('assignment', 'Nueva Asignación'),
            ('meeting', 'Nueva Reunión'),
            ('task', 'Nueva Tarea'),
            ('message', 'Nuevo Mensaje'),
            ('report', 'Nuevo Reporte')
        ]
    )
    
    admin_email_recipients = TextAreaField('Emails de Administradores',
        validators=[Optional()],
        description='Un email por línea'
    )
    
    submit = SubmitField('Guardar Configuración de Notificaciones')