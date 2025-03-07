from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.user import User
from app.forms.entrepreneur import ProfileForm, BusinessInfoForm
from app.utils.decorators import entrepreneur_required
from app.utils.validators import allowed_file

# Crear el Blueprint para el perfil del emprendedor
entrepreneur_profile = Blueprint('entrepreneur_profile', __name__)

@entrepreneur_profile.route('/profile')
@login_required
@entrepreneur_required
def view_profile():
    """Vista para ver el perfil del emprendedor"""
    # Obtener perfil del emprendedor
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    return render_template(
        'entrepreneur/profile.html',
        entrepreneur=entrepreneur
    )

@entrepreneur_profile.route('/profile/edit', methods=['GET', 'POST'])
@login_required
@entrepreneur_required
def edit_profile():
    """Vista para editar el perfil del emprendedor"""
    # Obtener perfil del emprendedor
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    user = User.query.get(current_user.id)
    
    form = ProfileForm(obj=entrepreneur)
    
    # Pre-poblar los campos del usuario
    if request.method == 'GET':
        form.name.data = user.name
        form.email.data = user.email
    
    if form.validate_on_submit():
        # Actualizar datos del usuario
        user.name = form.name.data
        user.email = form.email.data
        
        if form.password.data:  # Solo actualizar la contraseña si se proporciona una nueva
            user.set_password(form.password.data)
        
        # Actualizar datos del emprendedor
        entrepreneur.phone = form.phone.data
        entrepreneur.date_of_birth = form.date_of_birth.data
        entrepreneur.location = form.location.data
        entrepreneur.bio = form.bio.data
        
        # Manejar la carga de imagen de perfil
        if form.profile_image.data:
            if allowed_file(form.profile_image.data.filename):
                filename = secure_filename(form.profile_image.data.filename)
                # Crear nombre de archivo único
                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                
                # Guardar el archivo
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profiles')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                file_path = os.path.join(upload_folder, unique_filename)
                form.profile_image.data.save(file_path)
                
                # Actualizar ruta de imagen en la base de datos
                entrepreneur.profile_image = f"/static/uploads/profiles/{unique_filename}"
            else:
                flash('Formato de archivo no permitido. Use JPG, PNG o GIF.', 'error')
        
        # Guardar cambios
        db.session.commit()
        flash('Perfil actualizado exitosamente', 'success')
        return redirect(url_for('entrepreneur_profile.view_profile'))
    
    return render_template(
        'entrepreneur/profile_form.html',
        form=form,
        entrepreneur=entrepreneur
    )

@entrepreneur_profile.route('/profile/business', methods=['GET', 'POST'])
@login_required
@entrepreneur_required
def edit_business_info():
    """Vista para editar la información del negocio/emprendimiento"""
    # Obtener perfil del emprendedor
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    form = BusinessInfoForm(obj=entrepreneur)
    
    if form.validate_on_submit():
        # Actualizar datos del negocio
        entrepreneur.business_name = form.business_name.data
        entrepreneur.business_description = form.business_description.data
        entrepreneur.business_sector = form.business_sector.data
        entrepreneur.business_stage = form.business_stage.data
        entrepreneur.founding_date = form.founding_date.data
        entrepreneur.team_size = form.team_size.data
        entrepreneur.website = form.website.data
        entrepreneur.social_media = form.social_media.data
        
        # Manejar la carga del logo del negocio
        if form.business_logo.data:
            if allowed_file(form.business_logo.data.filename):
                filename = secure_filename(form.business_logo.data.filename)
                # Crear nombre de archivo único
                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                
                # Guardar el archivo
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'logos')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                file_path = os.path.join(upload_folder, unique_filename)
                form.business_logo.data.save(file_path)
                
                # Actualizar ruta del logo en la base de datos
                entrepreneur.business_logo = f"/static/uploads/logos/{unique_filename}"
            else:
                flash('Formato de archivo no permitido. Use JPG, PNG o GIF.', 'error')
        
        # Guardar cambios
        db.session.commit()
        flash('Información del negocio actualizada exitosamente', 'success')
        return redirect(url_for('entrepreneur_profile.view_profile'))
    
    return render_template(
        'entrepreneur/business_form.html',
        form=form,
        entrepreneur=entrepreneur
    )

@entrepreneur_profile.route('/profile/financial', methods=['GET', 'POST'])
@login_required
@entrepreneur_required
def edit_financial_info():
    """Vista para editar la información financiera del emprendimiento"""
    # Obtener perfil del emprendedor
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        # Actualizar datos financieros
        entrepreneur.revenue = request.form.get('revenue')
        entrepreneur.funding_stage = request.form.get('funding_stage')
        entrepreneur.investment_received = request.form.get('investment_received')
        entrepreneur.seeking_investment = 'seeking_investment' in request.form
        entrepreneur.seeking_amount = request.form.get('seeking_amount')
        entrepreneur.currency = request.form.get('currency', 'USD')
        
        # Guardar cambios
        db.session.commit()
        flash('Información financiera actualizada exitosamente', 'success')
        return redirect(url_for('entrepreneur_profile.view_profile'))
    
    return render_template(
        'entrepreneur/financial_form.html',
        entrepreneur=entrepreneur
    )

@entrepreneur_profile.route('/profile/export')
@login_required
@entrepreneur_required
def export_profile():
    """Exportar perfil del emprendedor como PDF"""
    from app.utils.pdf import generate_profile_pdf
    
    # Obtener perfil del emprendedor
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Generar el PDF
    pdf_data = generate_profile_pdf(entrepreneur)
    
    # Configurar respuesta para descarga de archivo
    from flask import Response
    filename = f"perfil_{entrepreneur.business_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(
        pdf_data,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )