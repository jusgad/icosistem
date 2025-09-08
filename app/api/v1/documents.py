"""
API endpoints para manejo de documentos del ecosistema de emprendimiento.
Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest, NotFound, Forbidden
from marshmallow import Schema, fields, validate, ValidationError
from sqlalchemy import or_, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import os
import uuid
import mimetypes
from typing import Dict, List, Optional, Tuple

# Importaciones locales
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.project import Project
from app.services.file_storage import FileStorageService
from app.services.notification_service import NotificationService
from app.core.permissions import require_permission, check_document_access
from app.core.exceptions import (
    ValidationException, 
    AuthorizationException, 
    ResourceNotFoundException,
    FileUploadException
)
from app.utils.decorators import api_response, rate_limit
from app.utils.validators import validate_file_type, validate_file_size
from app.utils.formatters import format_file_size, format_datetime
from app.extensions import db

# Blueprint para documentos
documents_bp = Blueprint('documents', __name__, url_prefix='/api/v1/documents')

# Configuración de archivos permitidos
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'rtf', 'odt', 'ods', 'odp',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg',
    'zip', 'rar', '7z', 'tar', 'gz'
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Schemas de validación con Marshmallow
class DocumentUploadSchema(Schema):
    """Schema para validar subida de documentos."""
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(missing='', validate=validate.Length(max=1000))
    document_type = fields.Str(
        required=True,
        validate=validate.OneOf([t.value for t in DocumentType])
    )
    project_id = fields.Int(missing=None, allow_none=True)
    is_public = fields.Bool(missing=False)
    tags = fields.List(fields.Str(), missing=[])
    category = fields.Str(missing='general', validate=validate.Length(max=100))
    
class DocumentUpdateSchema(Schema):
    """Schema para validar actualización de documentos."""
    title = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(validate=validate.Length(max=1000))
    document_type = fields.Str(
        validate=validate.OneOf([t.value for t in DocumentType])
    )
    is_public = fields.Bool()
    tags = fields.List(fields.Str())
    category = fields.Str(validate=validate.Length(max=100))
    status = fields.Str(
        validate=validate.OneOf([s.value for s in DocumentStatus])
    )

class DocumentFilterSchema(Schema):
    """Schema para validar filtros de búsqueda."""
    page = fields.Int(missing=1, validate=validate.Range(min=1))
    per_page = fields.Int(missing=20, validate=validate.Range(min=1, max=100))
    search = fields.Str(missing='')
    document_type = fields.Str(
        validate=validate.OneOf([t.value for t in DocumentType])
    )
    category = fields.Str()
    project_id = fields.Int()
    owner_id = fields.Int()
    is_public = fields.Bool()
    status = fields.Str(
        validate=validate.OneOf([s.value for s in DocumentStatus])
    )
    date_from = fields.DateTime()
    date_to = fields.DateTime()
    tags = fields.List(fields.Str())

# Funciones auxiliares
def get_current_user() -> User:
    """Obtiene el usuario actual basado en el JWT."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        raise AuthorizationException("Usuario no encontrado")
    return user

def allowed_file(filename: str) -> bool:
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(filename: str) -> str:
    """Genera un nombre único para el archivo."""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return unique_name

def build_document_response(document: Document, include_file_data: bool = False) -> Dict:
    """Construye la respuesta JSON para un documento."""
    response = {
        'id': document.id,
        'title': document.title,
        'description': document.description,
        'filename': document.filename,
        'original_filename': document.original_filename,
        'file_size': document.file_size,
        'file_size_formatted': format_file_size(document.file_size),
        'mime_type': document.mime_type,
        'document_type': document.document_type.value,
        'category': document.category,
        'is_public': document.is_public,
        'status': document.status.value,
        'tags': document.tags or [],
        'download_count': document.download_count,
        'created_at': format_datetime(document.created_at),
        'updated_at': format_datetime(document.updated_at),
        'owner': {
            'id': document.owner.id,
            'name': document.owner.get_display_name(),
            'email': document.owner.email,
            'user_type': document.owner.user_type.value
        }
    }
    
    if document.project:
        response['project'] = {
            'id': document.project.id,
            'name': document.project.name
        }
    
    if include_file_data:
        response['file_url'] = f"/api/v1/documents/{document.id}/download"
        response['preview_url'] = f"/api/v1/documents/{document.id}/preview"
    
    return response

