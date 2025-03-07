from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.user import User
from app.models.relationship import Relationship
from app.models.ally import Ally
from app.forms.admin import EntrepreneurSearchForm, EntrepreneurForm, AssignAllyForm
from app.utils.decorators import admin_required
from app.utils.notifications import send_notification
from app.services.email import send_email_template

# Crear Blueprint para las rutas de administración de emprendedores
admin_entrepreneurs = Blueprint('admin_entrepreneurs', __name__)

@admin_entrepreneurs.route('/admin/entrepreneurs')
@login_required
@admin_required
def list_entrepreneurs():
    """Vista para listar todos los emprendedores."""
    search_form = EntrepreneurSearchForm(request.args)
    
    # Configurar paginación
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ADMIN_ITEMS_PER_PAGE', 15)
    
    # Filtrar por búsqueda si está presente
    query = Entrepreneur.query.join(User)
    if search_form.validate():
        if search_form.search.data:
            search_term = f"%{search_form.search.data}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    Entrepreneur.company_name.ilike(search_term)
                )
            )
        
        if search_form.status.data:
            query = query.filter(User.is_active == (search_form.status.data == 'active'))
            
        if search_form.sector.data:
            query = query.filter(Entrepreneur.sector == search_form.sector.data)
            
        if search_form.has_ally.data:
            subquery = db.session.query(Relationship.entrepreneur_id).filter(
                Relationship.is_active == True
            ).subquery()
            
            if search_form.has_ally.data == 'yes':
                query = query.filter(Entrepreneur.id.in_(subquery))
            else:
                query = query.filter(~Entrepreneur.id.in_(subquery))
    
    # Ordenar resultados
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    
    if hasattr(Entrepreneur, sort_by):
        if order == 'desc':
            query = query.order_by(getattr(Entrepreneur, sort_by).desc())
        else:
            query = query.order_by(getattr(Entrepreneur, sort_by).asc())
    elif hasattr(User, sort_by):
        if order == 'desc':
            query = query.order_by(getattr(User, sort_by).desc())
        else:
            query = query.order_by(getattr(User, sort_by).asc())
    
    # Ejecutar paginación
    pagination = query.paginate(page=page, per_page=per_page)
    
    return render_template(
        'admin/entrepreneurs.html',
        entrepreneurs=pagination.items,
        pagination=pagination,
        search_form=search_form,
        sort_by=sort_by,
        order=order
    )


@admin_entrepreneurs.route('/admin/entrepreneurs/<int:entrepreneur_id>')
@login_required
@admin_required
def entrepreneur_detail(entrepreneur_id):
    """Vista para ver los detalles de un emprendedor."""
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Obtener relaciones activas con aliados
    relationships = Relationship.query.filter_by(
        entrepreneur_id=entrepreneur.id, 
        is_active=True
    ).all()
    
    # Obtener historial de aliados anteriores
    past_relationships = Relationship.query.filter_by(
        entrepreneur_id=entrepreneur.id, 
        is_active=False
    ).order_by(Relationship.end_date.desc()).all()
    
    return render_template(
        'admin/entrepreneur_detail.html',
        entrepreneur=entrepreneur,
        relationships=relationships,
        past_relationships=past_relationships
    )


@admin_entrepreneurs.route('/admin/entrepreneurs/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_entrepreneur():
    """Vista para crear un nuevo emprendedor."""
    form = EntrepreneurForm()
    
    if form.validate_on_submit():
        # Crear un nuevo usuario
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='entrepreneur',
            is_active=form.is_active.data
        )
        
        # Establecer contraseña
        user.set_password(form.password.data)
        
        # Guardar usuario para obtener su ID
        db.session.add(user)
        db.session.flush()
        
        # Crear el emprendedor
        entrepreneur = Entrepreneur(
            user_id=user.id,
            company_name=form.company_name.data,
            sector=form.sector.data,
            description=form.description.data,
            founding_date=form.founding_date.data,
            employees=form.employees.data,
            location=form.location.data,
            website=form.website.data,
            phase=form.phase.data
        )
        
        db.session.add(entrepreneur)
        db.session.commit()
        
        # Enviar email de bienvenida
        send_email_template(
            'welcome_entrepreneur',
            user.email,
            {
                'first_name': user.first_name,
                'username': user.username,
                'login_url': url_for('auth.login', _external=True)
            }
        )
        
        flash('Emprendedor creado exitosamente', 'success')
        return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))
    
    return render_template('admin/entrepreneur_form.html', form=form, title='Crear Emprendedor')


