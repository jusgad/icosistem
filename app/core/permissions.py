"""
Sistema de permisos y autorización para el ecosistema de emprendimiento.
Este módulo maneja todos los aspectos de control de acceso basado en roles (RBAC).
"""

import logging
from functools import wraps
from typing import List, Dict, Any, Optional, Callable, Union
from flask import current_app, request, jsonify, abort, redirect, url_for, flash
from flask_login import current_user
from flask_principal import Principal, Permission, RoleNeed, UserNeed, identity_loaded

from .constants import (
    USER_ROLES, ADMIN_ROLE, ENTREPRENEUR_ROLE, ALLY_ROLE, CLIENT_ROLE,
    ADMIN_ROLES, MENTOR_ROLES, MENTEE_ROLES
)
from .exceptions import AuthorizationError, UserNotFoundError
from .security import log_security_event

# Configurar logger de permisos
permissions_logger = logging.getLogger('ecosistema.permissions')


# ====================================
# DEFINICIÓN DE PERMISOS
# ====================================

class PermissionRegistry:
    """Registro centralizado de permisos del sistema."""
    
    # Permisos básicos de usuario
    VIEW_OWN_PROFILE = 'view_own_profile'
    EDIT_OWN_PROFILE = 'edit_own_profile'
    DELETE_OWN_PROFILE = 'delete_own_profile'
    
    # Permisos de administración de usuarios
    VIEW_ALL_USERS = 'view_all_users'
    CREATE_USERS = 'create_users'
    EDIT_ALL_USERS = 'edit_all_users'
    DELETE_USERS = 'delete_users'
    MANAGE_USER_ROLES = 'manage_user_roles'
    ACTIVATE_DEACTIVATE_USERS = 'activate_deactivate_users'
    
    # Permisos de proyectos
    VIEW_OWN_PROJECTS = 'view_own_projects'
    CREATE_PROJECTS = 'create_projects'
    EDIT_OWN_PROJECTS = 'edit_own_projects'
    DELETE_OWN_PROJECTS = 'delete_own_projects'
    VIEW_ALL_PROJECTS = 'view_all_projects'
    EDIT_ALL_PROJECTS = 'edit_all_projects'
    DELETE_ALL_PROJECTS = 'delete_all_projects'
    APPROVE_PROJECTS = 'approve_projects'
    
    # Permisos de reuniones
    SCHEDULE_MEETINGS = 'schedule_meetings'
    VIEW_OWN_MEETINGS = 'view_own_meetings'
    EDIT_OWN_MEETINGS = 'edit_own_meetings'
    CANCEL_OWN_MEETINGS = 'cancel_own_meetings'
    VIEW_ALL_MEETINGS = 'view_all_meetings'
    EDIT_ALL_MEETINGS = 'edit_all_meetings'
    CANCEL_ALL_MEETINGS = 'cancel_all_meetings'
    
    # Permisos de mentoría
    REQUEST_MENTORSHIP = 'request_mentorship'
    PROVIDE_MENTORSHIP = 'provide_mentorship'
    MANAGE_MENTORSHIP_SESSIONS = 'manage_mentorship_sessions'
    VIEW_MENTORSHIP_REPORTS = 'view_mentorship_reports'
    ASSIGN_MENTORS = 'assign_mentors'
    
    # Permisos de documentos
    UPLOAD_DOCUMENTS = 'upload_documents'
    VIEW_OWN_DOCUMENTS = 'view_own_documents'
    EDIT_OWN_DOCUMENTS = 'edit_own_documents'
    DELETE_OWN_DOCUMENTS = 'delete_own_documents'
    VIEW_ALL_DOCUMENTS = 'view_all_documents'
    MANAGE_ALL_DOCUMENTS = 'manage_all_documents'
    
    # Permisos de analytics y reportes
    VIEW_OWN_ANALYTICS = 'view_own_analytics'
    VIEW_SYSTEM_ANALYTICS = 'view_system_analytics'
    GENERATE_REPORTS = 'generate_reports'
    EXPORT_DATA = 'export_data'
    VIEW_AUDIT_LOGS = 'view_audit_logs'
    
    # Permisos de organizaciones
    CREATE_ORGANIZATIONS = 'create_organizations'
    MANAGE_OWN_ORGANIZATION = 'manage_own_organization'
    VIEW_ALL_ORGANIZATIONS = 'view_all_organizations'
    MANAGE_ALL_ORGANIZATIONS = 'manage_all_organizations'
    
    # Permisos de programas
    CREATE_PROGRAMS = 'create_programs'
    MANAGE_OWN_PROGRAMS = 'manage_own_programs'
    VIEW_ALL_PROGRAMS = 'view_all_programs'
    MANAGE_ALL_PROGRAMS = 'manage_all_programs'
    ENROLL_IN_PROGRAMS = 'enroll_in_programs'
    
    # Permisos de mensajería
    SEND_MESSAGES = 'send_messages'
    VIEW_OWN_MESSAGES = 'view_own_messages'
    DELETE_OWN_MESSAGES = 'delete_own_messages'
    VIEW_ALL_MESSAGES = 'view_all_messages'
    MODERATE_MESSAGES = 'moderate_messages'
    
    # Permisos del sistema
    ACCESS_ADMIN_PANEL = 'access_admin_panel'
    MANAGE_SYSTEM_SETTINGS = 'manage_system_settings'
    MANAGE_INTEGRATIONS = 'manage_integrations'
    PERFORM_BACKUPS = 'perform_backups'
    VIEW_SYSTEM_LOGS = 'view_system_logs'
    MANAGE_NOTIFICATIONS = 'manage_notifications'
    
    # Permisos especiales
    IMPERSONATE_USERS = 'impersonate_users'
    BYPASS_RATE_LIMITS = 'bypass_rate_limits'
    ACCESS_API = 'access_api'
    FULL_SYSTEM_ACCESS = 'full_system_access'


