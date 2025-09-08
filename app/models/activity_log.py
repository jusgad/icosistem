"""
Activity Log Model - Sistema de registro de actividades
======================================================

Este módulo define el modelo ActivityLog para registrar todas las actividades
importantes del sistema, proporcionando trazabilidad y auditoría completa.

Funcionalidades:
- Registro automático de actividades
- Categorización por tipos de acción
- Metadatos flexibles con JSON
- Índices optimizados para consultas
- Métodos de búsqueda y filtrado
- Integración con sistema de permisos
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json

from sqlalchemy import Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class ActivityType(Enum):
    """Tipos de actividades del sistema"""
    
    # Autenticación y sesiones
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    
    # Gestión de usuarios
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_ACTIVATE = "user_activate"
    USER_DEACTIVATE = "user_deactivate"
    
    # Gestión de perfiles
    PROFILE_UPDATE = "profile_update"
    PROFILE_PHOTO_UPDATE = "profile_photo_update"
    
    # Proyectos
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    PROJECT_PUBLISH = "project_publish"
    PROJECT_UNPUBLISH = "project_unpublish"
    PROJECT_COMPLETE = "project_complete"
    
    # Mentoría
    MENTORSHIP_REQUEST = "mentorship_request"
    MENTORSHIP_ACCEPT = "mentorship_accept"
    MENTORSHIP_REJECT = "mentorship_reject"
    MENTORSHIP_SESSION_CREATE = "mentorship_session_create"
    MENTORSHIP_SESSION_COMPLETE = "mentorship_session_complete"
    
    # Reuniones
    MEETING_CREATE = "meeting_create"
    MEETING_UPDATE = "meeting_update"
    MEETING_CANCEL = "meeting_cancel"
    MEETING_START = "meeting_start"
    MEETING_END = "meeting_end"
    
    # Documentos
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_SHARE = "document_share"
    
    # Mensajería
    MESSAGE_SEND = "message_send"
    MESSAGE_READ = "message_read"
    MESSAGE_DELETE = "message_delete"
    
    # Tareas
    TASK_CREATE = "task_create"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    TASK_DELETE = "task_delete"
    
    # Notificaciones
    NOTIFICATION_SEND = "notification_send"
    NOTIFICATION_READ = "notification_read"
    
    # Administración
    ADMIN_USER_IMPERSONATE = "admin_user_impersonate"
    ADMIN_SYSTEM_CONFIG = "admin_system_config"
    ADMIN_BACKUP_CREATE = "admin_backup_create"
    ADMIN_DATA_EXPORT = "admin_data_export"
    
    # Sistema
    API_ACCESS = "api_access"
    SYSTEM_ERROR = "system_error"
    SECURITY_VIOLATION = "security_violation"


class ActivitySeverity(Enum):
    """Niveles de severidad de las actividades"""
    LOW = "low"           # Actividades rutinarias
    MEDIUM = "medium"     # Actividades importantes
    HIGH = "high"         # Actividades críticas
    CRITICAL = "critical" # Actividades de seguridad


class ActivityLog(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Modelo para el registro de actividades del sistema
    
    Attributes:
        id: ID único del registro
        user_id: ID del usuario que realizó la actividad
        activity_type: Tipo de actividad realizada
        severity: Nivel de severidad de la actividad
        description: Descripción textual de la actividad
        meta_data: Datos adicionales en formato JSON
        ip_address: Dirección IP desde donde se realizó la actividad
        user_agent: User agent del cliente
        target_type: Tipo de entidad afectada (opcional)
        target_id: ID de la entidad afectada (opcional)
        session_id: ID de la sesión (opcional)
        organization_id: ID de la organización (para multitenancy)
        created_at: Timestamp de creación
        updated_at: Timestamp de última actualización
        deleted_at: Timestamp de eliminación lógica
    """
    
    __tablename__ = 'activity_logs'
    
    # Campos principales
    user_id = db.Column(
        db.Integer, 
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,  # Puede ser NULL para actividades del sistema
        index=True
    )
    
    activity_type = db.Column(
        db.Enum(ActivityType),
        nullable=False,
        index=True
    )
    
    severity = db.Column(
        db.Enum(ActivitySeverity),
        nullable=False,
        default=ActivitySeverity.LOW,
        index=True
    )
    
    description = db.Column(
        db.Text,
        nullable=False
    )
    
    # Metadatos flexibles (renamed to avoid SQLAlchemy reserved word)
    meta_data = db.Column(
        JSONB,  # PostgreSQL JSONB para mejor rendimiento
        nullable=True,
        default=dict
    )
    
    # Información de contexto
    ip_address = db.Column(
        db.String(45),  # IPv6 compatible
        nullable=True,
        index=True
    )
    
    user_agent = db.Column(
        db.Text,
        nullable=True
    )
    
    # Referencias opcionales a entidades
    target_type = db.Column(
        db.String(50),
        nullable=True,
        index=True
    )
    
    target_id = db.Column(
        db.Integer,
        nullable=True,
        index=True
    )
    
    # Sesión y organización
    session_id = db.Column(
        db.String(255),
        nullable=True,
        index=True
    )
    
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    # Relaciones
    user = db.relationship(
        'User',
        backref=db.backref('activity_logs', lazy='dynamic'),
        foreign_keys=[user_id]
    )
    
    organization = db.relationship(
        'Organization',
        backref=db.backref('activity_logs', lazy='dynamic')
    )
    
    # Índices compuestos para optimización
    __table_args__ = (
        Index('ix_activity_user_type', 'user_id', 'activity_type'),
        Index('ix_activity_severity_created', 'severity', 'created_at'),
        Index('ix_activity_target', 'target_type', 'target_id'),
        Index('ix_activity_org_created', 'organization_id', 'created_at'),
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<ActivityLog {self.id}: {self.activity_type.value} by User {self.user_id}>"
    
    @hybrid_property
    def is_security_related(self):
        """Verifica si la actividad está relacionada con seguridad"""
        security_types = {
            ActivityType.LOGIN,
            ActivityType.LOGOUT,
            ActivityType.PASSWORD_CHANGE,
            ActivityType.PASSWORD_RESET,
            ActivityType.ADMIN_USER_IMPERSONATE,
            ActivityType.SECURITY_VIOLATION
        }
        return self.activity_type in security_types
    
    @hybrid_property
    def is_administrative(self):
        """Verifica si la actividad es administrativa"""
        return self.activity_type.value.startswith('admin_')
    
    def to_dict(self, include_metadata=True):
        """Convierte el registro a diccionario"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type.value,
            'severity': self.severity.value,
            'description': self.description,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'session_id': self.session_id,
            'organization_id': self.organization_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_metadata and self.meta_data:
            data['metadata'] = self.meta_data
            
        return data
    
    @classmethod
    def log_activity(
        cls,
        activity_type: ActivityType,
        description: str,
        user_id: Optional[int] = None,
        severity: ActivitySeverity = ActivitySeverity.LOW,
        metadata: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        session_id: Optional[str] = None,
        organization_id: Optional[int] = None
    ) -> 'ActivityLog':
        """
        Método de clase para registrar una nueva actividad
        
        Args:
            activity_type: Tipo de actividad
            description: Descripción de la actividad
            user_id: ID del usuario (opcional)
            severity: Nivel de severidad
            metadata: Metadatos adicionales
            ip_address: Dirección IP
            user_agent: User agent
            target_type: Tipo de entidad afectada
            target_id: ID de entidad afectada
            session_id: ID de sesión
            organization_id: ID de organización
            
        Returns:
            Nueva instancia de ActivityLog
        """
        activity = cls(
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            severity=severity,
            meta_data=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
            target_type=target_type,
            target_id=target_id,
            session_id=session_id,
            organization_id=organization_id
        )
        
        db.session.add(activity)
        db.session.commit()
        
        return activity
    
    @classmethod
    def get_user_activities(
        cls,
        user_id: int,
        limit: int = 50,
        activity_types: Optional[list[ActivityType]] = None,
        severity_filter: Optional[ActivitySeverity] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """
        Obtiene las actividades de un usuario específico
        
        Args:
            user_id: ID del usuario
            limit: Límite de resultados
            activity_types: Filtrar por tipos de actividad
            severity_filter: Filtrar por severidad
            start_date: Fecha de inicio
            end_date: Fecha de fin
            
        Returns:
            Query de actividades filtradas
        """
        query = cls.query.filter(cls.user_id == user_id)
        
        if activity_types:
            query = query.filter(cls.activity_type.in_(activity_types))
            
        if severity_filter:
            query = query.filter(cls.severity == severity_filter)
            
        if start_date:
            query = query.filter(cls.created_at >= start_date)
            
        if end_date:
            query = query.filter(cls.created_at <= end_date)
            
        return query.order_by(cls.created_at.desc()).limit(limit)
    
    @classmethod
    def get_security_activities(
        cls,
        limit: int = 100,
        organization_id: Optional[int] = None
    ):
        """Obtiene actividades relacionadas con seguridad"""
        security_types = [
            ActivityType.LOGIN,
            ActivityType.LOGOUT,
            ActivityType.PASSWORD_CHANGE,
            ActivityType.PASSWORD_RESET,
            ActivityType.ADMIN_USER_IMPERSONATE,
            ActivityType.SECURITY_VIOLATION
        ]
        
        query = cls.query.filter(cls.activity_type.in_(security_types))
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
            
        return query.order_by(cls.created_at.desc()).limit(limit)
    
    @classmethod
    def get_activities_by_target(
        cls,
        target_type: str,
        target_id: int,
        limit: int = 50
    ):
        """Obtiene actividades por entidad objetivo"""
        return cls.query.filter(
            cls.target_type == target_type,
            cls.target_id == target_id
        ).order_by(cls.created_at.desc()).limit(limit)
    
    @classmethod
    def get_critical_activities(
        cls,
        limit: int = 100,
        organization_id: Optional[int] = None
    ):
        """Obtiene actividades críticas"""
        query = cls.query.filter(cls.severity == ActivitySeverity.CRITICAL)
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
            
        return query.order_by(cls.created_at.desc()).limit(limit)
    
    @classmethod
    def cleanup_old_activities(cls, days_to_keep: int = 365):
        """
        Limpia actividades antiguas (manteniendo las críticas)
        
        Args:
            days_to_keep: Días a mantener en el log
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        # Solo eliminar actividades no críticas
        old_activities = cls.query.filter(
            cls.created_at < cutoff_date,
            cls.severity != ActivitySeverity.CRITICAL
        )
        
        count = old_activities.count()
        old_activities.delete(synchronize_session=False)
        db.session.commit()
        
        return count
    
    @classmethod
    def get_activity_summary(
        cls,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict[str, int]:
        """
        Genera un resumen de actividades por tipo
        
        Returns:
            Diccionario con conteos por tipo de actividad
        """
        query = cls.query
        
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)
            
        if start_date:
            query = query.filter(cls.created_at >= start_date)
            
        if end_date:
            query = query.filter(cls.created_at <= end_date)
        
        # Agrupar por tipo de actividad
        results = db.session.query(
            cls.activity_type,
            db.func.count(cls.id).label('count')
        ).filter(
            query.whereclause
        ).group_by(cls.activity_type).all()
        
        return {result.activity_type.value: result.count for result in results}


# Función auxiliar para uso en decoradores
def log_activity_decorator(
    activity_type: ActivityType,
    description: str,
    severity: ActivitySeverity = ActivitySeverity.LOW,
    get_target_info=None
):
    """
    Decorador para registrar actividades automáticamente
    
    Args:
        activity_type: Tipo de actividad
        description: Descripción base
        severity: Nivel de severidad
        get_target_info: Función para extraer info del target
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            from flask import request, g
            
            # Ejecutar función original
            result = func(*args, **kwargs)
            
            # Extraer información del contexto
            user_id = getattr(g, 'current_user_id', None)
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent') if request else None
            session_id = getattr(g, 'session_id', None)
            organization_id = getattr(g, 'current_organization_id', None)
            
            # Información del target
            target_type = None
            target_id = None
            if get_target_info:
                target_info = get_target_info(result, *args, **kwargs)
                target_type = target_info.get('type')
                target_id = target_info.get('id')
            
            # Registrar actividad
            try:
                ActivityLog.log_activity(
                    activity_type=activity_type,
                    description=description,
                    user_id=user_id,
                    severity=severity,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    target_type=target_type,
                    target_id=target_id,
                    session_id=session_id,
                    organization_id=organization_id
                )
            except Exception as e:
                # Log del error pero no interrumpir el flujo principal
                print(f"Error logging activity: {e}")
            
            return result
        return wrapper
    return decorator