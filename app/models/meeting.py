from datetime import datetime
from app.extensions import db
from sqlalchemy import event

class Meeting(db.Model):
    """Modelo para reuniones entre emprendedores y aliados."""
    
    __tablename__ = 'meetings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    meeting_link = db.Column(db.String(255), nullable=True)  # Para reuniones virtuales
    
    # Tipo de reunión: 'presencial', 'virtual', 'híbrida'
    meeting_type = db.Column(db.String(20), default='virtual')
    
    # Estado de la reunión: 'programada', 'confirmada', 'cancelada', 'completada'
    status = db.Column(db.String(20), default='programada')
    
    # Notas posteriores a la reunión
    notes = db.Column(db.Text, nullable=True)
    
    # ID del calendario externo (Google Calendar, etc.)
    external_calendar_id = db.Column(db.String(255), nullable=True)
    
    # Relaciones
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    entrepreneur_id = db.Column(db.Integer, db.ForeignKey('entrepreneurs.id'), nullable=True)
    ally_id = db.Column(db.Integer, db.ForeignKey('allies.id'), nullable=True)
    
    # Definición de relaciones
    creator = db.relationship('User', backref=db.backref('created_meetings', lazy='dynamic'))
    entrepreneur = db.relationship('Entrepreneur', backref=db.backref('meetings', lazy='dynamic'))
    ally = db.relationship('Ally', backref=db.backref('meetings', lazy='dynamic'))
    
    # Relación con documentos asociados a la reunión
    documents = db.relationship('Document', secondary='meeting_documents', 
                              backref=db.backref('meetings', lazy='dynamic'))
    
    # Relación con tareas que surgen de la reunión
    tasks = db.relationship('Task', backref=db.backref('meeting', lazy=True))
    
    def __repr__(self):
        return f'<Meeting {self.id}: {self.title}>'
    
    def to_dict(self):
        """Convertir la reunión a un diccionario para API/JSON."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'location': self.location,
            'meeting_link': self.meeting_link,
            'meeting_type': self.meeting_type,
            'status': self.status,
            'creator_id': self.creator_id,
            'entrepreneur_id': self.entrepreneur_id,
            'ally_id': self.ally_id,
            'external_calendar_id': self.external_calendar_id
        }
    
    def duration_minutes(self):
        """Calcular la duración de la reunión en minutos."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 60
        return 0
    
    def is_upcoming(self):
        """Verificar si la reunión está próxima a ocurrir."""
        return self.start_time > datetime.utcnow() and self.status != 'cancelada'
    
    def cancel(self):
        """Cancelar la reunión."""
        self.status = 'cancelada'
        db.session.commit()
    
    def complete(self, notes=None):
        """Marcar la reunión como completada."""
        self.status = 'completada'
        if notes:
            self.notes = notes
        db.session.commit()
    
    @classmethod
    def get_upcoming_meetings(cls, user_id, days=7):
        """Obtener las próximas reuniones para un usuario en los próximos días."""
        from app.models.user import User
        from app.models.entrepreneur import Entrepreneur
        from app.models.ally import Ally
        
        # Fecha límite
        from datetime import timedelta
        limit_date = datetime.utcnow() + timedelta(days=days)
        
        # Obtener el tipo de usuario
        user = User.query.get(user_id)
        if not user:
            return []
        
        # Verificar si es emprendedor
        entrepreneur = Entrepreneur.query.filter_by(user_id=user_id).first()
        if entrepreneur:
            return cls.query.filter(
                cls.entrepreneur_id == entrepreneur.id,
                cls.start_time > datetime.utcnow(),
                cls.start_time < limit_date,
                cls.status != 'cancelada'
            ).order_by(cls.start_time).all()
        
        # Verificar si es aliado
        ally = Ally.query.filter_by(user_id=user_id).first()
        if ally:
            return cls.query.filter(
                cls.ally_id == ally.id,
                cls.start_time > datetime.utcnow(),
                cls.start_time < limit_date,
                cls.status != 'cancelada'
            ).order_by(cls.start_time).all()
        
        # Para otros tipos de usuario (admin, cliente)
        return cls.query.filter(
            cls.creator_id == user_id,
            cls.start_time > datetime.utcnow(),
            cls.start_time < limit_date,
            cls.status != 'cancelada'
        ).order_by(cls.start_time).all()


# Tabla de asociación para la relación muchos a muchos entre reuniones y documentos
meeting_documents = db.Table('meeting_documents',
    db.Column('meeting_id', db.Integer, db.ForeignKey('meetings.id'), primary_key=True),
    db.Column('document_id', db.Integer, db.ForeignKey('documents.id'), primary_key=True)
)


# Eventos SQLAlchemy para integración con servicios externos
@event.listens_for(Meeting, 'after_insert')
def create_calendar_event(mapper, connection, target):
    """Crear evento en calendario externo después de insertar una reunión."""
    # Este código se ejecutaría en un hilo separado para no bloquear la respuesta
    from app.services.google_calendar import create_calendar_event
    
    # Solo si no tiene ya un ID externo
    if not target.external_calendar_id:
        try:
            # Lógica para crear el evento en Google Calendar
            event_id = create_calendar_event(target)
            if event_id:
                # Actualizar el ID externo en la base de datos
                target.external_calendar_id = event_id
                db.session.commit()
        except Exception as e:
            # Registrar el error pero no fallar la operación principal
            print(f"Error al crear evento en calendario: {str(e)}")


@event.listens_for(Meeting, 'after_update')
def update_calendar_event(mapper, connection, target):
    """Actualizar evento en calendario externo después de modificar una reunión."""
    from app.services.google_calendar import update_calendar_event
    
    # Solo si tiene un ID externo
    if target.external_calendar_id:
        try:
            # Lógica para actualizar el evento en Google Calendar
            update_calendar_event(target)
        except Exception as e:
            # Registrar el error pero no fallar la operación principal
            print(f"Error al actualizar evento en calendario: {str(e)}")