# ====================================
# MAPEO DE ROLES A PERMISOS
# ====================================

ROLE_PERMISSIONS = {
    ADMIN_ROLE: [
        # Acceso completo
        PermissionRegistry.FULL_SYSTEM_ACCESS,
        
        # Gestión de usuarios
        PermissionRegistry.VIEW_ALL_USERS,
        PermissionRegistry.CREATE_USERS,
        PermissionRegistry.EDIT_ALL_USERS,
        PermissionRegistry.DELETE_USERS,
        PermissionRegistry.MANAGE_USER_ROLES,
        PermissionRegistry.ACTIVATE_DEACTIVATE_USERS,
        PermissionRegistry.IMPERSONATE_USERS,
        
        # Gestión de proyectos
        PermissionRegistry.VIEW_ALL_PROJECTS,
        PermissionRegistry.EDIT_ALL_PROJECTS,
        PermissionRegistry.DELETE_ALL_PROJECTS,
        PermissionRegistry.APPROVE_PROJECTS,
        
        # Gestión de reuniones
        PermissionRegistry.VIEW_ALL_MEETINGS,
        PermissionRegistry.EDIT_ALL_MEETINGS,
        PermissionRegistry.CANCEL_ALL_MEETINGS,
        
        # Mentoría
        PermissionRegistry.PROVIDE_MENTORSHIP,
        PermissionRegistry.MANAGE_MENTORSHIP_SESSIONS,
        PermissionRegistry.VIEW_MENTORSHIP_REPORTS,
        PermissionRegistry.ASSIGN_MENTORS,
        
        # Documentos
        PermissionRegistry.VIEW_ALL_DOCUMENTS,
        PermissionRegistry.MANAGE_ALL_DOCUMENTS,
        
        # Analytics y reportes
        PermissionRegistry.VIEW_SYSTEM_ANALYTICS,
        PermissionRegistry.GENERATE_REPORTS,
        PermissionRegistry.EXPORT_DATA,
        PermissionRegistry.VIEW_AUDIT_LOGS,
        
        # Organizaciones y programas
        PermissionRegistry.VIEW_ALL_ORGANIZATIONS,
        PermissionRegistry.MANAGE_ALL_ORGANIZATIONS,
        PermissionRegistry.VIEW_ALL_PROGRAMS,
        PermissionRegistry.MANAGE_ALL_PROGRAMS,
        
        # Mensajería
        PermissionRegistry.VIEW_ALL_MESSAGES,
        PermissionRegistry.MODERATE_MESSAGES,
        
        # Sistema
        PermissionRegistry.ACCESS_ADMIN_PANEL,
        PermissionRegistry.MANAGE_SYSTEM_SETTINGS,
        PermissionRegistry.MANAGE_INTEGRATIONS,
        PermissionRegistry.PERFORM_BACKUPS,
        PermissionRegistry.VIEW_SYSTEM_LOGS,
        PermissionRegistry.MANAGE_NOTIFICATIONS,
        PermissionRegistry.BYPASS_RATE_LIMITS,
        PermissionRegistry.ACCESS_API,
    ],
    
    ENTREPRENEUR_ROLE: [
        # Perfil propio
        PermissionRegistry.VIEW_OWN_PROFILE,
        PermissionRegistry.EDIT_OWN_PROFILE,
        
        # Proyectos propios
        PermissionRegistry.VIEW_OWN_PROJECTS,
        PermissionRegistry.CREATE_PROJECTS,
        PermissionRegistry.EDIT_OWN_PROJECTS,
        PermissionRegistry.DELETE_OWN_PROJECTS,
        
        # Reuniones
        PermissionRegistry.SCHEDULE_MEETINGS,
        PermissionRegistry.VIEW_OWN_MEETINGS,
        PermissionRegistry.EDIT_OWN_MEETINGS,
        PermissionRegistry.CANCEL_OWN_MEETINGS,
        
        # Mentoría
        PermissionRegistry.REQUEST_MENTORSHIP,
        
        # Documentos propios
        PermissionRegistry.UPLOAD_DOCUMENTS,
        PermissionRegistry.VIEW_OWN_DOCUMENTS,
        PermissionRegistry.EDIT_OWN_DOCUMENTS,
        PermissionRegistry.DELETE_OWN_DOCUMENTS,
        
        # Analytics propios
        PermissionRegistry.VIEW_OWN_ANALYTICS,
        
        # Programas
        PermissionRegistry.ENROLL_IN_PROGRAMS,
        
        # Mensajería
        PermissionRegistry.SEND_MESSAGES,
        PermissionRegistry.VIEW_OWN_MESSAGES,
        PermissionRegistry.DELETE_OWN_MESSAGES,
        
        # API
        PermissionRegistry.ACCESS_API,
    ],
    
    ALLY_ROLE: [
        # Perfil propio
        PermissionRegistry.VIEW_OWN_PROFILE,
        PermissionRegistry.EDIT_OWN_PROFILE,
        
        # Reuniones
        PermissionRegistry.SCHEDULE_MEETINGS,
        PermissionRegistry.VIEW_OWN_MEETINGS,
        PermissionRegistry.EDIT_OWN_MEETINGS,
        PermissionRegistry.CANCEL_OWN_MEETINGS,
        
        # Mentoría
        PermissionRegistry.PROVIDE_MENTORSHIP,
        PermissionRegistry.MANAGE_MENTORSHIP_SESSIONS,
        PermissionRegistry.VIEW_MENTORSHIP_REPORTS,
        
        # Documentos propios
        PermissionRegistry.UPLOAD_DOCUMENTS,
        PermissionRegistry.VIEW_OWN_DOCUMENTS,
        PermissionRegistry.EDIT_OWN_DOCUMENTS,
        PermissionRegistry.DELETE_OWN_DOCUMENTS,
        
        # Analytics
        PermissionRegistry.VIEW_OWN_ANALYTICS,
        PermissionRegistry.GENERATE_REPORTS,
        
        # Programas
        PermissionRegistry.CREATE_PROGRAMS,
        PermissionRegistry.MANAGE_OWN_PROGRAMS,
        
        # Mensajería
        PermissionRegistry.SEND_MESSAGES,
        PermissionRegistry.VIEW_OWN_MESSAGES,
        PermissionRegistry.DELETE_OWN_MESSAGES,
        
        # API
        PermissionRegistry.ACCESS_API,
    ],
    
    CLIENT_ROLE: [
        # Perfil propio
        PermissionRegistry.VIEW_OWN_PROFILE,
        PermissionRegistry.EDIT_OWN_PROFILE,
        
        # Vista limitada de proyectos
        PermissionRegistry.VIEW_OWN_PROJECTS,  # Solo proyectos relacionados
        
        # Analytics limitados
        PermissionRegistry.VIEW_OWN_ANALYTICS,
        
        # Mensajería
        PermissionRegistry.SEND_MESSAGES,
        PermissionRegistry.VIEW_OWN_MESSAGES,
        PermissionRegistry.DELETE_OWN_MESSAGES,
        
        # API limitada
        PermissionRegistry.ACCESS_API,
    ]
}