def check_document_permissions(document: Document, user: User, action: str = 'read') -> bool:
    """Verifica permisos sobre un documento."""
    # Administradores tienen acceso total
    if user.is_admin():
        return True
    
    # Propietario tiene acceso total
    if document.owner_id == user.id:
        return True
    
    # Documentos públicos pueden ser leídos por todos
    if action == 'read' and document.is_public:
        return True
    
    # Verificar acceso por proyecto
    if document.project:
        # Emprendedores pueden acceder a documentos de sus proyectos
        if hasattr(user, 'entrepreneur') and user.entrepreneur:
            if document.project.entrepreneur_id == user.entrepreneur.id:
                return True
        
        # Aliados pueden acceder a documentos de proyectos que mentoreen
        if hasattr(user, 'ally') and user.ally:
            if document.project.entrepreneur.ally_id == user.ally.id:
                return action == 'read'  # Solo lectura para aliados
    
    return False

# Endpoints de la API

@documents_bp.route('', methods=['GET'])
@jwt_required()
@rate_limit(60, per=60)  # 60 requests per minute
@api_response
def list_documents():
    """
    Lista documentos con filtros y paginación.
    
    Query parameters:
    - page: Número de página (default: 1)
    - per_page: Elementos por página (default: 20, max: 100)
    - search: Búsqueda en título y descripción
    - document_type: Filtrar por tipo de documento
    - category: Filtrar por categoría
    - project_id: Filtrar por proyecto
    - owner_id: Filtrar por propietario
    - is_public: Filtrar por visibilidad
    - status: Filtrar por estado
    - date_from: Fecha inicio (ISO format)
    - date_to: Fecha fin (ISO format)
    - tags: Lista de tags separados por coma
    """
    try:
        # Validar parámetros
        schema = DocumentFilterSchema()
        filters = schema.load(request.args)
        
        current_user = get_current_user()
        
        # Construir query base
        query = Document.query.options(
            selectinload(Document.owner),
            selectinload(Document.project)
        )
        
        # Aplicar filtros de permisos
        if not current_user.is_admin():
            # Los usuarios solo ven sus documentos o documentos públicos
            access_conditions = [
                Document.owner_id == current_user.id,
                Document.is_public == True
            ]
            
            # Si es emprendedor, agregar documentos de sus proyectos
            if hasattr(current_user, 'entrepreneur') and current_user.entrepreneur:
                entrepreneur_projects = [p.id for p in current_user.entrepreneur.projects]
                if entrepreneur_projects:
                    access_conditions.append(Document.project_id.in_(entrepreneur_projects))
            
            # Si es aliado, agregar documentos de proyectos que mentorea
            if hasattr(current_user, 'ally') and current_user.ally:
                mentored_entrepreneurs = [e.id for e in current_user.ally.entrepreneurs]
                if mentored_entrepreneurs:
                    from app.models.project import Project
                    mentored_projects = db.session.query(Project.id).filter(
                        Project.entrepreneur_id.in_(mentored_entrepreneurs)
                    ).subquery()
                    access_conditions.append(Document.project_id.in_(mentored_projects))
            
            query = query.filter(or_(*access_conditions))
        
        # Aplicar filtros de búsqueda
        if filters.get('search'):
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Document.title.ilike(search_term),
                    Document.description.ilike(search_term),
                    Document.original_filename.ilike(search_term)
                )
            )
        
        if filters.get('document_type'):
            query = query.filter(Document.document_type == filters['document_type'])
        
        if filters.get('category'):
            query = query.filter(Document.category == filters['category'])
        
        if filters.get('project_id'):
            query = query.filter(Document.project_id == filters['project_id'])
        
        if filters.get('owner_id'):
            query = query.filter(Document.owner_id == filters['owner_id'])
        
        if 'is_public' in filters:
            query = query.filter(Document.is_public == filters['is_public'])
        
        if filters.get('status'):
            query = query.filter(Document.status == filters['status'])
        
        if filters.get('date_from'):
            query = query.filter(Document.created_at >= filters['date_from'])
        
        if filters.get('date_to'):
            query = query.filter(Document.created_at <= filters['date_to'])
        
        if filters.get('tags'):
            for tag in filters['tags']:
                query = query.filter(Document.tags.contains([tag]))
        
        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Document.created_at.desc())
        
        # Aplicar paginación
        pagination = query.paginate(
            page=filters['page'],
            per_page=filters['per_page'],
            error_out=False
        )
        
        # Construir respuesta
        documents = [
            build_document_response(doc, include_file_data=True) 
            for doc in pagination.items
        ]
        
        return {
            'documents': documents,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            },
            'filters_applied': {k: v for k, v in filters.items() if v}
        }
        
    except ValidationError as e:
        raise ValidationException(f"Parámetros inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error listando documentos: {str(e)}")
        raise

