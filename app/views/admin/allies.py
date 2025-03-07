from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.forms.admin import AllyForm, AssignAllyForm
from app.utils.decorators import admin_required

# Creación del Blueprint
admin_allies = Blueprint('admin_allies', __name__)

@admin_allies.route('/admin/allies')
@login_required
@admin_required
def list_allies():
    """Vista para listar todos los aliados"""
    allies = Ally.query.all()
    return render_template('admin/allies.html', allies=allies)

@admin_allies.route('/admin/allies/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_ally():
    """Vista para crear un nuevo aliado"""
    form = AllyForm()
    
    if form.validate_on_submit():
        # Crear usuario primero
        user = User(
            name=form.name.data,
            email=form.email.data,
            role='ally'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # Para obtener el ID del usuario
        
        # Crear aliado con el ID de usuario
        ally = Ally(
            user_id=user.id,
            specialty=form.specialty.data,
            organization=form.organization.data,
            experience=form.experience.data,
            availability=form.availability.data
        )
        db.session.add(ally)
        db.session.commit()
        
        flash('Aliado creado exitosamente', 'success')
        return redirect(url_for('admin_allies.list_allies'))
        
    return render_template('admin/user_form.html', form=form, title='Nuevo Aliado')

@admin_allies.route('/admin/allies/<int:ally_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_ally(ally_id):
    """Vista para editar un aliado existente"""
    ally = Ally.query.get_or_404(ally_id)
    user = User.query.get(ally.user_id)
    
    form = AllyForm(obj=ally)
    
    # Pre-poblar los campos del usuario
    if request.method == 'GET':
        form.name.data = user.name
        form.email.data = user.email
    
    if form.validate_on_submit():
        # Actualizar datos de usuario
        user.name = form.name.data
        user.email = form.email.data
        
        if form.password.data:  # Solo cambiar la contraseña si se proporciona una nueva
            user.set_password(form.password.data)
        
        # Actualizar datos del aliado
        ally.specialty = form.specialty.data
        ally.organization = form.organization.data
        ally.experience = form.experience.data
        ally.availability = form.availability.data
        
        db.session.commit()
        flash('Aliado actualizado exitosamente', 'success')
        return redirect(url_for('admin_allies.list_allies'))
    
    return render_template('admin/user_form.html', form=form, title='Editar Aliado')

@admin_allies.route('/admin/allies/<int:ally_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_ally(ally_id):
    """Vista para eliminar un aliado"""
    ally = Ally.query.get_or_404(ally_id)
    user = User.query.get(ally.user_id)
    
    # Eliminar relaciones existentes
    Relationship.query.filter_by(ally_id=ally_id).delete()
    
    # Eliminar aliado y usuario
    db.session.delete(ally)
    db.session.delete(user)
    db.session.commit()
    
    flash('Aliado eliminado exitosamente', 'success')
    return redirect(url_for('admin_allies.list_allies'))

@admin_allies.route('/admin/assign_ally', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_ally():
    """Vista para asignar aliados a emprendedores"""
    form = AssignAllyForm()
    
    if form.validate_on_submit():
        # Verificar si ya existe una relación
        existing = Relationship.query.filter_by(
            entrepreneur_id=form.entrepreneur.data,
            ally_id=form.ally.data
        ).first()
        
        if existing:
            flash('Esta relación ya existe', 'warning')
        else:
            # Crear nueva relación
            relationship = Relationship(
                entrepreneur_id=form.entrepreneur.data,
                ally_id=form.ally.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                hours_assigned=form.hours.data,
                status='active'
            )
            db.session.add(relationship)
            db.session.commit()
            flash('Aliado asignado exitosamente', 'success')
            
        return redirect(url_for('admin_allies.assign_ally'))
    
    # Obtener relaciones existentes para mostrar
    relationships = Relationship.query.all()
    return render_template('admin/assign_ally.html', form=form, relationships=relationships)