# ====================================
# PERMISOS FLASK-PRINCIPAL
# ====================================

# Crear objetos Permission para Flask-Principal
def create_permission(permission_name: str) -> Permission:
    """Crear objeto Permission para Flask-Principal."""
    return Permission(RoleNeed(permission_name))


# Permisos comúnmente usados
admin_permission = Permission(RoleNeed(ADMIN_ROLE))
entrepreneur_permission = Permission(RoleNeed(ENTREPRENEUR_ROLE))
ally_permission = Permission(RoleNeed(ALLY_ROLE))
client_permission = Permission(RoleNeed(CLIENT_ROLE))

# Permisos combinados
staff_permission = Permission(RoleNeed(ADMIN_ROLE), RoleNeed(ALLY_ROLE))
authenticated_permission = Permission(
    RoleNeed(ADMIN_ROLE), 
    RoleNeed(ENTREPRENEUR_ROLE), 
    RoleNeed(ALLY_ROLE), 
    RoleNeed(CLIENT_ROLE)
)


# ====================================
# FUNCIONES DE VERIFICACIÓN DE PERMISOS
# ====================================

def has_role(user, role: str) -> bool:
    """
    Verificar si un usuario tiene un rol específico.
    
    Args:
        user: Usuario a verificar
        role: Rol a verificar
        
    Returns:
        True si el usuario tiene el rol
    """
    if not user or not hasattr(user, 'role'):
        return False
    
    return user.role == role


def has_permission(user, permission: str) -> bool:
    """
    Verificar si un usuario tiene un permiso específico.
    
    Args:
        user: Usuario a verificar
        permission: Permiso a verificar
        
    Returns:
        True si el usuario tiene el permiso
    """
    if not user or not hasattr(user, 'role'):
        return False
    
    # Admins tienen acceso completo
    if user.role == ADMIN_ROLE:
        return True
    
    # Verificar permisos del rol
    role_perms = ROLE_PERMISSIONS.get(user.role, [])
    return permission in role_perms or PermissionRegistry.FULL_SYSTEM_ACCESS in role_perms


