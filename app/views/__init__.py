from flask import Blueprint
from flask_login import current_user
from functools import wraps
from app.extensions import db

# Importación de Blueprints
from .main import main_bp
from .auth import auth_bp
from .admin.dashboard import admin_bp
from .entrepreneur.dashboard import entrepreneur_bp
from .ally.dashboard import ally_bp
from .client.dashboard import client_bp

# Decoradores personalizados para control de acceso
def admin_required(f):
    """Decorador para rutas que requieren acceso de administrador."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def entrepreneur_required(f):
    """Decorador para rutas que requieren acceso de emprendedor."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'entrepreneur':
            flash('Acceso denegado. Se requieren privilegios de emprendedor.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def ally_required(f):
    """Decorador para rutas que requieren acceso de aliado."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'ally':
            flash('Acceso denegado. Se requieren privilegios de aliado.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def client_required(f):
    """Decorador para rutas que requieren acceso de cliente."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'client':
            flash('Acceso denegado. Se requieren privilegios de cliente.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def init_views(app):
    """Inicializa todas las vistas de la aplicación."""
    
    # Registro de Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(entrepreneur_bp, url_prefix='/entrepreneur')
    app.register_blueprint(ally_bp, url_prefix='/ally')
    app.register_blueprint(client_bp, url_prefix='/client')

    # Manejo de errores personalizado
    register_error_handlers(app)
    
    # Contexto global para templates
    register_template_context(app)
    
    # Filtros personalizados para Jinja
    register_template_filters(app)

def register_error_handlers(app):
    """Registra manejadores de errores personalizados."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('error/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error/500.html'), 500

def register_template_context(app):
    """Registra variables de contexto global para templates."""
    
    @app.context_processor
    def utility_processor():
        def user_has_permission(permission):
            """Verifica si el usuario tiene un permiso específico."""
            if not current_user.is_authenticated:
                return False
            return current_user.has_permission(permission)

        def format_datetime(value, format='medium'):
            """Formatea fechas según la localización del usuario."""
            if format == 'full':
                format = "EEEE, d 'de' MMMM 'de' y 'a las' HH:mm"
            elif format == 'medium':
                format = "d 'de' MMM 'de' y HH:mm"
            return babel.dates.format_datetime(value, format)

        return dict(
            user_has_permission=user_has_permission,
            format_datetime=format_datetime,
            app_name=app.config['APP_NAME'],
            current_year=datetime.utcnow().year
        )

def register_template_filters(app):
    """Registra filtros personalizados para templates."""
    
    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea valores como moneda."""
        return f"${value:,.2f}"

    @app.template_filter('datetime')
    def datetime_filter(value, format='medium'):
        """Formatea fechas y horas."""
        if value is None:
            return ''
        return format_datetime(value, format)

    @app.template_filter('truncate_words')
    def truncate_words_filter(s, length=30, end='...'):
        """Trunca texto a un número específico de palabras."""
        if not s:
            return ''
        words = s.split()
        if len(words) > length:
            return ' '.join(words[:length]) + end
        return ' '.join(words)

# Exportar todos los blueprints y decoradores
__all__ = [
    'main_bp',
    'auth_bp',
    'admin_bp',
    'entrepreneur_bp',
    'ally_bp',
    'client_bp',
    'admin_required',
    'entrepreneur_required',
    'ally_required',
    'client_required',
    'init_views'
]

# Versión del módulo de vistas
__version__ = '1.0.0'

"""
Módulo de Vistas
===============

Este módulo contiene todas las rutas y vistas de la aplicación,
organizadas por blueprints según el tipo de usuario:

- main: Páginas públicas principales
- auth: Autenticación y gestión de usuarios
- admin: Panel de administración
- entrepreneur: Área de emprendedores
- ally: Área de aliados/mentores
- client: Área de clientes corporativos

Uso:
----
    from app.views import init_views
    
    def create_app():
        app = Flask(__name__)
        init_views(app)
        return app
"""
def register_before_request(app):
    """Registra funciones que se ejecutan antes de cada solicitud."""
    
    @app.before_request
    def before_request():
        # Almacenar tiempo de inicio para medir duración de requests
        g.start_time = time.time()
        
        # Verificar IP baneada
        if check_ip_banned(request.remote_addr):
            abort(403)
        
        # Establecer lenguaje preferido del usuario
        if current_user.is_authenticated:
            g.locale = current_user.locale
        else:
            g.locale = session.get('locale', 'es')
        
        # Registro de actividad para auditoría
        if current_user.is_authenticated:
            log_activity(
                user_id=current_user.id,
                action='page_view',
                resource=request.endpoint,
                ip_address=request.remote_addr
            )

def register_after_request(app):
    """Registra funciones que se ejecutan después de cada solicitud."""
    
    @app.after_request
    def after_request(response):
        # Agregar headers de seguridad
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Calcular y registrar tiempo de respuesta
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            app.logger.info(f'Request to {request.endpoint} took {elapsed:.2f}s')
        
        return response

def register_context_processors(app):
    """Registra procesadores de contexto adicionales."""
    
    @app.context_processor
    def inject_user_permissions():
        """Inyecta permisos del usuario en el contexto."""
        permissions = {}
        if current_user.is_authenticated:
            permissions = {
                'can_view_admin': current_user.role == 'admin',
                'can_manage_users': current_user.has_permission('manage_users'),
                'can_view_metrics': current_user.has_permission('view_metrics'),
                'can_export_data': current_user.has_permission('export_data')
            }
        return dict(user_permissions=permissions)
    
    @app.context_processor
    def inject_app_settings():
        """Inyecta configuraciones de la aplicación en el contexto."""
        return {
            'app_version': app.config.get('VERSION'),
            'support_email': app.config.get('SUPPORT_EMAIL'),
            'enable_features': {
                'chat': app.config.get('ENABLE_CHAT', True),
                'video_calls': app.config.get('ENABLE_VIDEO_CALLS', True),
                'file_sharing': app.config.get('ENABLE_FILE_SHARING', True)
            }
        }

def register_url_converters(app):
    """Registra conversores de URL personalizados."""
    
    class ListConverter(BaseConverter):
        def to_python(self, value):
            return value.split(',')
        
        def to_url(self, values):
            return ','.join(super(ListConverter, self).to_url(value)
                          for value in values)
    
    app.url_map.converters['list'] = ListConverter

def register_template_tests(app):
    """Registra pruebas personalizadas para templates."""
    
    @app.template_test('admin_user')
    def is_admin_user(user):
        return user.role == 'admin'
    
    @app.template_test('entrepreneur_user')
    def is_entrepreneur_user(user):
        return user.role == 'entrepreneur'
    
    @app.template_test('ally_user')
    def is_ally_user(user):
        return user.role == 'ally'

def register_cli_commands(app):
    """Registra comandos CLI personalizados."""
    
    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('password')
    def create_admin(email, password):
        """Crea un usuario administrador."""
        from app.models.user import User
        
        user = User(
            email=email,
            role='admin',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {email} created successfully')

def init_views(app):
    """Función principal de inicialización de vistas."""
    
    # Registrar blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(entrepreneur_bp, url_prefix='/entrepreneur')
    app.register_blueprint(ally_bp, url_prefix='/ally')
    app.register_blueprint(client_bp, url_prefix='/client')
    
    # Registrar funcionalidades adicionales
    register_before_request(app)
    register_after_request(app)
    register_error_handlers(app)
    register_template_context(app)
    register_template_filters(app)
    register_context_processors(app)
    register_url_converters(app)
    register_template_tests(app)
    register_cli_commands(app)
    
    # Configurar caché para vistas frecuentes
    configure_view_cache(app)
    
    return app

def configure_view_cache(app):
    """Configura caché para vistas frecuentemente accedidas."""
    
    cache = Cache(app)
    
    def cache_key():
        """Genera una clave de caché única por usuario y request."""
        return f'view_{request.endpoint}_{current_user.id if current_user.is_authenticated else "anonymous"}'
    
    # Ejemplo de vista cacheada
    @cache.cached(timeout=300, key_prefix=cache_key)
    def get_dashboard_data():
        """Obtiene datos del dashboard (cacheados por 5 minutos)."""
        # Lógica para obtener datos del dashboard
        pass

class ViewManager:
    """Gestor centralizado de vistas y funcionalidades."""
    
    def __init__(self, app):
        self.app = app
        self.limiter = Limiter(
            app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"]
        )
        self.setup_middleware()
        self.register_custom_endpoints()
        self.setup_monitoring()

    def setup_middleware(self):
        """Configura middleware para la aplicación."""
        # Soporte para proxy reverso
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_proto=1, x_host=1)
        
        # Middleware de compresión
        if not self.app.debug:
            self.app.wsgi_app = Compress(self.app.wsgi_app)

    def register_custom_endpoints(self):
        """Registra endpoints utilitarios."""
        
        @self.app.route('/health')
        @self.limiter.exempt
        def health_check():
            """Endpoint para verificación de salud del sistema."""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'version': current_app.config['VERSION'],
                'environment': current_app.config['ENV']
            })
        
        @self.app.route('/metrics')
        @admin_required
        def metrics():
            """Endpoint para métricas de la aplicación."""
            return jsonify({
                'users_total': User.query.count(),
                'users_active': User.query.filter_by(is_active=True).count(),
                'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
                'allies': User.query.filter_by(role='ally').count(),
                'clients': User.query.filter_by(role='client').count()
            })

    def setup_monitoring(self):
        """Configura monitoreo de la aplicación."""
        
        @self.app.before_request
        def start_timer():
            g.start = time.time()

        @self.app.after_request
        def log_request(response):
            if request.path != '/health':  # Ignorar health checks
                now = time.time()
                duration = round(now - g.start, 2)
                log_performance(
                    endpoint=request.endpoint,
                    method=request.method,
                    status_code=response.status_code,
                    duration=duration
                )
            return response

