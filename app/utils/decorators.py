# app/utils/decorators.py

from functools import wraps
from flask import request, redirect, url_for, flash, abort, current_app
from flask_login import current_user

def role_required(*roles):
    """
    Decorador que verifica si el usuario actual tiene uno de los roles especificados.
    Redirige a login si el usuario no está autenticado o aborta con 403 si no tiene el rol.
    
    Uso:
        @role_required('admin', 'ally')
        def vista_protegida():
            return 'Solo admins y aliados pueden ver esto'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Por favor inicie sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if not current_user.role in roles:
                current_app.logger.warning(
                    f'Usuario {current_user.id} con rol {current_user.role} intentó acceder '
                    f'a una vista restringida para {roles}.'
                )
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def ajax_required(f):
    """
    Decorador que verifica si la solicitud es AJAX.
    Aborta con un error 400 si no es una solicitud AJAX.
    
    Uso:
        @ajax_required
        def vista_ajax():
            return jsonify(data='solo para solicitudes ajax')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            abort(400, description='Se requiere una solicitud AJAX')
        return f(*args, **kwargs)
    return decorated_function

def login_fresh_required(f):
    """
    Decorador que verifica si la sesión del usuario es fresca.
    Útil para operaciones sensibles que requieren reautenticación.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.login_fresh():
            flash('Esta acción requiere confirmación de identidad.', 'warning')
            return redirect(url_for('auth.reauthenticate', next=request.url))
        
        return f(*args, **kwargs)
    return decorated_function

def cache_control(*directives):
    """
    Decorador para establecer cabeceras de control de caché HTTP.
    
    Uso:
        @cache_control('no-store', 'max-age=0')
        def vista_sin_cache():
            return 'Esta respuesta no se almacenará en caché'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['Cache-Control'] = ', '.join(directives)
            return response
        return decorated_function
    return decorator

def paginate(default_per_page=20, max_per_page=100):
    """
    Decorador para facilitar la paginación en vistas que devuelven listas.
    Inyecta un objeto de paginación en la función de vista.
    
    Uso:
        @paginate(default_per_page=15)
        def listar_usuarios(pagination):
            users = User.query.paginate(
                page=pagination.page,
                per_page=pagination.per_page,
                error_out=False
            )
            return render_template('users.html', users=users)
    """
    class Pagination:
        def __init__(self, page, per_page):
            self.page = page
            self.per_page = per_page

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            page = request.args.get('page', 1, type=int)
            per_page = min(
                request.args.get('per_page', default_per_page, type=int),
                max_per_page
            )
            pagination = Pagination(page, per_page)
            return f(*args, pagination=pagination, **kwargs)
        return decorated_function
    return decorator