def get_user_permissions(user) -> List[str]:
    """
    Obtener todos los permisos de un usuario.
    
    Args:
        user: Usuario
        
    Returns:
        Lista de permisos
    """
    if not user or not hasattr(user, 'role'):
        return []
    
    return ROLE_PERMISSIONS.get(user.role, [])


def can_access_resource(user, resource_type: str, resource_id: Optional[int] = None, 
                       action: str = 'view') -> bool:
    """
    Verificar si un usuario puede acceder a un recurso específico.
    
    Args:
        user: Usuario
        resource_type: Tipo de recurso (project, meeting, document, etc.)
        resource_id: ID del recurso (opcional)
        action: Acción a realizar (view, edit, delete)
        
    Returns:
        True si puede acceder
    """
    if not user:
        return False
    
    # Admins pueden acceder a todo
    if user.role == ADMIN_ROLE:
        return True
    
    # Mapear acciones a permisos
    permission_map = {
        'project': {
            'view': [PermissionRegistry.VIEW_OWN_PROJECTS, PermissionRegistry.VIEW_ALL_PROJECTS],
            'edit': [PermissionRegistry.EDIT_OWN_PROJECTS, PermissionRegistry.EDIT_ALL_PROJECTS],
            'delete': [PermissionRegistry.DELETE_OWN_PROJECTS, PermissionRegistry.DELETE_ALL_PROJECTS],
            'create': [PermissionRegistry.CREATE_PROJECTS]
        },
        'meeting': {
            'view': [PermissionRegistry.VIEW_OWN_MEETINGS, PermissionRegistry.VIEW_ALL_MEETINGS],
            'edit': [PermissionRegistry.EDIT_OWN_MEETINGS, PermissionRegistry.EDIT_ALL_MEETINGS],
            'delete': [PermissionRegistry.CANCEL_OWN_MEETINGS, PermissionRegistry.CANCEL_ALL_MEETINGS],
            'create': [PermissionRegistry.SCHEDULE_MEETINGS]
        },
        'document': {
            'view': [PermissionRegistry.VIEW_OWN_DOCUMENTS, PermissionRegistry.VIEW_ALL_DOCUMENTS],
            'edit': [PermissionRegistry.EDIT_OWN_DOCUMENTS, PermissionRegistry.MANAGE_ALL_DOCUMENTS],
            'delete': [PermissionRegistry.DELETE_OWN_DOCUMENTS, PermissionRegistry.MANAGE_ALL_DOCUMENTS],
            'create': [PermissionRegistry.UPLOAD_DOCUMENTS]
        },
        'user': {
            'view': [PermissionRegistry.VIEW_OWN_PROFILE, PermissionRegistry.VIEW_ALL_USERS],
            'edit': [PermissionRegistry.EDIT_OWN_PROFILE, PermissionRegistry.EDIT_ALL_USERS],
            'delete': [PermissionRegistry.DELETE_OWN_PROFILE, PermissionRegistry.DELETE_USERS],
            'create': [PermissionRegistry.CREATE_USERS]
        }
    }
    
    # Obtener permisos requeridos
    required_permissions = permission_map.get(resource_type, {}).get(action, [])
    if not required_permissions:
        return False
    
    # Verificar si el usuario tiene alguno de los permisos requeridos
    user_permissions = get_user_permissions(user)
    
    for perm in required_permissions:
        if perm in user_permissions:
            # Si es un permiso "all", permitir acceso
            if 'all' in perm.lower():
                return True
            
            # Si es un permiso "own", verificar ownership
            if 'own' in perm.lower() and resource_id:
                return check_resource_ownership(user, resource_type, resource_id)
            
            # Si no requiere ownership, permitir
            if 'own' not in perm.lower():
                return True
    
    return False


def can_modify_resource(user, resource_type: str, resource_id: int) -> bool:
    """Verificar si un usuario puede modificar un recurso."""
    return can_access_resource(user, resource_type, resource_id, 'edit')


def can_delete_resource(user, resource_type: str, resource_id: int) -> bool:
    """Verificar si un usuario puede eliminar un recurso."""
    return can_access_resource(user, resource_type, resource_id, 'delete')


def check_resource_ownership(user, resource_type: str, resource_id: int) -> bool:
    """
    Verificar si un usuario es propietario de un recurso.
    
    Args:
        user: Usuario
        resource_type: Tipo de recurso
        resource_id: ID del recurso
        
    Returns:
        True si es propietario
    """
    if not user or not resource_id:
        return False
    
    try:
        # Importar modelos dinámicamente para evitar importaciones circulares
        if resource_type == 'project':
            from app.models.project import Project
            resource = Project.query.get(resource_id)
            return resource and resource.entrepreneur_id == user.id
        
        elif resource_type == 'meeting':
            from app.models.meeting import Meeting
            resource = Meeting.query.get(resource_id)
            return resource and (resource.organizer_id == user.id or 
                               user.id in [p.id for p in resource.participants])
        
        elif resource_type == 'document':
            from app.models.document import Document  
            resource = Document.query.get(resource_id)
            return resource and resource.owner_id == user.id
        
        elif resource_type == 'user':
            return resource_id == user.id
        
        elif resource_type == 'organization':
            from app.models.organization import Organization
            resource = Organization.query.get(resource_id)
            return resource and resource.owner_id == user.id
        
        elif resource_type == 'program':
            from app.models.program import Program
            resource = Program.query.get(resource_id)
            return resource and resource.creator_id == user.id
        
        return False
        
    except Exception as e:
        permissions_logger.error(f"Error checking resource ownership: {str(e)}")
        return False


