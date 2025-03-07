from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.ally import Ally, AllySpecialty, AllyExperience
from app.models.user import User
from app.forms.ally import AllyProfileForm, AllyExperienceForm, AllySpecialtyForm
from app.utils.decorators import ally_required
from app.utils.formatters import format_date
from app.services.storage import upload_file

# Crear el Blueprint para las vistas de perfil del aliado
bp = Blueprint('ally_profile', __name__, url_prefix='/ally/profile')

@bp.route('/', methods=['GET'])
@login_required
@ally_required
def profile():
    """Vista del perfil del aliado"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener especialidades y experiencias del aliado
    specialties = AllySpecialty.query.filter_by(ally_id=ally.id).all()
    experiences = AllyExperience.query.filter_by(ally_id=ally.id).order_by(AllyExperience.end_date.desc()).all()
    
    # Obtener estadísticas básicas
    stats = {
        'total_entrepreneurs': len(ally.entrepreneurs),
        'total_hours': sum([relationship.hours for relationship in ally.relationships]),
        'avg_rating': sum([relationship.entrepreneur_rating or 0 for relationship in ally.relationships 
                         if relationship.entrepreneur_rating]) / len([r for r in ally.relationships 
                                                                     if r.entrepreneur_rating]) if [r for r in ally.relationships 
                                                                                                   if r.entrepreneur_rating] else 0
    }
    
    return render_template('ally/profile.html', 
                           ally=ally, 
                           specialties=specialties, 
                           experiences=experiences,
                           stats=stats)

@bp.route('/edit', methods=['GET', 'POST'])
@login_required
@ally_required
def edit_profile():
    """Vista para editar el perfil del aliado"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = AllyProfileForm(obj=ally)
    
    if form.validate_on_submit():
        # Actualizar datos del perfil
        form.populate_obj(ally)
        
        # Manejar la subida de la foto de perfil si se proporcionó una
        if 'profile_picture' in request.files and request.files['profile_picture'].filename:
            file = request.files['profile_picture']
            filename = upload_file(file, 'ally_profiles')
            ally.profile_picture = filename
        
        # Guardar cambios en la base de datos
        db.session.commit()
        
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('ally_profile.profile'))
    
    return render_template('ally/profile_edit.html', form=form, ally=ally)

@bp.route('/specialty/add', methods=['GET', 'POST'])
@login_required
@ally_required
def add_specialty():
    """Vista para añadir una especialidad al perfil del aliado"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Crear formulario para especialidad
    form = AllySpecialtyForm()
    
    if form.validate_on_submit():
        # Crear nueva especialidad
        specialty = AllySpecialty(
            ally_id=ally.id,
            name=form.name.data,
            description=form.description.data,
            level=form.level.data
        )
        
        # Guardar en la base de datos
        db.session.add(specialty)
        db.session.commit()
        
        flash('Especialidad añadida correctamente', 'success')
        return redirect(url_for('ally_profile.profile'))
    
    return render_template('ally/specialty_form.html', form=form)

@bp.route('/specialty/<int:specialty_id>/edit', methods=['GET', 'POST'])
@login_required
@ally_required
def edit_specialty(specialty_id):
    """Vista para editar una especialidad existente"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la especialidad específica y verificar que pertenezca al aliado
    specialty = AllySpecialty.query.filter_by(id=specialty_id, ally_id=ally.id).first_or_404()
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = AllySpecialtyForm(obj=specialty)
    
    if form.validate_on_submit():
        # Actualizar datos de la especialidad
        form.populate_obj(specialty)
        
        # Guardar cambios en la base de datos
        db.session.commit()
        
        flash('Especialidad actualizada correctamente', 'success')
        return redirect(url_for('ally_profile.profile'))
    
    return render_template('ally/specialty_form.html', form=form, specialty=specialty)

@bp.route('/specialty/<int:specialty_id>/delete', methods=['POST'])
@login_required
@ally_required
def delete_specialty(specialty_id):
    """Vista para eliminar una especialidad"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la especialidad específica y verificar que pertenezca al aliado
    specialty = AllySpecialty.query.filter_by(id=specialty_id, ally_id=ally.id).first_or_404()
    
    # Eliminar de la base de datos
    db.session.delete(specialty)
    db.session.commit()
    
    flash('Especialidad eliminada correctamente', 'success')
    return redirect(url_for('ally_profile.profile'))

@bp.route('/experience/add', methods=['GET', 'POST'])
@login_required
@ally_required
def add_experience():
    """Vista para añadir una experiencia al perfil del aliado"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Crear formulario para experiencia
    form = AllyExperienceForm()
    
    if form.validate_on_submit():
        # Crear nueva experiencia
        experience = AllyExperience(
            ally_id=ally.id,
            company=form.company.data,
            title=form.title.data,
            description=form.description.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            current=form.current.data
        )
        
        # Si es trabajo actual, establecer end_date como None
        if form.current.data:
            experience.end_date = None
        
        # Guardar en la base de datos
        db.session.add(experience)
        db.session.commit()
        
        flash('Experiencia añadida correctamente', 'success')
        return redirect(url_for('ally_profile.profile'))
    
    return render_template('ally/experience_form.html', form=form)

@bp.route('/experience/<int:experience_id>/edit', methods=['GET', 'POST'])
@login_required
@ally_required
def edit_experience(experience_id):
    """Vista para editar una experiencia existente"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la experiencia específica y verificar que pertenezca al aliado
    experience = AllyExperience.query.filter_by(id=experience_id, ally_id=ally.id).first_or_404()
    
    # Crear formulario y pre-poblarlo con datos existentes
    form = AllyExperienceForm(obj=experience)
    
    if form.validate_on_submit():
        # Actualizar datos de la experiencia
        form.populate_obj(experience)
        
        # Si es trabajo actual, establecer end_date como None
        if form.current.data:
            experience.end_date = None
        
        # Guardar cambios en la base de datos
        db.session.commit()
        
        flash('Experiencia actualizada correctamente', 'success')
        return redirect(url_for('ally_profile.profile'))
    
    return render_template('ally/experience_form.html', form=form, experience=experience)

@bp.route('/experience/<int:experience_id>/delete', methods=['POST'])
@login_required
@ally_required
def delete_experience(experience_id):
    """Vista para eliminar una experiencia"""
    # Obtener el perfil del aliado asociado al usuario actual
    ally = Ally.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Obtener la experiencia específica y verificar que pertenezca al aliado
    experience = AllyExperience.query.filter_by(id=experience_id, ally_id=ally.id).first_or_404()
    
    # Eliminar de la base de datos
    db.session.delete(experience)
    db.session.commit()
    
    flash('Experiencia eliminada correctamente', 'success')
    return redirect(url_for('ally_profile.profile'))