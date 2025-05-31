"""
Inicialización de extensiones Flask para el ecosistema de emprendimiento.
Este módulo centraliza todas las extensiones para evitar importaciones circulares.
"""

# === EXTENSIONES CORE ===
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

# === AUTENTICACIÓN Y AUTORIZACIÓN ===
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_principal import Principal, Permission, RoleNeed
from authlib.integrations.flask_client import OAuth

# === SEGURIDAD ===
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_bcrypt import Bcrypt

# === EMAIL Y COMUNICACIONES ===
from flask_mail import Mail

# === WEBSOCKETS ===
from flask_socketio import SocketIO

# === HTTP Y CORS ===
from flask_cors import CORS
from flask_compress import Compress

# === RATE LIMITING ===
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# === CACHE ===
from flask_caching import Cache

# === SESIONES ===
from flask_session import Session

# === INTERNACIONALIZACIÓN ===
from flask_babel import Babel

# === MONITOREO Y MÉTRICAS ===
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
import redis


# ====================================
# INICIALIZACIÓN DE EXTENSIONES
# ====================================

# === BASE DE DATOS ===
db = SQLAlchemy()
ma = Marshmallow()  # Para serialización JSON automática
migrate = Migrate()

# === AUTENTICACIÓN ===
login_manager = LoginManager()
jwt = JWTManager()
principal = Principal()
bcrypt = Bcrypt()

# === OAuth PROVIDERS ===
oauth = OAuth()

# Configuración de Login Manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'
login_manager.remember_cookie_duration = 86400  # 24 horas
login_manager.remember_cookie_secure = True
login_manager.remember_cookie_httponly = True

# === SEGURIDAD ===
csrf = CSRFProtect()
talisman = Talisman()

# === EMAIL ===
mail = Mail()

# === WEBSOCKETS ===
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# === HTTP ===
cors = CORS(
    resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:5000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    }
)
compress = Compress()

# === RATE LIMITING ===
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)

# === CACHE ===
cache = Cache()

# === SESIONES ===
session = Session()

# === INTERNACIONALIZACIÓN ===
babel = Babel()

# === AUTENTICACIÓN HTTP PARA APIs ===
basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth()

# === REDIS CONNECTION ===
redis_client = None


# ====================================
# CONFIGURACIONES ESPECÍFICAS
# ====================================

def init_redis(app):
    """
    Inicializa la conexión Redis si está disponible.
    """
    global redis_client
    
    redis_url = app.config.get('CACHE_REDIS_URL') or app.config.get('REDIS_URL')
    if redis_url:
        try:
            redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            redis_client.ping()
            app.logger.info("Redis connection established")
        except Exception as e:
            app.logger.warning(f"Redis connection failed: {e}")
            redis_client = None
    else:
        app.logger.info("Redis URL not configured")


# ====================================
# PROVIDERS OAUTH
# ====================================

