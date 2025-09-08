"""
Gestión de Documentos del Emprendedor - Vista completa para almacenamiento y organización.

Este módulo contiene todas las vistas relacionadas con la gestión de documentos
del emprendedor, incluyendo upload, organización, compartir, versionado,
búsqueda, analytics y integración con servicios externos.
"""

import os
import json
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
import zipfile
from io import BytesIO
import hashlib
from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app, g, send_file, abort, stream_template
)
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, asc, func, text
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF para PDFs

from app.core.permissions import require_role
from app.core.exceptions import ValidationError, PermissionError, ResourceNotFoundError, FileError
from app.models.entrepreneur import Entrepreneur
from app.models.document import (
    Document, DocumentType, DocumentCategory, DocumentVersion,
    DocumentAccess, AccessLevel, DocumentTag, DocumentFolder
)
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.mentorship import MentorshipSession
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.models.user import User
from app.forms.document import (
    DocumentUploadForm, DocumentEditForm, DocumentSearchForm,
    FolderForm, ShareDocumentForm, DocumentVersionForm,
    BulkActionForm, DocumentSettingsForm
)
from app.services.entrepreneur_service import EntrepreneurService
from app.services.file_storage import FileStorageService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.google_calendar import GoogleCalendarService
from app.utils.decorators import cache_response, rate_limit, validate_json
from app.utils.validators import validate_file_type, validate_file_size
from app.utils.formatters import format_file_size, format_date_short
from app.utils.file_utils import (
    get_file_extension, generate_unique_filename, get_file_type,
    create_thumbnail, extract_text_content, generate_file_hash,
    compress_image, is_image_file, is_pdf_file, is_office_file
)
from app.utils.string_utils import sanitize_input, generate_slug, extract_keywords
from app.utils.crypto_utils import encrypt_file, decrypt_file
from app.utils.export_utils import create_zip_archive
from app.utils.pagination import get_pagination_params

# Crear blueprint para documentos del emprendedor
entrepreneur_documents = Blueprint(
    'entrepreneur_documents', 
    __name__, 
    url_prefix='/entrepreneur/documents'
)

# Configuraciones
DOCUMENTS_PER_PAGE = 20
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_STORAGE = 5 * 1024 * 1024 * 1024  # 5GB por emprendedor
THUMBNAIL_SIZE = (300, 300)
PREVIEW_SIZE = (800, 600)

# Tipos de archivo permitidos
ALLOWED_EXTENSIONS = {
    'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
    'spreadsheets': {'xls', 'xlsx', 'csv', 'ods'},
    'presentations': {'ppt', 'pptx', 'odp'},
    'images': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'},
    'archives': {'zip', 'rar', '7z', 'tar', 'gz'},
    'other': {'json', 'xml', 'yaml', 'md'}
}

ALL_ALLOWED_EXTENSIONS = set()
for extensions in ALLOWED_EXTENSIONS.values():
    ALL_ALLOWED_EXTENSIONS.update(extensions)

# Configuración de watermarks
WATERMARK_TEXT = "CONFIDENCIAL - {empresa}"
WATERMARK_OPACITY = 0.3


@entrepreneur_documents.before_request
def load_entrepreneur():
    """Cargar datos del emprendedor antes de cada request."""
    if current_user.is_authenticated and hasattr(current_user, 'entrepreneur_profile'):
        g.entrepreneur = current_user.entrepreneur_profile
        g.entrepreneur_service = EntrepreneurService(g.entrepreneur)
        g.file_storage = FileStorageService()
    else:
        g.entrepreneur = None
        g.entrepreneur_service = None
        g.file_storage = None


