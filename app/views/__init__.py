"""
Views package para el ecosistema de emprendimiento.
Inicializa y configura todas las vistas web, blueprints, templates y componentes del frontend.

Este módulo proporciona:
- Registro centralizado de blueprints
- Configuración de templates con Jinja2
- Contexto global para templates
- Filtros y funciones personalizadas
- Integración con autenticación y permisos
- Manejo de errores de vistas
- Soporte para internacionalización (i18n)
- Analytics y tracking de vistas
- SEO y metadata dinámicos
- Sistema de temas y customización
- Compresión y optimización de assets

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, g, request, session, current_app, url_for, render_template
from flask_babel import Babel, get_locale, ngettext
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_assets import Environment, Bundle
from markupsafe import Markup
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
import os
import json
import logging
from functools import wraps
from urllib.parse import urlparse, urljoin
import re

# Importaciones locales - Blueprints principales
from .main import main_bp
from .auth import auth_bp
from .errors import errors_bp

# Blueprints por tipo de usuario
from .admin.dashboard import admin_dashboard_bp
from .admin.users import admin_users_bp
from .admin.entrepreneurs import admin_entrepreneurs_bp
from .admin.allies import admin_allies_bp
from .admin.organizations import admin_organizations_bp
from .admin.programs import admin_programs_bp
from .admin.analytics import admin_analytics_bp
from .admin.settings import admin_settings_bp

from .entrepreneur.dashboard import entrepreneur_dashboard_bp
from .entrepreneur.profile import entrepreneur_profile_bp
from .entrepreneur.projects import entrepreneur_projects_bp
from .entrepreneur.mentorship import entrepreneur_mentorship_bp
from .entrepreneur.calendar import entrepreneur_calendar_bp
from .entrepreneur.documents import entrepreneur_documents_bp
from .entrepreneur.tasks import entrepreneur_tasks_bp
from .entrepreneur.messages import entrepreneur_messages_bp
from .entrepreneur.progress import entrepreneur_progress_bp

from .ally.dashboard import ally_dashboard_bp
from .ally.profile import ally_profile_bp
from .ally.entrepreneurs import ally_entrepreneurs_bp
from .ally.mentorship import ally_mentorship_bp
from .ally.calendar import ally_calendar_bp
from .ally.hours import ally_hours_bp
from .ally.messages import ally_messages_bp
from .ally.reports import ally_reports_bp

from .client.dashboard import client_dashboard_bp
from .client.directory import client_directory_bp
from .client.impact import client_impact_bp
from .client.reports import client_reports_bp
from .client.analytics import client_analytics_bp

# Modelos necesarios
from app.models.user import User, UserType
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.organization import Organization
from app.models.program import Program

# Servicios y utilidades
from app.services.analytics_service import AnalyticsService
from app.utils.formatters import (
    format_currency, format_percentage, format_datetime,
    format_file_size, format_duration, truncate_text
)
from app.utils.string_utils import slugify, sanitize_html
from app.core.permissions import get_user_permissions

logger = logging.getLogger(__name__)

class ViewsManager:
    """Gestor centralizado de vistas y configuración."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.babel = None
        self.csrf = None
        self.compress = None
        self.assets = None
        self.analytics_service = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Inicializa el gestor de vistas con Flask."""
        self.app = app
        
        # Configurar extensiones
        self._setup_babel(app)
        self._setup_csrf(app) 
        self._setup_compression(app)
        self._setup_assets(app)
        
        # Registrar blueprints
        self._register_blueprints(app)
        
        # Configurar contexto de templates
        self._setup_template_context(app)
        
        # Configurar filtros de templates
        self._setup_template_filters(app)
        
        # Configurar funciones de templates
        self._setup_template_functions(app)
        
        # Configurar manejo de errores
        self._setup_error_handlers(app)
        
        # Configurar middleware de vistas
        self._setup_view_middleware(app)
    
    def _setup_babel(self, app: Flask):
        """Configura internacionalización."""
        self.babel = Babel(app)
        
        # Configurar idiomas soportados
        app.config.setdefault('LANGUAGES', {
            'es': 'Español',
            'en': 'English',
            'pt': 'Português'
        })
        
        @self.babel.localeselector
        def get_locale():
            """Determina el idioma del usuario."""
            # 1. Idioma explícito en URL o formulario
            if request.args.get('lang'):
                session['language'] = request.args.get('lang')
            
            # 2. Idioma guardado en sesión
            if 'language' in session:
                return session['language']
            
            # 3. Idioma del usuario autenticado
            if hasattr(g, 'current_user') and g.current_user:
                if hasattr(g.current_user, 'preferred_language'):
                    return g.current_user.preferred_language
            
            # 4. Mejor coincidencia con Accept-Language
            return request.accept_languages.best_match(
                app.config['LANGUAGES'].keys()) or 'es'
    
    def _setup_csrf(self, app: Flask):
        """Configura protección CSRF."""
        self.csrf = CSRFProtect(app)
        
        # Excluir APIs de CSRF (ya tienen otros mecanismos)
        @self.csrf.exempt
        def csrf_exempt_api():
            return request.path.startswith('/api/')
    
    def _setup_compression(self, app: Flask):
        """Configura compresión de respuestas."""
        self.compress = Compress(app)
        
        # Configurar tipos MIME para comprimir
        app.config.setdefault('COMPRESS_MIMETYPES', [
            'text/html', 'text/css', 'text/xml',
            'application/json', 'application/javascript',
            'text/javascript', 'application/xml'
        ])
    
    def _setup_assets(self, app: Flask):
        """Configura gestión de assets estáticos."""
        self.assets = Environment(app)
        
        # Configurar bundles CSS
        css_bundle = Bundle(
            'src/scss/main.scss',
            'src/scss/components/*.scss',
            'src/scss/layouts/*.scss',
            filters='scss,cssmin',
            output='dist/css/app.%(version)s.css'
        )
        
        # Configurar bundles JavaScript
        js_bundle = Bundle(
            'src/js/utils.js',
            'src/js/main.js',
            'src/js/components/*.js',
            filters='jsmin',
            output='dist/js/app.%(version)s.js'
        )
        
        # Registrar bundles
        self.assets.register('css_all', css_bundle)
        self.assets.register('js_all', js_bundle)
        
        # Bundle específico para dashboard
        dashboard_css = Bundle(
            'src/scss/dashboard.scss',
            'src/scss/charts.scss',
            filters='scss,cssmin',
            output='dist/css/dashboard.%(version)s.css'
        )
        
        dashboard_js = Bundle(
            'vendor/chart.js/chart.min.js',
            'src/js/dashboard.js',
            'src/js/charts.js',
            filters='jsmin',
            output='dist/js/dashboard.%(version)s.js'
        )
        
        self.assets.register('dashboard_css', dashboard_css)
        self.assets.register('dashboard_js', dashboard_js)
    
    def _register_blueprints(self, app: Flask):
        """Registra todos los blueprints de vistas."""
        
        # Blueprints principales
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(errors_bp)
        
        # Blueprints administrativos
        app.register_blueprint(admin_dashboard_bp, url_prefix='/admin')
        app.register_blueprint(admin_users_bp, url_prefix='/admin/users')
        app.register_blueprint(admin_entrepreneurs_bp, url_prefix='/admin/entrepreneurs')
        app.register_blueprint(admin_allies_bp, url_prefix='/admin/allies')
        app.register_blueprint(admin_organizations_bp, url_prefix='/admin/organizations')
        app.register_blueprint(admin_programs_bp, url_prefix='/admin/programs')
        app.register_blueprint(admin_analytics_bp, url_prefix='/admin/analytics')
        app.register_blueprint(admin_settings_bp, url_prefix='/admin/settings')
        
        # Blueprints para emprendedores
        app.register_blueprint(entrepreneur_dashboard_bp, url_prefix='/entrepreneur')
        app.register_blueprint(entrepreneur_profile_bp, url_prefix='/entrepreneur/profile')
        app.register_blueprint(entrepreneur_projects_bp, url_prefix='/entrepreneur/projects')
        app.register_blueprint(entrepreneur_mentorship_bp, url_prefix='/entrepreneur/mentorship')
        app.register_blueprint(entrepreneur_calendar_bp, url_prefix='/entrepreneur/calendar')
        app.register_blueprint(entrepreneur_documents_bp, url_prefix='/entrepreneur/documents')
        app.register_blueprint(entrepreneur_tasks_bp, url_prefix='/entrepreneur/tasks')
        app.register_blueprint(entrepreneur_messages_bp, url_prefix='/entrepreneur/messages')
        app.register_blueprint(entrepreneur_progress_bp, url_prefix='/entrepreneur/progress')
        
        # Blueprints para aliados/mentores
        app.register_blueprint(ally_dashboard_bp, url_prefix='/ally')
        app.register_blueprint(ally_profile_bp, url_prefix='/ally/profile')
        app.register_blueprint(ally_entrepreneurs_bp, url_prefix='/ally/entrepreneurs')
        app.register_blueprint(ally_mentorship_bp, url_prefix='/ally/mentorship')
        app.register_blueprint(ally_calendar_bp, url_prefix='/ally/calendar')
        app.register_blueprint(ally_hours_bp, url_prefix='/ally/hours')
        app.register_blueprint(ally_messages_bp, url_prefix='/ally/messages')
        app.register_blueprint(ally_reports_bp, url_prefix='/ally/reports')
        
        # Blueprints para clientes/stakeholders
        app.register_blueprint(client_dashboard_bp, url_prefix='/client')
        app.register_blueprint(client_directory_bp, url_prefix='/client/directory')
        app.register_blueprint(client_impact_bp, url_prefix='/client/impact')
        app.register_blueprint(client_reports_bp, url_prefix='/client/reports')
        app.register_blueprint(client_analytics_bp, url_prefix='/client/analytics')
        
        logger.info(f"Registered {len(app.blueprints)} blueprints")
    
    def _setup_template_context(self, app: Flask):
        """Configura contexto global para templates."""
        
        @app.context_processor
        def inject_global_context():
            """Inyecta variables globales en todos los templates."""
            context = {
                # Información de la aplicación
                'app_name': app.config.get('APP_NAME', 'Ecosistema Emprendimiento'),
                'app_version': app.config.get('APP_VERSION', '1.0.0'),
                'environment': app.config.get('ENVIRONMENT', 'production'),
                
                # Configuración de idiomas
                'current_language': get_locale(),
                'available_languages': app.config.get('LANGUAGES', {}),
                
                # Fecha y hora actual
                'now': datetime.utcnow(),
                'current_year': datetime.utcnow().year,
                
                # Configuración de tema
                'theme': session.get('theme', 'light'),
                'sidebar_collapsed': session.get('sidebar_collapsed', False),
                
                # URLs importantes
                'support_email': app.config.get('SUPPORT_EMAIL', 'soporte@ecosistema.com'),
                'documentation_url': app.config.get('DOCS_URL', '/docs'),
                
                # Feature flags
                'features': {
                    'analytics_enabled': app.config.get('ANALYTICS_ENABLED', True),
                    'chat_enabled': app.config.get('CHAT_ENABLED', True),
                    'notifications_enabled': app.config.get('NOTIFICATIONS_ENABLED', True),
                }
            }
            
            # Agregar información del usuario si está autenticado
            if hasattr(g, 'current_user') and g.current_user:
                context.update({
                    'current_user': g.current_user,
                    'user_permissions': get_user_permissions(g.current_user),
                    'user_notifications': self._get_user_notifications(g.current_user),
                    'user_stats': self._get_user_stats(g.current_user)
                })
            
            return context
        
        @app.context_processor 
        def inject_navigation():
            """Inyecta configuración de navegación."""
            return {
                'main_navigation': self._get_main_navigation(),
                'user_navigation': self._get_user_navigation(),
                'breadcrumbs': self._get_breadcrumbs()
            }
        
        @app.context_processor
        def inject_meta_tags():
            """Inyecta meta tags para SEO."""
            return {
                'meta_title': self._get_page_title(),
                'meta_description': self._get_page_description(),
                'meta_keywords': self._get_page_keywords(),
                'canonical_url': self._get_canonical_url(),
                'og_data': self._get_open_graph_data()
            }
    
    def _setup_template_filters(self, app: Flask):
        """Configura filtros personalizados para templates."""
        
        @app.template_filter('currency')
        def currency_filter(amount, currency='USD'):
            """Formato de moneda."""
            return format_currency(amount, currency)
        
        @app.template_filter('percentage')
        def percentage_filter(value, decimals=1):
            """Formato de porcentaje."""
            return format_percentage(value, decimals)
        
        @app.template_filter('datetime')
        def datetime_filter(dt, format='medium'):
            """Formato de fecha y hora."""
            return format_datetime(dt, format)
        
        @app.template_filter('timeago')
        def timeago_filter(dt):
            """Tiempo relativo (hace X tiempo)."""
            if not dt:
                return ''
            
            now = datetime.utcnow()
            diff = now - dt
            
            if diff.days > 0:
                return f"hace {diff.days} día{'s' if diff.days > 1 else ''}"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"hace {hours} hora{'s' if hours > 1 else ''}"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
            else:
                return "hace un momento"
        
        @app.template_filter('filesize')
        def filesize_filter(bytes_value):
            """Formato de tamaño de archivo."""
            return format_file_size(bytes_value)
        
        @app.template_filter('truncate_words')
        def truncate_words_filter(text, length=50, suffix='...'):
            """Trunca texto por palabras."""
            return truncate_text(text, length, suffix)
        
        @app.template_filter('slugify')
        def slugify_filter(text):
            """Convierte texto a slug."""
            return slugify(text)
        
        @app.template_filter('sanitize')
        def sanitize_filter(html):
            """Sanitiza HTML."""
            return Markup(sanitize_html(html))
        
        @app.template_filter('json')
        def json_filter(data):
            """Convierte a JSON para JavaScript."""
            return Markup(json.dumps(data))
        
        @app.template_filter('avatar_url')
        def avatar_url_filter(user, size=50):
            """URL de avatar del usuario."""
            if user and user.avatar_url:
                return user.avatar_url
            
            # Fallback a Gravatar o avatar por defecto
            import hashlib
            if user and user.email:
                email_hash = hashlib.md5(user.email.lower().encode()).hexdigest()
                return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"
            
            return url_for('static', filename='img/default-avatar.png')
    
    def _setup_template_functions(self, app: Flask):
        """Configura funciones globales para templates."""
        
        @app.template_global()
        def url_for_user_type(endpoint, **values):
            """URL específica según tipo de usuario."""
            if hasattr(g, 'current_user') and g.current_user:
                user_type = g.current_user.user_type
                
                if user_type == UserType.ADMIN:
                    prefix = 'admin.'
                elif user_type == UserType.ENTREPRENEUR:
                    prefix = 'entrepreneur.'
                elif user_type == UserType.ALLY:
                    prefix = 'ally.'
                elif user_type == UserType.CLIENT:
                    prefix = 'client.'
                else:
                    prefix = ''
                
                return url_for(f"{prefix}{endpoint}", **values)
            
            return url_for(endpoint, **values)
        
        @app.template_global()
        def has_permission(permission, resource=None):
            """Verifica permisos en templates."""
            if not hasattr(g, 'current_user') or not g.current_user:
                return False
            
            from app.core.permissions import check_permission
            return check_permission(g.current_user, permission, resource)
        
        @app.template_global()
        def is_user_type(*user_types):
            """Verifica tipo de usuario en templates."""
            if not hasattr(g, 'current_user') or not g.current_user:
                return False
            
            return g.current_user.user_type in user_types
        
        @app.template_global()
        def get_setting(key, default=None):
            """Obtiene configuración de la aplicación."""
            return app.config.get(key, default)
        
        @app.template_global()
        def render_field(field, **kwargs):
            """Renderiza campo de formulario con Bootstrap."""
            from markupsafe import Markup
            
            # Clases CSS base
            css_classes = kwargs.get('class', '')
            if field.errors:
                css_classes += ' is-invalid'
            
            # Renderizar campo
            field_html = field(class=css_classes, **kwargs)
            
            # Agregar mensajes de error
            if field.errors:
                error_html = ''.join([
                    f'<div class="invalid-feedback">{error}</div>'
                    for error in field.errors
                ])
                field_html += error_html
            
            return Markup(field_html)
        
        @app.template_global()
        def generate_csrf_token():
            """Genera token CSRF para forms AJAX."""
            from flask_wtf.csrf import generate_csrf
            return generate_csrf()
    
    def _setup_error_handlers(self, app: Flask):
        """Configura manejadores de errores globales."""
        
        @app.errorhandler(403)
        def forbidden_error(error):
            """Maneja errores 403 Forbidden."""
            self._track_error_page(403)
            return render_template('errors/403.html'), 403
        
        @app.errorhandler(404)
        def not_found_error(error):
            """Maneja errores 404 Not Found."""
            self._track_error_page(404)
            return render_template('errors/404.html'), 404
        
        @app.errorhandler(500)
        def internal_error(error):
            """Maneja errores 500 Internal Server Error."""
            self._track_error_page(500)
            return render_template('errors/500.html'), 500
        
        @app.errorhandler(503)
        def service_unavailable_error(error):
            """Maneja errores 503 Service Unavailable."""
            self._track_error_page(503)
            return render_template('errors/503.html'), 503
    
    def _setup_view_middleware(self, app: Flask):
        """Configura middleware específico para vistas."""
        
        @app.before_request
        def before_request():
            """Procesamiento antes de cada request."""
            # Registrar inicio de request para analytics
            g.request_start_time = datetime.utcnow()
            
            # Detectar dispositivo móvil
            g.is_mobile = 'Mobile' in request.user_agent.string
            
            # Configurar tema si se especifica
            if request.args.get('theme'):
                session['theme'] = request.args.get('theme')
        
        @app.after_request
        def after_request(response):
            """Procesamiento después de cada request."""
            # Agregar headers de seguridad
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # Trackear duración de request
            if hasattr(g, 'request_start_time'):
                duration = datetime.utcnow() - g.request_start_time
                self._track_page_view(duration)
            
            return response
    
    def _get_analytics_service(self):
        """Obtiene servicio de analytics de forma lazy."""
        if self.analytics_service is None:
            self.analytics_service = AnalyticsService()
        return self.analytics_service
    
    def _get_user_notifications(self, user: User) -> List[Dict]:
        """Obtiene notificaciones del usuario."""
        # Implementar lógica para obtener notificaciones
        return []
    
    def _get_user_stats(self, user: User) -> Dict:
        """Obtiene estadísticas del usuario."""
        stats = {
            'projects_count': 0,
            'messages_unread': 0,
            'tasks_pending': 0,
            'meetings_today': 0
        }
        
        if user.user_type == UserType.ENTREPRENEUR and hasattr(user, 'entrepreneur'):
            stats['projects_count'] = len(user.entrepreneur.projects)
            # Agregar más estadísticas específicas
        
        return stats
    
    def _get_main_navigation(self) -> List[Dict]:
        """Genera navegación principal."""
        nav_items = [
            {
                'title': 'Inicio',
                'url': url_for('main.index'),
                'icon': 'home',
                'active': request.endpoint == 'main.index'
            }
        ]
        
        # Navegación específica por tipo de usuario
        if hasattr(g, 'current_user') and g.current_user:
            user_type = g.current_user.user_type
            
            if user_type == UserType.ADMIN:
                nav_items.extend([
                    {
                        'title': 'Panel Admin',
                        'url': url_for('admin_dashboard.index'),
                        'icon': 'settings'
                    },
                    {
                        'title': 'Usuarios',
                        'url': url_for('admin_users.list_users'),
                        'icon': 'users'
                    },
                    {
                        'title': 'Analytics',
                        'url': url_for('admin_analytics.dashboard'),
                        'icon': 'bar-chart'
                    }
                ])
            
            elif user_type == UserType.ENTREPRENEUR:
                nav_items.extend([
                    {
                        'title': 'Dashboard',
                        'url': url_for('entrepreneur_dashboard.index'),
                        'icon': 'dashboard'
                    },
                    {
                        'title': 'Proyectos',
                        'url': url_for('entrepreneur_projects.list_projects'),
                        'icon': 'briefcase'
                    },
                    {
                        'title': 'Mentoría',
                        'url': url_for('entrepreneur_mentorship.sessions'),
                        'icon': 'user-check'
                    }
                ])
        
        return nav_items
    
    def _get_user_navigation(self) -> List[Dict]:
        """Genera navegación del usuario."""
        if not hasattr(g, 'current_user') or not g.current_user:
            return []
        
        return [
            {
                'title': 'Mi Perfil',
                'url': url_for_user_type('profile.view'),
                'icon': 'user'
            },
            {
                'title': 'Configuración',
                'url': url_for_user_type('profile.settings'),
                'icon': 'settings'
            },
            {
                'title': 'Cerrar Sesión',
                'url': url_for('auth.logout'),
                'icon': 'log-out'
            }
        ]
    
    def _get_breadcrumbs(self) -> List[Dict]:
        """Genera breadcrumbs automáticos."""
        breadcrumbs = []
        
        # Breadcrumb base
        breadcrumbs.append({
            'title': 'Inicio',
            'url': url_for('main.index')
        })
        
        # Agregar breadcrumbs específicos según la ruta
        if request.endpoint:
            parts = request.endpoint.split('.')
            
            if len(parts) >= 2:
                module = parts[0]
                action = parts[1] if len(parts) > 1 else 'index'
                
                # Mapeo de módulos a títulos
                module_titles = {
                    'admin_dashboard': 'Administración',
                    'entrepreneur_dashboard': 'Emprendedor',
                    'ally_dashboard': 'Mentor',
                    'client_dashboard': 'Cliente'
                }
                
                if module in module_titles:
                    breadcrumbs.append({
                        'title': module_titles[module],
                        'url': url_for(f"{module}.index") if action != 'index' else None
                    })
        
        return breadcrumbs
    
    def _get_page_title(self) -> str:
        """Genera título de página."""
        base_title = current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento')
        
        # Títulos específicos por endpoint
        titles = {
            'main.index': 'Inicio',
            'auth.login': 'Iniciar Sesión',
            'auth.register': 'Registro',
            'admin_dashboard.index': 'Panel de Administración',
            'entrepreneur_dashboard.index': 'Dashboard Emprendedor'
        }
        
        page_title = titles.get(request.endpoint, '')
        
        if page_title:
            return f"{page_title} - {base_title}"
        
        return base_title
    
    def _get_page_description(self) -> str:
        """Genera descripción de página para SEO."""
        descriptions = {
            'main.index': 'Plataforma integral para el desarrollo de emprendimientos y conexión con mentores.',
            'auth.login': 'Accede a tu cuenta en el ecosistema de emprendimiento.',
            'entrepreneur_dashboard.index': 'Panel de control para emprendedores con proyectos, métricas y mentoría.'
        }
        
        return descriptions.get(
            request.endpoint,
            'Ecosistema de emprendimiento con mentores, proyectos y recursos para emprendedores.'
        )
    
    def _get_page_keywords(self) -> str:
        """Genera keywords para SEO."""
        return 'emprendimiento, mentores, proyectos, startups, innovación, business'
    
    def _get_canonical_url(self) -> str:
        """Genera URL canónica."""
        return request.url
    
    def _get_open_graph_data(self) -> Dict:
        """Genera datos Open Graph para redes sociales."""
        return {
            'title': self._get_page_title(),
            'description': self._get_page_description(),
            'image': url_for('static', filename='img/og-image.png', _external=True),
            'url': self._get_canonical_url(),
            'type': 'website',
            'site_name': current_app.config.get('APP_NAME', 'Ecosistema Emprendimiento')
        }
    
    def _track_page_view(self, duration: timedelta):
        """Registra vista de página para analytics."""
        try:
            if current_app.config.get('ANALYTICS_ENABLED', True):
                analytics_service = self._get_analytics_service()
                analytics_service.track_page_view({
                    'page': request.endpoint,
                    'url': request.url,
                    'user_id': getattr(g, 'current_user_id', None),
                    'duration_ms': int(duration.total_seconds() * 1000),
                    'user_agent': request.user_agent.string,
                    'referrer': request.referrer,
                    'is_mobile': getattr(g, 'is_mobile', False)
                })
        except Exception as e:
            logger.error(f"Error tracking page view: {e}")
    
    def _track_error_page(self, status_code: int):
        """Registra páginas de error."""
        try:
            analytics_service = self._get_analytics_service()
            analytics_service.track_error_page({
                'status_code': status_code,
                'page': request.endpoint,
                'url': request.url,
                'user_id': getattr(g, 'current_user_id', None),
                'user_agent': request.user_agent.string,
                'referrer': request.referrer
            })
        except Exception as e:
            logger.error(f"Error tracking error page: {e}")

# Funciones de utilidad para templates
def url_for_user_type(endpoint, **values):
    """URL específica según tipo de usuario actual."""
    if hasattr(g, 'current_user') and g.current_user:
        user_type = g.current_user.user_type
        
        if user_type == UserType.ADMIN:
            prefix = 'admin_'
        elif user_type == UserType.ENTREPRENEUR:
            prefix = 'entrepreneur_'
        elif user_type == UserType.ALLY:
            prefix = 'ally_'
        elif user_type == UserType.CLIENT:
            prefix = 'client_'
        else:
            prefix = ''
        
        return url_for(f"{prefix}{endpoint}", **values)
    
    return url_for(endpoint, **values)

def create_views_manager(app: Flask = None) -> ViewsManager:
    """Factory function para crear el gestor de vistas."""
    return ViewsManager(app)

def configure_views_for_development(app: Flask):
    """Configuración específica para desarrollo."""
    app.config.update({
        'ASSETS_DEBUG': True,
        'COMPRESS_DEBUG': True,
        'SEND_FILE_MAX_AGE_DEFAULT': 0,
        'TEMPLATES_AUTO_RELOAD': True
    })

def configure_views_for_production(app: Flask):
    """Configuración específica para producción."""
    app.config.update({
        'ASSETS_DEBUG': False,
        'COMPRESS_DEBUG': False,
        'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # 1 año
        'TEMPLATES_AUTO_RELOAD': False
    })

# Instancia global del gestor
views_manager = ViewsManager()

# Funciones exportadas
__all__ = [
    'ViewsManager',
    'views_manager',
    'create_views_manager',
    'configure_views_for_development',
    'configure_views_for_production',
    'url_for_user_type'
]