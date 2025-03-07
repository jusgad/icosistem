# app/views/entrepreneur/documents.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from app.models.document import Document
from app.models.entrepreneur import Entrepreneur
from app.forms.entrepreneur import DocumentUploadForm, DocumentShareForm
from app.extensions import db
from app.utils.decorators import entrepreneur_required
from app.utils.notifications import send_notification
from app.services.storage import upload_file, get_file, delete_file

# Crear blueprint para las rutas de documentos de emprendedor
documents_bp = Blueprint('entrepreneur_documents', __name__, url_prefix='/entrepreneur/documents')

@documents_bp.route('/', methods=['GET'])
@login_required
@entrepreneur_required
def index():
    """Vista principal de documentos del emprendedor."""
    # Obtener todos los documentos del emprendedor actual
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    documents = Document.query.filter_by(entrepreneur_id=entrepreneur.id).order_by(Document.created_at.desc()).all()
    
    # Agrupar documentos por categoría
    document_categories = {}
    for doc in documents:
        if doc.category not in document_categories:
            document_categories[doc.category] = []
        document_categories[doc.category].append(doc)
    
    return render_template('entrepreneur/documents.html', 
                          documents=documents,
                          document_categories=document_categories,
                          upload_form=DocumentUploadForm())

@documents_bp.route('/upload', methods=['POST'])
@login_required
@entrepreneur_required
def upload_document():
    """Subir un nuevo documento."""
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Obtener archivo y asegurar nombre de archivo
        file = form.file.data
        filename = secure_filename(file.filename)
        
        # Generar ruta para guardar el archivo
        file_path = f"entrepreneurs/{entrepreneur.id}/documents/{form.category.data}/{filename}"
        
        # Subir archivo al servicio de almacenamiento
        file_url = upload_file(file, file_path)
        
        # Crear registro en la base de datos
        document = Document(
            name=form.name.data,
            description=form.description.data,
            category=form.category.data,
            file_path=file_path,
            file_url=file_url,
            file_type=file.content_type,
            file_size=os.fstat(file.fileno()).st_size,  # Tamaño en bytes
            entrepreneur_id=entrepreneur.id,
            created_by=current_user.id
        )
        
        db.session.add(document)
        db.session.commit()
        
        flash('Documento subido exitosamente', 'success')
        
        # Si el documento debe ser compartido con el aliado
        if form.share_with_ally.data and entrepreneur.ally:
            # Compartir documento con el aliado
            document.shared_with_ally = True
            db.session.commit()
            
            # Notificar al aliado
            notification_message = f"El emprendedor {entrepreneur.business_name} ha compartido un nuevo documento: {form.name.data}"
            send_notification(entrepreneur.ally.user_id, 'new_document', notification_message, 
                             link=url_for('ally.entrepreneurs.view_document', document_id=document.id))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {getattr(form, field).label.text}: {error}", 'error')
    
    return redirect(url_for('entrepreneur_documents.index'))

@documents_bp.route('/<int:document_id>', methods=['GET'])
@login_required
@entrepreneur_required
def view_document(document_id):
    """Ver detalles de un documento específico."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    document = Document.query.filter_by(id=document_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    share_form = DocumentShareForm(obj=document)
    
    return render_template('entrepreneur/document_detail.html',
                          document=document,
                          share_form=share_form)

@documents_bp.route('/<int:document_id>/download', methods=['GET'])
@login_required
@entrepreneur_required
def download_document(document_id):
    """Descargar un documento."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    document = Document.query.filter_by(id=document_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    # Registrar la descarga
    document.download_count += 1
    document.last_downloaded_at = datetime.utcnow()
    db.session.commit()
    
    # Obtener archivo del servicio de almacenamiento
    temp_file_path = get_file(document.file_path)
    
    return send_file(
        temp_file_path,
        as_attachment=True,
        download_name=document.name,
        mimetype=document.file_type
    )

@documents_bp.route('/<int:document_id>/share', methods=['POST'])
@login_required
@entrepreneur_required
def share_document(document_id):
    """Compartir un documento con el aliado."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    document = Document.query.filter_by(id=document_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    form = DocumentShareForm()
    
    if form.validate_on_submit():
        # Actualizar estado de compartición
        document.shared_with_ally = form.shared_with_ally.data
        document.share_notes = form.share_notes.data
        document.last_shared_at = datetime.utcnow() if form.shared_with_ally.data else None
        
        db.session.commit()
        
        if form.shared_with_ally.data and entrepreneur.ally:
            # Notificar al aliado
            notification_message = f"El emprendedor {entrepreneur.business_name} ha compartido un documento: {document.name}"
            send_notification(entrepreneur.ally.user_id, 'document_shared', notification_message, 
                             link=url_for('ally.entrepreneurs.view_document', document_id=document.id))
            
            flash('Documento compartido con tu aliado exitosamente', 'success')
        else:
            flash('Documento actualizado exitosamente', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en {getattr(form, field).label.text}: {error}", 'error')
    
    return redirect(url_for('entrepreneur_documents.view_document', document_id=document_id))

@documents_bp.route('/<int:document_id>/delete', methods=['POST'])
@login_required
@entrepreneur_required
def delete_document(document_id):
    """Eliminar un documento."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    document = Document.query.filter_by(id=document_id, entrepreneur_id=entrepreneur.id).first_or_404()
    
    # Eliminar archivo del servicio de almacenamiento
    delete_file(document.file_path)
    
    # Eliminar registro de la base de datos
    db.session.delete(document)
    db.session.commit()
    
    flash('Documento eliminado exitosamente', 'success')
    return redirect(url_for('entrepreneur_documents.index'))

@documents_bp.route('/categories', methods=['GET'])
@login_required
@entrepreneur_required
def list_categories():
    """Listar categorías de documentos disponibles."""
    # Esto podría venir de una configuración o tabla en la base de datos
    categories = current_app.config.get('DOCUMENT_CATEGORIES', [
        'plan_de_negocio',
        'legal',
        'financiero',
        'marketing',
        'producto',
        'recursos_humanos',
        'otros'
    ])
    
    return render_template('entrepreneur/document_categories.html', categories=categories)

@documents_bp.route('/category/<category>', methods=['GET'])
@login_required
@entrepreneur_required
def view_category(category):
    """Ver documentos de una categoría específica."""
    entrepreneur = Entrepreneur.query.filter_by(user_id=current_user.id).first_or_404()
    documents = Document.query.filter_by(
        entrepreneur_id=entrepreneur.id,
        category=category
    ).order_by(Document.created_at.desc()).all()
    
    return render_template('entrepreneur/documents_by_category.html',
                          category=category,
                          documents=documents,
                          upload_form=DocumentUploadForm(category=category))