@entrepreneur_documents.route('/')
@entrepreneur_documents.route('/list')
@login_required
@require_role('entrepreneur')
@cache_response(timeout=300)  # Cache por 5 minutos
def index():
    """
    Vista principal de documentos del emprendedor.
    
    Incluye:
    - Listado paginado con filtros avanzados
    - Organización por carpetas y categorías
    - Búsqueda full-text
    - Vista previa de documentos
    - Métricas de almacenamiento
    - Acciones masivas
    """
    try:
        # Obtener parámetros de filtrado y paginación
        page, per_page = get_pagination_params(request, default_per_page=DOCUMENTS_PER_PAGE)
        search_form = DocumentSearchForm(request.args)
        
        # Vista (grid o lista)
        view_type = request.args.get('view', 'grid')
        
        # Carpeta actual
        folder_id = request.args.get('folder_id', type=int)
        current_folder = None
        if folder_id:
            current_folder = DocumentFolder.query.filter_by(
                id=folder_id,
                entrepreneur_id=g.entrepreneur.id
            ).first()
        
        # Construir query base
        query = Document.query.filter_by(
            uploaded_by=current_user.id,
            is_deleted=False
        )
        
        # Filtrar por carpeta
        if current_folder:
            query = query.filter_by(folder_id=folder_id)
        elif folder_id is None:  # Solo mostrar documentos sin carpeta si no se especifica carpeta
            query = query.filter_by(folder_id=None)
        
        # Aplicar filtros de búsqueda
        query = _apply_document_filters(query, search_form)
        
        # Ordenamiento
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        query = _apply_document_sorting(query, sort_by, sort_order)
        
        # Optimizar consultas
        query = query.options(
            joinedload(Document.folder),
            joinedload(Document.project),
            selectinload(Document.tags),
            selectinload(Document.versions)
        )
        
        # Paginación
        documents_pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Obtener carpetas del emprendedor
        folders = DocumentFolder.query.filter_by(
            entrepreneur_id=g.entrepreneur.id,
            parent_id=folder_id  # Subcarpetas de la carpeta actual
        ).order_by(DocumentFolder.name).all()
        
        # Breadcrumb de navegación
        breadcrumb = _build_folder_breadcrumb(current_folder)
        
        # Métricas de almacenamiento
        storage_metrics = _get_storage_metrics(g.entrepreneur.id)
        
        # Documentos recientes
        recent_documents = _get_recent_documents(g.entrepreneur.id, limit=5)
        
        # Documentos compartidos conmigo
        shared_with_me = _get_shared_documents(current_user.id, limit=5)
        
        # Tags más utilizados
        popular_tags = _get_popular_tags(g.entrepreneur.id, limit=10)
        
        return render_template(
            'entrepreneur/documents/index.html',
            documents=documents_pagination.items,
            pagination=documents_pagination,
            folders=folders,
            current_folder=current_folder,
            breadcrumb=breadcrumb,
            search_form=search_form,
            storage_metrics=storage_metrics,
            recent_documents=recent_documents,
            shared_with_me=shared_with_me,
            popular_tags=popular_tags,
            view_type=view_type,
            current_sort=f"{sort_by}_{sort_order}",
            DocumentType=DocumentType,
            DocumentCategory=DocumentCategory,
            allowed_extensions=ALL_ALLOWED_EXTENSIONS
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando documentos: {str(e)}")
        flash('Error cargando los documentos', 'error')
        return redirect(url_for('entrepreneur_dashboard.index'))


@entrepreneur_documents.route('/upload', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def upload():
    """
    Subir nuevos documentos.
    """
    form = DocumentUploadForm()
    
    if request.method == 'GET':
        # Cargar opciones del formulario
        _populate_upload_form_choices(form)
        
        # Verificar espacio disponible
        storage_info = _get_storage_info(g.entrepreneur.id)
        
        # Carpeta de destino sugerida
        suggested_folder_id = request.args.get('folder_id', type=int)
        if suggested_folder_id:
            form.folder_id.data = suggested_folder_id
        
        return render_template(
            'entrepreneur/documents/upload.html',
            form=form,
            storage_info=storage_info,
            max_file_size=MAX_FILE_SIZE,
            allowed_extensions=ALL_ALLOWED_EXTENSIONS
        )
    
    try:
        # Validar formulario básico
        if not form.validate_on_submit():
            _populate_upload_form_choices(form)
            return render_template(
                'entrepreneur/documents/upload.html',
                form=form,
                max_file_size=MAX_FILE_SIZE
            )
        
        # Verificar archivos
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            flash('No se seleccionaron archivos', 'error')
            _populate_upload_form_choices(form)
            return render_template('entrepreneur/documents/upload.html', form=form)
        
        # Verificar espacio de almacenamiento
        total_size = sum(len(f.read()) for f in files)
        for f in files:
            f.seek(0)  # Resetear puntero
        
        if not _check_storage_capacity(g.entrepreneur.id, total_size):
            flash('No hay suficiente espacio de almacenamiento disponible', 'error')
            _populate_upload_form_choices(form)
            return render_template('entrepreneur/documents/upload.html', form=form)
        
        # Procesar cada archivo
        uploaded_documents = []
        errors = []
        
        for file in files:
            if file.filename == '':
                continue
            
            try:
                # Validar archivo individual
                validation_result = _validate_uploaded_file(file)
                if not validation_result['valid']:
                    errors.append(f"{file.filename}: {validation_result['error']}")
                    continue
                
                # Procesar y guardar archivo
                document = _process_and_save_file(file, form)
                uploaded_documents.append(document)
                
            except Exception as e:
                current_app.logger.error(f"Error procesando archivo {file.filename}: {str(e)}")
                errors.append(f"{file.filename}: Error procesando archivo")
        
        # Registrar actividad masiva
        if uploaded_documents:
            ActivityLog.create(
                user_id=current_user.id,
                action='documents_uploaded',
                resource_type='document',
                details={
                    'files_count': len(uploaded_documents),
                    'total_size': total_size,
                    'file_names': [doc.filename for doc in uploaded_documents]
                }
            )
            
            # Enviar notificaciones si es necesario
            _send_upload_notifications(uploaded_documents, form)
        
        # Mostrar resultados
        if uploaded_documents and not errors:
            flash(f'{len(uploaded_documents)} archivo(s) subido(s) exitosamente', 'success')
        elif uploaded_documents and errors:
            flash(f'{len(uploaded_documents)} archivo(s) subido(s), {len(errors)} error(es)', 'warning')
            for error in errors[:3]:  # Mostrar máximo 3 errores
                flash(error, 'error')
        else:
            flash('No se pudo subir ningún archivo', 'error')
            for error in errors[:3]:
                flash(error, 'error')
        
        # Redireccionar según el resultado
        if uploaded_documents:
            if len(uploaded_documents) == 1:
                return redirect(url_for('entrepreneur_documents.view', 
                                      document_id=uploaded_documents[0].id))
            else:
                folder_id = form.folder_id.data
                redirect_url = url_for('entrepreneur_documents.index')
                if folder_id:
                    redirect_url += f'?folder_id={folder_id}'
                return redirect(redirect_url)
        else:
            _populate_upload_form_choices(form)
            return render_template('entrepreneur/documents/upload.html', form=form)

    except Exception as e:
        current_app.logger.error(f"Error en upload de documentos: {str(e)}")
        flash('Error subiendo los archivos', 'error')
        _populate_upload_form_choices(form)
        return render_template('entrepreneur/documents/upload.html', form=form)


@entrepreneur_documents.route('/<int:document_id>')
@entrepreneur_documents.route('/<int:document_id>/view')
@login_required
@require_role('entrepreneur')
def view(document_id):
    """
    Ver detalles completos de un documento.
    """
    try:
        # Obtener documento con validación de acceso
        document = _get_document_or_404(document_id)
        
        # Verificar permisos de lectura
        if not _can_read_document(document, current_user.id):
            flash('No tienes permisos para ver este documento', 'error')
            return redirect(url_for('entrepreneur_documents.index'))
        
        # Registrar acceso
        _register_document_access(document, current_user.id, 'view')
        
        # Obtener versiones del documento
        versions = DocumentVersion.query.filter_by(
            document_id=document.id
        ).order_by(desc(DocumentVersion.created_at)).all()
        
        # Obtener accesos compartidos
        shared_accesses = DocumentAccess.query.filter_by(
            document_id=document.id
        ).options(joinedload(DocumentAccess.user)).all()
        
        # Historial de actividad
        activity_history = ActivityLog.query.filter_by(
            resource_type='document',
            resource_id=document.id
        ).order_by(desc(ActivityLog.created_at)).limit(20).all()
        
        # Documentos relacionados
        related_documents = _get_related_documents(document, limit=5)
        
        # Verificar si puede editar/eliminar
        can_edit = _can_edit_document(document, current_user.id)
        can_delete = _can_delete_document(document, current_user.id)
        can_share = _can_share_document(document, current_user.id)
        
        # Información de preview
        preview_info = _get_document_preview_info(document)
        
        # Metadatos del archivo
        file_metadata = _extract_file_metadata(document)
        
        return render_template(
            'entrepreneur/documents/view.html',
            document=document,
            versions=versions,
            shared_accesses=shared_accesses,
            activity_history=activity_history,
            related_documents=related_documents,
            can_edit=can_edit,
            can_delete=can_delete,
            can_share=can_share,
            preview_info=preview_info,
            file_metadata=file_metadata,
            DocumentType=DocumentType,
            AccessLevel=AccessLevel
        )

    except ResourceNotFoundError:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('entrepreneur_documents.index'))
    except Exception as e:
        current_app.logger.error(f"Error mostrando documento {document_id}: {str(e)}")
        flash('Error cargando el documento', 'error')
        return redirect(url_for('entrepreneur_documents.index'))


@entrepreneur_documents.route('/<int:document_id>/download')
@login_required
@require_role('entrepreneur')
@rate_limit(requests=30, window=300)  # 30 descargas por 5 minutos
def download(document_id):
    """
    Descargar documento.
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos de descarga
        if not _can_download_document(document, current_user.id):
            abort(403)
        
        # Registrar descarga
        _register_document_access(document, current_user.id, 'download')
        
        # Obtener ruta del archivo
        file_path = g.file_storage.get_file_path(document.file_path)
        
        if not os.path.exists(file_path):
            current_app.logger.error(f"Archivo físico no encontrado: {file_path}")
            flash('Archivo no encontrado en el almacenamiento', 'error')
            return redirect(url_for('entrepreneur_documents.view', document_id=document_id))
        
        # Aplicar watermark si es necesario
        if _should_apply_watermark(document):
            watermarked_path = _apply_watermark_to_file(document, file_path)
            if watermarked_path:
                file_path = watermarked_path
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=document.original_filename,
            mimetype=document.mime_type
        )

    except ResourceNotFoundError:
        abort(404)
    except Exception as e:
        current_app.logger.error(f"Error descargando documento {document_id}: {str(e)}")
        abort(500)


@entrepreneur_documents.route('/<int:document_id>/preview')
@login_required
@require_role('entrepreneur')
def preview(document_id):
    """
    Vista previa de documento.
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos
        if not _can_read_document(document, current_user.id):
            abort(403)
        
        # Registrar acceso
        _register_document_access(document, current_user.id, 'preview')
        
        # Generar preview según tipo de archivo
        preview_data = _generate_document_preview(document)
        
        if not preview_data:
            flash('Vista previa no disponible para este tipo de archivo', 'info')
            return redirect(url_for('entrepreneur_documents.view', document_id=document_id))
        
        return render_template(
            'entrepreneur/documents/preview.html',
            document=document,
            preview_data=preview_data
        )

    except ResourceNotFoundError:
        abort(404)
    except Exception as e:
        current_app.logger.error(f"Error generando preview del documento {document_id}: {str(e)}")
        abort(500)


@entrepreneur_documents.route('/<int:document_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def edit(document_id):
    """
    Editar metadatos de documento.
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos
        if not _can_edit_document(document, current_user.id):
            flash('No tienes permisos para editar este documento', 'error')
            return redirect(url_for('entrepreneur_documents.view', document_id=document_id))
        
        form = DocumentEditForm(obj=document)
        
        if request.method == 'GET':
            _populate_edit_form_choices(form)
            _populate_form_with_document_data(form, document)
            
            return render_template(
                'entrepreneur/documents/edit.html',
                form=form,
                document=document
            )
        
        if not form.validate_on_submit():
            _populate_edit_form_choices(form)
            return render_template(
                'entrepreneur/documents/edit.html',
                form=form,
                document=document
            )
        
        # Guardar datos originales para auditoria
        original_data = _extract_document_metadata(document)
        
        # Actualizar documento
        document.title = sanitize_input(form.title.data)
        document.description = sanitize_input(form.description.data)
        document.document_type = form.document_type.data
        document.category = form.category.data
        document.folder_id = form.folder_id.data if form.folder_id.data else None
        document.project_id = form.project_id.data if form.project_id.data else None
        document.is_confidential = form.is_confidential.data
        document.updated_at = datetime.now(timezone.utc)
        
        # Actualizar tags
        _update_document_tags(document, form.tags.data)
        
        document.save()
        
        # Detectar cambios significativos
        changes = _detect_document_changes(original_data, document)
        
        if changes:
            # Registrar actividad
            ActivityLog.create(
                user_id=current_user.id,
                action='document_updated',
                resource_type='document',
                resource_id=document.id,
                details={
                    'changes': changes,
                    'document_title': document.title
                }
            )
            
            # Notificar a usuarios con acceso si hay cambios significativos
            if any(key in changes for key in ['title', 'description', 'category']):
                _notify_document_access_users(document, 'updated')
        
        flash('Documento actualizado exitosamente', 'success')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))

    except ResourceNotFoundError:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('entrepreneur_documents.index'))
    except Exception as e:
        current_app.logger.error(f"Error editando documento {document_id}: {str(e)}")
        flash('Error actualizando el documento', 'error')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))


@entrepreneur_documents.route('/<int:document_id>/share', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def share(document_id):
    """
    Compartir documento con otros usuarios.
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos
        if not _can_share_document(document, current_user.id):
            flash('No tienes permisos para compartir este documento', 'error')
            return redirect(url_for('entrepreneur_documents.view', document_id=document_id))
        
        form = ShareDocumentForm()
        
        if request.method == 'GET':
            # Obtener usuarios disponibles para compartir
            available_users = _get_shareable_users(g.entrepreneur.id)
            form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in available_users]
            
            # Accesos actuales
            current_accesses = DocumentAccess.query.filter_by(
                document_id=document.id
            ).options(joinedload(DocumentAccess.user)).all()
            
            return render_template(
                'entrepreneur/documents/share.html',
                form=form,
                document=document,
                current_accesses=current_accesses,
                AccessLevel=AccessLevel
            )
        
        if not form.validate_on_submit():
            available_users = _get_shareable_users(g.entrepreneur.id)
            form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in available_users]
            return render_template(
                'entrepreneur/documents/share.html',
                form=form,
                document=document
            )
        
        # Verificar que no se esté compartiendo con el mismo usuario
        target_user_id = form.user_id.data
        if target_user_id == current_user.id:
            form.user_id.errors.append('No puedes compartir contigo mismo')
            available_users = _get_shareable_users(g.entrepreneur.id)
            form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in available_users]
            return render_template('entrepreneur/documents/share.html', form=form, document=document)
        
        # Verificar que no exista acceso previo
        existing_access = DocumentAccess.query.filter_by(
            document_id=document.id,
            user_id=target_user_id
        ).first()
        
        if existing_access:
            # Actualizar nivel de acceso existente
            existing_access.access_level = form.access_level.data
            existing_access.expires_at = form.expires_at.data
            existing_access.updated_at = datetime.now(timezone.utc)
            existing_access.save()
            action = 'updated'
        else:
            # Crear nuevo acceso
            access_data = {
                'document_id': document.id,
                'user_id': target_user_id,
                'granted_by': current_user.id,
                'access_level': form.access_level.data,
                'expires_at': form.expires_at.data,
                'message': sanitize_input(form.message.data) if form.message.data else None
            }
            
            DocumentAccess.create(**access_data)
            action = 'granted'
        
        # Obtener usuario objetivo
        target_user = User.query.get(target_user_id)
        
        # Enviar notificación
        NotificationService.send_notification(
            user_id=target_user_id,
            title='Documento compartido contigo',
            message=f'{current_user.full_name} compartió el documento "{document.title}" contigo',
            notification_type='document_shared',
            related_id=document.id
        )
        
        # Enviar email
        EmailService.send_document_shared_notification(
            target_user.email,
            target_user.first_name,
            current_user.full_name,
            document,
            form.access_level.data
        )
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action=f'document_access_{action}',
            resource_type='document',
            resource_id=document.id,
            details={
                'target_user': target_user.full_name,
                'access_level': form.access_level.data.value,
                'document_title': document.title
            }
        )
        
        flash(f'Documento compartido con {target_user.full_name}', 'success')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))

    except ResourceNotFoundError:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('entrepreneur_documents.index'))
    except Exception as e:
        current_app.logger.error(f"Error compartiendo documento {document_id}: {str(e)}")
        flash('Error compartiendo el documento', 'error')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))


