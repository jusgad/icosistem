"""
Modern Flask extensions initialization for the entrepreneurship ecosystem.
This module centralizes all modern extensions using latest patterns and libraries.
"""

from typing import Optional, Any
import redis.asyncio as redis
from datetime import timedelta

# === CORE EXTENSIONS ===
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# === MODERN API FRAMEWORK ===
from flask_restx import Api
from flask_pydantic import Pydantic

# === AUTHENTICATION & AUTHORIZATION ===
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_principal import Principal, Permission, RoleNeed
from authlib.integrations.flask_client import OAuth

# === SECURITY ===
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_bcrypt import Bcrypt

# === COMMUNICATION ===
from flask_mail import Mail
from flask_socketio import SocketIO

# === HTTP & COMPRESSION ===
from flask_cors import CORS
from flask_compress import Compress

# === RATE LIMITING ===
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# === CACHING ===
from flask_caching import Cache

# === SESSIONS ===
from flask_session import Session

# === INTERNATIONALIZATION ===
from flask_babel import Babel

# === MODERN LOGGING ===
from loguru import logger
import structlog

# === OBSERVABILITY ===
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# === MONITORING ===
from prometheus_client import Counter, Histogram, Gauge
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


# ====================================
# MODERN EXTENSION INITIALIZATION
# ====================================

