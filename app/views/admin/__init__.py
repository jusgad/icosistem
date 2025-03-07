from flask import Blueprint, current_app
from flask_login import current_user
from functools import wraps
from app.utils.audit import log_admin_action
from app.utils.permissions import AdminPermissions
import logging

# Crear el blueprint para el panel de administración
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Configurar logger
logger = logging.getLogger(__name__)

# Decoradores personalizados para el panel de administración
def admin_required(f):
    """Decorador para rutas que requieren acceso de administrador."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """Decorador para verificar permisos específicos de administrador."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission):
                flash(f'No tienes permiso para realizar esta acción: {permission}', 'error')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Importar las vistas del módulo admin
from .dashboard import *
from .users import *
from .entrepreneurs import *
from .allies import *
from .settings import *
from .reports import *
from .audit import *

# Registro de funciones antes de cada request en el panel admin
@admin_bp.before_request
@admin_required
def before_admin_request():
    """Se ejecuta antes de cada request en el panel de administración."""
    # Registrar actividad administrativa
    log_admin_action(
        user_id=current_user.id,
        action='page_view',
        resource=request.endpoint,
        ip_address=request.remote_addr
    )
    
    # Verificar estado de mantenimiento
    if current_app.config.get('MAINTENANCE_MODE') and not current_user.is_super_admin:
        flash('El sistema está en modo mantenimiento.', 'warning')
        return redirect(url_for('main.index'))

# Contexto global para templates del panel admin
@admin_bp.context_processor
def admin_context():
    """Agrega variables de contexto global para templates admin."""
    return {
        'admin_menu': get_admin_menu(),
        'pending_actions': get_pending_actions(),
        'system_status': get_system_status(),
        'admin_permissions': AdminPermissions
    }

# Filtros personalizados para templates admin
@admin_bp.app_template_filter('format_status')
def format_status_filter(status):
    """Formatea estados para mostrar en el panel."""
    status_classes = {
        'active': 'success',
        'pending': 'warning',
        'inactive': 'danger',
        'suspended': 'secondary'
    }
    return status_classes.get(status, 'primary')

# Funciones auxiliares
def get_admin_menu():
    """Genera el menú de navegación del panel admin."""
    menu = [
        {
            'name': 'Dashboard',
            'url': url_for('admin.dashboard'),
            'icon': 'dashboard',
            'permission': None  # Visible para todos los admins
        },
        {
            'name': 'Usuarios',
            'url': url_for('admin.users'),
            'icon': 'users',
            'permission': 'manage_users',
            'submenu': [
                {
                    'name': 'Listado',
                    'url': url_for('admin.users')
                },
                {
                    'name': 'Crear Usuario',
                    'url': url_for('admin.create_user')
                },
                {
                    'name': 'Importar Usuarios',
                    'url': url_for('admin.import_users')
                }
            ]
        },
        {
            'name': 'Emprendedores',
            'url': url_for('admin.entrepreneurs'),
            'icon': 'briefcase',
            'permission': 'manage_entrepreneurs',
            'submenu': [
                {
                    'name': 'Listado',
                    'url': url_for('admin.entrepreneurs')
                },
                {
                    'name': 'Solicitudes',
                    'url': url_for('admin.entrepreneur_requests')
                },
                {
                    'name': 'Asignaciones',
                    'url': url_for('admin.entrepreneur_assignments')
                }
            ]
        },
        {
            'name': 'Aliados',
            'url': url_for('admin.allies'),
            'icon': 'handshake',
            'permission': 'manage_allies',
            'submenu': [
                {
                    'name': 'Listado',
                    'url': url_for('admin.allies')
                },
                {
                    'name': 'Evaluaciones',
                    'url': url_for('admin.ally_evaluations')
                }
            ]
        },
        {
            'name': 'Reportes',
            'url': url_for('admin.reports'),
            'icon': 'chart-bar',
            'permission': 'view_reports',
            'submenu': [
                {
                    'name': 'General',
                    'url': url_for('admin.general_report')
                },
                {
                    'name': 'Impacto',
                    'url': url_for('admin.impact_report')
                },
                {
                    'name': 'Financiero',
                    'url': url_for('admin.financial_report')
                }
            ]
        },
        {
            'name': 'Configuración',
            'url': url_for('admin.settings'),
            'icon': 'cog',
            'permission': 'manage_settings',
            'submenu': [
                {
                    'name': 'General',
                    'url': url_for('admin.general_settings')
                },
                {
                    'name': 'Email',
                    'url': url_for('admin.email_settings')
                },
                {
                    'name': 'Seguridad',
                    'url': url_for('admin.security_settings')
                }
            ]
        },
        {
            'name': 'Auditoría',
            'url': url_for('admin.audit'),
            'icon': 'shield',
            'permission': 'view_audit_log'
        }
    ]
    
    # Filtrar elementos según permisos del usuario
    return [
        item for item in menu
        if not item['permission'] or current_user.has_permission(item['permission'])
    ]

