"""
Modelo Mensaje del Ecosistema de Emprendimiento

Este módulo define los modelos para gestión de mensajería y comunicación,
incluyendo conversaciones, mensajes, notificaciones y canales de comunicación.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional, Any, Union
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum, Float, Date, Table
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from enum import Enum
import re
from html import escape
import bleach

from .base import BaseModel
from .mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from ..extensions import db
from ..core.constants import (
    MESSAGE_TYPES,
    MESSAGE_STATUS,
    MESSAGE_PRIORITIES,
    CONVERSATION_TYPES,
    ATTACHMENT_TYPES,
    NOTIFICATION_TYPES
)
from ..core.exceptions import ValidationError


class MessageType(Enum):
    """Tipos de mensaje"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    LINK = "link"
    SYSTEM = "system"
    NOTIFICATION = "notification"
    ANNOUNCEMENT = "announcement"
    REMINDER = "reminder"
    TASK = "task"
    MEETING_INVITE = "meeting_invite"
    DOCUMENT_SHARE = "document_share"
    FEEDBACK = "feedback"
    QUESTION = "question"
    ANSWER = "answer"
    POLL = "poll"
    EVENT = "event"
    AUTOMATED = "automated"


class MessageStatus(Enum):
    """Estados del mensaje"""
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    DELETED = "deleted"
    ARCHIVED = "archived"


