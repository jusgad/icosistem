"""
Context processors para templates del ecosistema de emprendimiento.
Proporciona variables globales para todos los templates.
"""

from flask import current_app, request, session, g
from flask_login import current_user
from datetime import datetime
import os


def register_context_processors(app):
    """
    Registra todos los context processors con la aplicación Flask.
    
    Args:
        app (Flask): Instancia de la aplicación Flask.
    """
    
    @app.context_processor
    def inject_global_vars():
        """Inyectar variables globales en todos los templates."""
        return {
            # Información de la aplicación
            'APP_NAME': current_app.config.get('APP_NAME', 'Ecosistema de Emprendimiento'),
            'APP_VERSION': getattr(current_app, 'version', '1.0.0'),
            'ENVIRONMENT': current_app.config.get('FLASK_ENV', 'production'),
            
            # Información del usuario actual
            'current_user': current_user,
            'user_role': current_user.role if current_user.is_authenticated else None,
            'user_name': current_user.full_name if current_user.is_authenticated else None,
            
            # Información de la request
            'current_url': request.url,
            'current_endpoint': request.endpoint,
            'request_method': request.method,
            
            # Información temporal
            'current_year': datetime.now().year,
            'current_date': datetime.now(),
            
            # Configuraciones para el frontend
            'DEBUG': current_app.debug,
            'CSRF_TOKEN': session.get('csrf_token', ''),
            
            # URLs útiles
            'static_url': current_app.static_url_path,
            
            # Funciones auxiliares
            'enumerate': enumerate,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
        }
    
    @app.context_processor
    def inject_user_stats():
        """Inyectar estadísticas del usuario actual."""
        if not current_user.is_authenticated:
            return {}
        
        stats = {}
        
        if current_user.role == 'entrepreneur':
            # Estadísticas para emprendedores
            from app.models.project import Project
            stats.update({
                'user_projects_count': Project.query.filter_by(entrepreneur_id=current_user.id).count(),
                'user_active_projects': Project.query.filter_by(
                    entrepreneur_id=current_user.id,
                    status='active'
                ).count()
            })
        
        elif current_user.role == 'ally':
            # Estadísticas para aliados/mentores
            from app.models.mentorship import Mentorship
            stats.update({
                'user_mentorships_count': Mentorship.query.filter_by(ally_id=current_user.id).count(),
                'user_active_mentorships': Mentorship.query.filter_by(
                    ally_id=current_user.id,
                    status='active'
                ).count()
            })
        
        return stats
    
    @app.context_processor
    def inject_navigation():
        """Inyectar información de navegación."""
        nav_items = []
        
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                nav_items = [
                    {'name': 'Dashboard', 'url': 'admin.dashboard'},
                    {'name': 'Usuarios', 'url': 'admin.users'},
                    {'name': 'Emprendedores', 'url': 'admin.entrepreneurs'},
                    {'name': 'Aliados', 'url': 'admin.allies'},
                    {'name': 'Analytics', 'url': 'admin.analytics'}
                ]
            elif current_user.role == 'entrepreneur':
                nav_items = [
                    {'name': 'Dashboard', 'url': 'entrepreneur.dashboard'},
                    {'name': 'Proyectos', 'url': 'entrepreneur.projects'},
                    {'name': 'Mentorías', 'url': 'entrepreneur.mentorship'},
                    {'name': 'Calendario', 'url': 'entrepreneur.calendar'},
                    {'name': 'Documentos', 'url': 'entrepreneur.documents'}
                ]
            elif current_user.role == 'ally':
                nav_items = [
                    {'name': 'Dashboard', 'url': 'ally.dashboard'},
                    {'name': 'Emprendedores', 'url': 'ally.entrepreneurs'},
                    {'name': 'Mentorías', 'url': 'ally.mentorship'},
                    {'name': 'Calendario', 'url': 'ally.calendar'},
                    {'name': 'Reportes', 'url': 'ally.reports'}
                ]
            elif current_user.role == 'client':
                nav_items = [
                    {'name': 'Dashboard', 'url': 'client.dashboard'},
                    {'name': 'Directorio', 'url': 'client.directory'},
                    {'name': 'Analytics', 'url': 'client.analytics'},
                    {'name': 'Reportes', 'url': 'client.reports'}
                ]
        
        return {
            'navigation_items': nav_items,
            'sidebar_collapsed': session.get('sidebar_collapsed', False)
        }
    
    @app.context_processor
    def inject_notifications():
        """Inyectar notificaciones del usuario."""
        if not current_user.is_authenticated:
            return {'notifications': [], 'unread_notifications': 0}
        
        from app.models.notification import Notification
        
        # Obtener notificaciones no leídas del usuario
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(Notification.created_at.desc()).limit(5).all()
        
        return {
            'notifications': notifications,
            'unread_notifications': len(notifications)
        }
    
    @app.context_processor
    def inject_system_status():
        """Inyectar estado del sistema."""
        return {
            'maintenance_mode': current_app.config.get('MAINTENANCE_MODE', False),
            'system_message': current_app.config.get('SYSTEM_MESSAGE', ''),
            'feature_flags': current_app.config.get('FEATURE_FLAGS', {})
        }
    
    @app.context_processor
    def inject_theme():
        """Inyectar configuración de tema."""
        user_theme = 'light'  # tema por defecto
        
        if current_user.is_authenticated and hasattr(current_user, 'theme_preference'):
            user_theme = current_user.theme_preference or 'light'
        elif 'theme' in session:
            user_theme = session['theme']
        
        return {
            'current_theme': user_theme,
            'available_themes': ['light', 'dark', 'high-contrast'],
            'theme_colors': {
                'primary': '#007bff',
                'secondary': '#6c757d',
                'success': '#28a745',
                'warning': '#ffc107',
                'danger': '#dc3545',
                'info': '#17a2b8'
            }
        }
    
    @app.context_processor
    def inject_permissions():
        """Inyectar permisos del usuario actual."""
        if not current_user.is_authenticated:
            return {'user_permissions': []}
        
        permissions = []
        role = current_user.role
        
        if role == 'admin':
            permissions = [
                'view_all_users', 'edit_users', 'delete_users',
                'view_analytics', 'export_data', 'system_settings'
            ]
        elif role == 'entrepreneur':
            permissions = [
                'create_project', 'edit_own_project', 'view_mentors',
                'book_sessions', 'upload_documents'
            ]
        elif role == 'ally':
            permissions = [
                'view_entrepreneurs', 'create_sessions', 'view_reports',
                'mentor_entrepreneurs'
            ]
        elif role == 'client':
            permissions = [
                'view_directory', 'view_analytics', 'generate_reports'
            ]
        
        return {'user_permissions': permissions}
    
    app.logger.info("Context processors registered successfully")