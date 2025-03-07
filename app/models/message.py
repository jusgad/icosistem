from datetime import datetime
from app.extensions import db
from sqlalchemy.ext.declarative import declared_attr

class Message(db.Model):
    """Modelo para los mensajes intercambiados entre usuarios."""
    
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    
    # Relaciones con el remitente y destinatario
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Opcionalmente, si los mensajes pueden estar asociados a una tarea o documento
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    
    # Relaciones con el remitente y destinatario (backref)
    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy='dynamic'))
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('received_messages', lazy='dynamic'))
    
    # Opcionalmente, relaciones con tareas y documentos
    task = db.relationship('Task', backref=db.backref('messages', lazy='dynamic'))
    document = db.relationship('Document', backref=db.backref('messages', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Message {self.id}: {self.sender_id} -> {self.recipient_id}>'
    
    def to_dict(self):
        """Convertir el mensaje a un diccionario para API/JSON."""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'read': self.read,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'task_id': self.task_id,
            'document_id': self.document_id
        }
    
    @classmethod
    def get_conversation(cls, user1_id, user2_id, limit=50):
        """Obtener la conversación entre dos usuarios."""
        return cls.query.filter(
            (
                (cls.sender_id == user1_id) & 
                (cls.recipient_id == user2_id)
            ) | (
                (cls.sender_id == user2_id) & 
                (cls.recipient_id == user1_id)
            )
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def mark_as_read(cls, recipient_id, sender_id):
        """Marcar como leídos todos los mensajes de un remitente para un destinatario."""
        cls.query.filter_by(
            recipient_id=recipient_id, 
            sender_id=sender_id, 
            read=False
        ).update({'read': True})
        db.session.commit()
    
    @classmethod
    def get_unread_count(cls, user_id):
        """Obtener el número de mensajes no leídos para un usuario."""
        return cls.query.filter_by(
            recipient_id=user_id, 
            read=False
        ).count()