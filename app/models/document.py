"""
Modelo Documento del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de documentos y archivos,
incluyendo almacenamiento, versioning, permisos, colaboración y templates.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table, BigInteger
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
import os
import mimetypes
from pathlib import Path

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..core.constants import (
    DOCUMENT_TYPES,
    DOCUMENT_STATUS,
    DOCUMENT_CATEGORIES,
    ACCESS_LEVELS,
    FILE_STORAGE_PROVIDERS,
    DOCUMENT_FORMATS,
    APPROVAL_STATUS
)
from ..core.exceptions import ValidationError


class DocumentType(Enum):
    """Tipos de documento"""
    BUSINESS_PLAN = "business_plan"
    PITCH_DECK = "pitch_deck"
    FINANCIAL_MODEL = "financial_model"
    MARKET_RESEARCH = "market_research"
    LEGAL_DOCUMENT = "legal_document"
    CONTRACT = "contract"
    REPORT = "report"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEMPLATE = "template"
    FORM = "form"
    MANUAL = "manual"
    GUIDE = "guide"
    WHITEPAPER = "whitepaper"
    CASE_STUDY = "case_study"
    RESOURCE = "resource"
    POLICY = "policy"
    PROCEDURE = "procedure"
    TRAINING_MATERIAL = "training_material"
    MARKETING_MATERIAL = "marketing_material"
    TECHNICAL_SPEC = "technical_spec"
    OTHER = "other"


class DocumentStatus(Enum):
    """Estados del documento"""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    REJECTED = "rejected"
    DELETED = "deleted"


class DocumentCategory(Enum):
    """Categorías de documento"""
    BUSINESS = "business"
    LEGAL = "legal"
    FINANCIAL = "financial"
    TECHNICAL = "technical"
    MARKETING = "marketing"
    OPERATIONS = "operations"
    HR = "hr"
    TRAINING = "training"
    RESEARCH = "research"
    COMPLIANCE = "compliance"
    TEMPLATES = "templates"
    RESOURCES = "resources"


class AccessLevel(Enum):
    """Niveles de acceso"""
    PRIVATE = "private"          # Solo propietario
    RESTRICTED = "restricted"    # Usuarios específicos
    INTERNAL = "internal"        # Organización/programa
    PUBLIC = "public"           # Todos los usuarios
    EXTERNAL = "external"       # Incluyendo invitados


class FileStorageProvider(Enum):
    """Proveedores de almacenamiento"""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"
    DROPBOX = "dropbox"
    GOOGLE_DRIVE = "google_drive"


class ApprovalStatus(Enum):
    """Estados de aprobación"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