# ====================================
# DECORADORES DE PERMISOS
# ====================================

def require_role(*roles):
    """
    Decorador para requerir uno o más roles específicos.
    
    Args:
        *roles: Roles requeridos
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                log_security_event('UNAUTHORIZED_ACCESS_ATTEMPT', 
                                 {'endpoint': request.endpoint, 'required_roles': roles})
                
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not any(has_role(current_user, role) for role in roles):
                log_security_event('INSUFFICIENT_PERMISSIONS', 
                                 {'user_id': current_user.id, 
                                  'user_role': current_user.role,
                                  'required_roles': roles,
                                  'endpoint': request.endpoint})
                
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                flash('No tienes permisos para acceder a esta página.', 'error')
                return abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_permission(permission: str):
    """
    Decorador para requerir un permiso específico.
    
    Args:
        permission: Permiso requerido
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not has_permission(current_user, permission):
                log_security_event('PERMISSION_DENIED', 
                                 {'user_id': current_user.id,
                                  'required_permission': permission,
                                  'endpoint': request.endpoint})
                
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': f'Permission required: {permission}'}), 403
                
                flash('No tienes permisos para realizar esta acción.', 'error')
                return abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_resource_access(resource_type: str, resource_id_param: str = 'id', 
                           action: str = 'view'):
    """
    Decorador para requerir acceso a un recurso específico.
    
    Args:
        resource_type: Tipo de recurso
        resource_id_param: Nombre del parámetro que contiene el ID del recurso
        action: Acción a realizar
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('auth.login'))
            
            # Obtener ID del recurso
            resource_id = kwargs.get(resource_id_param) or request.view_args.get(resource_id_param)
            
            if not can_access_resource(current_user, resource_type, resource_id, action):
                log_security_event('RESOURCE_ACCESS_DENIED', 
                                 {'user_id': current_user.id,
                                  'resource_type': resource_type,
                                  'resource_id': resource_id,
                                  'action': action})
                
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Access denied to resource'}), 403
                
                flash('No tienes permisos para acceder a este recurso.', 'error')
                return abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# Decoradores específicos de roles
require_admin = require_role(ADMIN_ROLE)
require_entrepreneur = require_role(ENTREPRENEUR_ROLE)  
require_ally = require_role(ALLY_ROLE)
require_client = require_role(CLIENT_ROLE)
require_mentor = require_role(*MENTOR_ROLES)
require_staff = require_role(ADMIN_ROLE, ALLY_ROLE)


# ====================================
# FUNCIONES ESPECÍFICAS DE PERMISOS
# ====================================

def can_view_user_profile(user, target_user_id: int) -> bool:
    """Verificar si un usuario puede ver el perfil de otro."""
    if has_permission(user, PermissionRegistry.VIEW_ALL_USERS):
        return True
    
    if user.id == target_user_id:
        return has_permission(user, PermissionRegistry.VIEW_OWN_PROFILE)
    
    return False


def can_edit_user_profile(user, target_user_id: int) -> bool:
    """Verificar si un usuario puede editar el perfil de otro."""
    if has_permission(user, PermissionRegistry.EDIT_ALL_USERS):
        return True
    
    if user.id == target_user_id:
        return has_permission(user, PermissionRegistry.EDIT_OWN_PROFILE)
    
    return False


def can_manage_projects(user, project_id: Optional[int] = None) -> bool:
    """Verificar si un usuario puede gestionar proyectos."""
    if has_permission(user, PermissionRegistry.EDIT_ALL_PROJECTS):
        return True
    
    if project_id and has_permission(user, PermissionRegistry.EDIT_OWN_PROJECTS):
        return check_resource_ownership(user, 'project', project_id)
    
    return has_permission(user, PermissionRegistry.CREATE_PROJECTS)


def can_schedule_meetings(user) -> bool:
    """Verificar si un usuario puede programar reuniones."""
    return has_permission(user, PermissionRegistry.SCHEDULE_MEETINGS)


def can_access_analytics(user, scope: str = 'own') -> bool:
    """Verificar si un usuario puede acceder a analytics."""
    if scope == 'system':
        return has_permission(user, PermissionRegistry.VIEW_SYSTEM_ANALYTICS)
    
    return has_permission(user, PermissionRegistry.VIEW_OWN_ANALYTICS)


def can_provide_mentorship(user) -> bool:
    """Verificar si un usuario puede proporcionar mentoría."""
    return has_permission(user, PermissionRegistry.PROVIDE_MENTORSHIP)


def can_request_mentorship(user) -> bool:
    """Verificar si un usuario puede solicitar mentoría."""
    return has_permission(user, PermissionRegistry.REQUEST_MENTORSHIP)


# ====================================
# FILTROS DE CONSULTAS BASADOS EN PERMISOS
# ====================================

def filter_by_permissions(query, user, resource_type: str):
    """
    Filtrar consulta basada en permisos del usuario.
    
    Args:
        query: Consulta SQLAlchemy
        user: Usuario actual
        resource_type: Tipo de recurso
        
    Returns:
        Consulta filtrada
    """
    # Admins ven todo
    if user.role == ADMIN_ROLE:
        return query
    
    try:
        if resource_type == 'project':
            # Emprendedores ven solo sus proyectos
            if user.role == ENTREPRENEUR_ROLE:
                query = query.filter_by(entrepreneur_id=user.id)
            # Aliados ven proyectos de sus mentoreados
            elif user.role == ALLY_ROLE:
                from app.models.mentorship import Mentorship
                mentee_ids = [m.entrepreneur_id for m in 
                             Mentorship.query.filter_by(ally_id=user.id).all()]
                query = query.filter(Project.entrepreneur_id.in_(mentee_ids))
            # Clientes ven proyectos públicos o relacionados
            elif user.role == CLIENT_ROLE:
                query = query.filter_by(is_public=True)
        
        elif resource_type == 'meeting':
            # Usuarios ven solo sus reuniones
            from app.models.meeting import Meeting
            query = query.filter(
                (Meeting.organizer_id == user.id) |
                (Meeting.participants.any(id=user.id))
            )
        
        elif resource_type == 'document':
            # Usuarios ven solo sus documentos
            query = query.filter_by(owner_id=user.id)
        
        elif resource_type == 'user':
            # Usuarios normales solo se ven a sí mismos
            if not has_permission(user, PermissionRegistry.VIEW_ALL_USERS):
                query = query.filter_by(id=user.id)
        
        return query
        
    except Exception as e:
        permissions_logger.error(f"Error filtering query by permissions: {str(e)}")
        return query


# ====================================
# CONTEXT PROCESSORS
# ====================================

def permission_context_processor():
    """Context processor para templates con información de permisos."""
    
    def has_role_template(role):
        return has_role(current_user, role) if current_user.is_authenticated else False
    
    def has_permission_template(permission):
        return has_permission(current_user, permission) if current_user.is_authenticated else False
    
    def can_access_template(resource_type, resource_id=None, action='view'):
        return (can_access_resource(current_user, resource_type, resource_id, action) 
                if current_user.is_authenticated else False)
    
    return {
        'has_role': has_role_template,
        'has_permission': has_permission_template,
        'can_access': can_access_template,
        'current_user_permissions': get_user_permissions(current_user) if current_user.is_authenticated else [],
        'is_admin': has_role(current_user, ADMIN_ROLE) if current_user.is_authenticated else False,
        'is_entrepreneur': has_role(current_user, ENTREPRENEUR_ROLE) if current_user.is_authenticated else False,
        'is_ally': has_role(current_user, ALLY_ROLE) if current_user.is_authenticated else False,
        'is_client': has_role(current_user, CLIENT_ROLE) if current_user.is_authenticated else False,
        'can_admin': has_permission(current_user, PermissionRegistry.ACCESS_ADMIN_PANEL) if current_user.is_authenticated else False
    }


# ====================================
# GESTIÓN AVANZADA DE PERMISOS
# ====================================

class PermissionManager:
    """Gestor avanzado de permisos con cache y optimizaciones."""
    
    def __init__(self):
        self._permission_cache = {}
        self._cache_ttl = 300  # 5 minutos
        
    def check_permission_cached(self, user_id: int, permission: str) -> bool:
        """Verificar permiso con cache."""
        cache_key = f"perm:{user_id}:{permission}"
        
        try:
            from app.extensions import cache
            result = cache.get(cache_key)
            
            if result is None:
                # Obtener usuario y verificar permiso
                from app.models.user import User
                user = User.query.get(user_id)
                result = has_permission(user, permission)
                
                # Cachear resultado
                cache.set(cache_key, result, timeout=self._cache_ttl)
            
            return result
            
        except Exception as e:
            permissions_logger.error(f"Error checking cached permission: {str(e)}")
            # Fallback sin cache
            from app.models.user import User
            user = User.query.get(user_id)
            return has_permission(user, permission)
    
    def invalidate_user_permissions_cache(self, user_id: int):
        """Invalidar cache de permisos de un usuario."""
        try:
            from app.extensions import cache
            
            # Eliminar todas las claves de cache del usuario
            for permission in self._get_all_permissions():
                cache_key = f"perm:{user_id}:{permission}"
                cache.delete(cache_key)
                
        except Exception as e:
            permissions_logger.error(f"Error invalidating permissions cache: {str(e)}")
    
    def _get_all_permissions(self) -> List[str]:
        """Obtener lista de todos los permisos disponibles."""
        all_permissions = set()
        for role_perms in ROLE_PERMISSIONS.values():
            all_permissions.update(role_perms)
        return list(all_permissions)
    
    def bulk_check_permissions(self, user_id: int, permissions: List[str]) -> Dict[str, bool]:
        """Verificar múltiples permisos de una vez."""
        results = {}
        
        try:
            from app.models.user import User
            user = User.query.get(user_id)
            
            if not user:
                return {perm: False for perm in permissions}
            
            for permission in permissions:
                results[permission] = has_permission(user, permission)
                
        except Exception as e:
            permissions_logger.error(f"Error bulk checking permissions: {str(e)}")
            results = {perm: False for perm in permissions}
        
        return results
    
    def get_accessible_resources(self, user_id: int, resource_type: str) -> List[int]:
        """Obtener lista de IDs de recursos accesibles para un usuario."""
        try:
            from app.models.user import User
            user = User.query.get(user_id)
            
            if not user:
                return []
            
            # Admin puede acceder a todo
            if user.role == ADMIN_ROLE:
                return self._get_all_resource_ids(resource_type)
            
            # Otros roles según ownership
            if resource_type == 'project':
                from app.models.project import Project
                if user.role == ENTREPRENEUR_ROLE:
                    projects = Project.query.filter_by(entrepreneur_id=user.id).all()
                    return [p.id for p in projects]
                elif user.role == ALLY_ROLE:
                    # Proyectos de mentoreados
                    from app.models.mentorship import Mentorship
                    mentorships = Mentorship.query.filter_by(ally_id=user.id).all()
                    mentee_ids = [m.entrepreneur_id for m in mentorships]
                    projects = Project.query.filter(Project.entrepreneur_id.in_(mentee_ids)).all()
                    return [p.id for p in projects]
            
            elif resource_type == 'meeting':
                from app.models.meeting import Meeting
                meetings = Meeting.query.filter(
                    (Meeting.organizer_id == user.id) |
                    (Meeting.participants.any(id=user.id))
                ).all()
                return [m.id for m in meetings]
            
            elif resource_type == 'document':
                from app.models.document import Document
                documents = Document.query.filter_by(owner_id=user.id).all()
                return [d.id for d in documents]
            
            return []
            
        except Exception as e:
            permissions_logger.error(f"Error getting accessible resources: {str(e)}")
            return []
    
    def _get_all_resource_ids(self, resource_type: str) -> List[int]:
        """Obtener todos los IDs de un tipo de recurso."""
        try:
            if resource_type == 'project':
                from app.models.project import Project
                return [p.id for p in Project.query.all()]
            elif resource_type == 'meeting':
                from app.models.meeting import Meeting
                return [m.id for m in Meeting.query.all()]
            elif resource_type == 'document':
                from app.models.document import Document
                return [d.id for d in Document.query.all()]
            elif resource_type == 'user':
                from app.models.user import User
                return [u.id for u in User.query.all()]
            
            return []
            
        except Exception as e:
            permissions_logger.error(f"Error getting all resource IDs: {str(e)}")
            return []


# Instancia global del gestor de permisos
permission_manager = PermissionManager()


# ====================================
# MIDDLEWARE DE PERMISOS
# ====================================

class PermissionMiddleware:
    """Middleware para verificar permisos automáticamente."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializar middleware con la aplicación."""
        app.before_request(self.check_permissions)
    
    def check_permissions(self):
        """Verificar permisos antes de cada request."""
        # Saltar verificación para rutas estáticas y de auth
        if (request.endpoint in ['static', 'auth.login', 'auth.register'] or
            request.path.startswith('/static')):
            return
        
        # Verificar rutas que requieren autenticación
        protected_patterns = [
            '/admin', '/api', '/entrepreneur', '/ally', '/client'
        ]
        
        for pattern in protected_patterns:
            if request.path.startswith(pattern):
                if not current_user.is_authenticated:
                    if request.is_json:
                        return jsonify({'error': 'Authentication required'}), 401
                    return redirect(url_for('auth.login'))
                
                # Verificar permisos de role específicos
                if pattern == '/admin' and not has_role(current_user, ADMIN_ROLE):
                    return abort(403)
                elif pattern == '/entrepreneur' and not has_role(current_user, ENTREPRENEUR_ROLE):
                    return abort(403)
                elif pattern == '/ally' and not has_role(current_user, ALLY_ROLE):
                    return abort(403)
                elif pattern == '/client' and not has_role(current_user, CLIENT_ROLE):
                    return abort(403)