@admin_entrepreneurs.route('/admin/entrepreneurs/<int:entrepreneur_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_entrepreneur(entrepreneur_id):
    """Vista para editar un emprendedor existente."""
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    user = User.query.get(entrepreneur.user_id)
    
    form = EntrepreneurForm(obj=entrepreneur)
    
    # Completar el formulario con datos del usuario
    form.username.data = user.username
    form.email.data = user.email
    form.first_name.data = user.first_name
    form.last_name.data = user.last_name
    form.is_active.data = user.is_active
    
    # Si la contraseña no se modifica, no es requerida
    if request.method == 'POST':
        form.password.validators = []
        if not form.password.data:
            del form.password
    
    if form.validate_on_submit():
        # Actualizar datos del usuario
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.is_active = form.is_active.data
        
        # Actualizar contraseña si se proporciona
        if hasattr(form, 'password') and form.password.data:
            user.set_password(form.password.data)
        
        # Actualizar datos del emprendedor
        entrepreneur.company_name = form.company_name.data
        entrepreneur.sector = form.sector.data
        entrepreneur.description = form.description.data
        entrepreneur.founding_date = form.founding_date.data
        entrepreneur.employees = form.employees.data
        entrepreneur.location = form.location.data
        entrepreneur.website = form.website.data
        entrepreneur.phase = form.phase.data
        
        db.session.commit()
        flash('Emprendedor actualizado exitosamente', 'success')
        return redirect(url_for('admin_entrepreneurs.list_entrepreneurs'))
    
    return render_template('admin/entrepreneur_form.html', form=form, entrepreneur=entrepreneur, title='Editar Emprendedor')


@admin_entrepreneurs.route('/admin/entrepreneurs/<int:entrepreneur_id>/assign', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_ally(entrepreneur_id):
    """Vista para asignar un aliado a un emprendedor."""
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Verificar si ya tiene aliado activo
    active_relationship = Relationship.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        is_active=True
    ).first()
    
    form = AssignAllyForm()
    
    # Llenar el select de aliados disponibles
    form.ally_id.choices = [
        (ally.id, f"{ally.user.first_name} {ally.user.last_name} - {ally.specialty}")
        for ally in Ally.query.join(User).filter(User.is_active == True).all()
    ]
    
    if form.validate_on_submit():
        ally = Ally.query.get_or_404(form.ally_id.data)
        
        # Verificar si ya existe una relación activa y finalizarla
        if active_relationship:
            active_relationship.is_active = False
            active_relationship.end_date = form.start_date.data
            active_relationship.end_reason = "Reasignación administrativa"
        
        # Crear nueva relación
        relationship = Relationship(
            entrepreneur_id=entrepreneur.id,
            ally_id=ally.id,
            start_date=form.start_date.data,
            expected_end_date=form.expected_end_date.data,
            notes=form.notes.data,
            is_active=True
        )
        
        db.session.add(relationship)
        db.session.commit()
        
        # Notificar al emprendedor y al aliado
        send_notification(
            entrepreneur.user_id,
            'ally_assigned',
            f'Se te ha asignado a {ally.user.first_name} {ally.user.last_name} como tu aliado'
        )
        
        send_notification(
            ally.user_id,
            'entrepreneur_assigned',
            f'Se te ha asignado al emprendedor {entrepreneur.company_name}'
        )
        
        # Enviar emails
        send_email_template(
            'ally_assignment',
            entrepreneur.user.email,
            {
                'entrepreneur_name': entrepreneur.user.first_name,
                'ally_name': f"{ally.user.first_name} {ally.user.last_name}",
                'start_date': form.start_date.data.strftime("%d/%m/%Y")
            }
        )
        
        send_email_template(
            'entrepreneur_assignment',
            ally.user.email,
            {
                'ally_name': ally.user.first_name,
                'entrepreneur_name': entrepreneur.company_name,
                'start_date': form.start_date.data.strftime("%d/%m/%Y")
            }
        )
        
        flash('Aliado asignado exitosamente', 'success')
        return redirect(url_for('admin_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    return render_template(
        'admin/assign_ally.html',
        form=form,
        entrepreneur=entrepreneur,
        active_relationship=active_relationship,
        title='Asignar Aliado'
    )


@admin_entrepreneurs.route('/admin/entrepreneurs/<int:entrepreneur_id>/relationships/<int:relationship_id>/end', methods=['POST'])
@login_required
@admin_required
def end_relationship(entrepreneur_id, relationship_id):
    """Vista para finalizar una relación emprendedor-aliado."""
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    relationship = Relationship.query.get_or_404(relationship_id)
    
    # Verificar que la relación pertenece al emprendedor
    if relationship.entrepreneur_id != entrepreneur.id:
        flash('Relación no válida', 'danger')
        return redirect(url_for('admin_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))
    
    # Obtener datos del formulario
    end_reason = request.form.get('end_reason', 'Finalizado por administrador')
    
    # Finalizar relación
    relationship.is_active = False
    relationship.end_date = db.func.current_date()
    relationship.end_reason = end_reason
    
    db.session.commit()
    
    # Notificar a los involucrados
    ally = Ally.query.get(relationship.ally_id)
    
    send_notification(
        entrepreneur.user_id,
        'relationship_ended',
        f'Tu relación con el aliado {ally.user.first_name} {ally.user.last_name} ha finalizado'
    )
    
    send_notification(
        ally.user_id,
        'relationship_ended',
        f'Tu relación con el emprendedor {entrepreneur.company_name} ha finalizado'
    )
    
    flash('Relación finalizada exitosamente', 'success')
    return redirect(url_for('admin_entrepreneurs.entrepreneur_detail', entrepreneur_id=entrepreneur.id))