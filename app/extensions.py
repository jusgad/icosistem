from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask_moment import Moment
from flask_babel import Babel
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Inicialización de extensiones
# Estas extensiones se inicializan aquí sin una aplicación específica
# y luego se inicializan completamente en la función create_app

# Base de datos y migraciones
db = SQLAlchemy()
migrate = Migrate()

# Autenticación y seguridad
login_manager = LoginManager()
csrf = CSRFProtect()

# Comunicación
mail = Mail()
socketio = SocketIO()

# Internacionalización y formato
moment = Moment()  # Para formateo de fechas en el cliente
babel = Babel()    # Para internacionalización

# Rendimiento
cache = Cache()
limiter = Limiter(key_func=get_remote_address)

def init_extensions(app):
    """
    Inicializa todas las extensiones con la aplicación Flask.
    Esta función se llama desde create_app después de cargar la configuración.
    """
    # Inicializar base de datos y migraciones
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configurar autenticación
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    
    # Inicializar comunicación
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # Inicializar internacionalización
    moment.init_app(app)
    babel.init_app(app)
    
    # Inicializar caché y limitador de tasa
    cache.init_app(app, config={'CACHE_TYPE': 'simple'})
    limiter.init_app(app)
    
    # Configurar funciones de ayuda para plantillas
    @app.context_processor
    def utility_processor():
        """Agrega funciones útiles a las plantillas."""
        def format_datetime(value, format='medium'):
            """Formatea una fecha para mostrar en plantillas."""
            if format == 'full':
                format = "EEEE, d 'de' MMMM 'de' yyyy 'a las' HH:mm"
            elif format == 'medium':
                format = "d 'de' MMM 'de' yyyy, HH:mm"
            elif format == 'short':
                format = "dd/MM/yyyy HH:mm"
            return babel.dates.format_datetime(value, format)
        
        def format_currency(value, currency='USD'):
            """Formatea un valor como moneda."""
            return babel.numbers.format_currency(value, currency)
        
        return dict(
            format_datetime=format_datetime,
            format_currency=format_currency
        )
    
    # Configurar Babel para selección de idioma
    @babel.localeselector
    def get_locale():
        """Determina el idioma a usar basado en la configuración del usuario o navegador."""
        # Primero intentar obtener el idioma de la sesión del usuario
        from flask import session, request
        if 'language' in session:
            return session['language']
        # Si no hay idioma en la sesión, usar el idioma del navegador
        return request.accept_languages.best_match(['es', 'en', 'fr'])
    
    # Configurar caché para rutas comunes
    @app.after_request
    def add_cache_headers(response):
        """Agrega cabeceras de caché a respuestas estáticas."""
        if request.path.startswith('/static'):
            # Cachear archivos estáticos por 1 día
            response.cache_control.max_age = 86400
        return response