def init_oauth_providers(app):
    """
    Inicializa los providers de OAuth.
    """
    
    # Google OAuth
    if app.config.get('GOOGLE_CLIENT_ID'):
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
            client_kwargs={
                'scope': 'openid email profile https://www.googleapis.com/auth/calendar'
            }
        )
        app.logger.info("Google OAuth provider registered")
    
    # Microsoft OAuth (opcional)
    if app.config.get('MICROSOFT_CLIENT_ID'):
        oauth.register(
            name='microsoft',
            client_id=app.config['MICROSOFT_CLIENT_ID'],
            client_secret=app.config['MICROSOFT_CLIENT_SECRET'],
            server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid_configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        app.logger.info("Microsoft OAuth provider registered")


# ====================================
# PERMISOS Y ROLES
# ====================================

# Definir roles del sistema
admin_permission = Permission(RoleNeed('admin'))
entrepreneur_permission = Permission(RoleNeed('entrepreneur'))
ally_permission = Permission(RoleNeed('ally'))
client_permission = Permission(RoleNeed('client'))

# Permisos combinados
staff_permission = Permission(RoleNeed('admin'), RoleNeed('ally'))
user_permission = Permission(
    RoleNeed('admin'), 
    RoleNeed('entrepreneur'), 
    RoleNeed('ally'), 
    RoleNeed('client')
)


# ====================================
# CALLBACKS Y CONFIGURACIONES
# ====================================

@login_manager.user_loader
def load_user(user_id):
    """
    Callback para cargar usuario en Flask-Login.
    """
    from app.models.user import User
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    """
    Manejador para usuarios no autorizados.
    """
    from flask import request, jsonify, redirect, url_for, flash
    
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'Authentication required'}), 401
    
    flash('Debes iniciar sesión para acceder a esta página.', 'warning')
    return redirect(url_for('auth.login'))


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """
    Callback para tokens JWT expirados.
    """
    from flask import jsonify
    return jsonify({'error': 'Token has expired'}), 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """
    Callback para tokens JWT inválidos.
    """
    from flask import jsonify
    return jsonify({'error': 'Invalid token'}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    """
    Callback para tokens JWT faltantes.
    """
    from flask import jsonify
    return jsonify({'error': 'Authorization token is required'}), 401


# Token blacklist para JWT
jwt_blacklist = set()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    """
    Verificar si el token está en la lista negra.
    """
    jti = jwt_payload['jti']
    return jti in jwt_blacklist


def revoke_token(jti):
    """
    Añadir token a la lista negra.
    """
    jwt_blacklist.add(jti)


# ====================================
# CONFIGURACIÓN DE RATE LIMITING
# ====================================

def get_user_id():
    """
    Obtener ID de usuario para rate limiting personalizado.
    """
    from flask_login import current_user
    if current_user.is_authenticated:
        return str(current_user.id)
    return get_remote_address()


# Rate limiting por usuario autenticado
limiter_per_user = Limiter(
    key_func=get_user_id,
    default_limits=["200 per hour"]
)


# ====================================
# CONFIGURACIÓN DE WEBSOCKETS
# ====================================

# Namespace personalizado para WebSockets
class CustomNamespace:
    """
    Namespace base para WebSockets.
    """
    
    def __init__(self, namespace):
        self.namespace = namespace
    
    def on_connect(self, auth):
        """Manejar conexión WebSocket."""
        from flask_login import current_user
        from flask_socketio import emit, disconnect
        
        if not current_user.is_authenticated:
            disconnect()
            return False
        
        emit('status', {'msg': f'{current_user.email} has connected'})
        return True
    
    def on_disconnect(self):
        """Manejar desconexión WebSocket."""
        from flask_login import current_user
        from flask_socketio import emit
        
        if current_user.is_authenticated:
            emit('status', {'msg': f'{current_user.email} has disconnected'})


# ====================================
# CONFIGURACIÓN DE CACHÉ
# ====================================

def make_cache_key(*args, **kwargs):
    """
    Generar clave de caché personalizada.
    """
    from flask import request
    from flask_login import current_user
    
    # Incluir usuario en la clave si está autenticado
    user_id = getattr(current_user, 'id', 'anonymous') if current_user.is_authenticated else 'anonymous'
    
    # Crear clave basada en la ruta y parámetros
    path = request.path
    args_str = str(sorted(request.args.items()))
    
    return f"cache:{user_id}:{path}:{hash(args_str)}"


# ====================================
# CONFIGURACIÓN DE BABEL
# ====================================

@babel.localeselector
def get_locale():
    """
    Selector de idioma para Flask-Babel.
    """
    from flask import request, session
    from flask_login import current_user
    
    # 1. Idioma del usuario autenticado
    if current_user.is_authenticated and hasattr(current_user, 'language'):
        return current_user.language
    
    # 2. Idioma de la sesión
    if 'language' in session:
        return session['language']
    
    # 3. Idioma del navegador
    return request.accept_languages.best_match(['es', 'en']) or 'es'


@babel.timezoneselector
def get_timezone():
    """
    Selector de zona horaria.
    """
    from flask_login import current_user
    
    if current_user.is_authenticated and hasattr(current_user, 'timezone'):
        return current_user.timezone
    
    return 'America/Bogota'


# ====================================
# AUTENTICACIÓN BÁSICA PARA APIs
# ====================================

@basic_auth.verify_password
def verify_password(username, password):
    """
    Verificar credenciales para autenticación básica.
    """
    from app.models.user import User
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None


@basic_auth.error_handler
def basic_auth_error(status):
    """
    Manejador de errores para autenticación básica.
    """
    from flask import jsonify
    return jsonify({'error': 'Invalid credentials'}), status


@token_auth.verify_token
def verify_token(token):
    """
    Verificar token para autenticación por token.
    """
    from app.models.user import User
    
    user = User.query.filter_by(api_token=token).first()
    if user:
        return user
    return None


@token_auth.error_handler
def token_auth_error(status):
    """
    Manejador de errores para autenticación por token.
    """
    from flask import jsonify
    return jsonify({'error': 'Invalid token'}), status


# ====================================
# FUNCIÓN DE INICIALIZACIÓN PRINCIPAL
# ====================================

def init_all_extensions(app):
    """
    Inicializar todas las extensiones con la aplicación Flask.
    Esta función se llama desde app/__init__.py
    """
    
    # Base de datos
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)
    
    # Autenticación
    login_manager.init_app(app)
    jwt.init_app(app)
    principal.init_app(app)
    bcrypt.init_app(app)
    
    # OAuth
    oauth.init_app(app)
    init_oauth_providers(app)
    
    # Seguridad
    if app.config.get('WTF_CSRF_ENABLED', True):
        csrf.init_app(app)
    
    if app.config.get('ENABLE_SECURITY_HEADERS', True):
        talisman.init_app(app)
    
    # Email
    mail.init_app(app)
    
    # WebSockets
    socketio.init_app(
        app,
        cors_allowed_origins=app.config.get('SOCKETIO_CORS_ORIGINS', "*"),
        async_mode=app.config.get('SOCKETIO_ASYNC_MODE', 'threading'),
        logger=app.config.get('SOCKETIO_LOGGER', False),
        engineio_logger=app.config.get('ENGINEIO_LOGGER', False)
    )
    
    # HTTP
    cors.init_app(app)
    compress.init_app(app)
    
    # Rate limiting
    if app.config.get('RATELIMIT_ENABLED', True):
        limiter.init_app(app)
        limiter_per_user.init_app(app)
    
    # Cache
    cache.init_app(app)
    
    # Sesiones
    session.init_app(app)
    
    # Internacionalización
    babel.init_app(app)
    
    # Redis
    init_redis(app)
    
    app.logger.info("All extensions initialized successfully")


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    # Core
    'db', 'ma', 'migrate',
    
    # Auth
    'login_manager', 'jwt', 'principal', 'bcrypt', 'oauth',
    
    # Security
    'csrf', 'talisman',
    
    # Communication
    'mail', 'socketio',
    
    # HTTP
    'cors', 'compress',
    
    # Limiting & Caching
    'limiter', 'limiter_per_user', 'cache',
    
    # Session & I18n
    'session', 'babel',
    
    # API Auth
    'basic_auth', 'token_auth',
    
    # Permissions
    'admin_permission', 'entrepreneur_permission', 'ally_permission', 
    'client_permission', 'staff_permission', 'user_permission',
    
    # Utils
    'redis_client', 'revoke_token', 'make_cache_key',
    
    # Main init function
    'init_all_extensions'
]