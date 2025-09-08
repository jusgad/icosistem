"""
Namespaces Especializados para WebSockets - Ecosistema de Emprendimiento
========================================================================

Este módulo define namespaces especializados para diferentes funcionalidades
del sistema de WebSockets, proporcionando comunicación en tiempo real
organizada y segura para cada tipo de interacción.

Namespaces implementados:
- /chat: Comunicación instantánea entre usuarios
- /notifications: Sistema de notificaciones en tiempo real
- /presence: Tracking de presencia y actividad de usuarios
- /collaboration: Colaboración en tiempo real en documentos/proyectos
- /admin: Funcionalidades administrativas en tiempo real
- /analytics: Métricas y datos en tiempo real
- /mentorship: Sesiones de mentoría interactivas
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from flask import request, current_app
from flask_socketio import Namespace, emit, join_room, leave_room, disconnect
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import (
    SocketAuthenticationError,
    SocketAuthorizationError,
    ValidationError
)
from app.core.permissions import has_permission, UserRole
from app.models.user import User
from app.models.message import Message, MessageType
from app.models.notification import Notification
from app.models.project import Project
from app.models.mentorship import MentorshipSession
from app.models.meeting import Meeting
from app.models.document import Document
from app.services.user_service import UserService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.services.mentorship_service import MentorshipService
from app.utils.decorators import rate_limit
from app.utils.validators import validate_message_content, validate_room_name
from app.utils.formatters import format_datetime, format_user_info

logger = logging.getLogger(__name__)


class BaseNamespace(Namespace):
    """
    Namespace base con funcionalidades comunes
    
    Proporciona autenticación, autorización y utilidades
    compartidas para todos los namespaces especializados.
    """
    
    def __init__(self, namespace: str):
        super().__init__(namespace)
        self.user_service = UserService()
        self.connected_users: dict[str, dict[str, Any]] = {}
    
    def on_connect(self, auth):
        """Maneja conexiones al namespace"""
        try:
            # Verificar autenticación
            user = self._authenticate_user(auth)
            if not user:
                self._emit_error("Authentication required")
                disconnect()
                return
            
            # Verificar autorización para el namespace
            if not self._authorize_namespace_access(user):
                self._emit_error("Access denied to namespace")
                disconnect()
                return
            
            # Registrar usuario conectado
            self._register_user_connection(user)
            
            # Emitir evento de conexión exitosa
            emit('connected', {
                'namespace': self.namespace,
                'user_id': str(user.id),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            logger.info(f"Usuario {user.username} conectado a namespace {self.namespace}")
            
        except Exception as e:
            logger.error(f"Error en conexión a namespace {self.namespace}: {str(e)}")
            self._emit_error("Connection failed")
            disconnect()
    
    def on_disconnect(self):
        """Maneja desconexiones del namespace"""
        try:
            user_id = self._get_current_user_id()
            if user_id and user_id in self.connected_users:
                user_info = self.connected_users[user_id]
                del self.connected_users[user_id]
                
                logger.info(f"Usuario {user_info.get('username')} desconectado de namespace {self.namespace}")
                
        except Exception as e:
            logger.error(f"Error en desconexión de namespace {self.namespace}: {str(e)}")
    
    def _authenticate_user(self, auth) -> Optional[User]:
        """Autentica usuario basado en token"""
        try:
            if not auth or 'token' not in auth:
                return None
            
            # Verificar token JWT
            from flask_jwt_extended import decode_token
            token_data = decode_token(auth['token'])
            user_id = token_data['sub']
            
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return None
            
            return user
            
        except Exception as e:
            logger.error(f"Error en autenticación: {str(e)}")
            return None
    
    def _authorize_namespace_access(self, user: User) -> bool:
        """Verifica autorización para acceder al namespace"""
        # Override en subclases para lógica específica
        return True
    
    def _register_user_connection(self, user: User):
        """Registra la conexión del usuario"""
        self.connected_users[str(user.id)] = {
            'user_id': str(user.id),
            'username': user.username,
            'role': user.role.value,
            'session_id': request.sid,
            'connected_at': datetime.now(timezone.utc),
            'last_activity': datetime.now(timezone.utc)
        }
    
    def _get_current_user_id(self) -> Optional[str]:
        """Obtiene el ID del usuario actual por session_id"""
        session_id = request.sid
        for user_id, info in self.connected_users.items():
            if info['session_id'] == session_id:
                return user_id
        return None
    
    def _get_current_user(self) -> Optional[User]:
        """Obtiene el usuario actual"""
        user_id = self._get_current_user_id()
        return User.query.get(user_id) if user_id else None
    
    def _emit_error(self, message: str, code: str = "ERROR"):
        """Emite un error al cliente"""
        emit('error', {
            'code': code,
            'message': message,
            'timestamp': format_datetime(datetime.now(timezone.utc))
        })
    
    def _update_user_activity(self, user_id: str):
        """Actualiza la última actividad del usuario"""
        if user_id in self.connected_users:
            self.connected_users[user_id]['last_activity'] = datetime.now(timezone.utc)


class ChatNamespace(BaseNamespace):
    """
    Namespace para chat en tiempo real
    
    Maneja la comunicación instantánea entre usuarios del ecosistema:
    - Chat privado entre emprendedores y mentores
    - Canales de grupo por proyecto
    - Mensajería administrativa
    """
    
    def __init__(self):
        super().__init__('/chat')
        self.active_rooms: dict[str, set[str]] = {}
        self.typing_users: dict[str, dict[str, datetime]] = {}
    
    def _authorize_namespace_access(self, user: User) -> bool:
        """Solo usuarios activos pueden acceder al chat"""
        return user.is_active and user.role in [
            UserRole.ADMIN, 
            UserRole.ENTREPRENEUR, 
            UserRole.ALLY, 
            UserRole.CLIENT
        ]
    
    @rate_limit(rate=30, per=60)  # 30 mensajes por minuto
    def on_send_message(self, data):
        """Envía un mensaje en el chat"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            # Validar datos del mensaje
            room = data.get('room')
            content = data.get('content')
            message_type = data.get('type', 'text')
            
            if not room or not content:
                self._emit_error("Room and content are required")
                return
            
            # Validar contenido del mensaje
            if not validate_message_content(content, message_type):
                self._emit_error("Invalid message content")
                return
            
            # Verificar acceso a la sala
            if not self._can_access_room(user, room):
                self._emit_error("Access denied to room")
                return
            
            # Crear mensaje en la base de datos
            message = Message(
                sender_id=user.id,
                room=room,
                content=content,
                message_type=MessageType(message_type),
                metadata=data.get('metadata', {})
            )
            
            from app import db
            db.session.add(message)
            db.session.commit()
            
            # Preparar datos del mensaje para emisión
            message_data = {
                'id': str(message.id),
                'sender': format_user_info(user),
                'room': room,
                'content': content,
                'type': message_type,
                'timestamp': format_datetime(message.created_at),
                'metadata': message.metadata
            }
            
            # Emitir mensaje a todos en la sala
            self.emit('message_received', message_data, room=room)
            
            # Actualizar actividad del usuario
            self._update_user_activity(str(user.id))
            
            logger.info(f"Mensaje enviado por {user.username} en sala {room}")
            
        except SQLAlchemyError as e:
            logger.error(f"Error de base de datos al enviar mensaje: {str(e)}")
            self._emit_error("Database error")
        except Exception as e:
            logger.error(f"Error enviando mensaje: {str(e)}")
            self._emit_error("Failed to send message")
    
    def on_join_room(self, data):
        """Une usuario a una sala de chat"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            room = data.get('room')
            if not room or not validate_room_name(room):
                self._emit_error("Invalid room name")
                return
            
            # Verificar acceso a la sala
            if not self._can_access_room(user, room):
                self._emit_error("Access denied to room")
                return
            
            # Unirse a la sala
            join_room(room)
            
            # Registrar en salas activas
            if room not in self.active_rooms:
                self.active_rooms[room] = set()
            self.active_rooms[room].add(str(user.id))
            
            # Emitir confirmación
            emit('joined_room', {
                'room': room,
                'user_count': len(self.active_rooms[room]),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            # Notificar a otros en la sala
            self.emit('user_joined', {
                'user': format_user_info(user),
                'room': room,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room, include_self=False)
            
            logger.info(f"Usuario {user.username} se unió a sala {room}")
            
        except Exception as e:
            logger.error(f"Error uniendo a sala: {str(e)}")
            self._emit_error("Failed to join room")
    
    def on_leave_room(self, data):
        """Remueve usuario de una sala de chat"""
        try:
            user = self._get_current_user()
            if not user:
                return
            
            room = data.get('room')
            if not room:
                return
            
            # Dejar la sala
            leave_room(room)
            
            # Actualizar salas activas
            if room in self.active_rooms:
                self.active_rooms[room].discard(str(user.id))
                if not self.active_rooms[room]:
                    del self.active_rooms[room]
            
            # Notificar a otros en la sala
            self.emit('user_left', {
                'user': format_user_info(user),
                'room': room,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room)
            
            logger.info(f"Usuario {user.username} dejó sala {room}")
            
        except Exception as e:
            logger.error(f"Error dejando sala: {str(e)}")
    
    @rate_limit(rate=10, per=30)  # 10 eventos de typing por 30 segundos
    def on_typing_start(self, data):
        """Indica que el usuario está escribiendo"""
        try:
            user = self._get_current_user()
            if not user:
                return
            
            room = data.get('room')
            if not room or not self._can_access_room(user, room):
                return
            
            # Registrar usuario escribiendo
            if room not in self.typing_users:
                self.typing_users[room] = {}
            self.typing_users[room][str(user.id)] = datetime.now(timezone.utc)
            
            # Notificar a otros en la sala
            self.emit('user_typing', {
                'user': format_user_info(user),
                'room': room,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room, include_self=False)
            
        except Exception as e:
            logger.error(f"Error en typing start: {str(e)}")
    
    def on_typing_stop(self, data):
        """Indica que el usuario dejó de escribir"""
        try:
            user = self._get_current_user()
            if not user:
                return
            
            room = data.get('room')
            if not room:
                return
            
            # Remover usuario de typing
            if room in self.typing_users and str(user.id) in self.typing_users[room]:
                del self.typing_users[room][str(user.id)]
                if not self.typing_users[room]:
                    del self.typing_users[room]
            
            # Notificar a otros en la sala
            self.emit('user_stopped_typing', {
                'user': format_user_info(user),
                'room': room,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room, include_self=False)
            
        except Exception as e:
            logger.error(f"Error en typing stop: {str(e)}")
    
    def _can_access_room(self, user: User, room: str) -> bool:
        """Verifica si el usuario puede acceder a una sala específica"""
        try:
            # Salas públicas
            if room in ['general', 'announcements']:
                return True
            
            # Salas privadas de usuario
            if room.startswith(f'user_{user.id}_'):
                return True
            
            # Salas de proyecto
            if room.startswith('project_'):
                project_id = room.replace('project_', '')
                project = Project.query.get(project_id)
                return project and self._user_in_project(user, project)
            
            # Salas de mentoría
            if room.startswith('mentorship_'):
                session_id = room.replace('mentorship_', '')
                session = MentorshipSession.query.get(session_id)
                return session and (
                    session.entrepreneur_id == user.id or 
                    session.mentor_id == user.id
                )
            
            # Salas administrativas
            if room.startswith('admin_'):
                return user.role == UserRole.ADMIN
            
            return False
            
        except Exception as e:
            logger.error(f"Error verificando acceso a sala {room}: {str(e)}")
            return False
    
    def _user_in_project(self, user: User, project: Project) -> bool:
        """Verifica si el usuario está involucrado en el proyecto"""
        return (
            project.entrepreneur_id == user.id or
            user.role == UserRole.ADMIN or
            (user.role == UserRole.ALLY and user in project.mentors)
        )


class NotificationNamespace(BaseNamespace):
    """
    Namespace para notificaciones en tiempo real
    
    Maneja el envío y recepción de notificaciones instantáneas:
    - Notificaciones del sistema
    - Alertas de reuniones
    - Actualizaciones de estado
    - Mensajes administrativos
    """
    
    def __init__(self):
        super().__init__('/notifications')
        self.notification_service = NotificationService()
    
    def on_mark_as_read(self, data):
        """Marca notificaciones como leídas"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            notification_ids = data.get('notification_ids', [])
            if not notification_ids:
                self._emit_error("No notification IDs provided")
                return
            
            # Marcar notificaciones como leídas
            updated_count = self.notification_service.mark_as_read(
                user.id, 
                notification_ids
            )
            
            emit('notifications_read', {
                'count': updated_count,
                'notification_ids': notification_ids,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            logger.info(f"Usuario {user.username} marcó {updated_count} notificaciones como leídas")
            
        except Exception as e:
            logger.error(f"Error marcando notificaciones como leídas: {str(e)}")
            self._emit_error("Failed to mark notifications as read")
    
    def on_get_unread_count(self, data):
        """Obtiene el conteo de notificaciones no leídas"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            unread_count = self.notification_service.get_unread_count(user.id)
            
            emit('unread_count', {
                'count': unread_count,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo conteo de notificaciones: {str(e)}")
            self._emit_error("Failed to get unread count")
    
    def on_subscribe_to_topic(self, data):
        """Suscribe usuario a un tópico de notificaciones"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            topic = data.get('topic')
            if not topic:
                self._emit_error("Topic is required")
                return
            
            # Verificar acceso al tópico
            if not self._can_subscribe_to_topic(user, topic):
                self._emit_error("Access denied to topic")
                return
            
            # Unirse al room del tópico
            join_room(f'topic_{topic}')
            
            emit('subscribed_to_topic', {
                'topic': topic,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            logger.info(f"Usuario {user.username} suscrito a tópico {topic}")
            
        except Exception as e:
            logger.error(f"Error suscribiendo a tópico: {str(e)}")
            self._emit_error("Failed to subscribe to topic")
    
    def _can_subscribe_to_topic(self, user: User, topic: str) -> bool:
        """Verifica si el usuario puede suscribirse a un tópico"""
        # Tópicos públicos
        public_topics = ['system', 'announcements']
        if topic in public_topics:
            return True
        
        # Tópicos por rol
        role_topics = {
            'admin': UserRole.ADMIN,
            'entrepreneur': UserRole.ENTREPRENEUR,
            'ally': UserRole.ALLY,
            'client': UserRole.CLIENT
        }
        
        if topic in role_topics:
            return user.role == role_topics[topic]
        
        # Tópicos de proyecto
        if topic.startswith('project_'):
            project_id = topic.replace('project_', '')
            project = Project.query.get(project_id)
            return project and self._user_in_project(user, project)
        
        return False
    
    def _user_in_project(self, user: User, project: Project) -> bool:
        """Verifica si el usuario está en el proyecto"""
        return (
            project.entrepreneur_id == user.id or
            user.role == UserRole.ADMIN or
            (user.role == UserRole.ALLY and user in project.mentors)
        )


class PresenceNamespace(BaseNamespace):
    """
    Namespace para tracking de presencia de usuarios
    
    Maneja el estado de presencia y actividad de usuarios:
    - Estado online/offline
    - Última actividad
    - Ubicación actual en la aplicación
    """
    
    def __init__(self):
        super().__init__('/presence')
        self.user_presence: dict[str, dict[str, Any]] = {}
    
    def on_connect(self, auth):
        """Maneja conexión y establece presencia"""
        super().on_connect(auth)
        
        user = self._get_current_user()
        if user:
            self._update_presence(user, 'online')
    
    def on_disconnect(self):
        """Maneja desconexión y actualiza presencia"""
        user = self._get_current_user()
        if user:
            self._update_presence(user, 'offline')
        
        super().on_disconnect()
    
    def on_update_status(self, data):
        """Actualiza el estado del usuario"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            status = data.get('status', 'online')
            location = data.get('location', '')
            
            # Validar estado
            valid_statuses = ['online', 'away', 'busy', 'offline']
            if status not in valid_statuses:
                self._emit_error("Invalid status")
                return
            
            # Actualizar presencia
            self._update_presence(user, status, location)
            
            emit('status_updated', {
                'status': status,
                'location': location,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
        except Exception as e:
            logger.error(f"Error actualizando estado: {str(e)}")
            self._emit_error("Failed to update status")
    
    def on_get_presence(self, data):
        """Obtiene información de presencia de usuarios"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            user_ids = data.get('user_ids', [])
            if not user_ids:
                self._emit_error("User IDs required")
                return
            
            presence_data = {}
            for user_id in user_ids:
                if user_id in self.user_presence:
                    # Solo compartir información básica
                    presence_data[user_id] = {
                        'status': self.user_presence[user_id]['status'],
                        'last_seen': format_datetime(
                            self.user_presence[user_id]['last_activity']
                        )
                    }
            
            emit('presence_data', {
                'presence': presence_data,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo presencia: {str(e)}")
            self._emit_error("Failed to get presence data")
    
    def _update_presence(self, user: User, status: str, location: str = ''):
        """Actualiza la información de presencia del usuario"""
        try:
            user_id = str(user.id)
            now = datetime.now(timezone.utc)
            
            # Actualizar datos de presencia
            self.user_presence[user_id] = {
                'user_id': user_id,
                'username': user.username,
                'status': status,
                'location': location,
                'last_activity': now,
                'session_id': request.sid
            }
            
            # Emitir cambio de presencia a usuarios relevantes
            self._broadcast_presence_change(user, status, location, now)
            
            logger.info(f"Presencia actualizada para {user.username}: {status}")
            
        except Exception as e:
            logger.error(f"Error actualizando presencia: {str(e)}")
    
    def _broadcast_presence_change(self, user: User, status: str, location: str, timestamp: datetime):
        """Difunde cambio de presencia a usuarios relevantes"""
        try:
            presence_data = {
                'user': format_user_info(user),
                'status': status,
                'location': location,
                'timestamp': format_datetime(timestamp)
            }
            
            # Emitir a usuarios del mismo rol
            self.emit('presence_changed', presence_data, room=f'role_{user.role.value}')
            
            # Si es emprendedor, emitir a sus mentores
            if user.role == UserRole.ENTREPRENEUR:
                # Aquí implementarías la lógica para obtener mentores del emprendedor
                pass
            
            # Si es mentor, emitir a sus emprendedores
            if user.role == UserRole.ALLY:
                # Aquí implementarías la lógica para obtener emprendedores del mentor
                pass
            
        except Exception as e:
            logger.error(f"Error difundiendo cambio de presencia: {str(e)}")


class CollaborationNamespace(BaseNamespace):
    """
    Namespace para colaboración en tiempo real
    
    Maneja la colaboración simultánea en documentos y proyectos:
    - Edición colaborativa de documentos
    - Sincronización de cambios
    - Cursor y selección de usuarios
    """
    
    def __init__(self):
        super().__init__('/collaboration')
        self.active_documents: dict[str, dict[str, Any]] = {}
        self.document_cursors: dict[str, dict[str, Any]] = {}
    
    def on_join_document(self, data):
        """Une usuario a sesión de colaboración en documento"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            document_id = data.get('document_id')
            if not document_id:
                self._emit_error("Document ID required")
                return
            
            # Verificar acceso al documento
            document = Document.query.get(document_id)
            if not document or not self._can_access_document(user, document):
                self._emit_error("Access denied to document")
                return
            
            # Unirse a la sala del documento
            room = f'document_{document_id}'
            join_room(room)
            
            # Registrar documento activo
            if document_id not in self.active_documents:
                self.active_documents[document_id] = {
                    'users': {},
                    'content': document.content or '',
                    'version': 1
                }
            
            self.active_documents[document_id]['users'][str(user.id)] = {
                'user': format_user_info(user),
                'joined_at': format_datetime(datetime.now(timezone.utc))
            }
            
            # Emitir confirmación y estado actual
            emit('document_joined', {
                'document_id': document_id,
                'content': self.active_documents[document_id]['content'],
                'version': self.active_documents[document_id]['version'],
                'users': list(self.active_documents[document_id]['users'].values()),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            # Notificar a otros usuarios
            self.emit('user_joined_document', {
                'user': format_user_info(user),
                'document_id': document_id,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room, include_self=False)
            
            logger.info(f"Usuario {user.username} se unió a documento {document_id}")
            
        except Exception as e:
            logger.error(f"Error uniendo a documento: {str(e)}")
            self._emit_error("Failed to join document")
    
    def on_document_change(self, data):
        """Maneja cambios en el documento"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            document_id = data.get('document_id')
            changes = data.get('changes', [])
            version = data.get('version', 1)
            
            if not document_id or not changes:
                self._emit_error("Document ID and changes required")
                return
            
            # Verificar que el usuario esté en el documento
            if (document_id not in self.active_documents or 
                str(user.id) not in self.active_documents[document_id]['users']):
                self._emit_error("User not in document session")
                return
            
            # Aplicar cambios y actualizar versión
            current_version = self.active_documents[document_id]['version']
            if version != current_version:
                self._emit_error("Version conflict")
                return
            
            # Aquí implementarías la lógica de operational transformation
            # Por simplicidad, asumimos que los cambios son válidos
            self.active_documents[document_id]['version'] += 1
            
            # Emitir cambios a otros usuarios
            change_data = {
                'document_id': document_id,
                'changes': changes,
                'version': self.active_documents[document_id]['version'],
                'author': format_user_info(user),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }
            
            self.emit('document_changed', change_data, 
                     room=f'document_{document_id}', include_self=False)
            
        except Exception as e:
            logger.error(f"Error en cambio de documento: {str(e)}")
            self._emit_error("Failed to process document change")
    
    def _can_access_document(self, user: User, document: Document) -> bool:
        """Verifica si el usuario puede acceder al documento"""
        return (
            document.created_by_id == user.id or
            user.role == UserRole.ADMIN or
            document.is_public or
            user in document.collaborators
        )


class AdminNamespace(BaseNamespace):
    """
    Namespace para funcionalidades administrativas
    
    Proporciona herramientas en tiempo real para administradores:
    - Monitoreo del sistema
    - Gestión de usuarios
    - Alertas administrativas
    """
    
    def __init__(self):
        super().__init__('/admin')
        self.analytics_service = AnalyticsService()
    
    def _authorize_namespace_access(self, user: User) -> bool:
        """Solo administradores pueden acceder"""
        return user.role == UserRole.ADMIN
    
    def on_get_system_stats(self, data):
        """Obtiene estadísticas del sistema en tiempo real"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            # Obtener estadísticas
            stats = self.analytics_service.get_real_time_stats()
            
            emit('system_stats', {
                'stats': stats,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            self._emit_error("Failed to get system stats")
    
    def on_broadcast_announcement(self, data):
        """Difunde un anuncio a todos los usuarios"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            message = data.get('message')
            target_roles = data.get('target_roles', [])
            priority = data.get('priority', 'normal')
            
            if not message:
                self._emit_error("Message is required")
                return
            
            announcement_data = {
                'message': message,
                'priority': priority,
                'from': format_user_info(user),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }
            
            # Emitir a roles específicos o a todos
            if target_roles:
                for role in target_roles:
                    self.emit('admin_announcement', announcement_data, 
                             room=f'role_{role}')
            else:
                self.emit('admin_announcement', announcement_data)
            
            emit('announcement_sent', {
                'target_roles': target_roles or ['all'],
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            logger.info(f"Anuncio enviado por {user.username} a roles {target_roles}")
            
        except Exception as e:
            logger.error(f"Error enviando anuncio: {str(e)}")
            self._emit_error("Failed to send announcement")


class AnalyticsNamespace(BaseNamespace):
    """
    Namespace para métricas y analytics en tiempo real
    
    Proporciona datos y métricas actualizadas en tiempo real:
    - Métricas de uso
    - Estadísticas de proyectos
    - Datos de rendimiento
    """
    
    def __init__(self):
        super().__init__('/analytics')
        self.analytics_service = AnalyticsService()
    
    def _authorize_namespace_access(self, user: User) -> bool:
        """Usuarios con permisos de analytics pueden acceder"""
        return has_permission(user, 'view_analytics')
    
    def on_subscribe_to_metrics(self, data):
        """Suscribe a métricas específicas"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            metric_types = data.get('metrics', [])
            if not metric_types:
                self._emit_error("Metrics list required")
                return
            
            # Validar métricas solicitadas
            valid_metrics = [
                'user_activity', 'project_progress', 'meeting_stats',
                'message_volume', 'login_activity'
            ]
            
            invalid_metrics = [m for m in metric_types if m not in valid_metrics]
            if invalid_metrics:
                self._emit_error(f"Invalid metrics: {invalid_metrics}")
                return
            
            # Unirse a rooms de métricas
            for metric in metric_types:
                join_room(f'metric_{metric}')
            
            emit('subscribed_to_metrics', {
                'metrics': metric_types,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            logger.info(f"Usuario {user.username} suscrito a métricas {metric_types}")
            
        except Exception as e:
            logger.error(f"Error suscribiendo a métricas: {str(e)}")
            self._emit_error("Failed to subscribe to metrics")


class MentorshipNamespace(BaseNamespace):
    """
    Namespace para sesiones de mentoría interactivas
    
    Maneja la comunicación en tiempo real durante sesiones de mentoría:
    - Chat de sesión
    - Compartir pantalla
    - Notas colaborativas
    - Control de sesión
    """
    
    def __init__(self):
        super().__init__('/mentorship')
        self.mentorship_service = MentorshipService()
        self.active_sessions: dict[str, dict[str, Any]] = {}
    
    def _authorize_namespace_access(self, user: User) -> bool:
        """Solo emprendedores y mentores pueden acceder"""
        return user.role in [UserRole.ENTREPRENEUR, UserRole.ALLY]
    
    def on_join_session(self, data):
        """Une usuario a sesión de mentoría"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            session_id = data.get('session_id')
            if not session_id:
                self._emit_error("Session ID required")
                return
            
            # Verificar acceso a la sesión
            session = MentorshipSession.query.get(session_id)
            if not session or not self._can_access_session(user, session):
                self._emit_error("Access denied to session")
                return
            
            # Unirse a la sala de la sesión
            room = f'mentorship_{session_id}'
            join_room(room)
            
            # Registrar sesión activa
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = {
                    'participants': {},
                    'status': 'waiting',
                    'started_at': None
                }
            
            self.active_sessions[session_id]['participants'][str(user.id)] = {
                'user': format_user_info(user),
                'joined_at': format_datetime(datetime.now(timezone.utc)),
                'role': 'mentor' if user.id == session.mentor_id else 'entrepreneur'
            }
            
            # Emitir confirmación
            emit('session_joined', {
                'session_id': session_id,
                'participants': list(self.active_sessions[session_id]['participants'].values()),
                'status': self.active_sessions[session_id]['status'],
                'timestamp': format_datetime(datetime.now(timezone.utc))
            })
            
            # Notificar a otros participantes
            self.emit('participant_joined', {
                'user': format_user_info(user),
                'session_id': session_id,
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }, room=room, include_self=False)
            
            logger.info(f"Usuario {user.username} se unió a sesión de mentoría {session_id}")
            
        except Exception as e:
            logger.error(f"Error uniendo a sesión: {str(e)}")
            self._emit_error("Failed to join session")
    
    def on_start_session(self, data):
        """Inicia una sesión de mentoría"""
        try:
            user = self._get_current_user()
            if not user:
                self._emit_error("User not authenticated")
                return
            
            session_id = data.get('session_id')
            if not session_id:
                self._emit_error("Session ID required")
                return
            
            # Verificar que el usuario puede iniciar la sesión (mentor)
            session = MentorshipSession.query.get(session_id)
            if not session or session.mentor_id != user.id:
                self._emit_error("Only the mentor can start the session")
                return
            
            # Actualizar estado de la sesión
            if session_id in self.active_sessions:
                self.active_sessions[session_id]['status'] = 'active'
                self.active_sessions[session_id]['started_at'] = datetime.now(timezone.utc)
            
            # Emitir inicio de sesión
            session_data = {
                'session_id': session_id,
                'status': 'active',
                'started_at': format_datetime(datetime.now(timezone.utc)),
                'timestamp': format_datetime(datetime.now(timezone.utc))
            }
            
            self.emit('session_started', session_data, room=f'mentorship_{session_id}')
            
            logger.info(f"Sesión de mentoría {session_id} iniciada por {user.username}")
            
        except Exception as e:
            logger.error(f"Error iniciando sesión: {str(e)}")
            self._emit_error("Failed to start session")
    
    def _can_access_session(self, user: User, session: MentorshipSession) -> bool:
        """Verifica si el usuario puede acceder a la sesión"""
        return (
            session.entrepreneur_id == user.id or
            session.mentor_id == user.id or
            user.role == UserRole.ADMIN
        )


# Registro de todos los namespaces disponibles
AVAILABLE_NAMESPACES = {
    '/chat': ChatNamespace,
    '/notifications': NotificationNamespace,
    '/presence': PresenceNamespace,
    '/collaboration': CollaborationNamespace,
    '/admin': AdminNamespace,
    '/analytics': AnalyticsNamespace,
    '/mentorship': MentorshipNamespace
}


def register_all_namespaces(socketio):
    """
    Registra todos los namespaces disponibles
    
    Args:
        socketio: Instancia de SocketIO
    """
    try:
        for namespace_path, namespace_class in AVAILABLE_NAMESPACES.items():
            namespace_instance = namespace_class()
            socketio.on_namespace(namespace_instance)
            logger.info(f"Namespace {namespace_path} registrado exitosamente")
        
        logger.info(f"Todos los namespaces ({len(AVAILABLE_NAMESPACES)}) registrados correctamente")
        
    except Exception as e:
        logger.error(f"Error registrando namespaces: {str(e)}")
        raise


# Exportar clases y funciones principales
__all__ = [
    'BaseNamespace',
    'ChatNamespace',
    'NotificationNamespace', 
    'PresenceNamespace',
    'CollaborationNamespace',
    'AdminNamespace',
    'AnalyticsNamespace',
    'MentorshipNamespace',
    'AVAILABLE_NAMESPACES',
    'register_all_namespaces'
]