@entrepreneur_documents.route('/<int:document_id>/new-version', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def new_version(document_id):
    """
    Subir nueva versión de un documento.
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos
        if not _can_edit_document(document, current_user.id):
            flash('No tienes permisos para crear versiones de este documento', 'error')
            return redirect(url_for('entrepreneur_documents.view', document_id=document_id))
        
        form = DocumentVersionForm()
        
        if request.method == 'GET':
            return render_template(
                'entrepreneur/documents/new_version.html',
                form=form,
                document=document,
                max_file_size=MAX_FILE_SIZE
            )
        
        if not form.validate_on_submit():
            return render_template(
                'entrepreneur/documents/new_version.html',
                form=form,
                document=document
            )
        
        # Validar archivo
        file = form.file.data
        if not file or file.filename == '':
            form.file.errors.append('Se requiere un archivo')
            return render_template('entrepreneur/documents/new_version.html', form=form, document=document)
        
        # Validar tipo de archivo compatible
        if not _is_compatible_file_type(file, document):
            form.file.errors.append('El tipo de archivo debe ser compatible con el documento original')
            return render_template('entrepreneur/documents/new_version.html', form=form, document=document)
        
        # Crear nueva versión
        version = _create_document_version(document, file, form)
        
        # Actualizar documento principal
        document.current_version = version.version_number
        document.file_size = version.file_size
        document.file_path = version.file_path
        document.updated_at = datetime.now(timezone.utc)
        document.save()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='document_version_created',
            resource_type='document',
            resource_id=document.id,
            details={
                'version_number': version.version_number,
                'document_title': document.title,
                'change_notes': form.change_notes.data
            }
        )
        
        # Notificar a usuarios con acceso
        _notify_document_access_users(document, 'new_version', version.version_number)
        
        flash(f'Nueva versión {version.version_number} creada exitosamente', 'success')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))

    except ResourceNotFoundError:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('entrepreneur_documents.index'))
    except Exception as e:
        current_app.logger.error(f"Error creando nueva versión del documento {document_id}: {str(e)}")
        flash('Error creando la nueva versión', 'error')
        return redirect(url_for('entrepreneur_documents.view', document_id=document_id))


@entrepreneur_documents.route('/<int:document_id>/delete', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 eliminaciones por 5 minutos
def delete(document_id):
    """
    Eliminar documento (soft delete).
    """
    try:
        document = _get_document_or_404(document_id)
        
        # Verificar permisos
        if not _can_delete_document(document, current_user.id):
            return jsonify({
                'success': False,
                'error': 'No tienes permisos para eliminar este documento'
            }), 403
        
        # Verificar confirmación
        confirmation = request.json.get('confirmation')
        if confirmation != document.title:
            return jsonify({
                'success': False,
                'error': 'Confirmación incorrecta'
            }), 400
        
        # Soft delete
        document.is_deleted = True
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by = current_user.id
        document.save()
        
        # Eliminar accesos compartidos
        DocumentAccess.query.filter_by(document_id=document.id).delete()
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='document_deleted',
            resource_type='document',
            resource_id=document.id,
            details={
                'document_title': document.title,
                'original_filename': document.original_filename
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Documento "{document.title}" eliminado exitosamente',
            'redirect_url': url_for('entrepreneur_documents.index')
        })

    except ResourceNotFoundError:
        return jsonify({'success': False, 'error': 'Documento no encontrado'}), 404
    except Exception as e:
        current_app.logger.error(f"Error eliminando documento {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error eliminando el documento'
        }), 500


@entrepreneur_documents.route('/folders/create', methods=['GET', 'POST'])
@login_required
@require_role('entrepreneur')
def create_folder():
    """
    Crear nueva carpeta.
    """
    form = FolderForm()
    
    if request.method == 'GET':
        # Carpeta padre sugerida
        parent_id = request.args.get('parent_id', type=int)
        if parent_id:
            form.parent_id.data = parent_id
        
        # Cargar opciones
        _populate_folder_form_choices(form, g.entrepreneur.id)
        
        return render_template(
            'entrepreneur/documents/create_folder.html',
            form=form
        )
    
    try:
        if not form.validate_on_submit():
            _populate_folder_form_choices(form, g.entrepreneur.id)
            return render_template(
                'entrepreneur/documents/create_folder.html',
                form=form
            )
        
        # Verificar que no exista carpeta con el mismo nombre en la ubicación
        existing_folder = DocumentFolder.query.filter_by(
            entrepreneur_id=g.entrepreneur.id,
            parent_id=form.parent_id.data,
            name=form.name.data
        ).first()
        
        if existing_folder:
            form.name.errors.append('Ya existe una carpeta con este nombre en esta ubicación')
            _populate_folder_form_choices(form, g.entrepreneur.id)
            return render_template('entrepreneur/documents/create_folder.html', form=form)
        
        # Crear carpeta
        folder_data = {
            'name': sanitize_input(form.name.data),
            'description': sanitize_input(form.description.data) if form.description.data else None,
            'parent_id': form.parent_id.data if form.parent_id.data else None,
            'entrepreneur_id': g.entrepreneur.id,
            'created_by': current_user.id
        }
        
        folder = DocumentFolder.create(**folder_data)
        
        # Registrar actividad
        ActivityLog.create(
            user_id=current_user.id,
            action='folder_created',
            resource_type='document_folder',
            resource_id=folder.id,
            details={
                'folder_name': folder.name,
                'parent_folder': folder.parent.name if folder.parent else None
            }
        )
        
        flash(f'Carpeta "{folder.name}" creada exitosamente', 'success')
        
        # Redireccionar a la carpeta creada
        return redirect(url_for('entrepreneur_documents.index', folder_id=folder.id))

    except Exception as e:
        current_app.logger.error(f"Error creando carpeta: {str(e)}")
        flash('Error creando la carpeta', 'error')
        _populate_folder_form_choices(form, g.entrepreneur.id)
        return render_template('entrepreneur/documents/create_folder.html', form=form)


@entrepreneur_documents.route('/search')
@login_required
@require_role('entrepreneur')
def search():
    """
    Búsqueda avanzada de documentos.
    """
    try:
        # Obtener parámetros de búsqueda
        query_text = request.args.get('q', '').strip()
        document_type = request.args.get('type')
        category = request.args.get('category')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        tags = request.args.get('tags', '').strip()
        
        # Paginación
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Construir query de búsqueda
        search_results = _perform_advanced_search(
            entrepreneur_id=g.entrepreneur.id,
            query_text=query_text,
            document_type=document_type,
            category=category,
            date_from=date_from,
            date_to=date_to,
            tags=tags,
            page=page,
            per_page=per_page
        )
        
        # Sugerencias de búsqueda
        search_suggestions = _get_search_suggestions(query_text, g.entrepreneur.id)
        
        # Búsquedas recientes
        recent_searches = _get_recent_searches(current_user.id, limit=5)
        
        return render_template(
            'entrepreneur/documents/search.html',
            search_results=search_results,
            search_suggestions=search_suggestions,
            recent_searches=recent_searches,
            search_params={
                'q': query_text,
                'type': document_type,
                'category': category,
                'date_from': date_from,
                'date_to': date_to,
                'tags': tags
            },
            DocumentType=DocumentType,
            DocumentCategory=DocumentCategory
        )

    except Exception as e:
        current_app.logger.error(f"Error en búsqueda de documentos: {str(e)}")
        flash('Error realizando la búsqueda', 'error')
        return redirect(url_for('entrepreneur_documents.index'))


@entrepreneur_documents.route('/bulk-actions', methods=['POST'])
@login_required
@require_role('entrepreneur')
@rate_limit(requests=10, window=300)  # 10 acciones masivas por 5 minutos
def bulk_actions():
    """
    Realizar acciones masivas en documentos.
    """
    try:
        form = BulkActionForm()
        
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'errors': form.errors
            }), 400
        
        action = form.action.data
        document_ids = form.document_ids.data
        
        if not document_ids:
            return jsonify({
                'success': False,
                'error': 'No se seleccionaron documentos'
            }), 400
        
        # Obtener documentos verificando permisos
        documents = []
        for doc_id in document_ids:
            try:
                doc = _get_document_or_404(doc_id)
                documents.append(doc)
            except ResourceNotFoundError:
                continue
        
        if not documents:
            return jsonify({
                'success': False,
                'error': 'No se encontraron documentos válidos'
            }), 404
        
        # Ejecutar acción
        if action == 'delete':
            result = _bulk_delete_documents(documents)
        elif action == 'move':
            folder_id = form.target_folder_id.data
            result = _bulk_move_documents(documents, folder_id)
        elif action == 'download':
            result = _bulk_download_documents(documents)
        elif action == 'add_tags':
            tags = form.tags.data
            result = _bulk_add_tags(documents, tags)
        else:
            return jsonify({
                'success': False,
                'error': 'Acción no válida'
            }), 400
        
        # Registrar actividad masiva
        ActivityLog.create(
            user_id=current_user.id,
            action=f'bulk_{action}',
            resource_type='document',
            details={
                'action': action,
                'document_count': len(documents),
                'document_ids': document_ids,
                'result': result
            }
        )
        
        return jsonify({
            'success': True,
            'message': result.get('message', 'Acción ejecutada correctamente'),
            'result': result
        })

    except Exception as e:
        current_app.logger.error(f"Error en acciones masivas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error ejecutando la acción'
        }), 500


@entrepreneur_documents.route('/analytics')
@login_required
@require_role('entrepreneur')
def analytics():
    """
    Analytics y métricas de uso de documentos.
    """
    try:
        # Rango de fechas para análisis
        date_range = request.args.get('range', '30')  # días
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=int(date_range))
        
        # Métricas de almacenamiento
        storage_analytics = _get_storage_analytics(g.entrepreneur.id)
        
        # Análisis de tipos de documentos
        document_type_analysis = _get_document_type_analysis(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Análisis de actividad
        activity_analysis = _get_document_activity_analysis(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Documentos más accedidos
        most_accessed = _get_most_accessed_documents(
            g.entrepreneur.id, start_date, end_date, limit=10
        )
        
        # Análisis de colaboración
        collaboration_analytics = _get_collaboration_analytics(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Tendencias de crecimiento
        growth_trends = _get_storage_growth_trends(
            g.entrepreneur.id, start_date, end_date
        )
        
        # Recomendaciones de optimización
        optimization_recommendations = _get_storage_optimization_recommendations(
            storage_analytics, document_type_analysis
        )
        
        return render_template(
            'entrepreneur/documents/analytics.html',
            storage_analytics=storage_analytics,
            document_type_analysis=document_type_analysis,
            activity_analysis=activity_analysis,
            most_accessed=most_accessed,
            collaboration_analytics=collaboration_analytics,
            growth_trends=growth_trends,
            optimization_recommendations=optimization_recommendations,
            start_date=start_date,
            end_date=end_date,
            current_range=date_range
        )

    except Exception as e:
        current_app.logger.error(f"Error cargando analytics de documentos: {str(e)}")
        flash('Error cargando las métricas', 'error')
        return redirect(url_for('entrepreneur_documents.index'))


# === FUNCIONES AUXILIARES ===

def _get_document_or_404(document_id):
    """Obtener documento validando pertenencia o acceso."""
    # Primero verificar si es propietario
    document = Document.query.filter_by(
        id=document_id,
        uploaded_by=current_user.id,
        is_deleted=False
    ).first()
    
    if document:
        return document
    
    # Si no es propietario, verificar si tiene acceso compartido
    shared_access = DocumentAccess.query.filter_by(
        document_id=document_id,
        user_id=current_user.id
    ).join(Document).filter(
        Document.is_deleted == False
    ).first()
    
    if shared_access and _is_access_valid(shared_access):
        return shared_access.document
    
    raise ResourceNotFoundError("Documento no encontrado")


def _apply_document_filters(query, search_form):
    """Aplicar filtros de búsqueda a la consulta."""
    if search_form.search.data:
        search_term = f"%{search_form.search.data}%"
        query = query.filter(
            or_(
                Document.title.ilike(search_term),
                Document.description.ilike(search_term),
                Document.original_filename.ilike(search_term)
            )
        )
    
    if search_form.document_type.data and search_form.document_type.data != 'all':
        query = query.filter_by(document_type=DocumentType(search_form.document_type.data))
    
    if search_form.category.data and search_form.category.data != 'all':
        query = query.filter_by(category=DocumentCategory(search_form.category.data))
    
    if search_form.date_from.data:
        query = query.filter(Document.created_at >= search_form.date_from.data)
    
    if search_form.date_to.data:
        query = query.filter(Document.created_at <= search_form.date_to.data)
    
    if search_form.tags.data:
        tag_names = [tag.strip() for tag in search_form.tags.data.split(',')]
        query = query.join(Document.tags).filter(DocumentTag.name.in_(tag_names))
    
    return query


def _apply_document_sorting(query, sort_by, sort_order):
    """Aplicar ordenamiento a la consulta."""
    valid_sort_fields = {
        'title': Document.title,
        'created_at': Document.created_at,
        'updated_at': Document.updated_at,
        'file_size': Document.file_size,
        'type': Document.document_type
    }
    
    if sort_by not in valid_sort_fields:
        sort_by = 'created_at'
    
    sort_field = valid_sort_fields[sort_by]
    
    if sort_order == 'asc':
        query = query.order_by(asc(sort_field))
    else:
        query = query.order_by(desc(sort_field))
    
    return query


def _build_folder_breadcrumb(folder):
    """Construir breadcrumb de navegación por carpetas."""
    breadcrumb = []
    current = folder
    
    while current:
        breadcrumb.insert(0, current)
        current = current.parent
    
    return breadcrumb


def _get_storage_metrics(entrepreneur_id):
    """Obtener métricas de almacenamiento."""
    # Total de documentos
    total_documents = Document.query.filter_by(
        uploaded_by=entrepreneur_id,
        is_deleted=False
    ).count()
    
    # Espacio utilizado
    total_size = Document.query.filter_by(
        uploaded_by=entrepreneur_id,
        is_deleted=False
    ).with_entities(func.sum(Document.file_size)).scalar() or 0
    
    # Documentos por tipo
    type_distribution = {}
    for doc_type in DocumentType:
        count = Document.query.filter_by(
            uploaded_by=entrepreneur_id,
            document_type=doc_type,
            is_deleted=False
        ).count()
        type_distribution[doc_type.value] = count
    
    # Espacio disponible
    available_space = MAX_TOTAL_STORAGE - total_size
    usage_percentage = (total_size / MAX_TOTAL_STORAGE * 100) if MAX_TOTAL_STORAGE > 0 else 0
    
    return {
        'total_documents': total_documents,
        'total_size': total_size,
        'total_size_formatted': format_file_size(total_size),
        'available_space': available_space,
        'available_space_formatted': format_file_size(available_space),
        'max_storage': MAX_TOTAL_STORAGE,
        'max_storage_formatted': format_file_size(MAX_TOTAL_STORAGE),
        'usage_percentage': round(usage_percentage, 1),
        'type_distribution': type_distribution
    }


def _get_recent_documents(entrepreneur_id, limit=5):
    """Obtener documentos recientes."""
    return Document.query.filter_by(
        uploaded_by=entrepreneur_id,
        is_deleted=False
    ).order_by(desc(Document.created_at)).limit(limit).all()


def _get_shared_documents(user_id, limit=5):
    """Obtener documentos compartidos con el usuario."""
    return Document.query.join(DocumentAccess).filter(
        and_(
            DocumentAccess.user_id == user_id,
            Document.is_deleted == False,
            Document.uploaded_by != user_id  # Excluir documentos propios
        )
    ).order_by(desc(DocumentAccess.created_at)).limit(limit).all()


def _get_popular_tags(entrepreneur_id, limit=10):
    """Obtener tags más utilizados."""
    # Esta función requeriría una consulta más compleja
    # Por ahora retorna una lista mock
    return [
        {'name': 'plan-negocio', 'count': 15},
        {'name': 'financiero', 'count': 12},
        {'name': 'marketing', 'count': 8},
        {'name': 'legal', 'count': 6},
        {'name': 'presentacion', 'count': 5}
    ]


def _populate_upload_form_choices(form):
    """Poblar opciones del formulario de upload."""
    # Tipos de documento
    form.document_type.choices = [(t.value, t.value.replace('_', ' ').title()) for t in DocumentType]
    
    # Categorías
    form.category.choices = [(c.value, c.value.replace('_', ' ').title()) for c in DocumentCategory]
    
    # Carpetas
    folders = DocumentFolder.query.filter_by(
        entrepreneur_id=g.entrepreneur.id
    ).order_by(DocumentFolder.name).all()
    form.folder_id.choices = [('', 'Sin carpeta')] + [(f.id, f.name) for f in folders]
    
    # Proyectos
    projects = Project.query.filter_by(
        entrepreneur_id=g.entrepreneur.id
    ).order_by(Project.name).all()
    form.project_id.choices = [('', 'Sin proyecto')] + [(p.id, p.name) for p in projects]


def _get_storage_info(entrepreneur_id):
    """Obtener información de almacenamiento."""
    metrics = _get_storage_metrics(entrepreneur_id)
    
    return {
        'used_space': metrics['total_size'],
        'available_space': metrics['available_space'],
        'max_space': MAX_TOTAL_STORAGE,
        'usage_percentage': metrics['usage_percentage'],
        'can_upload': metrics['available_space'] > 0
    }


def _check_storage_capacity(entrepreneur_id, additional_size):
    """Verificar si hay capacidad para archivos adicionales."""
    current_usage = Document.query.filter_by(
        uploaded_by=entrepreneur_id,
        is_deleted=False
    ).with_entities(func.sum(Document.file_size)).scalar() or 0
    
    return (current_usage + additional_size) <= MAX_TOTAL_STORAGE


def _validate_uploaded_file(file):
    """Validar archivo subido."""
    # Verificar extensión
    filename = secure_filename(file.filename)
    if '.' not in filename:
        return {'valid': False, 'error': 'Archivo sin extensión'}
    
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in ALL_ALLOWED_EXTENSIONS:
        return {'valid': False, 'error': f'Tipo de archivo no permitido: .{extension}'}
    
    # Verificar tamaño
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return {'valid': False, 'error': f'Archivo muy grande (máximo {format_file_size(MAX_FILE_SIZE)})'}
    
    if file_size == 0:
        return {'valid': False, 'error': 'Archivo vacío'}
    
    # Validación básica de contenido por tipo MIME
    mime_type = file.content_type
    if not mime_type or mime_type == 'application/octet-stream':
        # Intentar detectar por extensión
        mime_type, _ = mimetypes.guess_type(filename)
    
    return {'valid': True, 'mime_type': mime_type, 'file_size': file_size}


def _process_and_save_file(file, form):
    """Procesar y guardar archivo."""
    # Generar información del archivo
    original_filename = secure_filename(file.filename)
    file_extension = get_file_extension(original_filename)
    unique_filename = generate_unique_filename(original_filename, current_user.id)
    
    # Validar archivo
    validation = _validate_uploaded_file(file)
    if not validation['valid']:
        raise ValidationError(validation['error'])
    
    # Generar hash del archivo
    file_hash = generate_file_hash(file)
    file.seek(0)  # Resetear puntero
    
    # Verificar duplicados
    existing_doc = Document.query.filter_by(
        uploaded_by=current_user.id,
        file_hash=file_hash,
        is_deleted=False
    ).first()
    
    if existing_doc:
        raise ValidationError(f'Ya existe un archivo idéntico: "{existing_doc.title}"')
    
    # Guardar archivo físico
    file_path = g.file_storage.save_file(
        file, 
        f"documents/{current_user.id}/{unique_filename}"
    )
    
    # Procesar según tipo de archivo
    processing_result = _process_file_by_type(file_path, file_extension)
    
    # Crear registro en base de datos
    document_data = {
        'title': sanitize_input(form.title.data) if form.title.data else Path(original_filename).stem,
        'description': sanitize_input(form.description.data) if form.description.data else None,
        'filename': unique_filename,
        'original_filename': original_filename,
        'file_path': file_path,
        'file_size': validation['file_size'],
        'file_hash': file_hash,
        'mime_type': validation['mime_type'],
        'document_type': form.document_type.data if form.document_type.data else _detect_document_type(file_extension),
        'category': form.category.data if form.category.data else None,
        'folder_id': form.folder_id.data if form.folder_id.data else None,
        'project_id': form.project_id.data if form.project_id.data else None,
        'is_confidential': form.is_confidential.data if hasattr(form, 'is_confidential') else False,
        'uploaded_by': current_user.id
    }
    
    # Agregar datos del procesamiento
    if processing_result:
        document_data.update(processing_result)
    
    document = Document.create(**document_data)
    
    # Procesar tags
    if hasattr(form, 'tags') and form.tags.data:
        _create_document_tags(document, form.tags.data)
    
    return document


def _process_file_by_type(file_path, file_extension):
    """Procesar archivo según su tipo."""
    processing_result = {}
    
    try:
        # Generar thumbnail para imágenes
        if file_extension.lower() in ALLOWED_EXTENSIONS['images']:
            thumbnail_path = _create_image_thumbnail(file_path)
            if thumbnail_path:
                processing_result['thumbnail_path'] = thumbnail_path
        
        # Generar preview para PDFs
        elif file_extension.lower() == 'pdf':
            thumbnail_path = _create_pdf_thumbnail(file_path)
            if thumbnail_path:
                processing_result['thumbnail_path'] = thumbnail_path
            
            # Extraer texto para búsqueda
            text_content = _extract_pdf_text(file_path)
            if text_content:
                processing_result['extracted_text'] = text_content[:5000]  # Límite de 5000 caracteres
        
        # Procesar documentos de Office
        elif file_extension.lower() in ALLOWED_EXTENSIONS['documents']:
            text_content = _extract_document_text(file_path, file_extension)
            if text_content:
                processing_result['extracted_text'] = text_content[:5000]
    
    except Exception as e:
        current_app.logger.warning(f"Error procesando archivo {file_path}: {str(e)}")
    
    return processing_result


def _create_image_thumbnail(file_path):
    """Crear thumbnail de imagen."""
    try:
        with Image.open(file_path) as img:
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Crear thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Generar ruta del thumbnail
            path_obj = Path(file_path)
            thumbnail_path = str(path_obj.parent / f"thumb_{path_obj.name}")
            
            # Guardar thumbnail
            img.save(thumbnail_path, 'JPEG', quality=85)
            
            return thumbnail_path
    
    except Exception as e:
        current_app.logger.error(f"Error creando thumbnail de imagen: {str(e)}")
        return None


def _create_pdf_thumbnail(file_path):
    """Crear thumbnail de PDF."""
    try:
        # Abrir PDF
        doc = fitz.open(file_path)
        
        if len(doc) == 0:
            return None
        
        # Obtener primera página
        page = doc[0]
        
        # Renderizar como imagen
        mat = fitz.Matrix(1.0, 1.0)  # Escala 1:1
        pix = page.get_pixmap(matrix=mat)
        
        # Convertir a PIL Image
        img_data = pix.tobytes("ppm")
        img = Image.open(BytesIO(img_data))
        
        # Crear thumbnail
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        
        # Generar ruta del thumbnail
        path_obj = Path(file_path)
        thumbnail_path = str(path_obj.parent / f"thumb_{path_obj.stem}.jpg")
        
        # Guardar thumbnail
        img.save(thumbnail_path, 'JPEG', quality=85)
        
        doc.close()
        return thumbnail_path
    
    except Exception as e:
        current_app.logger.error(f"Error creando thumbnail de PDF: {str(e)}")
        return None


def _extract_pdf_text(file_path):
    """Extraer texto de PDF para indexación."""
    try:
        doc = fitz.open(file_path)
        text_content = ""
        
        # Extraer texto de las primeras 10 páginas máximo
        for page_num in range(min(10, len(doc))):
            page = doc[page_num]
            text_content += page.get_text()
        
        doc.close()
        return text_content.strip()
    
    except Exception as e:
        current_app.logger.error(f"Error extrayendo texto de PDF: {str(e)}")
        return None


def _extract_document_text(file_path, file_extension):
    """Extraer texto de documentos de Office."""
    # Esta función requeriría librerías adicionales como python-docx, openpyxl, etc.
    # Por ahora retorna None
    return None


def _detect_document_type(file_extension):
    """Detectar tipo de documento por extensión."""
    ext = file_extension.lower()
    
    if ext in ALLOWED_EXTENSIONS['images']:
        return DocumentType.IMAGE
    elif ext in ALLOWED_EXTENSIONS['documents']:
        return DocumentType.DOCUMENT
    elif ext in ALLOWED_EXTENSIONS['spreadsheets']:
        return DocumentType.SPREADSHEET
    elif ext in ALLOWED_EXTENSIONS['presentations']:
        return DocumentType.PRESENTATION
    elif ext in ALLOWED_EXTENSIONS['archives']:
        return DocumentType.ARCHIVE
    else:
        return DocumentType.OTHER


def _create_document_tags(document, tags_string):
    """Crear tags para el documento."""
    if not tags_string:
        return
    
    tag_names = [tag.strip().lower() for tag in tags_string.split(',') if tag.strip()]
    
    for tag_name in tag_names:
        # Buscar o crear tag
        tag = DocumentTag.query.filter_by(name=tag_name).first()
        if not tag:
            tag = DocumentTag.create(name=tag_name)
        
        # Asociar con documento si no existe la relación
        if tag not in document.tags:
            document.tags.append(tag)
    
    document.save()


def _send_upload_notifications(documents, form):
    """Enviar notificaciones por upload de documentos."""
    # Si se asignó a un proyecto, notificar a colaboradores
    if form.project_id.data:
        project = Project.query.get(form.project_id.data)
        if project and project.assigned_ally:
            NotificationService.send_notification(
                user_id=project.assigned_ally.user_id,
                title='Nuevos documentos en proyecto',
                message=f'{current_user.full_name} subió {len(documents)} documento(s) al proyecto "{project.name}"',
                notification_type='project_documents_added',
                related_id=project.id
            )


def _can_read_document(document, user_id):
    """Verificar si el usuario puede leer el documento."""
    # Es el propietario
    if document.uploaded_by == user_id:
        return True
    
    # Tiene acceso compartido
    access = DocumentAccess.query.filter_by(
        document_id=document.id,
        user_id=user_id
    ).first()
    
    return access and _is_access_valid(access)


def _can_edit_document(document, user_id):
    """Verificar si el usuario puede editar el documento."""
    # Solo el propietario puede editar metadatos
    if document.uploaded_by == user_id:
        return True
    
    # Verificar acceso de escritura
    access = DocumentAccess.query.filter_by(
        document_id=document.id,
        user_id=user_id
    ).first()
    
    return (access and 
            _is_access_valid(access) and 
            access.access_level in [AccessLevel.WRITE, AccessLevel.ADMIN])


def _can_delete_document(document, user_id):
    """Verificar si el usuario puede eliminar el documento."""
    # Solo el propietario puede eliminar
    return document.uploaded_by == user_id


def _can_share_document(document, user_id):
    """Verificar si el usuario puede compartir el documento."""
    # El propietario siempre puede compartir
    if document.uploaded_by == user_id:
        return True
    
    # Verificar acceso de administrador
    access = DocumentAccess.query.filter_by(
        document_id=document.id,
        user_id=user_id
    ).first()
    
    return (access and 
            _is_access_valid(access) and 
            access.access_level == AccessLevel.ADMIN)


def _can_download_document(document, user_id):
    """Verificar si el usuario puede descargar el documento."""
    return _can_read_document(document, user_id)


def _is_access_valid(access):
    """Verificar si el acceso compartido es válido."""
    if access.expires_at and access.expires_at < datetime.now(timezone.utc):
        return False
    return True


def _register_document_access(document, user_id, action):
    """Registrar acceso al documento."""
    ActivityLog.create(
        user_id=user_id,
        action=f'document_{action}',
        resource_type='document',
        resource_id=document.id,
        details={
            'document_title': document.title,
            'action': action
        }
    )


def _get_related_documents(document, limit=5):
    """Obtener documentos relacionados."""
    related = []
    
    # Documentos del mismo proyecto
    if document.project_id:
        project_docs = Document.query.filter(
            and_(
                Document.project_id == document.project_id,
                Document.id != document.id,
                Document.is_deleted == False
            )
        ).limit(limit).all()
        related.extend(project_docs)
    
    # Documentos con tags similares
    if document.tags and len(related) < limit:
        tag_names = [tag.name for tag in document.tags]
        similar_docs = Document.query.join(Document.tags).filter(
            and_(
                DocumentTag.name.in_(tag_names),
                Document.id != document.id,
                Document.uploaded_by == document.uploaded_by,
                Document.is_deleted == False
            )
        ).limit(limit - len(related)).all()
        related.extend(similar_docs)
    
    return related[:limit]


def _get_document_preview_info(document):
    """Obtener información de preview del documento."""
    preview_info = {
        'can_preview': False,
        'preview_type': None,
        'thumbnail_available': bool(document.thumbnail_path)
    }
    
    file_ext = get_file_extension(document.filename).lower()
    
    if file_ext in ALLOWED_EXTENSIONS['images']:
        preview_info['can_preview'] = True
        preview_info['preview_type'] = 'image'
    elif file_ext == 'pdf':
        preview_info['can_preview'] = True
        preview_info['preview_type'] = 'pdf'
    elif file_ext in ['txt', 'md', 'json', 'xml']:
        preview_info['can_preview'] = True
        preview_info['preview_type'] = 'text'
    
    return preview_info


def _extract_file_metadata(document):
    """Extraer metadatos del archivo."""
    metadata = {
        'size_formatted': format_file_size(document.file_size),
        'extension': get_file_extension(document.filename).upper(),
        'mime_type': document.mime_type,
        'created_date': document.created_at.strftime('%d/%m/%Y %H:%M'),
        'updated_date': document.updated_at.strftime('%d/%m/%Y %H:%M') if document.updated_at else None
    }
    
    # Metadatos específicos por tipo
    file_ext = get_file_extension(document.filename).lower()
    
    if file_ext in ALLOWED_EXTENSIONS['images'] and document.thumbnail_path:
        try:
            with Image.open(g.file_storage.get_file_path(document.file_path)) as img:
                metadata['dimensions'] = f"{img.width} × {img.height} px"
                metadata['color_mode'] = img.mode
        except:
            pass
    
    elif file_ext == 'pdf':
        try:
            doc = fitz.open(g.file_storage.get_file_path(document.file_path))
            metadata['pages'] = len(doc)
            doc.close()
        except:
            pass
    
    return metadata


def _should_apply_watermark(document):
    """Determinar si se debe aplicar watermark."""
    return document.is_confidential


def _apply_watermark_to_file(document, file_path):
    """Aplicar watermark a archivo."""
    # Por ahora solo para imágenes
    file_ext = get_file_extension(document.filename).lower()
    
    if file_ext not in ALLOWED_EXTENSIONS['images']:
        return None
    
    try:
        with Image.open(file_path) as img:
            # Crear watermark
            watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark)
            
            # Calcular tamaño de fuente
            font_size = max(20, min(img.width, img.height) // 20)
            
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            # Texto del watermark
            watermark_text = WATERMARK_TEXT.format(
                empresa=g.entrepreneur.company_name or "CONFIDENCIAL"
            )
            
            # Calcular posición
            text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (img.width - text_width) // 2
            y = (img.height - text_height) // 2
            
            # Dibujar watermark
            draw.text(
                (x, y), 
                watermark_text, 
                fill=(255, 255, 255, int(255 * WATERMARK_OPACITY)),
                font=font
            )
            
            # Aplicar watermark
            watermarked = Image.alpha_composite(img.convert('RGBA'), watermark)
            
            # Guardar archivo temporal
            temp_path = file_path.replace('.', '_watermarked.')
            watermarked.convert('RGB').save(temp_path, quality=95)
            
            return temp_path
    
    except Exception as e:
        current_app.logger.error(f"Error aplicando watermark: {str(e)}")
        return None


def _generate_document_preview(document):
    """Generar datos de preview del documento."""
    file_ext = get_file_extension(document.filename).lower()
    file_path = g.file_storage.get_file_path(document.file_path)
    
    preview_data = {
        'type': None,
        'content': None,
        'error': None
    }
    
    try:
        if file_ext in ALLOWED_EXTENSIONS['images']:
            preview_data['type'] = 'image'
            preview_data['content'] = {
                'src': url_for('entrepreneur_documents.serve_file', 
                              document_id=document.id, file_type='original'),
                'thumbnail_src': url_for('entrepreneur_documents.serve_file', 
                                       document_id=document.id, file_type='thumbnail') if document.thumbnail_path else None
            }
        
        elif file_ext == 'pdf':
            preview_data['type'] = 'pdf'
            preview_data['content'] = {
                'src': url_for('entrepreneur_documents.serve_file', 
                              document_id=document.id, file_type='original'),
                'thumbnail_src': url_for('entrepreneur_documents.serve_file', 
                                       document_id=document.id, file_type='thumbnail') if document.thumbnail_path else None
            }
        
        elif file_ext in ['txt', 'md', 'json', 'xml']:
            preview_data['type'] = 'text'
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(10000)  # Máximo 10KB
                preview_data['content'] = {
                    'text': content,
                    'language': file_ext
                }
        
        else:
            preview_data['error'] = 'Vista previa no disponible para este tipo de archivo'
    
    except Exception as e:
        current_app.logger.error(f"Error generando preview: {str(e)}")
        preview_data['error'] = 'Error generando vista previa'
    
    return preview_data


# Funciones auxiliares adicionales (implementación simplificada por espacio)

def _populate_edit_form_choices(form):
    """Poblar opciones del formulario de edición."""
    _populate_upload_form_choices(form)

def _populate_form_with_document_data(form, document):
    """Poblar formulario con datos del documento."""
    if document.tags:
        form.tags.data = ', '.join([tag.name for tag in document.tags])

def _extract_document_metadata(document):
    """Extraer metadatos para auditoria."""
    return {
        'title': document.title,
        'description': document.description,
        'document_type': document.document_type.value if document.document_type else None,
        'category': document.category.value if document.category else None,
        'is_confidential': document.is_confidential
    }

def _update_document_tags(document, tags_string):
    """Actualizar tags del documento."""
    # Limpiar tags existentes
    document.tags.clear()
    
    # Crear nuevos tags
    if tags_string:
        _create_document_tags(document, tags_string)

def _detect_document_changes(original_data, document):
    """Detectar cambios en el documento."""
    changes = {}
    
    current_data = _extract_document_metadata(document)
    
    for key, new_value in current_data.items():
        old_value = original_data.get(key)
        if old_value != new_value:
            changes[key] = {
                'old': old_value,
                'new': new_value
            }
    
    return changes

def _notify_document_access_users(document, action, version=None):
    """Notificar a usuarios con acceso al documento."""
    accesses = DocumentAccess.query.filter_by(document_id=document.id).all()
    
    for access in accesses:
        if _is_access_valid(access):
            message = f'El documento "{document.title}" ha sido {action}'
            if version:
                message += f' (versión {version})'
            
            NotificationService.send_notification(
                user_id=access.user_id,
                title='Documento actualizado',
                message=message,
                notification_type=f'document_{action}',
                related_id=document.id
            )

def _get_shareable_users(entrepreneur_id):
    """Obtener usuarios con los que se pueden compartir documentos."""
    # Aliados asignados, clientes, otros emprendedores del ecosistema
    users = []
    
    # Aliado asignado
    entrepreneur = Entrepreneur.query.get(entrepreneur_id)
    if entrepreneur.assigned_ally:
        users.append(entrepreneur.assigned_ally.user)
    
    # Por simplicidad, retornar solo el aliado por ahora
    return users

def _is_compatible_file_type(file, document):
    """Verificar si el archivo es compatible para nueva versión."""
    new_ext = get_file_extension(file.filename).lower()
    current_ext = get_file_extension(document.filename).lower()
    
    # Mismo tipo básico
    return _detect_document_type(new_ext) == document.document_type

def _create_document_version(document, file, form):
    """Crear nueva versión del documento."""
    # Obtener siguiente número de versión
    last_version = DocumentVersion.query.filter_by(
        document_id=document.id
    ).order_by(desc(DocumentVersion.version_number)).first()
    
    next_version = (last_version.version_number + 1) if last_version else 2
    
    # Procesar archivo
    original_filename = secure_filename(file.filename)
    unique_filename = generate_unique_filename(original_filename, current_user.id)
    
    validation = _validate_uploaded_file(file)
    if not validation['valid']:
        raise ValidationError(validation['error'])
    
    # Guardar archivo
    file_path = g.file_storage.save_file(
        file, 
        f"documents/{current_user.id}/versions/{unique_filename}"
    )
    
    # Crear registro de versión
    version_data = {
        'document_id': document.id,
        'version_number': next_version,
        'filename': unique_filename,
        'original_filename': original_filename,
        'file_path': file_path,
        'file_size': validation['file_size'],
        'mime_type': validation['mime_type'],
        'change_notes': sanitize_input(form.change_notes.data) if form.change_notes.data else None,
        'created_by': current_user.id
    }
    
    return DocumentVersion.create(**version_data)

def _perform_advanced_search(entrepreneur_id, query_text, document_type, category, 
                           date_from, date_to, tags, page, per_page):
    """Realizar búsqueda avanzada de documentos."""
    # Implementación simplificada
    query = Document.query.filter_by(uploaded_by=entrepreneur_id, is_deleted=False)
    
    if query_text:
        search_term = f"%{query_text}%"
        query = query.filter(
            or_(
                Document.title.ilike(search_term),
                Document.description.ilike(search_term),
                Document.extracted_text.ilike(search_term)
            )
        )
    
    # Aplicar otros filtros...
    
    return query.paginate(page=page, per_page=per_page, error_out=False)

def _get_search_suggestions(query_text, entrepreneur_id):
    """Obtener sugerencias de búsqueda."""
    return []

def _get_recent_searches(user_id, limit=5):
    """Obtener búsquedas recientes."""
    return []

def _bulk_delete_documents(documents):
    """Eliminar documentos en masa."""
    count = 0
    for doc in documents:
        if _can_delete_document(doc, current_user.id):
            doc.is_deleted = True
            doc.deleted_at = datetime.now(timezone.utc)
            doc.deleted_by = current_user.id
            doc.save()
            count += 1
    
    return {'message': f'{count} documento(s) eliminado(s)', 'count': count}

def _bulk_move_documents(documents, folder_id):
    """Mover documentos en masa."""
    count = 0
    for doc in documents:
        if _can_edit_document(doc, current_user.id):
            doc.folder_id = folder_id
            doc.save()
            count += 1
    
    return {'message': f'{count} documento(s) movido(s)', 'count': count}

def _bulk_download_documents(documents):
    """Descargar documentos en masa como ZIP."""
    # Crear archivo ZIP temporal
    zip_path = create_zip_archive([doc.file_path for doc in documents])
    
    return {
        'message': 'Archivo ZIP creado',
        'download_url': url_for('entrepreneur_documents.download_bulk', zip_file=zip_path)
    }

def _bulk_add_tags(documents, tags):
    """Agregar tags en masa."""
    count = 0
    for doc in documents:
        if _can_edit_document(doc, current_user.id):
            _update_document_tags(doc, tags)
            count += 1
    
    return {'message': f'Tags agregados a {count} documento(s)', 'count': count}

def _populate_folder_form_choices(form, entrepreneur_id):
    """Poblar opciones del formulario de carpeta."""
    folders = DocumentFolder.query.filter_by(entrepreneur_id=entrepreneur_id).all()
    form.parent_id.choices = [('', 'Sin carpeta padre')] + [(f.id, f.name) for f in folders]

# Funciones de analytics (implementación simplificada)
def _get_storage_analytics(entrepreneur_id):
    """Obtener analytics de almacenamiento."""
    return _get_storage_metrics(entrepreneur_id)

def _get_document_type_analysis(entrepreneur_id, start_date, end_date):
    """Análisis por tipos de documento."""
    return {}

def _get_document_activity_analysis(entrepreneur_id, start_date, end_date):
    """Análisis de actividad de documentos."""
    return {}

def _get_most_accessed_documents(entrepreneur_id, start_date, end_date, limit):
    """Documentos más accedidos."""
    return []

def _get_collaboration_analytics(entrepreneur_id, start_date, end_date):
    """Analytics de colaboración."""
    return {}

def _get_storage_growth_trends(entrepreneur_id, start_date, end_date):
    """Tendencias de crecimiento de almacenamiento."""
    return {}

def _get_storage_optimization_recommendations(storage_analytics, type_analysis):
    """Recomendaciones de optimización."""
    return []


# === RUTAS ADICIONALES ===

@entrepreneur_documents.route('/serve/<int:document_id>/<file_type>')
@login_required
@require_role('entrepreneur')
def serve_file(document_id, file_type):
    """Servir archivos (original, thumbnail, etc.)."""
    try:
        document = _get_document_or_404(document_id)
        
        if not _can_read_document(document, current_user.id):
            abort(403)
        
        if file_type == 'original':
            file_path = document.file_path
        elif file_type == 'thumbnail' and document.thumbnail_path:
            file_path = document.thumbnail_path
        else:
            abort(404)
        
        full_path = g.file_storage.get_file_path(file_path)
        
        if not os.path.exists(full_path):
            abort(404)
        
        return send_file(full_path)
    
    except ResourceNotFoundError:
        abort(404)
    except Exception as e:
        current_app.logger.error(f"Error sirviendo archivo: {str(e)}")
        abort(500)


# === MANEJADORES DE ERRORES ===

@entrepreneur_documents.errorhandler(ValidationError)
def handle_validation_error(error):
    """Manejar errores de validación."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_documents.index'))


@entrepreneur_documents.errorhandler(PermissionError)
def handle_permission_error(error):
    """Manejar errores de permisos."""
    if request.is_json:
        return jsonify({'success': False, 'error': 'Sin permisos'}), 403
    else:
        flash('No tienes permisos para realizar esta acción', 'error')
        return redirect(url_for('entrepreneur_documents.index'))


@entrepreneur_documents.errorhandler(ResourceNotFoundError)
def handle_not_found_error(error):
    """Manejar errores de recurso no encontrado."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 404
    else:
        flash(str(error), 'error')
        return redirect(url_for('entrepreneur_documents.index'))


@entrepreneur_documents.errorhandler(FileError)
def handle_file_error(error):
    """Manejar errores de archivos."""
    if request.is_json:
        return jsonify({'success': False, 'error': str(error)}), 400
    else:
        flash(str(error), 'error')
        return redirect(request.referrer or url_for('entrepreneur_documents.index'))


# === CONTEXT PROCESSORS ===

@entrepreneur_documents.context_processor
def inject_document_utils():
    """Inyectar utilidades en los templates."""
    return {
        'format_file_size': format_file_size,
        'format_date_short': format_date_short,
        'DocumentType': DocumentType,
        'DocumentCategory': DocumentCategory,
        'AccessLevel': AccessLevel,
        'allowed_extensions': ALL_ALLOWED_EXTENSIONS,
        'max_file_size': MAX_FILE_SIZE,
        'max_file_size_formatted': format_file_size(MAX_FILE_SIZE)
    }