# Tabla de asociación para colaboradores del documento
document_collaborators = Table(
    'document_collaborators',
    Column('document_id', Integer, ForeignKey('documents.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('permission_level', String(20), default='read'),  # read, comment, edit, admin
    Column('invited_by_id', Integer, ForeignKey('users.id')),
    Column('invited_at', DateTime, default=datetime.utcnow),
    Column('accepted_at', DateTime),
    Column('last_accessed_at', DateTime),
    Column('is_active', Boolean, default=True),
    Column('notification_settings', JSON),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para tags del documento
document_tags = Table(
    'document_tags',
    Column('document_id', Integer, ForeignKey('documents.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Document(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Documento
    
    Representa documentos y archivos en el ecosistema de emprendimiento
    con funcionalidades avanzadas de gestión, colaboración y control de versiones.
    """
    
    __tablename__ = 'documents'
    
    # Información básica
    title = Column(String(300), nullable=False, index=True)
    description = Column(Text)
    document_type = Column(SQLEnum(DocumentType), nullable=False, index=True)
    category = Column(SQLEnum(DocumentCategory), index=True)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.DRAFT, index=True)
    
    # Propietario del documento
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    owner = relationship("User", foreign_keys=[owner_id])
    
    # Información del archivo
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500))
    file_path = Column(String(1000))  # Ruta en el sistema de almacenamiento
    file_url = Column(String(1000))   # URL pública si aplica
    file_size = Column(BigInteger)    # Tamaño en bytes
    mime_type = Column(String(100))
    file_extension = Column(String(20))
    file_hash = Column(String(128))   # Hash para verificar integridad
    
    # Almacenamiento
    storage_provider = Column(SQLEnum(FileStorageProvider), default=FileStorageProvider.LOCAL)
    storage_path = Column(String(1000))  # Ruta específica del proveedor
    storage_metadata = Column(JSON)      # Metadatos específicos del proveedor
    
    # Control de versiones
    version = Column(String(20), default='1.0')
    version_number = Column(Integer, default=1)
    parent_document_id = Column(Integer, ForeignKey('documents.id'))
    parent_document = relationship("Document", remote_side="Document.id", backref="versions")
    is_latest_version = Column(Boolean, default=True, index=True)
    
    # Contenido y metadatos
    content_text = Column(Text)          # Texto extraído para búsqueda
    content_preview = Column(Text)       # Vista previa del contenido
    page_count = Column(Integer)         # Número de páginas (PDFs, docs)
    word_count = Column(Integer)         # Número de palabras
    language = Column(String(10), default='es')
    
    # Control de acceso
    access_level = Column(SQLEnum(AccessLevel), default=AccessLevel.PRIVATE, index=True)
    password_protected = Column(Boolean, default=False)
    password_hash = Column(String(255))
    download_enabled = Column(Boolean, default=True)
    print_enabled = Column(Boolean, default=True)
    copy_enabled = Column(Boolean, default=True)
    
    # Configuración de colaboración
    comments_enabled = Column(Boolean, default=True)
    suggestions_enabled = Column(Boolean, default=True)
    version_control_enabled = Column(Boolean, default=True)
    collaboration_enabled = Column(Boolean, default=True)
    
    # Fechas importantes
    published_at = Column(DateTime)
    expires_at = Column(DateTime)
    last_accessed_at = Column(DateTime)
    last_modified_at = Column(DateTime)
    
    # Aprobación y revisión
    approval_status = Column(SQLEnum(ApprovalStatus))
    approved_by_id = Column(Integer, ForeignKey('users.id'))
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    approved_at = Column(DateTime)
    approval_notes = Column(Text)
    
    # Métricas y estadísticas
    view_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    rating = Column(Float)
    rating_count = Column(Integer, default=0)
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project", back_populates="documents")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program", back_populates="documents")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization", back_populates="documents")
    
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship("Client", back_populates="documents")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting", back_populates="documents")
    
    task_id = Column(Integer, ForeignKey('tasks.id'))
    task = relationship("Task", back_populates="documents")
    
    # Configuración avanzada
    auto_save_enabled = Column(Boolean, default=True)
    backup_enabled = Column(Boolean, default=True)
    encryption_enabled = Column(Boolean, default=False)
    watermark_enabled = Column(Boolean, default=False)
    
    # SEO y búsqueda
    keywords = Column(JSON)              # Keywords para búsqueda
    search_vector = Column(Text)         # Vector de búsqueda full-text
    
    # Configuración personalizada
    custom_properties = Column(JSON)     # Propiedades personalizadas
    processing_status = Column(String(50))  # Estado del procesamiento (OCR, etc.)
    processing_metadata = Column(JSON)   # Metadatos del procesamiento
    
    # Relaciones
    
    # Colaboradores
    collaborators = relationship("User",
                               secondary=document_collaborators,
                               back_populates="collaborative_documents")
    
    # Tags
    tags = relationship("Tag", secondary=document_tags, back_populates="documents")
    
    # Comentarios
    comments = relationship("DocumentComment", back_populates="document")
    
    # Actividades del documento
    activities = relationship("ActivityLog", back_populates="document")
    
    # Shares/Compartidos
    shares = relationship("DocumentShare", back_populates="document")
    
    def __init__(self, **kwargs):
        """Inicialización del documento"""
        super().__init__(**kwargs)
        
        # Extraer información del archivo si se proporciona filename
        if self.filename and not self.file_extension:
            self.file_extension = Path(self.filename).suffix.lower()
        
        if self.filename and not self.mime_type:
            self.mime_type, _ = mimetypes.guess_type(self.filename)
        
        # Configurar metadatos por defecto
        if not self.storage_metadata:
            self.storage_metadata = {}
        
        if not self.custom_properties:
            self.custom_properties = {}
        
        # Configurar versión inicial
        if not self.version:
            self.version = '1.0'
            self.version_number = 1
    
    def __repr__(self):
        return f'<Document {self.title} ({self.document_type.value})>'
    
    def __str__(self):
        return f'{self.title} - {self.filename}'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título del documento"""
        if not title or len(title.strip()) < 1:
            raise ValidationError("El título es requerido")
        if len(title) > 300:
            raise ValidationError("El título no puede exceder 300 caracteres")
        return title.strip()
    
    @validates('filename')
    def validate_filename(self, key, filename):
        """Validar nombre del archivo"""
        if not filename:
            raise ValidationError("El nombre del archivo es requerido")
        if len(filename) > 500:
            raise ValidationError("El nombre del archivo no puede exceder 500 caracteres")
        
        # Validar caracteres peligrosos
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in dangerous_chars):
            raise ValidationError("El nombre del archivo contiene caracteres no válidos")
        
        return filename
    
    @validates('file_size')
    def validate_file_size(self, key, size):
        """Validar tamaño del archivo"""
        if size is not None:
            max_size = 500 * 1024 * 1024  # 500MB por defecto
            if size > max_size:
                raise ValidationError(f"El archivo excede el tamaño máximo permitido ({max_size // (1024*1024)}MB)")
            if size < 0:
                raise ValidationError("El tamaño del archivo no puede ser negativo")
        return size
    
    @validates('version')
    def validate_version(self, key, version):
        """Validar formato de versión"""
        if version:
            # Formato: X.Y o X.Y.Z
            version_pattern = r'^\d+\.\d+(\.\d+)?$'
            if not re.match(version_pattern, version):
                raise ValidationError("Formato de versión inválido (usar X.Y o X.Y.Z)")
        return version
    
    @validates('rating')
    def validate_rating(self, key, rating):
        """Validar calificación"""
        if rating is not None:
            if rating < 1 or rating > 5:
                raise ValidationError("La calificación debe estar entre 1 y 5")
        return rating
    
    # Propiedades híbridas
    @hybrid_property
    def file_size_formatted(self):
        """Tamaño del archivo formateado"""
        if not self.file_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"
    
    @hybrid_property
    def is_image(self):
        """Verificar si es una imagen"""
        return self.mime_type and self.mime_type.startswith('image/')
    
    @hybrid_property
    def is_video(self):
        """Verificar si es un video"""
        return self.mime_type and self.mime_type.startswith('video/')
    
    @hybrid_property
    def is_audio(self):
        """Verificar si es audio"""
        return self.mime_type and self.mime_type.startswith('audio/')
    
    @hybrid_property
    def is_pdf(self):
        """Verificar si es PDF"""
        return self.mime_type == 'application/pdf'
    
    @hybrid_property
    def is_office_document(self):
        """Verificar si es documento de Office"""
        office_types = [
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        return self.mime_type in office_types
    
    @hybrid_property
    def is_expired(self):
        """Verificar si el documento está vencido"""
        return self.expires_at and self.expires_at < datetime.utcnow()
    
    @hybrid_property
    def is_public(self):
        """Verificar si es público"""
        return self.access_level in [AccessLevel.PUBLIC, AccessLevel.EXTERNAL]
    
    @hybrid_property
    def can_be_previewed(self):
        """Verificar si puede tener vista previa"""
        previewable_types = [
            'application/pdf',
            'text/plain',
            'text/html',
            'text/csv'
        ]
        return (self.is_image or 
                self.mime_type in previewable_types or 
                self.is_office_document)
    
    @hybrid_property
    def collaborator_count(self):
        """Número de colaboradores"""
        return len(self.collaborators)
    
    @hybrid_property
    def days_since_modified(self):
        """Días desde la última modificación"""
        if self.last_modified_at:
            return (datetime.utcnow() - self.last_modified_at).days
        return (datetime.utcnow() - self.created_at).days if self.created_at else 0
    
    # Métodos de negocio
    def add_collaborator(self, user, permission_level: str = 'read', 
                        invited_by_user_id: int = None, 
                        notification_settings: Dict[str, Any] = None) -> bool:
        """Agregar colaborador al documento"""
        # Verificar permisos válidos
        valid_permissions = ['read', 'comment', 'edit', 'admin']
        if permission_level not in valid_permissions:
            raise ValidationError(f"Nivel de permiso inválido: {permission_level}")
        
        # Verificar si ya es colaborador
        from .. import db
        
        existing = db.session.execute(
            document_collaborators.select().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user.id
            )
        ).first()
        
        if existing:
            if existing.is_active:
                return False  # Ya es colaborador activo
            else:
                # Reactivar colaborador
                db.session.execute(
                    document_collaborators.update().where(
                        document_collaborators.c.document_id == self.id,
                        document_collaborators.c.user_id == user.id
                    ).values(
                        is_active=True,
                        permission_level=permission_level,
                        invited_at=datetime.utcnow(),
                        notification_settings=notification_settings or {
                            'document_changes': True,
                            'comments': True,
                            'version_updates': True
                        }
                    )
                )
                return True
        
        # Agregar nuevo colaborador
        collaborator_data = {
            'document_id': self.id,
            'user_id': user.id,
            'permission_level': permission_level,
            'invited_by_id': invited_by_user_id or self.owner_id,
            'notification_settings': notification_settings or {
                'document_changes': True,
                'comments': True,
                'version_updates': True
            }
        }
        
        db.session.execute(document_collaborators.insert().values(collaborator_data))
        
        # Log de actividad
        self._log_activity('collaborator_added', f"Colaborador {user.full_name} agregado con permisos {permission_level}")
        
        return True
    
    def remove_collaborator(self, user, removed_by_user_id: int = None) -> bool:
        """Remover colaborador del documento"""
        from .. import db
        
        # Verificar si es colaborador
        collaborator = db.session.execute(
            document_collaborators.select().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user.id,
                document_collaborators.c.is_active == True
            )
        ).first()
        
        if not collaborator:
            return False
        
        # Marcar como inactivo
        db.session.execute(
            document_collaborators.update().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user.id
            ).values(is_active=False)
        )
        
        # Log de actividad
        self._log_activity('collaborator_removed', f"Colaborador {user.full_name} removido")
        
        return True
    
    def update_collaborator_permission(self, user, new_permission: str, 
                                     updated_by_user_id: int = None) -> bool:
        """Actualizar permisos de colaborador"""
        valid_permissions = ['read', 'comment', 'edit', 'admin']
        if new_permission not in valid_permissions:
            raise ValidationError(f"Nivel de permiso inválido: {new_permission}")
        
        from .. import db
        
        result = db.session.execute(
            document_collaborators.update().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user.id
            ).values(permission_level=new_permission)
        )
        
        if result.rowcount > 0:
            self._log_activity('permission_updated', f"Permisos de {user.full_name} actualizados a {new_permission}")
            return True
        
        return False
    
    def get_user_permission(self, user_id: int) -> Optional[str]:
        """Obtener nivel de permiso de un usuario"""
        # Propietario tiene permisos de admin
        if user_id == self.owner_id:
            return 'admin'
        
        from .. import db
        
        collaborator = db.session.execute(
            document_collaborators.select().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user_id,
                document_collaborators.c.is_active == True
            )
        ).first()
        
        return collaborator.permission_level if collaborator else None
    
    def can_user_access(self, user_id: int, required_permission: str = 'read') -> bool:
        """Verificar si un usuario puede acceder al documento"""
        # Documentos públicos pueden ser leídos por todos
        if self.access_level in [AccessLevel.PUBLIC, AccessLevel.EXTERNAL] and required_permission == 'read':
            return True
        
        user_permission = self.get_user_permission(user_id)
        if not user_permission:
            return False
        
        # Jerarquía de permisos
        permission_hierarchy = ['read', 'comment', 'edit', 'admin']
        user_level = permission_hierarchy.index(user_permission)
        required_level = permission_hierarchy.index(required_permission)
        
        return user_level >= required_level
    
    def create_new_version(self, updated_by_user_id: int, version_notes: str = None,
                          new_file_path: str = None, new_file_size: int = None) -> 'Document':
        """Crear nueva versión del documento"""
        # Marcar versión actual como no-latest
        self.is_latest_version = False
        
        # Calcular nueva versión
        version_parts = self.version.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1])
        patch = int(version_parts[2]) if len(version_parts) > 2 else 0
        
        # Incrementar versión menor
        minor += 1
        new_version = f"{major}.{minor}"
        if patch > 0:
            new_version += f".{patch}"
        
        # Crear nueva versión
        new_document = Document(
            title=self.title,
            description=self.description,
            document_type=self.document_type,
            category=self.category,
            status=DocumentStatus.DRAFT,
            owner_id=self.owner_id,
            filename=self.filename,
            original_filename=self.original_filename,
            file_path=new_file_path or self.file_path,
            file_size=new_file_size or self.file_size,
            mime_type=self.mime_type,
            file_extension=self.file_extension,
            storage_provider=self.storage_provider,
            version=new_version,
            version_number=self.version_number + 1,
            parent_document_id=self.parent_document_id or self.id,
            is_latest_version=True,
            access_level=self.access_level,
            project_id=self.project_id,
            program_id=self.program_id,
            organization_id=self.organization_id
        )
        
        from .. import db
        db.session.add(new_document)
        db.session.flush()  # Para obtener ID
        
        # Copiar colaboradores
        for collaborator in self.collaborators:
            new_document.add_collaborator(collaborator, 
                                        self.get_user_permission(collaborator.id))
        
        # Log de actividad
        self._log_activity('version_created', f"Nueva versión {new_version} creada", updated_by_user_id)
        
        return new_document
    
    def increment_view_count(self, user_id: int = None):
        """Incrementar contador de visualizaciones"""
        self.view_count = (self.view_count or 0) + 1
        self.last_accessed_at = datetime.utcnow()
        
        if user_id:
            self._update_collaborator_access(user_id)
        
        # Log de actividad (sin spam, solo una vez por día por usuario)
        if user_id:
            self._log_activity('document_viewed', f"Documento visualizado", user_id, 
                             should_log=self._should_log_view(user_id))
    
    def increment_download_count(self, user_id: int = None):
        """Incrementar contador de descargas"""
        self.download_count = (self.download_count or 0) + 1
        
        if user_id:
            self._update_collaborator_access(user_id)
            self._log_activity('document_downloaded', f"Documento descargado", user_id)
    
    def increment_share_count(self, user_id: int = None):
        """Incrementar contador de compartidos"""
        self.share_count = (self.share_count or 0) + 1
        
        if user_id:
            self._log_activity('document_shared', f"Documento compartido", user_id)
    
    def _update_collaborator_access(self, user_id: int):
        """Actualizar último acceso del colaborador"""
        from .. import db
        
        db.session.execute(
            document_collaborators.update().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.user_id == user_id
            ).values(last_accessed_at=datetime.utcnow())
        )
    
    def _should_log_view(self, user_id: int) -> bool:
        """Determinar si se debe logear la visualización"""
        from .activity_log import ActivityLog
        
        # Solo logear una vez por día por usuario
        today = date.today()
        existing_view = ActivityLog.query.filter(
            ActivityLog.document_id == self.id,
            ActivityLog.user_id == user_id,
            ActivityLog.activity_type == 'document_viewed',
            ActivityLog.created_at >= datetime.combine(today, datetime.min.time())
        ).first()
        
        return existing_view is None
    
    def add_rating(self, user_id: int, rating_value: float, review: str = None):
        """Agregar calificación al documento"""
        if rating_value < 1 or rating_value > 5:
            raise ValidationError("La calificación debe estar entre 1 y 5")
        
        # Aquí se podría crear un modelo DocumentRating separado
        # Por simplicidad, calculamos el promedio directamente
        
        current_total = (self.rating or 0) * (self.rating_count or 0)
        new_total = current_total + rating_value
        self.rating_count = (self.rating_count or 0) + 1
        self.rating = new_total / self.rating_count
        
        self._log_activity('document_rated', f"Documento calificado: {rating_value} estrellas", user_id)
    
    def publish_document(self, published_by_user_id: int):
        """Publicar documento"""
        if self.status == DocumentStatus.PUBLISHED:
            return False
        
        self.status = DocumentStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        
        self._log_activity('document_published', "Documento publicado", published_by_user_id)
        return True
    
    def archive_document(self, archived_by_user_id: int, reason: str = None):
        """Archivar documento"""
        self.status = DocumentStatus.ARCHIVED
        
        archive_note = f"Documento archivado"
        if reason:
            archive_note += f": {reason}"
        
        self._log_activity('document_archived', archive_note, archived_by_user_id)
    
    def set_expiration_date(self, expires_at: datetime, set_by_user_id: int):
        """Establecer fecha de vencimiento"""
        if expires_at <= datetime.utcnow():
            raise ValidationError("La fecha de vencimiento debe ser futura")
        
        self.expires_at = expires_at
        self._log_activity('expiration_set', f"Fecha de vencimiento establecida: {expires_at.isoformat()}", set_by_user_id)
    
    def process_content_extraction(self):
        """Procesar extracción de contenido para búsqueda"""
        # Placeholder para procesamiento de contenido
        # En producción, esto invocaría servicios de OCR, parsing, etc.
        
        self.processing_status = 'processing'
        
        try:
            if self.is_pdf:
                self._extract_pdf_content()
            elif self.is_office_document:
                self._extract_office_content()
            elif self.mime_type == 'text/plain':
                self._extract_text_content()
            
            self.processing_status = 'completed'
            
        except Exception as e:
            self.processing_status = 'failed'
            self.processing_metadata = {'error': str(e)}
    
    def _extract_pdf_content(self):
        """Extraer contenido de PDF"""
        # Implementar extracción de PDF usando PyPDF2, pdfplumber, etc.
        self.content_text = "Contenido PDF extraído..."
        self.page_count = 10  # Placeholder
        self.word_count = 1500  # Placeholder
    
    def _extract_office_content(self):
        """Extraer contenido de documentos Office"""
        # Implementar extracción usando python-docx, openpyxl, etc.
        self.content_text = "Contenido Office extraído..."
        self.word_count = 800  # Placeholder
    
    def _extract_text_content(self):
        """Extraer contenido de archivo de texto"""
        # Leer archivo de texto directamente
        self.content_text = "Contenido de texto..."
        if self.content_text:
            self.word_count = len(self.content_text.split())
    
    def _log_activity(self, activity_type: str, description: str, 
                     user_id: int = None, should_log: bool = True):
        """Registrar actividad del documento"""
        if not should_log:
            return
            
        from .activity_log import ActivityLog
        from .. import db
        
        activity = ActivityLog(
            activity_type=activity_type,
            description=description,
            document_id=self.id,
            user_id=user_id or self.owner_id,
            metadata={
                'document_title': self.title,
                'document_type': self.document_type.value,
                'version': self.version
            }
        )
        
        db.session.add(activity)
    
    def generate_share_link(self, shared_by_user_id: int, expires_in_hours: int = 24,
                           permission_level: str = 'read', requires_login: bool = True) -> str:
        """Generar enlace de compartir"""
        import uuid
        
        share_token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        share = DocumentShare(
            document_id=self.id,
            shared_by_id=shared_by_user_id,
            share_token=share_token,
            permission_level=permission_level,
            expires_at=expires_at,
            requires_login=requires_login,
            is_active=True
        )
        
        from .. import db
        db.session.add(share)
        
        # Incrementar contador
        self.increment_share_count(shared_by_user_id)
        
        # Generar URL
        base_url = "https://app.ecosistema.com"  # Configurar desde settings
        share_url = f"{base_url}/documents/shared/{share_token}"
        
        return share_url
    
    def get_version_history(self) -> List['Document']:
        """Obtener historial de versiones"""
        if self.parent_document_id:
            # Este es una versión, obtener desde el documento padre
            return Document.query.filter(
                (Document.id == self.parent_document_id) |
                (Document.parent_document_id == self.parent_document_id)
            ).order_by(Document.version_number.desc()).all()
        else:
            # Este es el documento original
            return Document.query.filter(
                (Document.id == self.id) |
                (Document.parent_document_id == self.id)
            ).order_by(Document.version_number.desc()).all()
    
    def get_latest_version(self) -> 'Document':
        """Obtener la versión más reciente"""
        if self.is_latest_version:
            return self
        
        versions = self.get_version_history()
        return next((v for v in versions if v.is_latest_version), self)
    
    def get_document_analytics(self) -> Dict[str, Any]:
        """Obtener analytics del documento"""
        collaborator_stats = self._get_collaborator_stats()
        
        return {
            'basic_info': {
                'title': self.title,
                'type': self.document_type.value,
                'category': self.category.value if self.category else None,
                'status': self.status.value,
                'version': self.version,
                'file_size': self.file_size_formatted,
                'mime_type': self.mime_type,
                'created_at': self.created_at.isoformat() if self.created_at else None
            },
            'engagement': {
                'view_count': self.view_count,
                'download_count': self.download_count,
                'share_count': self.share_count,
                'comment_count': self.comment_count,
                'rating': self.rating,
                'rating_count': self.rating_count
            },
            'collaboration': {
                'collaborator_count': self.collaborator_count,
                'active_collaborators': collaborator_stats['active_count'],
                'recent_activity': collaborator_stats['recent_activity'],
                'permission_distribution': collaborator_stats['permission_distribution']
            },
            'content': {
                'page_count': self.page_count,
                'word_count': self.word_count,
                'language': self.language,
                'has_content_extraction': bool(self.content_text),
                'processing_status': self.processing_status
            },
            'access': {
                'access_level': self.access_level.value,
                'is_public': self.is_public,
                'password_protected': self.password_protected,
                'download_enabled': self.download_enabled
            },
            'lifecycle': {
                'days_since_created': (datetime.utcnow() - self.created_at).days if self.created_at else 0,
                'days_since_modified': self.days_since_modified,
                'is_expired': self.is_expired,
                'expires_at': self.expires_at.isoformat() if self.expires_at else None
            }
        }
    
    def _get_collaborator_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de colaboradores"""
        from .. import db
        
        collaborators_data = db.session.execute(
            document_collaborators.select().where(
                document_collaborators.c.document_id == self.id,
                document_collaborators.c.is_active == True
            )
        ).fetchall()
        
        if not collaborators_data:
            return {
                'active_count': 0,
                'recent_activity': 0,
                'permission_distribution': {}
            }
        
        # Contar actividad reciente (última semana)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_activity = len([
            c for c in collaborators_data 
            if c.last_accessed_at and c.last_accessed_at >= week_ago
        ])
        
        # Distribución de permisos
        permission_dist = {}
        for collaborator in collaborators_data:
            perm = collaborator.permission_level
            permission_dist[perm] = permission_dist.get(perm, 0) + 1
        
        return {
            'active_count': len(collaborators_data),
            'recent_activity': recent_activity,
            'permission_distribution': permission_dist
        }
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener actividad reciente del documento"""
        recent_activities = (self.activities
                           .order_by(ActivityLog.created_at.desc())
                           .limit(limit)
                           .all())
        
        return [
            {
                'id': activity.id,
                'type': activity.activity_type,
                'description': activity.description,
                'user': activity.user.full_name if activity.user else 'Sistema',
                'timestamp': activity.created_at.isoformat(),
                'metadata': activity.metadata
            }
            for activity in recent_activities
        ]
    
    def create_backup(self, backup_type: str = 'manual', 
                     created_by_user_id: int = None) -> Dict[str, Any]:
        """Crear backup del documento"""
        import uuid
        
        backup_id = str(uuid.uuid4())
        backup_timestamp = datetime.utcnow()
        
        backup_metadata = {
            'backup_id': backup_id,
            'backup_type': backup_type,
            'original_document_id': self.id,
            'document_title': self.title,
            'document_version': self.version,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'created_at': backup_timestamp.isoformat(),
            'created_by': created_by_user_id
        }
        
        # En producción, aquí se copiaría el archivo físico
        # backup_file_path = f"backups/{backup_id}/{self.filename}"
        
        self._log_activity('backup_created', f"Backup creado: {backup_id}", created_by_user_id)
        
        return backup_metadata
    
    # Métodos de búsqueda y filtrado
    @classmethod
    def search_documents(cls, query: str = None, filters: Dict[str, Any] = None,
                        user_id: int = None, limit: int = 50, offset: int = 0):
        """Buscar documentos"""
        search = cls.query.filter(cls.is_deleted == False)
        
        # Filtrar por acceso del usuario
        if user_id:
            search = search.filter(
                (cls.owner_id == user_id) |
                (cls.access_level.in_([AccessLevel.PUBLIC, AccessLevel.EXTERNAL])) |
                (cls.collaborators.any(id=user_id))
            )
        
        # Búsqueda por texto
        if query:
            search_term = f"%{query}%"
            search = search.filter(
                cls.title.ilike(search_term) |
                cls.description.ilike(search_term) |
                cls.content_text.ilike(search_term) |
                cls.filename.ilike(search_term)
            )
        
        # Aplicar filtros
        if filters:
            if filters.get('document_type'):
                search = search.filter(cls.document_type == filters['document_type'])
            
            if filters.get('category'):
                search = search.filter(cls.category == filters['category'])
            
            if filters.get('status'):
                if isinstance(filters['status'], list):
                    search = search.filter(cls.status.in_(filters['status']))
                else:
                    search = search.filter(cls.status == filters['status'])
            
            if filters.get('owner_id'):
                search = search.filter(cls.owner_id == filters['owner_id'])
            
            if filters.get('project_id'):
                search = search.filter(cls.project_id == filters['project_id'])
            
            if filters.get('organization_id'):
                search = search.filter(cls.organization_id == filters['organization_id'])
            
            if filters.get('access_level'):
                search = search.filter(cls.access_level == filters['access_level'])
            
            if filters.get('file_type'):
                if filters['file_type'] == 'image':
                    search = search.filter(cls.mime_type.like('image/%'))
                elif filters['file_type'] == 'video':
                    search = search.filter(cls.mime_type.like('video/%'))
                elif filters['file_type'] == 'audio':
                    search = search.filter(cls.mime_type.like('audio/%'))
                elif filters['file_type'] == 'pdf':
                    search = search.filter(cls.mime_type == 'application/pdf')
                elif filters['file_type'] == 'office':
                    office_types = [
                        'application/msword',
                        'application/vnd.openxmlformats-officedocument%',
                        'application/vnd.ms-%'
                    ]
                    conditions = [cls.mime_type.like(mt) for mt in office_types]
                    search = search.filter(db.or_(*conditions))
            
            if filters.get('created_after'):
                search = search.filter(cls.created_at >= filters['created_after'])
            
            if filters.get('created_before'):
                search = search.filter(cls.created_at <= filters['created_before'])
            
            if filters.get('min_rating'):
                search = search.filter(cls.rating >= filters['min_rating'])
            
            if filters.get('has_content'):
                search = search.filter(cls.content_text.isnot(None))
            
            if filters.get('latest_versions_only'):
                search = search.filter(cls.is_latest_version == True)
        
        # Ordenamiento
        sort_by = filters.get('sort_by', 'updated_at') if filters else 'updated_at'
        sort_order = filters.get('sort_order', 'desc') if filters else 'desc'
        
        if sort_by == 'title':
            order_column = cls.title
        elif sort_by == 'created_at':
            order_column = cls.created_at
        elif sort_by == 'file_size':
            order_column = cls.file_size
        elif sort_by == 'view_count':
            order_column = cls.view_count
        elif sort_by == 'rating':
            order_column = cls.rating
        else:
            order_column = cls.updated_at
        
        if sort_order == 'desc':
            search = search.order_by(order_column.desc())
        else:
            search = search.order_by(order_column.asc())
        
        return search.offset(offset).limit(limit).all()
    
    @classmethod
    def get_recent_documents(cls, user_id: int, days: int = 7, limit: int = 10):
        """Obtener documentos recientes del usuario"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        return cls.query.filter(
            (cls.owner_id == user_id) |
            (cls.collaborators.any(id=user_id)),
            cls.updated_at >= since_date,
            cls.is_deleted == False
        ).order_by(cls.updated_at.desc()).limit(limit).all()
    
    @classmethod
    def get_popular_documents(cls, organization_id: int = None, limit: int = 10):
        """Obtener documentos populares por visualizaciones"""
        query = cls.query.filter(
            cls.view_count > 0,
            cls.access_level.in_([AccessLevel.PUBLIC, AccessLevel.INTERNAL]),
            cls.is_deleted == False
        )
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
        
        return query.order_by(cls.view_count.desc()).limit(limit).all()
    
    @classmethod
    def get_expiring_documents(cls, days_ahead: int = 30):
        """Obtener documentos que vencen próximamente"""
        expiry_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        return cls.query.filter(
            cls.expires_at.isnot(None),
            cls.expires_at <= expiry_date,
            cls.expires_at > datetime.utcnow(),
            cls.is_deleted == False
        ).order_by(cls.expires_at.asc()).all()
    
    def to_dict(self, include_content=False, include_collaborators=False, 
               include_analytics=False, user_id: int = None) -> Dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'document_type': self.document_type.value,
            'category': self.category.value if self.category else None,
            'status': self.status.value,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_size_formatted': self.file_size_formatted,
            'mime_type': self.mime_type,
            'file_extension': self.file_extension,
            'version': self.version,
            'version_number': self.version_number,
            'is_latest_version': self.is_latest_version,
            'access_level': self.access_level.value,
            'owner_id': self.owner_id,
            'owner_name': self.owner.full_name if self.owner else None,
            'is_image': self.is_image,
            'is_video': self.is_video,
            'is_audio': self.is_audio,
            'is_pdf': self.is_pdf,
            'is_office_document': self.is_office_document,
            'can_be_previewed': self.can_be_previewed,
            'is_public': self.is_public,
            'is_expired': self.is_expired,
            'view_count': self.view_count,
            'download_count': self.download_count,
            'share_count': self.share_count,
            'comment_count': self.comment_count,
            'rating': self.rating,
            'rating_count': self.rating_count,
            'collaborator_count': self.collaborator_count,
            'days_since_modified': self.days_since_modified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
        
        # Información de contexto
        if self.project_id:
            data['project'] = {
                'id': self.project_id,
                'name': self.project.name if self.project else None
            }
        
        if self.organization_id:
            data['organization'] = {
                'id': self.organization_id,
                'name': self.organization.name if self.organization else None
            }
        
        # Permisos del usuario
        if user_id:
            data['user_permission'] = self.get_user_permission(user_id)
            data['can_edit'] = self.can_user_access(user_id, 'edit')
            data['can_comment'] = self.can_user_access(user_id, 'comment')
            data['is_owner'] = self.owner_id == user_id
        
        # Contenido extraído
        if include_content:
            data.update({
                'content_text': self.content_text,
                'content_preview': self.content_preview,
                'page_count': self.page_count,
                'word_count': self.word_count,
                'language': self.language,
                'processing_status': self.processing_status
            })
        
        # Colaboradores
        if include_collaborators:
            data['collaborators'] = [
                {
                    'id': collaborator.id,
                    'name': collaborator.full_name,
                    'email': collaborator.email,
                    'permission': self.get_user_permission(collaborator.id)
                }
                for collaborator in self.collaborators
            ]
        
        # Analytics
        if include_analytics:
            data['analytics'] = self.get_document_analytics()
        
        return data


class DocumentComment(BaseModel, TimestampMixin, AuditMixin):
    """
    Modelo de Comentario de Documento
    
    Representa comentarios y anotaciones en documentos.
    """
    
    __tablename__ = 'document_comments'
    
    # Relación con documento
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    document = relationship("Document", back_populates="comments")
    
    # Autor del comentario
    author_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    author = relationship("User")
    
    # Comentario padre (para respuestas)
    parent_comment_id = Column(Integer, ForeignKey('document_comments.id'))
    parent_comment = relationship("DocumentComment", remote_side="DocumentComment.id", backref="replies")
    
    # Contenido del comentario
    content = Column(Text, nullable=False)
    content_html = Column(Text)
    
    # Ubicación en el documento
    page_number = Column(Integer)
    position_data = Column(JSON)  # Coordenadas, selección de texto, etc.
    
    # Estado del comentario
    is_resolved = Column(Boolean, default=False)
    resolved_by_id = Column(Integer, ForeignKey('users.id'))
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    resolved_at = Column(DateTime)
    
    # Tipo de comentario
    comment_type = Column(String(50), default='comment')  # comment, suggestion, question, issue
    
    def __repr__(self):
        return f'<DocumentComment {self.id} on Document {self.document_id}>'
    
    def resolve_comment(self, resolved_by_user_id: int):
        """Resolver comentario"""
        self.is_resolved = True
        self.resolved_by_id = resolved_by_user_id
        self.resolved_at = datetime.utcnow()


class DocumentShare(BaseModel, TimestampMixin):
    """
    Modelo de Compartir Documento
    
    Representa enlaces de compartir para documentos.
    """
    
    __tablename__ = 'document_shares'
    
    # Relación con documento
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    document = relationship("Document", back_populates="shares")
    
    # Usuario que compartió
    shared_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    shared_by = relationship("User")
    
    # Token único del enlace
    share_token = Column(String(128), unique=True, nullable=False, index=True)
    
    # Configuración del enlace
    permission_level = Column(String(20), default='read')
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    requires_login = Column(Boolean, default=True)
    max_uses = Column(Integer)  # Máximo número de usos
    
    # Estadísticas
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime)
    
    def __repr__(self):
        return f'<DocumentShare {self.share_token}>'
    
    @hybrid_property
    def is_expired(self):
        """Verificar si el enlace está vencido"""
        return (self.expires_at and self.expires_at < datetime.utcnow()) or not self.is_active
    
    def increment_access(self):
        """Incrementar contador de accesos"""
        self.access_count += 1
        self.last_accessed_at = datetime.utcnow()


class Tag(BaseModel, TimestampMixin):
    """
    Modelo de Tag/Etiqueta
    
    Representa tags para categorizar documentos.
    """
    
    __tablename__ = 'tags'
    
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text)
    color = Column(String(7))  # Color hex
    
    # Estadísticas
    usage_count = Column(Integer, default=0)
    
    # Relaciones
    documents = relationship("Document", secondary=document_tags, back_populates="tags")
    
    def __repr__(self):
        return f'<Tag {self.name}>'


# Funciones de utilidad para el módulo
def get_document_statistics(organization_id: int = None, user_id: int = None,
                          date_from: date = None, date_to: date = None) -> Dict[str, Any]:
    """Obtener estadísticas de documentos"""
    query = Document.query.filter(Document.is_deleted == False)
    
    if organization_id:
        query = query.filter(Document.organization_id == organization_id)
    
    if user_id:
        query = query.filter(
            (Document.owner_id == user_id) |
            (Document.collaborators.any(id=user_id))
        )
    
    if date_from:
        date_from_dt = datetime.combine(date_from, datetime.min.time())
        query = query.filter(Document.created_at >= date_from_dt)
    
    if date_to:
        date_to_dt = datetime.combine(date_to, datetime.max.time())
        query = query.filter(Document.created_at <= date_to_dt)
    
    documents = query.all()
    
    if not documents:
        return {
            'total_documents': 0,
            'total_file_size': 0,
            'average_file_size': 0,
            'most_common_type': None,
            'documents_by_status': {},
            'engagement_metrics': {}
        }
    
    # Estadísticas básicas
    total_documents = len(documents)
    total_file_size = sum(doc.file_size or 0 for doc in documents)
    avg_file_size = total_file_size / total_documents if total_documents > 0 else 0
    
    # Distribución por tipo
    type_distribution = {}
    for doc in documents:
        doc_type = doc.document_type.value
        type_distribution[doc_type] = type_distribution.get(doc_type, 0) + 1
    
    most_common_type = max(type_distribution.items(), key=lambda x: x[1])[0] if type_distribution else None
    
    # Distribución por estado
    status_distribution = {}
    for doc in documents:
        status = doc.status.value
        status_distribution[status] = status_distribution.get(status, 0) + 1
    
    # Métricas de engagement
    total_views = sum(doc.view_count or 0 for doc in documents)
    total_downloads = sum(doc.download_count or 0 for doc in documents)
    total_shares = sum(doc.share_count or 0 for doc in documents)
    
    # Documentos con colaboradores
    collaborative_docs = len([doc for doc in documents if doc.collaborator_count > 0])
    
    return {
        'total_documents': total_documents,
        'total_file_size': total_file_size,
        'total_file_size_formatted': f"{total_file_size / (1024**3):.2f} GB" if total_file_size > 1024**3 else f"{total_file_size / (1024**2):.2f} MB",
        'average_file_size': avg_file_size,
        'type_distribution': type_distribution,
        'most_common_type': most_common_type,
        'status_distribution': status_distribution,
        'engagement_metrics': {
            'total_views': total_views,
            'total_downloads': total_downloads,
            'total_shares': total_shares,
            'avg_views_per_document': total_views / total_documents if total_documents > 0 else 0,
            'collaborative_documents': collaborative_docs,
            'collaboration_rate': (collaborative_docs / total_documents * 100) if total_documents > 0 else 0
        },
        'storage_insights': {
            'documents_by_provider': {
                provider.value: len([d for d in documents if d.storage_provider == provider])
                for provider in FileStorageProvider
            },
            'largest_files': [
                {
                    'title': doc.title,
                    'size': doc.file_size_formatted,
                    'type': doc.document_type.value
                }
                for doc in sorted(documents, key=lambda x: x.file_size or 0, reverse=True)[:5]
            ]
        }
    }


def cleanup_expired_shares():
    """Limpiar enlaces de compartir vencidos"""
    expired_shares = DocumentShare.query.filter(
        DocumentShare.expires_at < datetime.utcnow(),
        DocumentShare.is_active == True
    ).all()
    
    for share in expired_shares:
        share.is_active = False
    
    return len(expired_shares)


def process_pending_documents():
    """Procesar documentos pendientes de extracción de contenido"""
    pending_docs = Document.query.filter(
        Document.processing_status.in_(['pending', 'failed']),
        Document.is_deleted == False
    ).limit(10).all()  # Procesar máximo 10 por vez
    
    processed_count = 0
    
    for doc in pending_docs:
        try:
            doc.process_content_extraction()
            processed_count += 1
        except Exception as e:
            print(f"Error procesando documento {doc.id}: {e}")
    
    return processed_count