# ====================================
# HERRAMIENTAS DE AUDITORIA DE PERMISOS
# ====================================

def audit_user_permissions(user_id: int) -> Dict[str, Any]:
    """Auditar permisos de un usuario específico."""
    try:
        from app.models.user import User
        user = User.query.get(user_id)
        
        if not user:
            return {'error': 'Usuario no encontrado'}
        
        user_permissions = get_user_permissions(user)
        
        audit_data = {
            'user_id': user_id,
            'user_email': user.email,
            'user_role': user.role,
            'permissions_count': len(user_permissions),
            'permissions': user_permissions,
            'role_info': USER_ROLES.get(user.role, {}),
            'can_admin': has_permission(user, PermissionRegistry.ACCESS_ADMIN_PANEL),
            'high_risk_permissions': []
        }
        
        # Identificar permisos de alto riesgo
        high_risk_perms = [
            PermissionRegistry.FULL_SYSTEM_ACCESS,
            PermissionRegistry.DELETE_USERS,
            PermissionRegistry.IMPERSONATE_USERS,
            PermissionRegistry.MANAGE_SYSTEM_SETTINGS,
            PermissionRegistry.VIEW_AUDIT_LOGS
        ]
        
        audit_data['high_risk_permissions'] = [
            perm for perm in high_risk_perms if perm in user_permissions
        ]
        
        return audit_data
        
    except Exception as e:
        permissions_logger.error(f"Error auditing user permissions: {str(e)}")
        return {'error': str(e)}