def get_pending_actions():
    """Obtiene acciones pendientes para el panel admin."""
    return {
        'pending_approvals': get_pending_approvals_count(),
        'pending_assignments': get_pending_assignments_count(),
        'pending_reports': get_pending_reports_count(),
        'system_alerts': get_system_alerts()
    }

def get_system_status():
    """Obtiene estado general del sistema."""
    return {
        'users_online': get_online_users_count(),
        'system_load': get_system_load(),
        'storage_usage': get_storage_usage(),
        'last_backup': get_last_backup_time(),
        'maintenance_mode': current_app.config.get('MAINTENANCE_MODE', False)
    }

# Configuración de manejo de errores para el panel admin
@admin_bp.errorhandler(403)
def admin_forbidden_error(error):
    """Manejo de error 403 en el panel admin."""
    return render_template('admin/error/403.html'), 403

@admin_bp.errorhandler(404)
def admin_not_found_error(error):
    """Manejo de error 404 en el panel admin."""
    return render_template('admin/error/404.html'), 404

@admin_bp.errorhandler(500)
def admin_internal_error(error):
    """Manejo de error 500 en el panel admin."""
    logger.error(f"Error interno en panel admin: {str(error)}")
    return render_template('admin/error/500.html'), 500

# Exportar elementos importantes
__all__ = [
    'admin_bp',
    'admin_required',
    'permission_required',
    'AdminPermissions'
]


"""
Módulo de Administración
=======================

Este módulo contiene todas las vistas y funcionalidades del panel de administración.
Incluye:

- Gestión de usuarios
- Gestión de emprendedores
- Gestión de aliados
- Reportes y análisis
- Configuración del sistema
- Auditoría y seguridad

Uso:
----
    from app.views.admin import admin_bp
    
    # En la aplicación principal
    app.register_blueprint(admin_bp)
"""

class AdminMetrics:
    """Clase para gestionar métricas del panel administrativo."""
    
    @staticmethod
    def get_user_metrics():
        """Obtiene métricas relacionadas con usuarios."""
        return {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'new_users_today': User.query.filter(
                User.created_at >= datetime.utcnow().date()
            ).count(),
            'user_types': {
                'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
                'allies': User.query.filter_by(role='ally').count(),
                'clients': User.query.filter_by(role='client').count(),
                'admins': User.query.filter_by(role='admin').count()
            }
        }
    
    @staticmethod
    def get_activity_metrics():
        """Obtiene métricas de actividad del sistema."""
        return {
            'logins_today': AuthLog.query.filter(
                AuthLog.action == 'login',
                AuthLog.created_at >= datetime.utcnow().date()
            ).count(),
            'active_sessions': Session.query.filter(
                Session.expires_at > datetime.utcnow()
            ).count(),
            'failed_logins': AuthLog.query.filter(
                AuthLog.action == 'failed_login',
                AuthLog.created_at >= datetime.utcnow().date()
            ).count()
        }

class AdminCache:
    """Gestión de caché para el panel administrativo."""
    
    def __init__(self, app):
        self.cache = Cache(app)
        self.default_timeout = 300  # 5 minutos
    
    def cached_stats(self, timeout=None):
        """Decorador para cachear estadísticas."""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                cache_key = f'admin_stats_{f.__name__}'
                rv = self.cache.get(cache_key)
                if rv is None:
                    rv = f(*args, **kwargs)
                    self.cache.set(cache_key, rv, 
                                 timeout=timeout or self.default_timeout)
                return rv
            return decorated_function
        return decorator
    
    def invalidate_stats(self):
        """Invalida todas las estadísticas cacheadas."""
        keys = self.cache.get('admin_stats_keys') or []
        for key in keys:
            self.cache.delete(key)

