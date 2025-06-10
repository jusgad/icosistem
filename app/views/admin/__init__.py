"""
Admin Views Package para el ecosistema de emprendimiento.
Inicializa y configura todas las vistas administrativas, permisos, navegación y funcionalidades.

Este módulo proporciona:
- Registro centralizado de blueprints administrativos
- Sistema de permisos y autorización granular
- Navegación dinámica y menús contextuales
- Configuración específica para área administrativa
- Decoradores de seguridad y validación
- Utilidades comunes para operaciones admin
- Templates y contexto específico
- Auditoría y logging de acciones administrativas
- Filtros y funciones para templates admin
- Sistema de notificaciones para administradores

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Flask, Blueprint, g, request, session, current_app, url_for, redirect, flash
from flask_babel import _, get_locale
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from functools import wraps
import logging
from collections import defaultdict, OrderedDict

# Importaciones de blueprints administrativos
from .dashboard import admin_dashboard_bp
from .users import admin_users_bp
from .entrepreneurs import admin_entrepreneurs_bp
from .allies import admin_allies_bp
from .organizations import admin_organizations_bp
from .programs import admin_programs_bp
from .analytics import admin_analytics_bp
from .settings import admin_settings_bp

# Importaciones de modelos
from app.models.user import User, UserType, UserStatus
from app.models.admin_log import AdminLog, AdminAction, ActionSeverity
from app.models.permission import Permission, Role
from app.models.system_setting import SystemSetting
from app.models.notification import Notification

# Servicios y utilidades
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService
from app.core.permissions import require_permission, check_permission
from app.core.exceptions import AuthorizationException, ValidationException
from app.utils.formatters import format_datetime, format_currency, format_percentage
from app.utils.string_utils import get_client_ip, truncate_text
from app.utils.decorators import admin_required, log_admin_action
from app.extensions import db, cache

logger = logging.getLogger(__name__)

class AdminManager:
    """Gestor centralizado para funcionalidades administrativas."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.blueprints = OrderedDict()
        self.navigation_items = []
        self.quick_actions = []
        self.dashboard_widgets = []
        self.analytics_service = None
        self.audit_service = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Inicializa el gestor administrativo con Flask."""
        self.app = app
        
        # Registrar blueprints administrativos
        self._register_admin_blueprints(app)
        
        # Configurar contexto de templates
        self._setup_admin_context(app)
        
        # Configurar filtros de templates
        self._setup_admin_filters(app)
        
        # Configurar funciones globales
        self._setup_admin_functions(app)
        
        # Configurar navegación
        self._setup_navigation()
        
        # Configurar middleware administrativo
        self._setup_admin_middleware(app)
        
        # Configurar widgets del dashboard
        self._setup_dashboard_widgets()
        
        # Configurar acciones rápidas
        self._setup_quick_actions()
    
    def _register_admin_blueprints(self, app: Flask):
        """Registra todos los blueprints administrativos."""
        
        # Definir blueprints con metadatos
        admin_blueprints = [
            {
                'blueprint': admin_dashboard_bp,
                'name': 'admin_dashboard',
                'title': _('Dashboard'),
                'icon': 'home',
                'order': 1,
                'permission': 'admin.dashboard.view'
            },
            {
                'blueprint': admin_users_bp,
                'name': 'admin_users',
                'title': _('Usuarios'),
                'icon': 'users',
                'order': 2,
                'permission': 'admin.users.view'
            },
            {
                'blueprint': admin_entrepreneurs_bp,
                'name': 'admin_entrepreneurs',
                'title': _('Emprendedores'),
                'icon': 'briefcase',
                'order': 3,
                'permission': 'admin.entrepreneurs.view'
            },
            {
                'blueprint': admin_allies_bp,
                'name': 'admin_allies',
                'title': _('Mentores'),
                'icon': 'user-check',
                'order': 4,
                'permission': 'admin.allies.view'
            },
            {
                'blueprint': admin_organizations_bp,
                'name': 'admin_organizations',
                'title': _('Organizaciones'),
                'icon': 'building',
                'order': 5,
                'permission': 'admin.organizations.view'
            },
            {
                'blueprint': admin_programs_bp,
                'name': 'admin_programs',
                'title': _('Programas'),
                'icon': 'layers',
                'order': 6,
                'permission': 'admin.programs.view'
            },
            {
                'blueprint': admin_analytics_bp,
                'name': 'admin_analytics',
                'title': _('Analytics'),
                'icon': 'bar-chart',
                'order': 7,
                'permission': 'admin.analytics.view'
            },
            {
                'blueprint': admin_settings_bp,
                'name': 'admin_settings',
                'title': _('Configuración'),
                'icon': 'settings',
                'order': 8,
                'permission': 'admin.settings.view'
            }
        ]
        
        # Registrar blueprints y guardar metadatos
        for bp_info in admin_blueprints:
            app.register_blueprint(bp_info['blueprint'])
            self.blueprints[bp_info['name']] = bp_info
            
        logger.info(f"Registered {len(admin_blueprints)} admin blueprints")
    
    def _setup_admin_context(self, app: Flask):
        """Configura contexto específico para templates administrativos."""
        
        @app.context_processor
        def inject_admin_context():
            """Inyecta contexto administrativo en templates."""
            if not self._is_admin_area():
                return {}
            
            current_user = getattr(g, 'current_user', None)
            if not current_user or not current_user.is_admin():
                return {}
            
            return {
                # Navegación administrativa
                'admin_navigation': self._get_admin_navigation(current_user),
                'admin_breadcrumbs': self._get_admin_breadcrumbs(),
                'admin_quick_actions': self._get_admin_quick_actions(current_user),
                
                # Información del sistema
                'admin_stats': self._get_admin_stats(),
                'system_health': self._get_system_health(),
                'pending_notifications': self._get_pending_notifications(current_user),
                
                # Configuración administrativa
                'admin_config': {
                    'theme': session.get('admin_theme', 'default'),
                    'sidebar_collapsed': session.get('admin_sidebar_collapsed', False),
                    'items_per_page': session.get('admin_items_per_page', 25),
                    'timezone': current_user.timezone or 'UTC'
                },
                
                # Permisos y capacidades
                'admin_permissions': self._get_user_admin_permissions(current_user),
                'can_impersonate': check_permission(current_user, 'admin.users.impersonate'),
                'can_access_logs': check_permission(current_user, 'admin.logs.view'),
                
                # Dashboard widgets
                'dashboard_widgets': self._get_dashboard_widgets(current_user),
                
                # Información de auditoría
                'last_admin_login': self._get_last_admin_login(current_user),
                'admin_session_duration': self._get_admin_session_duration(),
                
                # URLs importantes
                'admin_urls': {
                    'dashboard': url_for('admin_dashboard.index'),
                    'profile': url_for('admin_dashboard.profile'),
                    'logout': url_for('auth.logout'),
                    'help': url_for('admin_dashboard.help'),
                    'system_logs': url_for('admin_analytics.system_logs')
                }
            }
    
    def _setup_admin_filters(self, app: Flask):
        """Configura filtros específicos para templates administrativos."""
        
        @app.template_filter('admin_status_badge')
        def admin_status_badge_filter(status):
            """Genera badge HTML para estados."""
            badge_classes = {
                UserStatus.ACTIVE: 'badge-success',
                UserStatus.INACTIVE: 'badge-secondary', 
                UserStatus.PENDING_VERIFICATION: 'badge-warning',
                UserStatus.SUSPENDED: 'badge-danger',
                UserStatus.DELETED: 'badge-dark'
            }
            
            status_text = {
                UserStatus.ACTIVE: _('Activo'),
                UserStatus.INACTIVE: _('Inactivo'),
                UserStatus.PENDING_VERIFICATION: _('Pendiente'),
                UserStatus.SUSPENDED: _('Suspendido'),
                UserStatus.DELETED: _('Eliminado')
            }
            
            badge_class = badge_classes.get(status, 'badge-secondary')
            text = status_text.get(status, str(status))
            
            return f'<span class="badge {badge_class}">{text}</span>'
        
        @app.template_filter('admin_user_type_icon')
        def admin_user_type_icon_filter(user_type):
            """Genera icono para tipo de usuario."""
            icons = {
                UserType.ADMIN: 'shield',
                UserType.ENTREPRENEUR: 'briefcase',
                UserType.ALLY: 'user-check',
                UserType.CLIENT: 'users'
            }
            return icons.get(user_type, 'user')
        
        @app.template_filter('admin_format_action')
        def admin_format_action_filter(action):
            """Formatea acciones administrativas."""
            action_texts = {
                AdminAction.CREATE: _('Crear'),
                AdminAction.READ: _('Ver'),
                AdminAction.UPDATE: _('Actualizar'),
                AdminAction.DELETE: _('Eliminar'),
                AdminAction.BULK_UPDATE: _('Actualización masiva'),
                AdminAction.EXPORT: _('Exportar'),
                AdminAction.IMPORT: _('Importar'),
                AdminAction.LOGIN: _('Iniciar sesión'),
                AdminAction.LOGOUT: _('Cerrar sesión')
            }
            return action_texts.get(action, str(action))
        
        @app.template_filter('admin_permission_level')
        def admin_permission_level_filter(permission_name):
            """Determina nivel de permiso basado en el nombre."""
            if 'create' in permission_name or 'delete' in permission_name:
                return 'high'
            elif 'update' in permission_name or 'manage' in permission_name:
                return 'medium'
            else:
                return 'low'
        
        @app.template_filter('admin_highlight_search')
        def admin_highlight_search_filter(text, search_term):
            """Resalta término de búsqueda en texto."""
            if not search_term or not text:
                return text
            
            import re
            pattern = re.compile(re.escape(search_term), re.IGNORECASE)
            return pattern.sub(f'<mark>\\g<0></mark>', str(text))
    
    def _setup_admin_functions(self, app: Flask):
        """Configura funciones globales para templates administrativos."""
        
        @app.template_global('has_admin_permission')
        def has_admin_permission(permission_name, resource=None):
            """Verifica permisos administrativos en templates."""
            current_user = getattr(g, 'current_user', None)
            if not current_user or not current_user.is_admin():
                return False
            
            return check_permission(current_user, permission_name, resource)
        
        @app.template_global('get_admin_setting')
        def get_admin_setting(key, default=None):
            """Obtiene configuración del sistema."""
            try:
                setting = SystemSetting.query.filter_by(key=key).first()
                return setting.value if setting else default
            except Exception:
                return default
        
        @app.template_global('admin_url_for')
        def admin_url_for(endpoint, **values):
            """URL helper específico para área administrativa."""
            if not endpoint.startswith('admin_'):
                endpoint = f'admin_{endpoint}'
            return url_for(endpoint, **values)
        
        @app.template_global('format_admin_number')
        def format_admin_number(number, decimal_places=0):
            """Formatea números para display administrativo."""
            if number is None:
                return '-'
            
            if number >= 1000000:
                return f"{number/1000000:.{decimal_places}f}M"
            elif number >= 1000:
                return f"{number/1000:.{decimal_places}f}K"
            else:
                return f"{number:.{decimal_places}f}"
        
        @app.template_global('get_model_display_name')
        def get_model_display_name(obj):
            """Obtiene nombre para mostrar de un modelo."""
            if hasattr(obj, 'get_display_name'):
                return obj.get_display_name()
            elif hasattr(obj, 'name'):
                return obj.name
            elif hasattr(obj, 'title'):
                return obj.title
            elif hasattr(obj, 'email'):
                return obj.email
            else:
                return str(obj)
    
    def _setup_navigation(self):
        """Configura navegación administrativa."""
        self.navigation_items = [
            {
                'id': 'dashboard',
                'title': _('Dashboard'),
                'icon': 'home',
                'url': 'admin_dashboard.index',
                'permission': 'admin.dashboard.view',
                'order': 1
            },
            {
                'id': 'users',
                'title': _('Gestión de Usuarios'),
                'icon': 'users',
                'permission': 'admin.users.view',
                'order': 2,
                'children': [
                    {
                        'title': _('Todos los Usuarios'),
                        'url': 'admin_users.list_users',
                        'permission': 'admin.users.view'
                    },
                    {
                        'title': _('Emprendedores'),
                        'url': 'admin_entrepreneurs.list',
                        'permission': 'admin.entrepreneurs.view'
                    },
                    {
                        'title': _('Mentores'),
                        'url': 'admin_allies.list',
                        'permission': 'admin.allies.view'
                    },
                    {
                        'title': _('Crear Usuario'),
                        'url': 'admin_users.create',
                        'permission': 'admin.users.create'
                    }
                ]
            },
            {
                'id': 'content',
                'title': _('Gestión de Contenido'),
                'icon': 'layers',
                'permission': 'admin.content.view',
                'order': 3,
                'children': [
                    {
                        'title': _('Organizaciones'),
                        'url': 'admin_organizations.list',
                        'permission': 'admin.organizations.view'
                    },
                    {
                        'title': _('Programas'),
                        'url': 'admin_programs.list',
                        'permission': 'admin.programs.view'
                    }
                ]
            },
            {
                'id': 'analytics',
                'title': _('Analytics'),
                'icon': 'bar-chart',
                'url': 'admin_analytics.dashboard',
                'permission': 'admin.analytics.view',
                'order': 4
            },
            {
                'id': 'system',
                'title': _('Sistema'),
                'icon': 'settings',
                'permission': 'admin.system.view',
                'order': 5,
                'children': [
                    {
                        'title': _('Configuración'),
                        'url': 'admin_settings.general',
                        'permission': 'admin.settings.view'
                    },
                    {
                        'title': _('Logs del Sistema'),
                        'url': 'admin_analytics.system_logs',
                        'permission': 'admin.logs.view'
                    },
                    {
                        'title': _('Respaldos'),
                        'url': 'admin_settings.backups',
                        'permission': 'admin.system.backup'
                    }
                ]
            }
        ]
    
    def _setup_admin_middleware(self, app: Flask):
        """Configura middleware específico para área administrativa."""
        
        @app.before_request
        def admin_before_request():
            """Procesamiento antes de requests administrativos."""
            if not self._is_admin_area():
                return
            
            # Verificar autenticación y permisos administrativos
            current_user = getattr(g, 'current_user', None)
            
            if not current_user:
                flash(_('Debes iniciar sesión para acceder al área administrativa.'), 'error')
                return redirect(url_for('auth.login'))
            
            if not current_user.is_admin():
                flash(_('No tienes permisos para acceder al área administrativa.'), 'error')
                return redirect(url_for('main.index'))
            
            # Verificar si la cuenta está activa
            if current_user.status != UserStatus.ACTIVE:
                flash(_('Tu cuenta no está activa.'), 'error')
                return redirect(url_for('auth.logout'))
            
            # Establecer configuraciones de sesión administrativa
            if 'admin_session_start' not in session:
                session['admin_session_start'] = datetime.utcnow().isoformat()
                self._log_admin_access(current_user, 'admin_area_entered')
            
            # Verificar timeout de sesión administrativa (opcional)
            admin_timeout = current_app.config.get('ADMIN_SESSION_TIMEOUT_MINUTES', 120)
            if admin_timeout:
                last_activity = session.get('admin_last_activity')
                if last_activity:
                    last_activity_dt = datetime.fromisoformat(last_activity)
                    if datetime.utcnow() - last_activity_dt > timedelta(minutes=admin_timeout):
                        session.clear()
                        flash(_('Sesión administrativa expirada por inactividad.'), 'warning')
                        return redirect(url_for('auth.login'))
            
            session['admin_last_activity'] = datetime.utcnow().isoformat()
        
        @app.after_request
        def admin_after_request(response):
            """Procesamiento después de requests administrativos."""
            if not self._is_admin_area():
                return response
            
            # Agregar headers de seguridad específicos para admin
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            
            return response
    
    def _setup_dashboard_widgets(self):
        """Configura widgets para el dashboard administrativo."""
        self.dashboard_widgets = [
            {
                'id': 'users_overview',
                'title': _('Resumen de Usuarios'),
                'type': 'stats',
                'permission': 'admin.users.view',
                'order': 1,
                'size': 'col-md-3'
            },
            {
                'id': 'projects_overview',
                'title': _('Proyectos Activos'),
                'type': 'stats',
                'permission': 'admin.projects.view',
                'order': 2,
                'size': 'col-md-3'
            },
            {
                'id': 'recent_activity',
                'title': _('Actividad Reciente'),
                'type': 'list',
                'permission': 'admin.logs.view',
                'order': 3,
                'size': 'col-md-6'
            },
            {
                'id': 'system_health',
                'title': _('Estado del Sistema'),
                'type': 'status',
                'permission': 'admin.system.view',
                'order': 4,
                'size': 'col-md-6'
            }
        ]
    
    def _setup_quick_actions(self):
        """Configura acciones rápidas administrativas."""
        self.quick_actions = [
            {
                'id': 'create_user',
                'title': _('Crear Usuario'),
                'icon': 'user-plus',
                'url': 'admin_users.create',
                'permission': 'admin.users.create',
                'class': 'btn-primary'
            },
            {
                'id': 'export_data',
                'title': _('Exportar Datos'),
                'icon': 'download',
                'url': 'admin_analytics.export',
                'permission': 'admin.data.export',
                'class': 'btn-success'
            },
            {
                'id': 'system_backup',
                'title': _('Crear Respaldo'),
                'icon': 'archive',
                'url': 'admin_settings.create_backup',
                'permission': 'admin.system.backup',
                'class': 'btn-warning'
            },
            {
                'id': 'view_logs',
                'title': _('Ver Logs'),
                'icon': 'file-text',
                'url': 'admin_analytics.system_logs',
                'permission': 'admin.logs.view',
                'class': 'btn-info'
            }
        ]
    
    def _is_admin_area(self) -> bool:
        """Verifica si el request actual es para área administrativa."""
        return (request.endpoint and 
                (request.endpoint.startswith('admin_') or 
                 request.path.startswith('/admin')))
    
    def _get_admin_navigation(self, user: User) -> List[Dict]:
        """Obtiene navegación filtrada por permisos del usuario."""
        filtered_nav = []
        
        for item in self.navigation_items:
            if item.get('permission') and not check_permission(user, item['permission']):
                continue
            
            nav_item = item.copy()
            
            # Filtrar children por permisos
            if 'children' in nav_item:
                filtered_children = []
                for child in nav_item['children']:
                    if child.get('permission') and not check_permission(user, child['permission']):
                        continue
                    filtered_children.append(child)
                
                nav_item['children'] = filtered_children
                
                # Si no hay children válidos, omitir el item padre
                if not filtered_children:
                    continue
            
            # Determinar si está activo
            nav_item['active'] = self._is_nav_item_active(nav_item)
            
            filtered_nav.append(nav_item)
        
        return sorted(filtered_nav, key=lambda x: x.get('order', 999))
    
    def _is_nav_item_active(self, nav_item: Dict) -> bool:
        """Determina si un item de navegación está activo."""
        current_endpoint = request.endpoint
        
        if nav_item.get('url'):
            return current_endpoint == nav_item['url']
        
        if nav_item.get('children'):
            for child in nav_item['children']:
                if child.get('url') == current_endpoint:
                    return True
        
        return False
    
    def _get_admin_breadcrumbs(self) -> List[Dict]:
        """Genera breadcrumbs automáticos para área administrativa."""
        breadcrumbs = [
            {'title': _('Admin'), 'url': url_for('admin_dashboard.index')}
        ]
        
        current_endpoint = request.endpoint
        if not current_endpoint:
            return breadcrumbs
        
        # Mapeo de endpoints a breadcrumbs
        breadcrumb_map = {
            'admin_users.list_users': [
                {'title': _('Usuarios'), 'url': url_for('admin_users.list_users')}
            ],
            'admin_users.view': [
                {'title': _('Usuarios'), 'url': url_for('admin_users.list_users')},
                {'title': _('Ver Usuario'), 'url': None}
            ],
            'admin_entrepreneurs.list': [
                {'title': _('Emprendedores'), 'url': url_for('admin_entrepreneurs.list')}
            ],
            'admin_analytics.dashboard': [
                {'title': _('Analytics'), 'url': url_for('admin_analytics.dashboard')}
            ]
        }
        
        if current_endpoint in breadcrumb_map:
            breadcrumbs.extend(breadcrumb_map[current_endpoint])
        
        return breadcrumbs
    
    def _get_admin_quick_actions(self, user: User) -> List[Dict]:
        """Obtiene acciones rápidas filtradas por permisos."""
        filtered_actions = []
        
        for action in self.quick_actions:
            if action.get('permission') and not check_permission(user, action['permission']):
                continue
            
            action_copy = action.copy()
            try:
                action_copy['url'] = url_for(action['url'])
            except Exception:
                continue  # Skip si la URL no es válida
            
            filtered_actions.append(action_copy)
        
        return filtered_actions
    
    def _get_admin_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas básicas del sistema."""
        try:
            return {
                'total_users': User.query.filter(User.status != UserStatus.DELETED).count(),
                'active_users': User.query.filter(User.status == UserStatus.ACTIVE).count(),
                'pending_users': User.query.filter(User.status == UserStatus.PENDING_VERIFICATION).count(),
                'total_entrepreneurs': User.query.filter(User.user_type == UserType.ENTREPRENEUR).count(),
                'total_allies': User.query.filter(User.user_type == UserType.ALLY).count(),
                'new_users_today': User.query.filter(
                    User.created_at >= datetime.utcnow().date()
                ).count()
            }
        except Exception as e:
            logger.error(f"Error getting admin stats: {str(e)}")
            return {}
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Obtiene estado de salud del sistema."""
        try:
            health = {
                'status': 'healthy',
                'database': 'connected',
                'cache': 'connected',
                'disk_usage': 0,
                'memory_usage': 0
            }
            
            # Verificar conexión a base de datos
            try:
                db.session.execute('SELECT 1')
                health['database'] = 'connected'
            except Exception:
                health['database'] = 'error'
                health['status'] = 'warning'
            
            # Verificar cache
            try:
                cache.get('health_check')
                health['cache'] = 'connected'
            except Exception:
                health['cache'] = 'error'
                health['status'] = 'warning'
            
            return health
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_pending_notifications(self, user: User) -> List[Dict]:
        """Obtiene notificaciones pendientes para el administrador."""
        try:
            notifications = Notification.query.filter_by(
                user_id=user.id,
                is_read=False
            ).order_by(Notification.created_at.desc()).limit(5).all()
            
            return [
                {
                    'id': notif.id,
                    'title': notif.title,
                    'message': truncate_text(notif.message, 100),
                    'created_at': notif.created_at,
                    'type': notif.type.value if notif.type else 'info'
                }
                for notif in notifications
            ]
        except Exception as e:
            logger.error(f"Error getting pending notifications: {str(e)}")
            return []
    
    def _get_user_admin_permissions(self, user: User) -> List[str]:
        """Obtiene lista de permisos administrativos del usuario."""
        try:
            permissions = []
            for permission in user.get_permissions():
                if permission.name.startswith('admin.'):
                    permissions.append(permission.name)
            return permissions
        except Exception:
            return []
    
    def _get_dashboard_widgets(self, user: User) -> List[Dict]:
        """Obtiene widgets filtrados por permisos para el dashboard."""
        filtered_widgets = []
        
        for widget in self.dashboard_widgets:
            if widget.get('permission') and not check_permission(user, widget['permission']):
                continue
            
            filtered_widgets.append(widget)
        
        return sorted(filtered_widgets, key=lambda x: x.get('order', 999))
    
    def _get_last_admin_login(self, user: User) -> Optional[datetime]:
        """Obtiene fecha del último login administrativo."""
        try:
            last_log = AdminLog.query.filter_by(
                admin_id=user.id,
                action=AdminAction.LOGIN
            ).order_by(AdminLog.created_at.desc()).first()
            
            return last_log.created_at if last_log else None
        except Exception:
            return None
    
    def _get_admin_session_duration(self) -> Optional[timedelta]:
        """Obtiene duración de la sesión administrativa actual."""
        start_time = session.get('admin_session_start')
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
            return datetime.utcnow() - start_dt
        return None
    
    def _log_admin_access(self, user: User, action: str):
        """Registra acceso al área administrativa."""
        try:
            audit_service = AuditService()
            audit_service.log_admin_action(
                admin_id=user.id,
                action=action,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string
            )
        except Exception as e:
            logger.error(f"Error logging admin access: {str(e)}")

# Decoradores específicos para área administrativa
def admin_required(permission: str = None):
    """
    Decorador que requiere acceso administrativo y opcionalmente un permiso específico.
    
    Args:
        permission: Permiso específico requerido (opcional)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = getattr(g, 'current_user', None)
            
            if not current_user:
                flash(_('Debes iniciar sesión para acceder al área administrativa.'), 'error')
                return redirect(url_for('auth.login'))
            
            if not current_user.is_admin():
                raise AuthorizationException(_('Acceso administrativo requerido'))
            
            if permission and not check_permission(current_user, permission):
                raise AuthorizationException(f'Permiso requerido: {permission}')
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_admin_action(action: AdminAction, severity: ActionSeverity = ActionSeverity.MEDIUM):
    """
    Decorador para logging automático de acciones administrativas.
    
    Args:
        action: Tipo de acción administrativa
        severity: Severidad de la acción
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = getattr(g, 'current_user', None)
            
            # Ejecutar función
            result = f(*args, **kwargs)
            
            # Log de la acción
            try:
                if current_user:
                    admin_log = AdminLog(
                        admin_id=current_user.id,
                        action=action,
                        severity=severity,
                        endpoint=request.endpoint,
                        ip_address=get_client_ip(),
                        user_agent=request.user_agent.string,
                        request_data={
                            'args': dict(request.args),
                            'form': dict(request.form) if request.form else None,
                            'json': request.get_json(silent=True)
                        }
                    )
                    db.session.add(admin_log)
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error logging admin action: {str(e)}")
            
            return result
        return decorated_function
    return decorator

# Funciones de utilidad
def get_admin_navigation() -> List[Dict]:
    """Obtiene navegación administrativa para el usuario actual."""
    current_user = getattr(g, 'current_user', None)
    if not current_user or not current_user.is_admin():
        return []
    
    return admin_manager._get_admin_navigation(current_user)

def get_admin_breadcrumbs() -> List[Dict]:
    """Obtiene breadcrumbs para la página actual."""
    return admin_manager._get_admin_breadcrumbs()

def check_admin_permission(permission: str, resource: Any = None) -> bool:
    """Verifica permiso administrativo para el usuario actual."""
    current_user = getattr(g, 'current_user', None)
    if not current_user or not current_user.is_admin():
        return False
    
    return check_permission(current_user, permission, resource)

def get_admin_setting(key: str, default: Any = None) -> Any:
    """Obtiene configuración del sistema."""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        return setting.value if setting else default
    except Exception:
        return default

def set_admin_setting(key: str, value: Any, description: str = None) -> bool:
    """Establece configuración del sistema."""
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSetting(
                key=key,
                value=value,
                description=description
            )
            db.session.add(setting)
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error setting admin setting {key}: {str(e)}")
        db.session.rollback()
        return False

# Instancia global del gestor administrativo
admin_manager = AdminManager()

# Configuraciones específicas por entorno
def configure_admin_for_development():
    """Configuración administrativa para desarrollo."""
    return {
        'ADMIN_SESSION_TIMEOUT_MINUTES': None,  # Sin timeout en desarrollo
        'ADMIN_DEBUG_MODE': True,
        'ADMIN_SHOW_QUERY_COUNT': True,
        'ADMIN_AUTO_RELOAD_TEMPLATES': True
    }

def configure_admin_for_production():
    """Configuración administrativa para producción."""
    return {
        'ADMIN_SESSION_TIMEOUT_MINUTES': 120,  # 2 horas
        'ADMIN_DEBUG_MODE': False,
        'ADMIN_SHOW_QUERY_COUNT': False,
        'ADMIN_AUTO_RELOAD_TEMPLATES': False,
        'ADMIN_REQUIRE_2FA': True,
        'ADMIN_IP_WHITELIST': [],  # Lista de IPs permitidas
        'ADMIN_AUDIT_ALL_ACTIONS': True
    }

# Exportaciones
__all__ = [
    'admin_manager',
    'AdminManager',
    'admin_required',
    'log_admin_action',
    'get_admin_navigation',
    'get_admin_breadcrumbs', 
    'check_admin_permission',
    'get_admin_setting',
    'set_admin_setting',
    'configure_admin_for_development',
    'configure_admin_for_production',
    
    # Blueprints administrativos
    'admin_dashboard_bp',
    'admin_users_bp',
    'admin_entrepreneurs_bp',
    'admin_allies_bp',
    'admin_organizations_bp',
    'admin_programs_bp',
    'admin_analytics_bp',
    'admin_settings_bp'
]