def generate_permissions_report() -> Dict[str, Any]:
    """Generar reporte completo de permisos del sistema."""
    try:
        from app.models.user import User
        
        users = User.query.all()
        
        report = {
            'total_users': len(users),
            'users_by_role': {},
            'permissions_by_role': ROLE_PERMISSIONS.copy(),
            'users_with_high_risk_permissions': [],
            'inactive_users_with_permissions': [],
            'orphaned_permissions': []
        }
        
        # Contar usuarios por rol
        for user in users:
            role = user.role
            if role not in report['users_by_role']:
                report['users_by_role'][role] = 0
            report['users_by_role'][role] += 1
            
            # Verificar usuarios de alto riesgo
            user_perms = get_user_permissions(user)
            high_risk_perms = [
                PermissionRegistry.FULL_SYSTEM_ACCESS,
                PermissionRegistry.DELETE_USERS,
                PermissionRegistry.IMPERSONATE_USERS
            ]
            
            if any(perm in user_perms for perm in high_risk_perms):
                report['users_with_high_risk_permissions'].append({
                    'user_id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active
                })
            
            # Verificar usuarios inactivos con permisos
            if not user.is_active and user_perms:
                report['inactive_users_with_permissions'].append({
                    'user_id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'permissions_count': len(user_perms)
                })
        
        return report
        
    except Exception as e:
        permissions_logger.error(f"Error generating permissions report: {str(e)}")
        return {'error': str(e)}