@documents_bp.route('', methods=['POST'])
@jwt_required()
@rate_limit(10, per=60)  # 10 uploads per minute
@api_response
def upload_document():
    """
    Sube un nuevo documento.
    
    Form data:
    - file: Archivo a subir (required)
    - title: Título del documento (required)
    - description: Descripción del documento
    - document_type: Tipo de documento (required)
    - project_id: ID del proyecto asociado
    - is_public: Si el documento es público
    - tags: Tags separados por coma
    - category: Categoría del documento
    """
    try:
        current_user = get_current_user()
        
        # Verificar que se envió un archivo
        if 'file' not in request.files:
            raise ValidationException("No se proporcionó archivo")
        
        file = request.files['file']
        if file.filename == '':
            raise ValidationException("No se seleccionó archivo")
        
        # Validar archivo
        if not allowed_file(file.filename):
            raise ValidationException(
                f"Tipo de archivo no permitido. Tipos válidos: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validar tamaño del archivo
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise ValidationException(
                f"Archivo demasiado grande. Tamaño máximo: {format_file_size(MAX_FILE_SIZE)}"
            )
        
        # Validar datos del formulario
        form_data = request.form.to_dict()
        if 'tags' in form_data:
            form_data['tags'] = [tag.strip() for tag in form_data['tags'].split(',') if tag.strip()]
        
        schema = DocumentUploadSchema()
        data = schema.load(form_data)
        
        # Verificar proyecto si se especifica
        project = None
        if data.get('project_id'):
            project = Project.query.get(data['project_id'])
            if not project:
                raise ResourceNotFoundException("Proyecto no encontrado")
            
            # Verificar permisos sobre el proyecto
            if not current_user.is_admin() and project.entrepreneur.user_id != current_user.id:
                raise AuthorizationException("Sin permisos para asociar documentos a este proyecto")
        
        # Generar nombre único para el archivo
        original_filename = secure_filename(file.filename)
        unique_filename = generate_unique_filename(original_filename)
        
        # Subir archivo usando el servicio de almacenamiento
        file_storage = FileStorageService()
        file_path = file_storage.save_file(
            file, 
            unique_filename, 
            folder='documents',
            allowed_extensions=ALLOWED_EXTENSIONS
        )
        
        # Determinar tipo MIME
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        # Crear documento en la base de datos
        document = Document(
            title=data['title'],
            description=data.get('description', ''),
            filename=unique_filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            document_type=DocumentType(data['document_type']),
            category=data.get('category', 'general'),
            is_public=data.get('is_public', False),
            tags=data.get('tags', []),
            status=DocumentStatus.ACTIVE,
            owner_id=current_user.id,
            project_id=data.get('project_id')
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Enviar notificación si el documento está asociado a un proyecto
        if project:
            notification_service = NotificationService()
            notification_service.notify_document_uploaded(document, current_user)
        
        # Log de actividad
        current_app.logger.info(
            f"Documento subido: {document.id} por usuario {current_user.id}"
        )
        
        return {
            'message': 'Documento subido exitosamente',
            'document': build_document_response(document, include_file_data=True)
        }, 201
        
    except ValidationError as e:
        raise ValidationException(f"Datos inválidos: {e.messages}")
    except FileUploadException as e:
        raise ValidationException(f"Error subiendo archivo: {str(e)}")
    except Exception as e:
        # Limpiar archivo si algo salió mal
        try:
            if 'file_path' in locals():
                file_storage = FileStorageService()
                file_storage.delete_file(file_path)
        except:
            pass
        
        current_app.logger.error(f"Error subiendo documento: {str(e)}")
        raise

@documents_bp.route('/<int:document_id>', methods=['GET'])
@jwt_required()
@rate_limit(120, per=60)  # 120 requests per minute
@api_response
def get_document(document_id: int):
    """Obtiene información detallada de un documento."""
    try:
        current_user = get_current_user()
        
        document = Document.query.options(
            selectinload(Document.owner),
            selectinload(Document.project)
        ).get(document_id)
        
        if not document:
            raise ResourceNotFoundException("Documento no encontrado")
        
        # Verificar permisos
        if not check_document_permissions(document, current_user, 'read'):
            raise AuthorizationException("Sin permisos para acceder a este documento")
        
        return {
            'document': build_document_response(document, include_file_data=True)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo documento {document_id}: {str(e)}")
        raise

@documents_bp.route('/<int:document_id>', methods=['PUT'])
@jwt_required()
@rate_limit(30, per=60)  # 30 updates per minute
@api_response
def update_document(document_id: int):
    """
    Actualiza información de un documento.
    
    JSON body puede contener:
    - title: Nuevo título
    - description: Nueva descripción
    - document_type: Nuevo tipo
    - is_public: Nueva visibilidad
    - tags: Nuevos tags
    - category: Nueva categoría
    - status: Nuevo estado (solo admin)
    """
    try:
        current_user = get_current_user()
        
        document = Document.query.get(document_id)
        if not document:
            raise ResourceNotFoundException("Documento no encontrado")
        
        # Verificar permisos de edición
        if not check_document_permissions(document, current_user, 'update'):
            raise AuthorizationException("Sin permisos para editar este documento")
        
        # Validar datos
        schema = DocumentUpdateSchema()
        data = schema.load(request.get_json() or {})
        
        # Actualizar campos
        if 'title' in data:
            document.title = data['title']
        
        if 'description' in data:
            document.description = data['description']
        
        if 'document_type' in data:
            document.document_type = DocumentType(data['document_type'])
        
        if 'is_public' in data:
            document.is_public = data['is_public']
        
        if 'tags' in data:
            document.tags = data['tags']
        
        if 'category' in data:
            document.category = data['category']
        
        # Solo admin puede cambiar estado
        if 'status' in data and current_user.is_admin():
            document.status = DocumentStatus(data['status'])
        
        document.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        current_app.logger.info(
            f"Documento actualizado: {document.id} por usuario {current_user.id}"
        )
        
        return {
            'message': 'Documento actualizado exitosamente',
            'document': build_document_response(document, include_file_data=True)
        }
        
    except ValidationError as e:
        raise ValidationException(f"Datos inválidos: {e.messages}")
    except Exception as e:
        current_app.logger.error(f"Error actualizando documento {document_id}: {str(e)}")
        raise

@documents_bp.route('/<int:document_id>', methods=['DELETE'])
@jwt_required()
@rate_limit(20, per=60)  # 20 deletes per minute
@api_response
def delete_document(document_id: int):
    """Elimina un documento."""
    try:
        current_user = get_current_user()
        
        document = Document.query.get(document_id)
        if not document:
            raise ResourceNotFoundException("Documento no encontrado")
        
        # Verificar permisos de eliminación
        if not check_document_permissions(document, current_user, 'delete'):
            raise AuthorizationException("Sin permisos para eliminar este documento")
        
        # Eliminar archivo físico
        try:
            file_storage = FileStorageService()
            file_storage.delete_file(document.file_path)
        except Exception as e:
            current_app.logger.warning(f"Error eliminando archivo físico: {str(e)}")
        
        # Eliminar de base de datos
        db.session.delete(document)
        db.session.commit()
        
        current_app.logger.info(
            f"Documento eliminado: {document_id} por usuario {current_user.id}"
        )
        
        return {
            'message': 'Documento eliminado exitosamente'
        }
        
    except Exception as e:
        current_app.logger.error(f"Error eliminando documento {document_id}: {str(e)}")
        raise

@documents_bp.route('/<int:document_id>/download', methods=['GET'])
@jwt_required()
@rate_limit(100, per=60)  # 100 downloads per minute
def download_document(document_id: int):
    """Descarga un archivo de documento."""
    try:
        current_user = get_current_user()
        
        document = Document.query.get(document_id)
        if not document:
            raise ResourceNotFoundException("Documento no encontrado")
        
        # Verificar permisos
        if not check_document_permissions(document, current_user, 'read'):
            raise AuthorizationException("Sin permisos para descargar este documento")
        
        # Incrementar contador de descargas
        document.download_count += 1
        db.session.commit()
        
        # Servir archivo
        file_storage = FileStorageService()
        file_path = file_storage.get_file_path(document.file_path)
        
        current_app.logger.info(
            f"Documento descargado: {document.id} por usuario {current_user.id}"
        )
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=document.original_filename,
            mimetype=document.mime_type
        )
        
    except Exception as e:
        current_app.logger.error(f"Error descargando documento {document_id}: {str(e)}")
        raise

@documents_bp.route('/<int:document_id>/preview', methods=['GET'])
@jwt_required()
@rate_limit(100, per=60)  # 100 previews per minute
def preview_document(document_id: int):
    """Obtiene vista previa de un documento (para archivos soportados)."""
    try:
        current_user = get_current_user()
        
        document = Document.query.get(document_id)
        if not document:
            raise ResourceNotFoundException("Documento no encontrado")
        
        # Verificar permisos
        if not check_document_permissions(document, current_user, 'read'):
            raise AuthorizationException("Sin permisos para previsualizar este documento")
        
        # Solo para ciertos tipos de archivo
        preview_types = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'txt'}
        file_ext = document.original_filename.rsplit('.', 1)[1].lower()
        
        if file_ext not in preview_types:
            raise ValidationException("Vista previa no disponible para este tipo de archivo")
        
        # Servir archivo para vista previa
        file_storage = FileStorageService()
        file_path = file_storage.get_file_path(document.file_path)
        
        return send_file(
            file_path,
            mimetype=document.mime_type
        )
        
    except Exception as e:
        current_app.logger.error(f"Error previsualizando documento {document_id}: {str(e)}")
        raise

@documents_bp.route('/categories', methods=['GET'])
@jwt_required()
@rate_limit(60, per=60)
@api_response
def get_categories():
    """Obtiene lista de categorías de documentos disponibles."""
    try:
        current_user = get_current_user()
        
        # Obtener categorías únicas de documentos accesibles
        query = db.session.query(Document.category.distinct()).filter(
            Document.category.isnot(None),
            Document.status == DocumentStatus.ACTIVE
        )
        
        # Aplicar filtros de acceso si no es admin
        if not current_user.is_admin():
            access_conditions = [
                Document.owner_id == current_user.id,
                Document.is_public == True
            ]
            query = query.filter(or_(*access_conditions))
        
        categories = [row[0] for row in query.all() if row[0]]
        
        return {
            'categories': sorted(categories)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo categorías: {str(e)}")
        raise

@documents_bp.route('/statistics', methods=['GET'])
@jwt_required()
@require_permission('admin')
@rate_limit(30, per=60)
@api_response
def get_statistics():
    """Obtiene estadísticas de documentos (solo admin)."""
    try:
        # Estadísticas generales
        total_documents = Document.query.count()
        active_documents = Document.query.filter(Document.status == DocumentStatus.ACTIVE).count()
        public_documents = Document.query.filter(Document.is_public == True).count()
        
        # Estadísticas por tipo
        type_stats = db.session.query(
            Document.document_type,
            db.func.count(Document.id)
        ).group_by(Document.document_type).all()
        
        # Estadísticas por categoría
        category_stats = db.session.query(
            Document.category,
            db.func.count(Document.id)
        ).group_by(Document.category).all()
        
        # Documentos más descargados
        top_downloads = Document.query.filter(
            Document.download_count > 0
        ).order_by(Document.download_count.desc()).limit(10).all()
        
        # Tamaño total de archivos
        total_size = db.session.query(db.func.sum(Document.file_size)).scalar() or 0
        
        return {
            'general': {
                'total_documents': total_documents,
                'active_documents': active_documents,
                'public_documents': public_documents,
                'total_size': total_size,
                'total_size_formatted': format_file_size(total_size)
            },
            'by_type': [
                {'type': type_val.value, 'count': count} 
                for type_val, count in type_stats
            ],
            'by_category': [
                {'category': cat, 'count': count} 
                for cat, count in category_stats
            ],
            'top_downloads': [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'download_count': doc.download_count,
                    'owner': doc.owner.get_display_name()
                }
                for doc in top_downloads
            ]
        }
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estadísticas: {str(e)}")
        raise

# Manejo de errores específicos del blueprint
@documents_bp.errorhandler(ValidationException)
def handle_validation_error(e):
    return jsonify({'error': str(e), 'type': 'validation_error'}), 400

@documents_bp.errorhandler(AuthorizationException)
def handle_authorization_error(e):
    return jsonify({'error': str(e), 'type': 'authorization_error'}), 403

@documents_bp.errorhandler(ResourceNotFoundException)
def handle_not_found_error(e):
    return jsonify({'error': str(e), 'type': 'not_found_error'}), 404

@documents_bp.errorhandler(FileUploadException)
def handle_file_upload_error(e):
    return jsonify({'error': str(e), 'type': 'file_upload_error'}), 400

@documents_bp.errorhandler(413)
def handle_file_too_large(e):
    return jsonify({
        'error': f'Archivo demasiado grande. Tamaño máximo permitido: {format_file_size(MAX_FILE_SIZE)}',
        'type': 'file_size_error'
    }), 413