class AdminNotifications:
    """Sistema de notificaciones para administradores."""
    
    @staticmethod
    def send_alert(message, level='info', admin_ids=None):
        """Envía una alerta a los administradores."""
        notification = AdminNotification(
            message=message,
            level=level,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        
        if admin_ids:
            admins = User.query.filter(
                User.id.in_(admin_ids),
                User.role == 'admin'
            ).all()
        else:
            admins = User.query.filter_by(role='admin').all()
        
        for admin in admins:
            notification.recipients.append(admin)
        
        db.session.commit()
        
        # Enviar notificación en tiempo real si está configurado
        if current_app.config.get('ENABLE_REALTIME_NOTIFICATIONS'):
            socketio.emit('admin_notification', {
                'message': message,
                'level': level,
                'timestamp': notification.created_at.isoformat()
            }, room='admin_room')
    
    @staticmethod
    def get_pending_notifications(admin_id):
        """Obtiene notificaciones pendientes para un administrador."""
        return AdminNotification.query.filter(
            AdminNotification.recipients.any(id=admin_id),
            AdminNotification.read_at.is_(None)
        ).order_by(AdminNotification.created_at.desc()).all()

class AdminTaskScheduler:
    """Programador de tareas administrativas."""
    
    def __init__(self, app):
        self.scheduler = APScheduler()
        self.scheduler.init_app(app)
        self.scheduler.start()
        self.setup_tasks()
    
    def setup_tasks(self):
        """Configura tareas programadas."""
        # Backup diario
        self.scheduler.add_job(
            func=self.daily_backup,
            trigger='cron',
            hour=3,  # 3 AM
            id='daily_backup'
        )
        
        # Limpieza de logs
        self.scheduler.add_job(
            func=self.clean_old_logs,
            trigger='cron',
            day=1,  # Primer día del mes
            id='monthly_log_cleanup'
        )
        
        # Reportes automáticos
        self.scheduler.add_job(
            func=self.generate_monthly_report,
            trigger='cron',
            day=1,
            hour=5,
            id='monthly_report'
        )
    
    @staticmethod
    def daily_backup():
        """Realiza backup diario del sistema."""
        try:
            backup_path = create_backup()
            AdminNotifications.send_alert(
                f'Backup diario completado: {backup_path}',
                level='success'
            )
        except Exception as e:
            logger.error(f"Error en backup diario: {str(e)}")
            AdminNotifications.send_alert(
                'Error al realizar backup diario',
                level='error'
            )
    
    @staticmethod
    def clean_old_logs():
        """Limpia logs antiguos."""
        try:
            threshold = datetime.utcnow() - timedelta(days=90)
            deleted = AuthLog.query.filter(
                AuthLog.created_at < threshold
            ).delete()
            db.session.commit()
            AdminNotifications.send_alert(
                f'Se eliminaron {deleted} registros de log antiguos',
                level='info'
            )
        except Exception as e:
            logger.error(f"Error en limpieza de logs: {str(e)}")
            AdminNotifications.send_alert(
                'Error al limpiar logs antiguos',
                level='error'
            )

class AdminAPI:
    """API interna para el panel de administración."""
    
    @staticmethod
    @admin_bp.route('/api/stats')
    @admin_required
    def get_stats():
        """Endpoint para obtener estadísticas."""
        try:
            return jsonify({
                'users': AdminMetrics.get_user_metrics(),
                'activity': AdminMetrics.get_activity_metrics(),
                'system': get_system_status()
            })
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {str(e)}")
            return jsonify({'error': 'Error al obtener estadísticas'}), 500
    
    @staticmethod
    @admin_bp.route('/api/notifications/mark-read', methods=['POST'])
    @admin_required
    def mark_notifications_read():
        """Marca notificaciones como leídas."""
        try:
            notification_ids = request.json.get('notification_ids', [])
            notifications = AdminNotification.query.filter(
                AdminNotification.id.in_(notification_ids),
                AdminNotification.recipients.any(id=current_user.id)
            ).all()
            
            for notification in notifications:
                notification.read_at = datetime.utcnow()
            
            db.session.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Error al marcar notificaciones: {str(e)}")
            return jsonify({'error': 'Error al procesar la solicitud'}), 500

def init_admin(app):
    """Inicializa todas las funcionalidades del panel admin."""
    
    # Inicializar componentes
    admin_cache = AdminCache(app)
    admin_scheduler = AdminTaskScheduler(app)
    
    # Registrar extensiones en el contexto de la aplicación
    app.admin_cache = admin_cache
    app.admin_scheduler = admin_scheduler
    
    # Configurar WebSocket para notificaciones en tiempo real
    if app.config.get('ENABLE_REALTIME_NOTIFICATIONS'):
        @socketio.on('connect', namespace='/admin')
        def handle_admin_connect():
            if current_user.is_authenticated and current_user.role == 'admin':
                join_room('admin_room')
    
    return {
        'cache': admin_cache,
        'scheduler': admin_scheduler,
        'metrics': AdminMetrics,
        'notifications': AdminNotifications
    }