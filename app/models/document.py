from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.extensions import db


class Document(db.Model):
    """Modelo para los documentos subidos por emprendedores y aliados."""
    
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50), nullable=False)  # e.g., pdf, docx, xlsx
    file_size = Column(Integer, nullable=False)  # tamaño en bytes
    
    # Tipo de documento (informe, plantilla, contrato, etc.)
    document_type = Column(String(100), nullable=False)
    
    # Campos para el control de versiones
    version = Column(String(20), nullable=True)
    is_latest_version = Column(Boolean, default=True)
    parent_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones con otros modelos
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = relationship('User', foreign_keys=[created_by_id])
    
    entrepreneur_id = Column(Integer, ForeignKey('entrepreneurs.id'), nullable=True)
    entrepreneur = relationship('Entrepreneur', back_populates='documents')
    
    ally_id = Column(Integer, ForeignKey('allies.id'), nullable=True)
    ally = relationship('Ally', back_populates='documents')
    
    # Para documentos relacionados con una tarea específica
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)
    task = relationship('Task', back_populates='documents')
    
    # Para versiones anteriores del documento
    previous_versions = relationship('Document', 
                                     backref=db.backref('parent', remote_side=[id]),
                                     foreign_keys=[parent_id])
    
    # Para la gestión de permisos
    is_public = Column(Boolean, default=False)  # Visible para cualquier usuario
    is_shared = Column(Boolean, default=False)  # Compartido con el aliado/emprendedor
    
    def __repr__(self):
        return f'<Document {self.title}>'
    
    def to_dict(self):
        """Convierte el modelo a un diccionario."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'document_type': self.document_type,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by_id': self.created_by_id,
            'entrepreneur_id': self.entrepreneur_id,
            'ally_id': self.ally_id,
            'task_id': self.task_id,
            'is_public': self.is_public,
            'is_shared': self.is_shared
        }
    
    @property
    def file_extension(self):
        """Retorna la extensión del archivo."""
        if '.' in self.file_path:
            return self.file_path.rsplit('.', 1)[1].lower()
        return ''
    
    @property
    def formatted_size(self):
        """Retorna el tamaño del archivo formateado (KB, MB)."""
        if self.file_size < 1024:
            return f"{self.file_size} bytes"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    @classmethod
    def get_by_entrepreneur(cls, entrepreneur_id):
        """Retorna documentos asociados a un emprendedor."""
        return cls.query.filter_by(entrepreneur_id=entrepreneur_id).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_by_ally(cls, ally_id):
        """Retorna documentos asociados a un aliado."""
        return cls.query.filter_by(ally_id=ally_id).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_shared_with_ally(cls, entrepreneur_id, ally_id):
        """Retorna documentos compartidos entre un emprendedor y un aliado."""
        return cls.query.filter_by(
            entrepreneur_id=entrepreneur_id, 
            is_shared=True
        ).order_by(cls.created_at.desc()).all()
    
    def create_new_version(self, file_path, file_size, created_by_id, version=None):
        """Crea una nueva versión del documento actual."""
        # Marcar versión actual como no más reciente
        self.is_latest_version = False
        db.session.flush()
        
        # Crear nueva versión
        new_version = Document(
            title=self.title,
            description=self.description,
            file_path=file_path,
            file_type=self.file_type,
            file_size=file_size,
            document_type=self.document_type,
            version=version or f"{float(self.version or 1.0) + 0.1:.1f}",
            is_latest_version=True,
            parent_id=self.id,
            created_by_id=created_by_id,
            entrepreneur_id=self.entrepreneur_id,
            ally_id=self.ally_id,
            task_id=self.task_id,
            is_public=self.is_public,
            is_shared=self.is_shared
        )
        
        return new_version