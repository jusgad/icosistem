"""
Modelos base y mixins para el ecosistema de emprendimiento.
Este módulo define las clases base que proporcionan funcionalidad común a todos los modelos.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union
from flask import current_app, g
from flask_login import current_user
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, event
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator, VARCHAR
from app.extensions import db

# Configurar logger para modelos
models_logger = logging.getLogger('ecosistema.models')


# ====================================
# TIPOS PERSONALIZADOS
# ====================================

class GUID(TypeDecorator):
    """Tipo personalizado para UUID que funciona con SQLite y PostgreSQL."""
    
    impl = VARCHAR
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(VARCHAR(36))
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            return str(value)
    
    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class JSONType(TypeDecorator):
    """Tipo personalizado para JSON que maneja serialización automática."""
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, ensure_ascii=False, default=str)
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
        return value


# ====================================
# MODELO BASE
# ====================================

class BaseModel(db.Model):
    """
    Modelo base que proporciona funcionalidad común a todos los modelos.
    Incluye ID único, métodos de serialización, validación y utilidades.
    """
    
    __abstract__ = True
    
    # Columna ID principal con UUID
    id = Column(GUID(), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Metadatos adicionales
    metadata_fields = Column(JSONType, default=dict, doc="Campos adicionales en formato JSON")
    
    def __init__(self, **kwargs):
        """Inicializar modelo con validación automática."""
        # Separar metadata de campos del modelo
        metadata = kwargs.pop('metadata', {})
        
        # Inicializar modelo
        super().__init__(**kwargs)
        
        # Establecer metadata
        if metadata:
            self.metadata_fields = metadata
        
        # Validar datos iniciales
        self._validate_on_init()
    
    def _validate_on_init(self):
        """Validación ejecutada al inicializar el modelo."""
        pass  # Implementar en subclases si es necesario
    
    # ====================================
    # MÉTODOS DE SERIALIZACIÓN
    # ====================================
    
    def to_dict(self, include_relationships: bool = False, 
                exclude_fields: list[str] = None) -> dict[str, Any]:
        """
        Convertir modelo a diccionario.
        
        Args:
            include_relationships: Incluir relaciones en la serialización
            exclude_fields: Campos a excluir de la serialización
            
        Returns:
            Diccionario con los datos del modelo
        """
        exclude_fields = exclude_fields or []
        result = {}
        
        # Serializar columnas básicas
        for column in self.__table__.columns:
            if column.name not in exclude_fields:
                value = getattr(self, column.name)
                
                # Manejar tipos especiales
                if isinstance(value, datetime):
                    result[column.name] = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    result[column.name] = str(value)
                else:
                    result[column.name] = value
        
        # Incluir relaciones si se solicita
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                if relationship.key not in exclude_fields:
                    related_obj = getattr(self, relationship.key)
                    
                    if related_obj is not None:
                        if hasattr(related_obj, '__iter__') and not isinstance(related_obj, str):
                            # Relación one-to-many o many-to-many
                            result[relationship.key] = [
                                obj.to_dict(include_relationships=False) 
                                if hasattr(obj, 'to_dict') else str(obj)
                                for obj in related_obj
                            ]
                        else:
                            # Relación one-to-one o many-to-one
                            result[relationship.key] = (
                                related_obj.to_dict(include_relationships=False)
                                if hasattr(related_obj, 'to_dict') else str(related_obj)
                            )
        
        return result
    
    def to_json(self, **kwargs) -> str:
        """Convertir modelo a JSON string."""
        return json.dumps(self.to_dict(**kwargs), ensure_ascii=False, indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], exclude_fields: list[str] = None):
        """
        Crear instancia del modelo desde diccionario.
        
        Args:
            data: Diccionario con los datos
            exclude_fields: Campos a excluir
            
        Returns:
            Nueva instancia del modelo
        """
        exclude_fields = exclude_fields or ['id', 'created_at', 'updated_at']
        
        # Filtrar campos válidos
        valid_fields = {}
        for key, value in data.items():
            if key not in exclude_fields and hasattr(cls, key):
                valid_fields[key] = value
        
        return cls(**valid_fields)
    
    # ====================================
    # MÉTODOS DE CONSULTA
    # ====================================
    
    @classmethod
    def get_by_id(cls, id_value: Union[str, uuid.UUID]):
        """Obtener instancia por ID."""
        if isinstance(id_value, str):
            try:
                id_value = uuid.UUID(id_value)
            except ValueError:
                return None
        
        return cls.query.filter_by(id=id_value).first()
    
    @classmethod
    def get_or_404(cls, id_value: Union[str, uuid.UUID]):
        """Obtener instancia por ID o lanzar 404."""
        instance = cls.get_by_id(id_value)
        if not instance:
            from flask import abort
            abort(404)
        return instance
    
    @classmethod
    def exists(cls, **filters) -> bool:
        """Verificar si existe una instancia con los filtros dados."""
        return cls.query.filter_by(**filters).first() is not None
    
    @classmethod
    def count(cls, **filters) -> int:
        """Contar instancias con filtros opcionales."""
        query = cls.query
        if filters:
            query = query.filter_by(**filters)
        return query.count()
    
    # ====================================
    # MÉTODOS DE PERSISTENCIA
    # ====================================
    
    def save(self, commit: bool = True):
        """Guardar modelo en la base de datos."""
        try:
            db.session.add(self)
            if commit:
                db.session.commit()
            return self
        except Exception as e:
            db.session.rollback()
            models_logger.error(f"Error saving {self.__class__.__name__}: {str(e)}")
            raise
    
    def update(self, data: dict[str, Any], commit: bool = True):
        """Actualizar modelo con nuevos datos."""
        try:
            for key, value in data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            if commit:
                db.session.commit()
            return self
        except Exception as e:
            db.session.rollback()
            models_logger.error(f"Error updating {self.__class__.__name__}: {str(e)}")
            raise
    
    def delete(self, commit: bool = True):
        """Eliminar modelo de la base de datos."""
        try:
            db.session.delete(self)
            if commit:
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            models_logger.error(f"Error deleting {self.__class__.__name__}: {str(e)}")
            raise
    
    # ====================================
    # MÉTODOS DE UTILIDAD
    # ====================================
    
    def refresh(self):
        """Refrescar modelo desde la base de datos."""
        db.session.refresh(self)
        return self
    
    def clone(self, **override_fields):
        """Crear copia del modelo con campos opcionales sobrescritos."""
        data = self.to_dict(exclude_fields=['id', 'created_at', 'updated_at'])
        data.update(override_fields)
        return self.__class__(**data)
    
    def get_metadata(self, key: str, default=None):
        """Obtener valor de metadata."""
        if not self.metadata_fields:
            return default
        return self.metadata_fields.get(key, default)
    
    def set_metadata(self, key: str, value: Any, commit: bool = True):
        """Establecer valor de metadata."""
        if not self.metadata_fields:
            self.metadata_fields = {}
        
        self.metadata_fields[key] = value
        
        # Marcar como modificado para SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, 'metadata_fields')
        
        if commit:
            db.session.commit()
    
    def remove_metadata(self, key: str, commit: bool = True):
        """Remover clave de metadata."""
        if self.metadata_fields and key in self.metadata_fields:
            del self.metadata_fields[key]
            flag_modified(self, 'metadata_fields')
            
            if commit:
                db.session.commit()
    
    # ====================================
    # REPRESENTACIONES
    # ====================================
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def __str__(self):
        # Intentar usar nombre si existe, sino ID
        if hasattr(self, 'name') and self.name:
            return f"{self.__class__.__name__}: {self.name}"
        elif hasattr(self, 'title') and self.title:
            return f"{self.__class__.__name__}: {self.title}"
        elif hasattr(self, 'email') and self.email:
            return f"{self.__class__.__name__}: {self.email}"
        else:
            return f"{self.__class__.__name__}: {str(self.id)[:8]}"


# ====================================
# MIXIN DE TIMESTAMPS
# ====================================

class TimestampMixin:
    """Mixin que añade campos de timestamp automáticos."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False,
                     doc="Fecha y hora de creación")
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=datetime.utcnow, 
                     onupdate=datetime.utcnow, nullable=False,
                     doc="Fecha y hora de última actualización")
    
    @property
    def age(self):
        """Obtener edad del registro desde su creación."""
        return datetime.now(timezone.utc) - self.created_at
    
    @property
    def time_since_update(self):
        """Obtener tiempo desde la última actualización."""
        return datetime.now(timezone.utc) - self.updated_at
    
    def is_recent(self, hours: int = 24) -> bool:
        """Verificar si el registro es reciente."""
        from datetime import timedelta
        return self.created_at > (datetime.now(timezone.utc) - timedelta(hours=hours))
    
    def was_updated_recently(self, hours: int = 1) -> bool:
        """Verificar si fue actualizado recientemente."""
        from datetime import timedelta
        return self.updated_at > (datetime.now(timezone.utc) - timedelta(hours=hours))