class ModernExtensions:
    """Modern centralized extension manager"""
    
    def __init__(self):
        # Core
        self.db = SQLAlchemy()
        self.migrate = Migrate()
        self.pydantic = Pydantic()
        
        # Modern API
        self.api = Api(
            version='2.0',
            title='Ecosistema Emprendimiento API',
            description='Modern API for entrepreneurship ecosystem management',
            doc='/docs/',
            prefix='/api/v2',
            security='Bearer Auth',
            authorizations={
                'Bearer Auth': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'Authorization'
                }
            }
        )
        
        # Auth
        self.login_manager = LoginManager()
        self.jwt = JWTManager()
        self.principal = Principal()
        self.bcrypt = Bcrypt()
        self.oauth = OAuth()
        
        # Security
        self.csrf = CSRFProtect()
        self.talisman = Talisman()
        
        # Communication
        self.mail = Mail()
        self.socketio = SocketIO(
            cors_allowed_origins="*",
            async_mode='eventlet',  # Modern async mode
            ping_timeout=60,
            ping_interval=25,
            logger=False,
            engineio_logger=False
        )
        
        # HTTP
        self.cors = CORS()
        self.compress = Compress()
        
        # Rate limiting with Redis backend
        self.limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["1000 per hour"],
            storage_uri="redis://localhost:6379/2"
        )
        
        # Advanced caching
        self.cache = Cache()
        
        # Sessions
        self.session = Session()
        
        # I18n
        self.babel = Babel()
        
        # Modern connections
        self.redis_client: Optional[redis.Redis] = None
        
        # Metrics
        self.metrics = self._init_metrics()
        
        # Configure login manager
        self._configure_login_manager()
        
        # Configure JWT
        self._configure_jwt()

    def _init_metrics(self) -> dict[str, Any]:
        """Initialize Prometheus metrics"""
        return {
            'request_count': Counter(
                'flask_requests_total',
                'Total Flask requests',
                ['method', 'endpoint', 'status']
            ),
            'request_duration': Histogram(
                'flask_request_duration_seconds',
                'Flask request duration',
                ['method', 'endpoint']
            ),
            'active_users': Gauge(
                'flask_active_users',
                'Number of active users'
            ),
            'database_connections': Gauge(
                'database_connections_active',
                'Active database connections'
            )
        }

    def _configure_login_manager(self):
        """Configure modern login manager settings"""
        self.login_manager.login_view = 'auth.login'
        self.login_manager.login_message = 'Authentication required'
        self.login_manager.login_message_category = 'info'
        self.login_manager.session_protection = 'strong'
        self.login_manager.remember_cookie_duration = timedelta(days=7)
        self.login_manager.remember_cookie_secure = True
        self.login_manager.remember_cookie_httponly = True
        self.login_manager.remember_cookie_samesite = 'Strict'

    def _configure_jwt(self):
        """Configure modern JWT settings"""
        # JWT configurations will be set during init_app
        pass

    async def init_redis(self, app):
        """Initialize async Redis connection"""
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            await self.redis_client.ping()
            app.logger.info("Redis connection established")
        except Exception as e:
            app.logger.error(f"Redis connection failed: {e}")
            self.redis_client = None

    def init_observability(self, app):
        """Initialize modern observability stack"""
        if not OTEL_AVAILABLE:
            app.logger.warning("OpenTelemetry not available, skipping instrumentation")
            return

        # Initialize OpenTelemetry
        trace.set_tracer_provider(TracerProvider())
        
        # Auto-instrument Flask
        FlaskInstrumentor().instrument_app(app)
        
        # Auto-instrument SQLAlchemy
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)
        
        app.logger.info("OpenTelemetry instrumentation initialized")

    def init_sentry(self, app):
        """Initialize Sentry error tracking"""
        sentry_dsn = app.config.get('SENTRY_DSN')
        if sentry_dsn:
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    FlaskIntegration(),
                    SqlalchemyIntegration()
                ],
                traces_sample_rate=app.config.get('SENTRY_TRACES_SAMPLE_RATE', 0.1),
                profiles_sample_rate=app.config.get('SENTRY_PROFILES_SAMPLE_RATE', 0.1),
                environment=app.config.get('ENVIRONMENT', 'development')
            )
            app.logger.info("Sentry error tracking initialized")

    def init_structured_logging(self, app):
        """Initialize structured logging with Loguru"""
        # Configure Loguru
        logger.remove()  # Remove default handler
        
        # Add structured logging handler
        logger.add(
            sink=app.config.get('LOG_FILE', 'logs/app.log'),
            rotation="10 MB",
            retention="30 days",
            compression="gzip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            serialize=True  # JSON format
        )
        
        if app.debug:
            logger.add(
                sink=lambda msg: app.logger.info(msg.rstrip()),
                colorize=True,
                format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}"
            )

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )

    def init_app(self, app):
        """Initialize all modern extensions"""
        # Core database
        self.db.init_app(app)
        self.migrate.init_app(app, self.db)
        self.pydantic.init_app(app)
        
        # Modern API
        self.api.init_app(app)
        
        # Authentication
        self.login_manager.init_app(app)
        self.jwt.init_app(app)
        self.principal.init_app(app)
        self.bcrypt.init_app(app)
        
        # OAuth providers
        self._init_oauth_providers(app)
        
        # Security
        if app.config.get('WTF_CSRF_ENABLED', True):
            self.csrf.init_app(app)
        
        if app.config.get('ENABLE_SECURITY_HEADERS', True):
            self.talisman.init_app(app, **app.config.get('TALISMAN_CONFIG', {}))
        
        # Communication
        self.mail.init_app(app)
        self.socketio.init_app(app)
        
        # HTTP
        self.cors.init_app(app, resources=app.config.get('CORS_RESOURCES', {
            r"/api/*": {
                "origins": ["http://localhost:3000", "https://localhost:3000"],
                "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
                "supports_credentials": True
            }
        }))
        self.compress.init_app(app)
        
        # Rate limiting
        if app.config.get('RATELIMIT_ENABLED', True):
            self.limiter.init_app(app)
        
        # Caching with Redis if available
        cache_config = {
            'CACHE_TYPE': 'RedisCache',
            'CACHE_REDIS_URL': app.config.get('REDIS_URL', 'redis://localhost:6379/1'),
            'CACHE_DEFAULT_TIMEOUT': 300,
            'CACHE_KEY_PREFIX': 'ecosistema:'
        }
        if not app.config.get('REDIS_URL'):
            cache_config['CACHE_TYPE'] = 'SimpleCache'
        
        app.config.update(cache_config)
        self.cache.init_app(app)
        
        # Sessions
        self.session.init_app(app)
        
        # Internationalization
        self.babel.init_app(app)
        
        # Modern features
        self.init_observability(app)
        self.init_sentry(app)
        self.init_structured_logging(app)
        
        # Initialize Redis asynchronously
        with app.app_context():
            import asyncio
            asyncio.create_task(self.init_redis(app))
        
        app.logger.info("All modern extensions initialized successfully")

    def _init_oauth_providers(self, app):
        """Initialize OAuth providers with modern configuration"""
        self.oauth.init_app(app)
        
        # Google OAuth with enhanced scopes
        if app.config.get('GOOGLE_CLIENT_ID'):
            self.oauth.register(
                name='google',
                client_id=app.config['GOOGLE_CLIENT_ID'],
                client_secret=app.config['GOOGLE_CLIENT_SECRET'],
                server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
                client_kwargs={
                    'scope': ' '.join([
                        'openid',
                        'email',
                        'profile',
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/drive.file'
                    ])
                }
            )
        
        # Microsoft OAuth
        if app.config.get('MICROSOFT_CLIENT_ID'):
            self.oauth.register(
                name='microsoft',
                client_id=app.config['MICROSOFT_CLIENT_ID'],
                client_secret=app.config['MICROSOFT_CLIENT_SECRET'],
                server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid_configuration',
                client_kwargs={
                    'scope': 'openid email profile https://graph.microsoft.com/calendars.readwrite'
                }
            )


# ====================================
# GLOBAL EXTENSIONS INSTANCE
# ====================================

# Create global extensions instance
extensions = ModernExtensions()

# Expose individual extensions for backward compatibility
db = extensions.db
migrate = extensions.migrate
pydantic = extensions.pydantic
api = extensions.api
login_manager = extensions.login_manager
jwt = extensions.jwt
principal = extensions.principal
bcrypt = extensions.bcrypt
oauth = extensions.oauth
csrf = extensions.csrf
talisman = extensions.talisman
mail = extensions.mail
socketio = extensions.socketio
cors = extensions.cors
compress = extensions.compress
limiter = extensions.limiter
cache = extensions.cache
session = extensions.session
babel = extensions.babel