# ====================================
# CONFIGURACIÓN DE FLASK-PRINCIPAL
# ====================================

@identity_loaded.connect
def on_identity_loaded(sender, identity):
    """Configurar identity cuando se carga un usuario."""
    identity.user = current_user
    
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))
    
    if hasattr(current_user, 'role'):
        identity.provides.add(RoleNeed(current_user.role))
        
        # Añadir todos los permisos del rol
        user_permissions = get_user_permissions(current_user)
        for permission in user_permissions:
            identity.provides.add(RoleNeed(permission))


# ====================================
# FUNCIONES DE INICIALIZACIÓN
# ====================================

def init_permissions(app):
    """Inicializar sistema de permisos con la aplicación."""
    
    # Registrar context processor
    app.context_processor(permission_context_processor)
    
    # Inicializar middleware
    PermissionMiddleware(app)
    
    # Registrar comandos CLI para gestión de permisos
    @app.cli.command()
    @click.argument('user_id', type=int)
    def audit_permissions(user_id):
        """Auditar permisos de un usuario."""
        result = audit_user_permissions(user_id)
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    
    @app.cli.command()
    def permissions_report():
        """Generar reporte de permisos del sistema."""
        result = generate_permissions_report()
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    
    app.logger.info("Permission system initialized successfully")


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    # Registry y constantes
    'PermissionRegistry',
    'ROLE_PERMISSIONS',
    
    # Permisos Flask-Principal
    'admin_permission',
    'entrepreneur_permission', 
    'ally_permission',
    'client_permission',
    'staff_permission',
    'authenticated_permission',
    
    # Funciones de verificación
    'has_role',
    'has_permission',
    'get_user_permissions',
    'can_access_resource',
    'can_modify_resource',
    'can_delete_resource',
    'check_resource_ownership',
    
    # Decoradores
    'require_role',
    'require_permission',
    'require_resource_access',
    'require_admin',
    'require_entrepreneur',
    'require_ally',
    'require_client',
    'require_mentor',
    'require_staff',
    
    # Funciones específicas
    'can_view_user_profile',
    'can_edit_user_profile',
    'can_manage_projects',
    'can_schedule_meetings',
    'can_access_analytics',
    'can_provide_mentorship',
    'can_request_mentorship',
    
    # Utilidades
    'filter_by_permissions',
    'permission_context_processor',
    'permission_manager',
    'PermissionManager',
    'PermissionMiddleware',
    
    # Auditoría
    'audit_user_permissions',
    'generate_permissions_report',
    
    # Inicialización
    'init_permissions',
    'on_identity_loaded'
]