# ====================================
# MIXIN DE AUDITORÍA
# ====================================

class AuditMixin:
    """Mixin que añade campos de auditoría para tracking de cambios."""
    
    @declared_attr
    def created_by_id(cls):
        return Column(GUID(), nullable=True, doc="ID del usuario que creó el registro")
    
    @declared_attr
    def updated_by_id(cls):
        return Column(GUID(), nullable=True, doc="ID del usuario que actualizó el registro")
    
    @declared_attr
    def version(cls):
        return Column(Integer, default=1, nullable=False, doc="Versión del registro")
    
    def set_audit_fields(self, user_id: Optional[uuid.UUID] = None):
        """Establecer campos de auditoría automáticamente."""
        if user_id is None and current_user and hasattr(current_user, 'id'):
            user_id = current_user.id
        
        if user_id:
            if not self.created_by_id:
                self.created_by_id = user_id
            self.updated_by_id = user_id
        
        # Incrementar versión
        if hasattr(self, 'version') and self.version:
            self.version += 1
        else:
            self.version = 1
    
    @property
    def created_by(self):
        """Obtener usuario que creó el registro."""
        if self.created_by_id:
            from .user import User
            return User.query.get(self.created_by_id)
        return None
    
    @property 
    def updated_by(self):
        """Obtener usuario que actualizó el registro."""
        if self.updated_by_id:
            from .user import User
            return User.query.get(self.updated_by_id)
        return None