# ====================================
# MODERN PERMISSIONS SYSTEM
# ====================================

class ModernPermissions:
    """Modern role-based permissions system"""
    
    ADMIN = Permission(RoleNeed('admin'))
    ENTREPRENEUR = Permission(RoleNeed('entrepreneur'))
    ALLY = Permission(RoleNeed('ally'))
    CLIENT = Permission(RoleNeed('client'))
    
    # Combined permissions
    STAFF = Permission(RoleNeed('admin'), RoleNeed('ally'))
    USER = Permission(
        RoleNeed('admin'),
        RoleNeed('entrepreneur'),
        RoleNeed('ally'),
        RoleNeed('client')
    )
    
    # Resource-specific permissions
    CAN_MANAGE_USERS = Permission(RoleNeed('admin'))
    CAN_VIEW_ANALYTICS = Permission(RoleNeed('admin'), RoleNeed('ally'), RoleNeed('client'))
    CAN_CREATE_PROJECTS = Permission(RoleNeed('admin'), RoleNeed('entrepreneur'))
    CAN_MENTOR = Permission(RoleNeed('admin'), RoleNeed('ally'))


permissions = ModernPermissions()


# ====================================
# MODERN JWT CALLBACKS
# ====================================

@jwt.user_identity_loader
def user_identity_lookup(user):
    """Modern user identity loader"""
    return {
        'id': user.id,
        'email': user.email,
        'role': user.role.name if user.role else None
    }


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """Modern user lookup callback"""
    from app.models.user import User
    identity = jwt_data["sub"]
    return User.query.filter_by(id=identity['id']).first()


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Modern expired token handler"""
    return {
        'error': 'token_expired',
        'message': 'The token has expired'
    }, 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Modern invalid token handler"""
    return {
        'error': 'invalid_token',
        'message': 'Invalid token format'
    }, 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    """Modern missing token handler"""
    return {
        'error': 'authorization_required',
        'message': 'Request does not contain a valid access token'
    }, 401


# ====================================
# MODERN USER LOADER
# ====================================

@login_manager.user_loader
def load_user(user_id):
    """Modern user loader with caching"""
    from app.models.user import User
    
    # Try to get from cache first
    cache_key = f"user:{user_id}"
    cached_user = cache.get(cache_key)
    
    if cached_user:
        return cached_user
    
    # Load from database
    user = User.query.get(int(user_id))
    if user:
        # Cache for 5 minutes
        cache.set(cache_key, user, timeout=300)
    
    return user


@login_manager.unauthorized_handler
def unauthorized():
    """Modern unauthorized handler"""
    from flask import request, jsonify, redirect, url_for, flash
    
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({
            'error': 'authentication_required',
            'message': 'Authentication is required to access this resource'
        }), 401
    
    flash('Please log in to access this page.', 'info')
    return redirect(url_for('auth.login'))


# ====================================
# MODERN BABEL CONFIGURATION
# ====================================

@babel.localeselector
def get_locale():
    """Modern locale selector with user preferences"""
    from flask import request, session
    from flask_login import current_user
    
    # 1. User preference (if authenticated)
    if current_user.is_authenticated and hasattr(current_user, 'preferred_language'):
        return current_user.preferred_language
    
    # 2. Session preference
    if 'language' in session:
        return session['language']
    
    # 3. Request header
    return request.accept_languages.best_match(['es', 'en', 'pt']) or 'es'


@babel.timezoneselector
def get_timezone():
    """Modern timezone selector"""
    from flask_login import current_user
    
    if current_user.is_authenticated and hasattr(current_user, 'timezone'):
        return current_user.timezone
    
    return 'UTC'


# ====================================
# MODERN RATE LIMITING
# ====================================

def get_user_id_for_rate_limit():
    """Get user ID for personalized rate limiting"""
    from flask_login import current_user
    
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{get_remote_address()}"


# User-specific rate limiter
user_limiter = Limiter(
    key_func=get_user_id_for_rate_limit,
    default_limits=["2000 per hour"],
    storage_uri="redis://localhost:6379/2"
)


# ====================================
# INITIALIZATION FUNCTION
# ====================================

def init_app(app):
    """Initialize all modern extensions with the Flask app"""
    extensions.init_app(app)
    
    # Initialize user-specific limiter
    if app.config.get('RATELIMIT_ENABLED', True):
        user_limiter.init_app(app)
    
    return extensions


# ====================================
# EXPORTS
# ====================================

__all__ = [
    # Main extensions manager
    'extensions',
    'init_app',
    
    # Individual extensions
    'db', 'migrate', 'pydantic', 'api',
    'login_manager', 'jwt', 'principal', 'bcrypt', 'oauth',
    'csrf', 'talisman',
    'mail', 'socketio',
    'cors', 'compress',
    'limiter', 'user_limiter', 'cache',
    'session', 'babel',
    
    # Modern permissions
    'permissions',
    'ModernPermissions',
    
    # Utilities
    'logger', 'structlog'
]