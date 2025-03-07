# app/models/__init__.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from flask import current_app
import logging

# Importación de modelos
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.relationship import Relationship
from app.models.message import Message
from app.models.meeting import Meeting
from app.models.document import Document
from app.models.task import Task
from app.models.config import Config

# Lista de modelos exportados
__all__ = [
    'User',
    'Entrepreneur',
    'Ally',
    'Client', 
    'Relationship',
    'Message',
    'Meeting',
    'Document',
    'Task',
    'Config',
    'init_app'
]

logger = logging.getLogger(__name__)

def init_app(app, db):
    """
    Inicializa los modelos de la aplicación y configura eventos y comportamientos.
    
    Args:
        app: La instancia de la aplicación Flask
        db: La instancia de SQLAlchemy
    """
    # Registrar eventos para los modelos
    
    # Evento: Después de crear un usuario nuevo
    @event.listens_for(User, 'after_insert')
    def after_user_insert(mapper, connection, target):
        logger.info(f"Nuevo usuario creado: {target.username} (ID: {target.id})")
        
        # Crear notificación para administradores
        if not target.is_admin:
            stmt = """
            INSERT INTO notification (user_id, message, created_at, is_read)
            SELECT u.id, :message, CURRENT_TIMESTAMP, 0
            FROM user u
            WHERE u.is_admin = 1
            """
            connection.execute(stmt, 
                               message=f"Nuevo usuario registrado: {target.username}")

    # Evento: Después de asignar un aliado a un emprendedor
    @event.listens_for(Relationship, 'after_insert')
    def after_relationship_insert(mapper, connection, target):
        logger.info(f"Nueva relación: Emprendedor {target.entrepreneur_id} - Aliado {target.ally_id}")
        
        # Crear mensajes automáticos de bienvenida
        stmt = """
        INSERT INTO message (sender_id, recipient_id, content, sent_at, is_read)
        VALUES (:ally_id, :entrepreneur_id, :welcome_message, CURRENT_TIMESTAMP, 0)
        """
        connection.execute(stmt,
                          ally_id=target.ally_id,
                          entrepreneur_id=target.entrepreneur_id,
                          welcome_message="¡Hola! Soy tu nuevo aliado asignado. Estoy aquí para apoyarte en tu emprendimiento.")

    # Evento: Antes de eliminar un documento
    @event.listens_for(Document, 'before_delete')
    def before_document_delete(mapper, connection, target):
        logger.warning(f"Eliminando documento: {target.filename} (ID: {target.id})")
        
        # Registrar la eliminación en el historial
        stmt = """
        INSERT INTO document_history (document_id, user_id, action, timestamp)
        VALUES (:document_id, :user_id, 'DELETE', CURRENT_TIMESTAMP)
        """
        connection.execute(stmt,
                          document_id=target.id,
                          user_id=current_app.config.get('CURRENT_USER_ID', None))

    # Evento: Después de actualizar una tarea
    @event.listens_for(Task, 'after_update')
    def after_task_update(mapper, connection, target):
        if target.status == 'completed':
            logger.info(f"Tarea completada: {target.title} (ID: {target.id})")
            
            # Notificar al aliado cuando el emprendedor completa una tarea
            if hasattr(target, 'entrepreneur_id'):
                stmt = """
                SELECT ally_id FROM relationship WHERE entrepreneur_id = :entrepreneur_id
                """
                result = connection.execute(stmt, entrepreneur_id=target.entrepreneur_id).fetchone()
                
                if result and result[0]:
                    ally_id = result[0]
                    stmt = """
                    INSERT INTO notification (user_id, message, created_at, is_read, link)
                    VALUES (:ally_id, :message, CURRENT_TIMESTAMP, 0, :link)
                    """
                    connection.execute(stmt,
                                      ally_id=ally_id,
                                      message=f"Tarea completada por emprendedor: {target.title}",
                                      link=f"/ally/task/{target.id}")

    # Configurar hooks de limpieza para mensajes antiguos (ejemplo de mantenimiento)
    if app.config.get('AUTO_CLEANUP_MESSAGES', False):
        # Programar limpieza periódica de mensajes antiguos
        from app.utils.scheduler import scheduler
        
        @scheduler.task('cron', id='clean_old_messages', hour=3, minute=0)
        def clean_old_messages():
            """Limpia mensajes más antiguos que el período configurado"""
            retention_days = app.config.get('MESSAGE_RETENTION_DAYS', 365)
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            with app.app_context():
                deleted = Message.query.filter(Message.sent_at < cutoff_date).delete()
                db.session.commit()
                logger.info(f"Limpieza programada: {deleted} mensajes antiguos eliminados")

    # Registrar los modelos de eventos en la aplicación
    app.models_initialized = True
    logger.info("Modelos inicializados correctamente con eventos y comportamientos")