# ====================================
# MIXIN DE SOFT DELETE
# ====================================

class SoftDeleteMixin:
    """Mixin que implementa soft delete (eliminación lógica)."""
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True, 
                     doc="Fecha y hora de eliminación lógica")
    
    @declared_attr
    def deleted_by_id(cls):
        return Column(GUID(), nullable=True, 
                     doc="ID del usuario que eliminó el registro")
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False, 
                     doc="Indica si el registro está eliminado")
    
    def soft_delete(self, user_id: Optional[uuid.UUID] = None, commit: bool = True):
        """Realizar eliminación lógica."""
        if user_id is None and current_user and hasattr(current_user, 'id'):
            user_id = current_user.id
        
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by_id = user_id
        
        if commit:
            db.session.commit()
        
        models_logger.info(f"Soft deleted {self.__class__.__name__} ID: {self.id}")
    
    def restore(self, commit: bool = True):
        """Restaurar registro eliminado lógicamente."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by_id = None
        
        if commit:
            db.session.commit()
        
        models_logger.info(f"Restored {self.__class__.__name__} ID: {self.id}")
    
    @property
    def deleted_by(self):
        """Obtener usuario que eliminó el registro."""
        if self.deleted_by_id:
            from .user import User
            return User.query.get(self.deleted_by_id)
        return None
    
    @classmethod
    def active(cls):
        """Query para obtener solo registros activos (no eliminados)."""
        return cls.query.filter(cls.is_deleted == False)
    
    @classmethod
    def deleted(cls):
        """Query para obtener solo registros eliminados."""
        return cls.query.filter(cls.is_deleted == True)
    
    @classmethod
    def with_deleted(cls):
        """Query que incluye registros eliminados."""
        return cls.query


# ====================================
# EVENTOS AUTOMÁTICOS PARA MIXINS
# ====================================

@event.listens_for(AuditMixin, 'before_insert', propagate=True)
def set_audit_on_insert(mapper, connection, target):
    """Establecer campos de auditoría al insertar."""
    target.set_audit_fields()


@event.listens_for(AuditMixin, 'before_update', propagate=True)
def set_audit_on_update(mapper, connection, target):
    """Establecer campos de auditoría al actualizar."""
    target.set_audit_fields()


# ====================================
# VALIDADORES COMUNES
# ====================================

class ValidationMixin:
    """Mixin que proporciona validadores comunes."""
    
    def validate_required_fields(self, *fields):
        """Validar que campos requeridos no estén vacíos."""
        errors = []
        for field in fields:
            value = getattr(self, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(f"Campo requerido: {field}")
        
        if errors:
            raise ValueError(f"Errores de validación: {', '.join(errors)}")
    
    def validate_email(self, email_field: str):
        """Validar formato de email."""
        email = getattr(self, email_field, None)
        if email:
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, email):
                raise ValueError(f"Formato de email inválido: {email}")
    
    def validate_phone(self, phone_field: str):
        """Validar formato de teléfono colombiano."""
        phone = getattr(self, phone_field, None)
        if phone:
            import re
            # Patrones para Colombia
            patterns = [
                r'^\+57[13][0-9]{9}$',  # +57 + código área + número
                r'^[13][0-9]{9}$',       # Sin código país
                r'^3[0-9]{9}$'           # Celular
            ]
            
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if not any(re.match(pattern, clean_phone) for pattern in patterns):
                raise ValueError(f"Formato de teléfono inválido: {phone}")
    
    def validate_length(self, field: str, min_length: int = None, max_length: int = None):
        """Validar longitud de campo."""
        value = getattr(self, field, None)
        if value and isinstance(value, str):
            if min_length and len(value) < min_length:
                raise ValueError(f"Campo {field} muy corto (mínimo {min_length} caracteres)")
            if max_length and len(value) > max_length:
                raise ValueError(f"Campo {field} muy largo (máximo {max_length} caracteres)")


# ====================================
# MODELO BASE COMBINADO
# ====================================

class CompleteBaseModel(BaseModel, TimestampMixin, AuditMixin, ValidationMixin):
    """
    Modelo base completo que combina todas las funcionalidades.
    Usar para modelos que necesiten toda la funcionalidad.
    """
    __abstract__ = True


class SoftDeleteModel(CompleteBaseModel, SoftDeleteMixin):
    """
    Modelo base con soft delete incluido.
    Usar para modelos que requieran eliminación lógica.
    """
    __abstract__ = True


# ====================================
# UTILIDADES PARA CONSULTAS
# ====================================

def get_or_create(model_class, defaults=None, **kwargs):
    """
    Obtener o crear una instancia del modelo.
    
    Args:
        model_class: Clase del modelo
        defaults: Valores por defecto si se crea
        **kwargs: Filtros para buscar
        
    Returns:
        Tupla (instancia, created)
    """
    instance = model_class.query.filter_by(**kwargs).first()
    
    if instance:
        return instance, False
    
    # Crear nueva instancia
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    
    instance = model_class(**params)
    instance.save()
    
    return instance, True


def bulk_create(model_class, data_list: list[dict[str, Any]], batch_size: int = 1000):
    """
    Crear múltiples instancias de manera eficiente.
    
    Args:
        model_class: Clase del modelo
        data_list: Lista de diccionarios con datos
        batch_size: Tamaño del lote para inserción
        
    Returns:
        Lista de instancias creadas
    """
    instances = []
    
    try:
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            batch_instances = [model_class(**data) for data in batch]
            
            db.session.add_all(batch_instances)
            instances.extend(batch_instances)
        
        db.session.commit()
        models_logger.info(f"Bulk created {len(instances)} {model_class.__name__} instances")
        
        return instances
        
    except Exception as e:
        db.session.rollback()
        models_logger.error(f"Error in bulk create: {str(e)}")
        raise


def bulk_update(model_class, updates: list[dict[str, Any]], id_field: str = 'id'):
    """
    Actualizar múltiples instancias de manera eficiente.
    
    Args:
        model_class: Clase del modelo
        updates: Lista de diccionarios con ID y campos a actualizar
        id_field: Campo ID para identificar registros
        
    Returns:
        Número de registros actualizados
    """
    try:
        updated_count = 0
        
        for update_data in updates:
            if id_field not in update_data:
                continue
            
            id_value = update_data.pop(id_field)
            
            result = model_class.query.filter(
                getattr(model_class, id_field) == id_value
            ).update(update_data)
            
            updated_count += result
        
        db.session.commit()
        models_logger.info(f"Bulk updated {updated_count} {model_class.__name__} instances")
        
        return updated_count
        
    except Exception as e:
        db.session.rollback()
        models_logger.error(f"Error in bulk update: {str(e)}")
        raise


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    # Tipos personalizados
    'GUID',
    'JSONType',
    
    # Modelos base
    'BaseModel',
    'CompleteBaseModel', 
    'SoftDeleteModel',
    
    # Mixins
    'TimestampMixin',
    'AuditMixin',
    'SoftDeleteMixin',
    'ValidationMixin',
    
    # Utilidades
    'get_or_create',
    'bulk_create',
    'bulk_update'
]