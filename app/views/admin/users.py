from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.forms.admin import UserForm, UserSearchForm
from app.utils.decorators import admin_required

# Crear Blueprint para las rutas de administración de usuarios
admin_users = Blueprint('admin_users', __name__)

@admin_users.route('/admin/users')
@login_required
@admin_required
def list_users():
    """Vista para listar todos los usuarios."""
    search_form = UserSearchForm(request.args)
    
    # Configurar paginación
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 15)
    
    # Filtrar por búsqueda si está presente
    query = User.query
    if search_form.validate():
        if search_form.search.data:
            search_term = f"%{search_form.search.data}%"
            query = query.filter(
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                (User.first_name.ilike(search_term)) |
                (User.last_name.ilike(search_term))
            )
        
        if search_form.role.data:
            query = query.filter(User.role == search_form.role.data)
            
        if search_form.status.data:
            query = query.filter(User.is_active == (search_form.status.data == 'active'))
    
    # Ordenar resultados
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    
    if hasattr(User, sort_by):
        if order == 'desc':
            query = query.order_by(getattr(User, sort_by).desc())
        else:
            query = query.order_by(getattr(User, sort_by).asc())
    
    # Ejecutar paginación
    pagination = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin/users.html',
        users=pagination.items,
        pagination=pagination,
        search_form=search_form,
        sort_by=sort_by,
        order=order
    )


@admin_users.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Vista para crear un nuevo usuario."""
    form = UserForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            is_active=form.is_active.data
        )
        
        # Establecer contraseña
        user.set_password(form.password.data)
        
        # Guardar en la base de datos
        db.session.add(user)
        db.session.commit()
        
        flash('Usuario creado exitosamente', 'success')
        return redirect(url_for('admin_users.list_users'))
    
    return render_template('admin/user_form.html', form=form, title='Crear Usuario')


@admin_users.route('/admin/users/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Vista para editar un usuario existente."""
    user = User.query.get_or_404(user_id)
    
    # No permitir que un administrador se desactive a sí mismo
    if user.id == current_user.id and not user.is_active:
        flash('No puedes desactivar tu propia cuenta', 'danger')
        return redirect(url_for('admin_users.list_users'))
    
    form = UserForm(obj=user)
    
    # Si la contraseña no se modifica, no es requerida
    if request.method == 'POST':
        form.password.validators = []
        if not form.password.data:
            del form.password
    
    if form.validate_on_submit():
        form.populate_obj(user)
        
        # Actualizar contraseña si se proporciona
        if hasattr(form, 'password') and form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        flash('Usuario actualizado exitosamente', 'success')
        return redirect(url_for('admin_users.list_users'))
    
    return render_template('admin/user_form.html', form=form, user=user, title='Editar Usuario')


@admin_users.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Vista para eliminar un usuario."""
    user = User.query.get_or_404(user_id)
    
    # No permitir que un administrador se elimine a sí mismo
    if user.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta', 'danger')
        return redirect(url_for('admin_users.list_users'))
    
    # En lugar de eliminar definitivamente, marcar como inactivo
    # o implementar eliminación lógica para preservar integridad referencial
    user.is_active = False
    # También se podría implementar: user.deleted_at = datetime.utcnow()
    
    db.session.commit()
    flash('Usuario eliminado exitosamente', 'success')
    
    return redirect(url_for('admin_users.list_users'))


@admin_users.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Vista para activar/desactivar un usuario."""
    user = User.query.get_or_404(user_id)
    
    # No permitir que un administrador se desactive a sí mismo
    if user.id == current_user.id and user.is_active:
        flash('No puedes desactivar tu propia cuenta', 'danger')
        return redirect(url_for('admin_users.list_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario {status} exitosamente', 'success')
    
    return redirect(url_for('admin_users.list_users'))