class MessagePriority(Enum):
    """Prioridades del mensaje"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class ConversationType(Enum):
    """Tipos de conversación"""
    DIRECT = "direct"  # 1:1
    GROUP = "group"    # Grupo pequeño
    CHANNEL = "channel"  # Canal público/privado
    BROADCAST = "broadcast"  # Difusión masiva
    SUPPORT = "support"  # Soporte técnico
    MENTORSHIP = "mentorship"  # Conversación de mentoría
    PROJECT = "project"  # Conversación de proyecto
    PROGRAM = "program"  # Conversación de programa
    ORGANIZATION = "organization"  # Conversación organizacional


class AttachmentType(Enum):
    """Tipos de archivo adjunto"""
    IMAGE = "image"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet" 
    PRESENTATION = "presentation"
    PDF = "pdf"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


# Tabla de asociación para participantes de conversación
conversation_participants = Table(
    'conversation_participants',
    db.metadata,
    Column('conversation_id', Integer, ForeignKey('conversations.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role', String(50), default='member'),  # admin, moderator, member
    Column('joined_at', DateTime, default=datetime.utcnow),
    Column('left_at', DateTime),
    Column('is_active', Boolean, default=True),
    Column('last_read_at', DateTime),
    Column('notification_settings', JSON),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# Tabla de asociación para destinatarios de mensaje
message_recipients = Table(
    'message_recipients',
    db.metadata,
    Column('message_id', Integer, ForeignKey('messages.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('status', String(20), default='sent'),  # sent, delivered, read, failed
    Column('delivered_at', DateTime),
    Column('read_at', DateTime),
    Column('failed_reason', String(500)),
    Column('notification_sent', Boolean, default=False),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Conversation(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Conversación
    
    Representa conversaciones/chats entre usuarios del ecosistema,
    incluyendo conversaciones directas, grupales y canales.
    """
    
    __tablename__ = 'conversations'
    
    # Información básica
    title = Column(String(200))  # Título para grupos/canales
    description = Column(Text)
    conversation_type = Column(SQLEnum(ConversationType), nullable=False, index=True)
    
    # Creador de la conversación
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    creator = relationship("User", foreign_keys=[creator_id])
    
    # Configuración de la conversación
    is_private = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False, index=True)
    is_muted = Column(Boolean, default=False)
    allow_guests = Column(Boolean, default=False)
    max_participants = Column(Integer)
    
    # Configuración de mensajes
    message_retention_days = Column(Integer)  # Retención de mensajes
    allow_file_sharing = Column(Boolean, default=True)
    allow_voice_messages = Column(Boolean, default=True)
    require_approval = Column(Boolean, default=False)  # Mensajes requieren aprobación
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    
    mentorship_id = Column(Integer, ForeignKey('mentorship_relationships.id'))
    mentorship = relationship("MentorshipRelationship")
    
    program_id = Column(Integer, ForeignKey('programs.id'))
    program = relationship("Program")
    
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    organization = relationship("Organization")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting")
    
    # Estadísticas
    total_messages = Column(Integer, default=0)
    last_message_at = Column(DateTime)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    
    # Configuración personalizada
    custom_settings = Column(JSON)
    tags = Column(JSON)  # Tags para categorización
    
    # Relaciones
    
    # Participantes
    participants = relationship("User",
                              secondary=conversation_participants,
                              back_populates="conversations")
    
    # Mensajes de la conversación
    messages = relationship("Message", back_populates="conversation")
    
    def __init__(self, **kwargs):
        """Inicialización de la conversación"""
        super().__init__(**kwargs)
        
        # Configurar título por defecto para conversaciones directas
        if self.conversation_type == ConversationType.DIRECT and not self.title:
            self.title = "Conversación Directa"
        
        # Configuración por defecto
        if not self.custom_settings:
            self.custom_settings = {
                'auto_delete_messages': False,
                'typing_indicators': True,
                'read_receipts': True,
                'message_reactions': True,
                'thread_replies': True
            }
    
    def __repr__(self):
        return f'<Conversation {self.title or self.id} ({self.conversation_type.value})>'
    
    def __str__(self):
        return f'{self.title or f"Conversación {self.id}"} - {self.conversation_type.value}'
    
    # Validaciones
    @validates('title')
    def validate_title(self, key, title):
        """Validar título"""
        if title and len(title) > 200:
            raise ValidationError("El título no puede exceder 200 caracteres")
        return title.strip() if title else title
    
    @validates('max_participants')
    def validate_max_participants(self, key, max_participants):
        """Validar máximo de participantes"""
        if max_participants is not None:
            if max_participants < 2 or max_participants > 10000:
                raise ValidationError("El máximo de participantes debe estar entre 2 y 10,000")
        return max_participants
    
    @validates('message_retention_days')
    def validate_retention(self, key, days):
        """Validar retención de mensajes"""
        if days is not None:
            if days < 1 or days > 3650:  # Entre 1 día y 10 años
                raise ValidationError("La retención debe estar entre 1 y 3,650 días")
        return days
    
    # Propiedades híbridas
    @hybrid_property
    def participant_count(self):
        """Número de participantes activos"""
        from .. import db
        
        count = db.session.execute(
            conversation_participants.select().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.is_active == True
            )
        ).rowcount
        
        return count
    
    @hybrid_property
    def is_active(self):
        """Verificar si la conversación está activa"""
        return not self.is_archived and not self.is_deleted
    
    @hybrid_property
    def unread_count_for_user(self):
        """Contar mensajes no leídos (requiere user_id en contexto)"""
        # Esta propiedad se calculará dinámicamente en métodos específicos
        return 0
    
    @hybrid_property
    def last_message_preview(self):
        """Vista previa del último mensaje"""
        if self.messages:
            last_msg = max(self.messages, key=lambda m: m.created_at)
            if last_msg.message_type == MessageType.TEXT:
                return last_msg.content[:50] + "..." if len(last_msg.content) > 50 else last_msg.content
            else:
                return f"[{last_msg.message_type.value.title()}]"
        return "Sin mensajes"
    
    # Métodos de negocio
    def add_participant(self, user, role: str = 'member', 
                       notification_settings: dict[str, Any] = None) -> bool:
        """Agregar participante a la conversación"""
        # Verificar límite de participantes
        if self.max_participants and self.participant_count >= self.max_participants:
            raise ValidationError("Se ha alcanzado el máximo de participantes")
        
        # Verificar si ya es participante
        from .. import db
        
        existing = db.session.execute(
            conversation_participants.select().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user.id
            )
        ).first()
        
        if existing:
            if existing.is_active:
                return False  # Ya es participante activo
            else:
                # Reactivar participante
                db.session.execute(
                    conversation_participants.update().where(
                        conversation_participants.c.conversation_id == self.id,
                        conversation_participants.c.user_id == user.id
                    ).values(
                        is_active=True,
                        joined_at=datetime.now(timezone.utc),
                        left_at=None
                    )
                )
                return True
        
        # Agregar nuevo participante
        participant_data = {
            'conversation_id': self.id,
            'user_id': user.id,
            'role': role,
            'notification_settings': notification_settings or {
                'mentions': True,
                'all_messages': True,
                'push_notifications': True
            }
        }
        
        db.session.execute(conversation_participants.insert().values(participant_data))
        
        # Crear mensaje de sistema
        self._create_system_message(f"{user.full_name} se unió a la conversación")
        
        return True
    
    def remove_participant(self, user, removed_by_user_id: int = None) -> bool:
        """Remover participante de la conversación"""
        from .. import db
        
        # Verificar si es participante
        participant = db.session.execute(
            conversation_participants.select().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user.id,
                conversation_participants.c.is_active == True
            )
        ).first()
        
        if not participant:
            return False
        
        # Marcar como inactivo
        db.session.execute(
            conversation_participants.update().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user.id
            ).values(
                is_active=False,
                left_at=datetime.now(timezone.utc)
            )
        )
        
        # Crear mensaje de sistema
        if removed_by_user_id and removed_by_user_id != user.id:
            remover = User.query.get(removed_by_user_id)
            self._create_system_message(f"{user.full_name} fue removido por {remover.full_name}")
        else:
            self._create_system_message(f"{user.full_name} abandonó la conversación")
        
        return True
    
    def update_participant_role(self, user, new_role: str, updated_by_user_id: int):
        """Actualizar rol de participante"""
        from .. import db
        
        db.session.execute(
            conversation_participants.update().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user.id
            ).values(role=new_role)
        )
        
        updater = User.query.get(updated_by_user_id)
        self._create_system_message(f"{user.full_name} ahora es {new_role} (actualizado por {updater.full_name})")
    
    def mark_as_read(self, user, read_at: datetime = None):
        """Marcar conversación como leída para un usuario"""
        from .. import db
        
        read_time = read_at or datetime.now(timezone.utc)
        
        db.session.execute(
            conversation_participants.update().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user.id
            ).values(last_read_at=read_time)
        )
    
    def get_unread_count(self, user_id: int) -> int:
        """Obtener número de mensajes no leídos para un usuario"""
        from .. import db
        
        # Obtener última fecha de lectura
        participant = db.session.execute(
            conversation_participants.select().where(
                conversation_participants.c.conversation_id == self.id,
                conversation_participants.c.user_id == user_id
            )
        ).first()
        
        if not participant or not participant.last_read_at:
            return self.total_messages
        
        # Contar mensajes posteriores a la última lectura
        unread_count = Message.query.filter(
            Message.conversation_id == self.id,
            Message.created_at > participant.last_read_at,
            Message.sender_id != user_id,  # No contar propios mensajes
            Message.is_deleted == False
        ).count()
        
        return unread_count
    
    def archive_conversation(self, archived_by_user_id: int):
        """Archivar conversación"""
        self.is_archived = True
        self._create_system_message("Conversación archivada", archived_by_user_id)
    
    def unarchive_conversation(self, unarchived_by_user_id: int):
        """Desarchivar conversación"""
        self.is_archived = False
        self._create_system_message("Conversación desarchivada", unarchived_by_user_id)
    
    def _create_system_message(self, content: str, sender_id: int = None):
        """Crear mensaje de sistema"""
        system_message = Message(
            conversation_id=self.id,
            sender_id=sender_id,
            content=content,
            message_type=MessageType.SYSTEM,
            status=MessageStatus.SENT
        )
        
        from .. import db
        db.session.add(system_message)
        
        # Actualizar estadísticas
        self.total_messages += 1
        self.last_message_at = datetime.now(timezone.utc)
        self.last_activity_at = datetime.now(timezone.utc)
    
    def get_conversation_summary(self, user_id: int) -> dict[str, Any]:
        """Obtener resumen de la conversación para un usuario"""
        unread_count = self.get_unread_count(user_id)
        
        return {
            'id': self.id,
            'title': self.title,
            'type': self.conversation_type.value,
            'participant_count': self.participant_count,
            'total_messages': self.total_messages,
            'unread_count': unread_count,
            'last_message_preview': self.last_message_preview,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_activity_at': self.last_activity_at.isoformat(),
            'is_muted': self.is_muted,
            'is_archived': self.is_archived,
            'is_private': self.is_private,
            'context': {
                'project': self.project.name if self.project else None,
                'mentorship': f"{self.mentorship.mentor.full_name} -> {self.mentorship.mentee.full_name}" if self.mentorship else None,
                'program': self.program.name if self.program else None,
                'organization': self.organization.name if self.organization else None
            }
        }
    
    # Métodos de búsqueda
    @classmethod
    def get_user_conversations(cls, user_id: int, include_archived: bool = False):
        """Obtener conversaciones de un usuario"""
        from .. import db
        
        query = cls.query.join(
            conversation_participants,
            cls.id == conversation_participants.c.conversation_id
        ).filter(
            conversation_participants.c.user_id == user_id,
            conversation_participants.c.is_active == True,
            cls.is_deleted == False
        )
        
        if not include_archived:
            query = query.filter(cls.is_archived == False)
        
        return query.order_by(cls.last_activity_at.desc()).all()
    
    @classmethod
    def find_direct_conversation(cls, user1_id: int, user2_id: int):
        """Encontrar conversación directa entre dos usuarios"""
        from .. import db
        
        # Buscar conversación directa que contenga ambos usuarios
        conversation = db.session.execute(
            cls.query.filter(
                cls.conversation_type == ConversationType.DIRECT
            ).join(
                conversation_participants, 
                cls.id == conversation_participants.c.conversation_id
            ).filter(
                conversation_participants.c.user_id.in_([user1_id, user2_id]),
                conversation_participants.c.is_active == True
            ).group_by(cls.id).having(
                db.func.count(conversation_participants.c.user_id) == 2
            )
        ).first()
        
        return conversation
    
    def to_dict(self, include_participants=False, user_id: int = None) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'conversation_type': self.conversation_type.value,
            'is_private': self.is_private,
            'is_archived': self.is_archived,
            'is_muted': self.is_muted,
            'participant_count': self.participant_count,
            'total_messages': self.total_messages,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_activity_at': self.last_activity_at.isoformat(),
            'allow_file_sharing': self.allow_file_sharing,
            'allow_voice_messages': self.allow_voice_messages,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if user_id:
            data['unread_count'] = self.get_unread_count(user_id)
        
        if include_participants:
            data['participants'] = [
                {
                    'id': participant.id,
                    'name': participant.full_name,
                    'email': participant.email,
                    'avatar_url': getattr(participant, 'avatar_url', None)
                }
                for participant in self.participants
            ]
        
        return data