def register_api_routes(app):
    """Registra rutas de API con control de versiones."""
    
    # API v1
    from .api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    
    # API v2 (si existe)
    from .api.v2 import api_v2_bp
    app.register_blueprint(api_v2_bp, url_prefix='/api/v2')

def register_websocket_handlers(app):
    """Registra manejadores de WebSocket."""
    
    @socketio.on('connect')
    def handle_connect():
        if not current_user.is_authenticated:
            return False
        join_room(f'user_{current_user.id}')
        
    @socketio.on('join_chat')
    def handle_join_chat(data):
        chat_id = data.get('chat_id')
        if chat_id and current_user.can_access_chat(chat_id):
            join_room(f'chat_{chat_id}')

def register_custom_decorators():
    """Registra decoradores personalizados para vistas."""
    
    def check_subscription(f):
        """Verifica si el usuario tiene una suscripción activa."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_active_subscription():
                flash('Esta función requiere una suscripción activa.', 'warning')
                return redirect(url_for('billing.plans'))
            return f(*args, **kwargs)
        return decorated_function
    
    def track_usage(category):
        """Registra el uso de funcionalidades específicas."""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if current_user.is_authenticated:
                    Usage.log(user_id=current_user.id, category=category)
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    return {
        'check_subscription': check_subscription,
        'track_usage': track_usage
    }

class APIVersionManager:
    """Gestor de versiones de API."""
    
    def __init__(self, app):
        self.app = app
        self.versions = {}
        self.deprecated = set()
    
    def register_version(self, version, blueprint, deprecated=False):
        """Registra una versión de la API."""
        self.versions[version] = blueprint
        if deprecated:
            self.deprecated.add(version)
        
        # Agregar headers para versiones deprecadas
        if deprecated:
            @blueprint.after_request
            def add_deprecated_header(response):
                response.headers['X-API-Deprecated'] = 'true'
                response.headers['X-API-Message'] = f'Version {version} is deprecated'
                return response

class ViewMetrics:
    """Recolector de métricas de vistas."""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'calls': 0,
            'errors': 0,
            'total_time': 0,
            'avg_time': 0
        })
    
    def record(self, view_name, duration, error=False):
        """Registra una llamada a una vista."""
        metrics = self.metrics[view_name]
        metrics['calls'] += 1
        metrics['total_time'] += duration
        metrics['avg_time'] = metrics['total_time'] / metrics['calls']
        if error:
            metrics['errors'] += 1
    
    def get_report(self):
        """Genera un reporte de métricas."""
        return {
            name: {
                'calls': m['calls'],
                'errors': m['errors'],
                'error_rate': (m['errors'] / m['calls'] * 100) if m['calls'] > 0 else 0,
                'avg_time': round(m['avg_time'], 3)
            }
            for name, m in self.metrics.items()
        }

def init_views(app):
    """Inicialización principal de vistas con todas las funcionalidades."""
    
    # Instanciar gestores principales
    view_manager = ViewManager(app)
    api_version_manager = APIVersionManager(app)
    view_metrics = ViewMetrics()
    
    # Registrar blueprints principales
    register_main_blueprints(app)
    register_api_routes(app)
    register_websocket_handlers(app)
    
    # Registrar funcionalidades adicionales
    custom_decorators = register_custom_decorators()
    
    # Configurar métricas y monitoreo
    configure_monitoring(app, view_metrics)
    
    # Devolver instancias importantes
    return {
        'view_manager': view_manager,
        'api_manager': api_version_manager,
        'metrics': view_metrics,
        'decorators': custom_decorators
    }