class Message(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Modelo Mensaje
    
    Representa mensajes individuales dentro de conversaciones,
    incluyendo texto, archivos, notificaciones y mensajes del sistema.
    """
    
    __tablename__ = 'messages'
    
    # Relación con conversación
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False, index=True)
    conversation = relationship("Conversation", back_populates="messages")
    
    # Remitente del mensaje
    sender_id = Column(Integer, ForeignKey('users.id'), index=True)  # Null para mensajes de sistema
    sender = relationship("User", foreign_keys=[sender_id])
    
    # Mensaje padre (para respuestas/hilos)
    parent_message_id = Column(Integer, ForeignKey('messages.id'))
    parent_message = relationship("Message", remote_side="Message.id", backref="replies")
    
    # Contenido del mensaje
    content = Column(Text)  # Contenido principal
    content_html = Column(Text)  # Contenido HTML renderizado
    message_type = Column(SQLEnum(MessageType), default=MessageType.TEXT, index=True)
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SENT, index=True)
    priority = Column(SQLEnum(MessagePriority), default=MessagePriority.NORMAL)
    
    # Metadatos del mensaje
    subject = Column(String(300))  # Asunto (para algunos tipos de mensaje)
    message_metadata = Column(JSON)  # Metadatos adicionales
    
    # Archivos adjuntos
    attachments = Column(JSON)  # Lista de archivos adjuntos
    
    # Menciones y referencias
    mentions = Column(JSON)  # Usuarios mencionados
    hashtags = Column(JSON)  # Hashtags en el mensaje
    links = Column(JSON)  # Enlaces extraídos
    
    # Configuración del mensaje
    is_pinned = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)
    requires_response = Column(Boolean, default=False)
    response_deadline = Column(DateTime)
    
    # Programación de mensajes
    scheduled_at = Column(DateTime)  # Para mensajes programados
    is_scheduled = Column(Boolean, default=False, index=True)
    
    # Edición y eliminación
    edited_at = Column(DateTime)
    edited_by_id = Column(Integer, ForeignKey('users.id'))
    edited_by = relationship("User", foreign_keys=[edited_by_id])
    edit_history = Column(JSON)  # Historial de ediciones
    
    deleted_at = Column(DateTime)
    deleted_by_id = Column(Integer, ForeignKey('users.id'))
    deleted_by = relationship("User", foreign_keys=[deleted_by_id])
    
    # Reacciones y interacciones
    reactions = Column(JSON)  # Reacciones emoji
    view_count = Column(Integer, default=0)
    
    # Enlaces a entidades del ecosistema
    project_id = Column(Integer, ForeignKey('projects.id'))
    project = relationship("Project")
    
    task_id = Column(Integer, ForeignKey('tasks.id'))
    task = relationship("Task")
    
    meeting_id = Column(Integer, ForeignKey('meetings.id'))
    meeting = relationship("Meeting")
    
    document_id = Column(Integer, ForeignKey('documents.id'))
    document = relationship("Document")
    
    # Destinatarios (para mensajes directos/broadcast)
    recipients = relationship("User",
                            secondary=message_recipients,
                            back_populates="received_messages")
    
    def __init__(self, **kwargs):
        """Inicialización del mensaje"""
        super().__init__(**kwargs)
        
        # Procesar contenido si es texto
        if self.message_type == MessageType.TEXT and self.content:
            self._process_text_content()
        
        # Configurar metadatos por defecto
        if not self.message_metadata:
            self.message_metadata = {}
    
    def __repr__(self):
        return f'<Message {self.id} - {self.message_type.value}>'
    
    def __str__(self):
        content_preview = self.content[:50] + "..." if self.content and len(self.content) > 50 else self.content or ""
        return f'{self.message_type.value}: {content_preview}'
    
    # Validaciones
    @validates('content')
    def validate_content(self, key, content):
        """Validar contenido del mensaje"""
        if self.message_type == MessageType.TEXT:
            if not content or len(content.strip()) == 0:
                raise ValidationError("Los mensajes de texto no pueden estar vacíos")
            if len(content) > 10000:  # Límite de 10k caracteres
                raise ValidationError("El mensaje excede el límite de 10,000 caracteres")
            
            # Limpiar HTML peligroso
            content = bleach.clean(content, tags=['b', 'i', 'u', 'em', 'strong', 'br', 'p'], strip=True)
        
        return content
    
    @validates('subject')
    def validate_subject(self, key, subject):
        """Validar asunto"""
        if subject and len(subject) > 300:
            raise ValidationError("El asunto no puede exceder 300 caracteres")
        return subject.strip() if subject else subject
    
    @validates('attachments')
    def validate_attachments(self, key, attachments):
        """Validar archivos adjuntos"""
        if attachments:
            if not isinstance(attachments, list):
                raise ValidationError("Los archivos adjuntos deben ser una lista")
            
            if len(attachments) > 10:  # Máximo 10 archivos
                raise ValidationError("Máximo 10 archivos adjuntos por mensaje")
            
            # Validar estructura de cada archivo
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    raise ValidationError("Cada archivo adjunto debe ser un objeto")
                
                required_fields = ['filename', 'url', 'size', 'mime_type']
                for field in required_fields:
                    if field not in attachment:
                        raise ValidationError(f"Campo requerido '{field}' faltante en archivo adjunto")
        
        return attachments
    
    # Propiedades híbridas
    @hybrid_property
    def is_reply(self):
        """Verificar si es una respuesta"""
        return self.parent_message_id is not None
    
    @hybrid_property
    def has_attachments(self):
        """Verificar si tiene archivos adjuntos"""
        return self.attachments and len(self.attachments) > 0
    
    @hybrid_property
    def has_mentions(self):
        """Verificar si tiene menciones"""
        return self.mentions and len(self.mentions) > 0
    
    @hybrid_property
    def is_system_message(self):
        """Verificar si es mensaje del sistema"""
        return self.message_type == MessageType.SYSTEM
    
    @hybrid_property
    def reply_count(self):
        """Número de respuestas"""
        if not self.replies:
            return 0
        return len([reply for reply in self.replies if not reply.is_deleted])
    
    @hybrid_property
    def reaction_count(self):
        """Número total de reacciones"""
        if not self.reactions:
            return 0
        return sum(len(users) for users in self.reactions.values())
    
    @hybrid_property
    def content_preview(self):
        """Vista previa del contenido"""
        if self.message_type == MessageType.TEXT:
            return self.content[:100] + "..." if self.content and len(self.content) > 100 else self.content
        elif self.message_type == MessageType.IMAGE:
            return "📷 Imagen"
        elif self.message_type == MessageType.FILE:
            filename = self.attachments[0]['filename'] if self.attachments else 'archivo'
            return f"📎 {filename}"
        elif self.message_type == MessageType.AUDIO:
            return "🎵 Audio"
        elif self.message_type == MessageType.VIDEO:
            return "🎥 Video"
        else:
            return f"[{self.message_type.value.title()}]"
    
    # Métodos de negocio
    def _process_text_content(self):
        """Procesar contenido de texto para extraer menciones, links, etc."""
        if not self.content:
            return
        
        # Extraer menciones (@usuario)
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, self.content)
        if mentions:
            self.mentions = mentions
        
        # Extraer hashtags (#tag)
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, self.content)
        if hashtags:
            self.hashtags = hashtags
        
        # Extraer URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        links = re.findall(url_pattern, self.content)
        if links:
            self.links = [{'url': link, 'title': None, 'description': None} for link in links]
        
        # Generar contenido HTML seguro
        self.content_html = self._generate_html_content()
    
    def _generate_html_content(self) -> str:
        """Generar contenido HTML del texto"""
        if not self.content:
            return ""
        
        html_content = escape(self.content)
        
        # Convertir menciones a enlaces
        if self.mentions:
            for mention in self.mentions:
                html_content = html_content.replace(
                    f'@{mention}', 
                    f'<span class="mention" data-user="{mention}">@{mention}</span>'
                )
        
        # Convertir hashtags a enlaces
        if self.hashtags:
            for hashtag in self.hashtags:
                html_content = html_content.replace(
                    f'#{hashtag}', 
                    f'<span class="hashtag" data-tag="{hashtag}">#{hashtag}</span>'
                )
        
        # Convertir URLs a enlaces
        if self.links:
            for link_data in self.links:
                url = link_data['url']
                html_content = html_content.replace(
                    url, 
                    f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
                )
        
        # Convertir saltos de línea
        html_content = html_content.replace('\n', '<br>')
        
        return html_content
    
    def add_attachment(self, filename: str, url: str, size: int, 
                      mime_type: str, attachment_type: AttachmentType = None) -> bool:
        """Agregar archivo adjunto"""
        if not self.attachments:
            self.attachments = []
        
        if len(self.attachments) >= 10:
            raise ValidationError("Máximo 10 archivos adjuntos por mensaje")
        
        # Determinar tipo de archivo si no se especifica
        if not attachment_type:
            if mime_type.startswith('image/'):
                attachment_type = AttachmentType.IMAGE
            elif mime_type.startswith('audio/'):
                attachment_type = AttachmentType.AUDIO
            elif mime_type.startswith('video/'):
                attachment_type = AttachmentType.VIDEO
            elif mime_type == 'application/pdf':
                attachment_type = AttachmentType.PDF
            elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                attachment_type = AttachmentType.DOCUMENT
            elif mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                attachment_type = AttachmentType.SPREADSHEET
            elif mime_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
                attachment_type = AttachmentType.PRESENTATION
            else:
                attachment_type = AttachmentType.OTHER
        
        attachment = {
            'id': len(self.attachments) + 1,
            'filename': filename,
            'url': url,
            'size': size,
            'mime_type': mime_type,
            'type': attachment_type.value,
            'uploaded_at': datetime.now(timezone.utc).isoformat()
        }
        
        self.attachments.append(attachment)
        
        # Actualizar tipo de mensaje si es necesario
        if self.message_type == MessageType.TEXT:
            if attachment_type == AttachmentType.IMAGE:
                self.message_type = MessageType.IMAGE
            elif attachment_type in [AttachmentType.AUDIO]:
                self.message_type = MessageType.AUDIO
            elif attachment_type in [AttachmentType.VIDEO]:
                self.message_type = MessageType.VIDEO
            else:
                self.message_type = MessageType.FILE
        
        return True
    
    def add_reaction(self, user_id: int, emoji: str) -> bool:
        """Agregar reacción al mensaje"""
        if not self.reactions:
            self.reactions = {}
        
        if emoji not in self.reactions:
            self.reactions[emoji] = []
        
        if user_id not in self.reactions[emoji]:
            self.reactions[emoji].append(user_id)
            return True
        
        return False
    
    def remove_reaction(self, user_id: int, emoji: str) -> bool:
        """Remover reacción del mensaje"""
        if not self.reactions or emoji not in self.reactions:
            return False
        
        if user_id in self.reactions[emoji]:
            self.reactions[emoji].remove(user_id)
            
            # Remover emoji si no hay más reacciones
            if len(self.reactions[emoji]) == 0:
                del self.reactions[emoji]
            
            return True
        
        return False
    
    def edit_message(self, new_content: str, edited_by_user_id: int) -> bool:
        """Editar mensaje"""
        if self.message_type != MessageType.TEXT:
            raise ValidationError("Solo se pueden editar mensajes de texto")
        
        if self.is_system_message:
            raise ValidationError("No se pueden editar mensajes del sistema")
        
        # Guardar historial de edición
        if not self.edit_history:
            self.edit_history = []
        
        self.edit_history.append({
            'content': self.content,
            'edited_at': datetime.now(timezone.utc).isoformat(),
            'edited_by': edited_by_user_id
        })
        
        # Actualizar contenido
        old_content = self.content
        self.content = new_content
        self.edited_at = datetime.now(timezone.utc)
        self.edited_by_id = edited_by_user_id
        
        # Reprocesar contenido
        self._process_text_content()
        
        return True
    
    def delete_message(self, deleted_by_user_id: int, soft_delete: bool = True):
        """Eliminar mensaje"""
        if soft_delete:
            self.is_deleted = True
            self.deleted_at = datetime.now(timezone.utc)
            self.deleted_by_id = deleted_by_user_id
            self.content = "[Mensaje eliminado]"
            self.content_html = "[Mensaje eliminado]"
        else:
            # Eliminación completa (raramente usada)
            from .. import db
            db.session.delete(self)
    
    def mark_as_read_by_user(self, user_id: int, read_at: datetime = None):
        """Marcar mensaje como leído por un usuario"""
        from .. import db
        
        read_time = read_at or datetime.now(timezone.utc)
        
        # Actualizar estado en tabla de destinatarios
        db.session.execute(
            message_recipients.update().where(
                message_recipients.c.message_id == self.id,
                message_recipients.c.user_id == user_id
            ).values(
                status='read',
                read_at=read_time
            )
        )
        
        # Actualizar última lectura en conversación
        self.conversation.mark_as_read(User.query.get(user_id), read_time)
    
    def get_delivery_status(self) -> dict[str, Any]:
        """Obtener estado de entrega del mensaje"""
        from .. import db
        
        recipients_data = db.session.execute(
            message_recipients.select().where(
                message_recipients.c.message_id == self.id
            )
        ).fetchall()
        
        if not recipients_data:
            return {
                'total_recipients': 0,
                'delivered': 0,
                'read': 0,
                'failed': 0,
                'delivery_rate': 0,
                'read_rate': 0
            }
        
        total = len(recipients_data)
        delivered = len([r for r in recipients_data if r.status in ['delivered', 'read']])
        read = len([r for r in recipients_data if r.status == 'read'])
        failed = len([r for r in recipients_data if r.status == 'failed'])
        
        return {
            'total_recipients': total,
            'delivered': delivered,
            'read': read,
            'failed': failed,
            'delivery_rate': (delivered / total * 100) if total > 0 else 0,
            'read_rate': (read / total * 100) if total > 0 else 0,
            'pending': total - delivered - failed
        }
    
    def pin_message(self, pinned_by_user_id: int):
        """Fijar mensaje en la conversación"""
        if self.is_pinned:
            return False
        
        self.is_pinned = True
        
        # Crear mensaje de sistema
        pinner = User.query.get(pinned_by_user_id)
        self.conversation._create_system_message(
            f"Mensaje fijado por {pinner.full_name}", 
            pinned_by_user_id
        )
        
        return True
    
    def unpin_message(self, unpinned_by_user_id: int):
        """Desfijar mensaje"""
        if not self.is_pinned:
            return False
        
        self.is_pinned = False
        
        # Crear mensaje de sistema
        unpinner = User.query.get(unpinned_by_user_id)
        self.conversation._create_system_message(
            f"Mensaje desfijado por {unpinner.full_name}", 
            unpinned_by_user_id
        )
        
        return True
    
    def schedule_message(self, send_at: datetime):
        """Programar mensaje para envío futuro"""
        if send_at <= datetime.now(timezone.utc):
            raise ValidationError("La fecha de programación debe ser futura")
        
        self.scheduled_at = send_at
        self.is_scheduled = True
        self.status = MessageStatus.DRAFT
    
    def send_scheduled_message(self):
        """Enviar mensaje programado"""
        if not self.is_scheduled:
            raise ValidationError("El mensaje no está programado")
        
        if self.scheduled_at > datetime.now(timezone.utc):
            raise ValidationError("Aún no es hora de enviar el mensaje")
        
        self.is_scheduled = False
        self.status = MessageStatus.SENT
        
        # Actualizar estadísticas de conversación
        self.conversation.total_messages += 1
        self.conversation.last_message_at = datetime.now(timezone.utc)
        self.conversation.last_activity_at = datetime.now(timezone.utc)
    
    def create_reply(self, sender_id: int, content: str, message_type: MessageType = MessageType.TEXT):
        """Crear respuesta a este mensaje"""
        reply = Message(
            conversation_id=self.conversation_id,
            sender_id=sender_id,
            parent_message_id=self.id,
            content=content,
            message_type=message_type,
            status=MessageStatus.SENT
        )
        
        from .. import db
        db.session.add(reply)
        
        # Actualizar estadísticas de conversación
        self.conversation.total_messages += 1
        self.conversation.last_message_at = datetime.now(timezone.utc)
        self.conversation.last_activity_at = datetime.now(timezone.utc)
        
        return reply
    
    def get_thread_messages(self) -> list['Message']:
        """Obtener mensajes del hilo (respuestas)"""
        return Message.query.filter(
            Message.parent_message_id == self.id,
            Message.is_deleted == False
        ).order_by(Message.created_at.asc()).all()
    
    def increment_view_count(self):
        """Incrementar contador de visualizaciones"""
        self.view_count = (self.view_count or 0) + 1
    
    # Métodos de búsqueda
    @classmethod
    def search_messages(cls, conversation_id: int, query: str = None, 
                       message_type: MessageType = None, sender_id: int = None,
                       date_from: datetime = None, date_to: datetime = None,
                       has_attachments: bool = None, limit: int = 50):
        """Buscar mensajes en una conversación"""
        search = cls.query.filter(
            cls.conversation_id == conversation_id,
            cls.is_deleted == False
        )
        
        if query:
            search_term = f"%{query}%"
            search = search.filter(cls.content.ilike(search_term))
        
        if message_type:
            search = search.filter(cls.message_type == message_type)
        
        if sender_id:
            search = search.filter(cls.sender_id == sender_id)
        
        if date_from:
            search = search.filter(cls.created_at >= date_from)
        
        if date_to:
            search = search.filter(cls.created_at <= date_to)
        
        if has_attachments is not None:
            if has_attachments:
                search = search.filter(cls.attachments.isnot(None))
            else:
                search = search.filter(cls.attachments.is_(None))
        
        return search.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_pinned_messages(cls, conversation_id: int):
        """Obtener mensajes fijados de una conversación"""
        return cls.query.filter(
            cls.conversation_id == conversation_id,
            cls.is_pinned == True,
            cls.is_deleted == False
        ).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_scheduled_messages(cls, due_before: datetime = None):
        """Obtener mensajes programados listos para envío"""
        query = cls.query.filter(
            cls.is_scheduled == True,
            cls.status == MessageStatus.DRAFT
        )
        
        if due_before:
            query = query.filter(cls.scheduled_at <= due_before)
        else:
            query = query.filter(cls.scheduled_at <= datetime.now(timezone.utc))
        
        return query.all()
    
    def to_dict(self, include_thread=False, include_reactions=True, user_id: int = None) -> dict[str, Any]:
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.full_name if self.sender else 'Sistema',
            'sender_avatar': getattr(self.sender, 'avatar_url', None) if self.sender else None,
            'content': self.content,
            'content_html': self.content_html,
            'content_preview': self.content_preview,
            'message_type': self.message_type.value,
            'status': self.status.value,
            'priority': self.priority.value,
            'is_reply': self.is_reply,
            'parent_message_id': self.parent_message_id,
            'reply_count': self.reply_count,
            'has_attachments': self.has_attachments,
            'attachments': self.attachments,
            'has_mentions': self.has_mentions,
            'mentions': self.mentions,
            'hashtags': self.hashtags,
            'links': self.links,
            'is_pinned': self.is_pinned,
            'is_urgent': self.is_urgent,
            'is_system_message': self.is_system_message,
            'is_edited': bool(self.edited_at),
            'edited_at': self.edited_at.isoformat() if self.edited_at else None,
            'is_scheduled': self.is_scheduled,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'view_count': self.view_count,
            'message_metadata': self.message_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_reactions and self.reactions:
            data['reactions'] = self.reactions
            data['reaction_count'] = self.reaction_count
        
        if include_thread and self.reply_count > 0:
            data['thread_messages'] = [
                reply.to_dict(include_thread=False, user_id=user_id) 
                for reply in self.get_thread_messages()[:5]  # Últimas 5 respuestas
            ]
        
        # Información específica del usuario
        if user_id:
            data['is_own_message'] = self.sender_id == user_id
            if self.reactions:
                data['user_reactions'] = [
                    emoji for emoji, users in self.reactions.items() 
                    if user_id in users
                ]
        
        return data


# Funciones de utilidad para el módulo
def get_messaging_statistics(user_id: int = None, organization_id: int = None,
                           date_from: date = None, date_to: date = None) -> dict[str, Any]:
    """Obtener estadísticas de mensajería"""
    conversations_query = Conversation.query.filter(Conversation.is_deleted == False)
    messages_query = Message.query.filter(Message.is_deleted == False)
    
    if user_id:
        from .. import db
        conversations_query = conversations_query.join(
            conversation_participants,
            Conversation.id == conversation_participants.c.conversation_id
        ).filter(conversation_participants.c.user_id == user_id)
        
        messages_query = messages_query.filter(Message.sender_id == user_id)
    
    if organization_id:
        conversations_query = conversations_query.filter(
            Conversation.organization_id == organization_id
        )
    
    if date_from:
        date_from_dt = datetime.combine(date_from, datetime.min.time())
        conversations_query = conversations_query.filter(
            Conversation.created_at >= date_from_dt
        )
        messages_query = messages_query.filter(Message.created_at >= date_from_dt)
    
    if date_to:
        date_to_dt = datetime.combine(date_to, datetime.max.time())
        conversations_query = conversations_query.filter(
            Conversation.created_at <= date_to_dt
        )
        messages_query = messages_query.filter(Message.created_at <= date_to_dt)
    
    conversations = conversations_query.all()
    messages = messages_query.all()
    
    if not conversations and not messages:
        return {
            'total_conversations': 0,
            'total_messages': 0,
            'active_conversations': 0,
            'average_messages_per_conversation': 0,
            'messages_per_day': 0,
            'most_active_conversation_type': None
        }
    
    # Estadísticas básicas
    total_conversations = len(conversations)
    total_messages = len(messages)
    active_conversations = len([c for c in conversations if not c.is_archived])
    
    # Promedio de mensajes por conversación
    avg_messages_per_conv = total_messages / total_conversations if total_conversations > 0 else 0
    
    # Mensajes por día (última semana)
    week_ago = datetime.now() - timedelta(days=7)
    recent_messages = [m for m in messages if m.created_at >= week_ago]
    messages_per_day = len(recent_messages) / 7
    
    # Distribución por tipo de conversación
    conv_type_distribution = {}
    for conv in conversations:
        conv_type = conv.conversation_type.value
        conv_type_distribution[conv_type] = conv_type_distribution.get(conv_type, 0) + 1
    
    most_active_type = max(conv_type_distribution.items(), key=lambda x: x[1])[0] if conv_type_distribution else None
    
    # Distribución por tipo de mensaje
    msg_type_distribution = {}
    for msg in messages:
        msg_type = msg.message_type.value
        msg_type_distribution[msg_type] = msg_type_distribution.get(msg_type, 0) + 1
    
    # Análisis de actividad por hora
    hourly_activity = {}
    for msg in messages:
        hour = msg.created_at.hour
        hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
    
    peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0] if hourly_activity else None
    
    return {
        'total_conversations': total_conversations,
        'total_messages': total_messages,
        'active_conversations': active_conversations,
        'archived_conversations': total_conversations - active_conversations,
        'average_messages_per_conversation': round(avg_messages_per_conv, 1),
        'messages_per_day_last_week': round(messages_per_day, 1),
        'conversation_type_distribution': conv_type_distribution,
        'most_active_conversation_type': most_active_type,
        'message_type_distribution': msg_type_distribution,
        'peak_messaging_hour': peak_hour,
        'engagement_metrics': {
            'conversations_with_recent_activity': len([
                c for c in conversations 
                if c.last_activity_at and c.last_activity_at >= week_ago
            ]),
            'average_participants_per_conversation': round(
                sum(c.participant_count for c in conversations) / total_conversations, 1
            ) if total_conversations > 0 else 0
        }
    }


def create_direct_conversation(user1_id: int, user2_id: int) -> Conversation:
    """Crear conversación directa entre dos usuarios"""
    # Verificar si ya existe
    existing = Conversation.find_direct_conversation(user1_id, user2_id)
    if existing:
        return existing
    
    # Crear nueva conversación
    conversation = Conversation(
        conversation_type=ConversationType.DIRECT,
        creator_id=user1_id,
        is_private=True,
        max_participants=2
    )
    
    from .. import db
    db.session.add(conversation)
    db.session.flush()  # Para obtener ID
    
    # Agregar participantes
    conversation.add_participant(User.query.get(user1_id), 'admin')
    conversation.add_participant(User.query.get(user2_id), 'member')
    
    return conversation


def send_system_notification(user_ids: list[int], title: str, content: str,
                           notification_type: str = 'info', 
                           related_entity_type: str = None,
                           related_entity_id: int = None) -> list[Message]:
    """Enviar notificación del sistema a múltiples usuarios"""
    messages = []
    
    for user_id in user_ids:
        # Crear conversación de notificación si no existe
        notification_conv = Conversation.query.filter(
            Conversation.conversation_type == ConversationType.BROADCAST,
            Conversation.creator_id == 1,  # Usuario del sistema
            Conversation.participants.any(id=user_id)
        ).first()
        
        if not notification_conv:
            notification_conv = Conversation(
                title="Notificaciones del Sistema",
                conversation_type=ConversationType.BROADCAST,
                creator_id=1,  # Usuario del sistema
                is_private=True,
                allow_guests=False
            )
            
            from .. import db
            db.session.add(notification_conv)
            db.session.flush()
            
            notification_conv.add_participant(User.query.get(user_id), 'member')
        
        # Crear mensaje de notificación
        message = Message(
            conversation_id=notification_conv.id,
            sender_id=1,  # Usuario del sistema
            subject=title,
            content=content,
            message_type=MessageType.NOTIFICATION,
            status=MessageStatus.SENT,
            priority=MessagePriority.HIGH if notification_type == 'urgent' else MessagePriority.NORMAL,
            message_metadata={
                'notification_type': notification_type,
                'related_entity_type': related_entity_type,
                'related_entity_id': related_entity_id
            }
        )
        
        from .. import db
        db.session.add(message)
        messages.append(message)
        
        # Actualizar estadísticas de conversación
        notification_conv.total_messages += 1
        notification_conv.last_message_at = datetime.now(timezone.utc)
        notification_conv.last_activity_at = datetime.now(timezone.utc)
    
    return messages


def process_scheduled_messages():
    """Procesar mensajes programados listos para envío"""
    scheduled_messages = Message.get_scheduled_messages()
    processed_count = 0
    
    for message in scheduled_messages:
        try:
            message.send_scheduled_message()
            processed_count += 1
        except Exception as e:
            # Log error pero continuar con otros mensajes
            print(f"Error enviando mensaje programado {message.id}: {e}")
    
    return processed_count