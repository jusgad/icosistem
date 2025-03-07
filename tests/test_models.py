# tests/test_models.py
"""Pruebas unitarias para los modelos de datos de la aplicación."""

import pytest
from datetime import datetime, timedelta

from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.relationship import Relationship
from app.models.message import Message
from app.models.meeting import Meeting
from app.models.document import Document
from app.models.task import Task


class TestUserModel:
    """Pruebas para el modelo User."""
    
    def test_create_user(self, session):
        """Probar creación básica de usuario."""
        user = User(
            username="testuser",
            email="test@example.com",
            role="entrepreneur"
        )
        user.set_password("password123")
        
        session.add(user)
        session.commit()
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "entrepreneur"
        assert user.check_password("password123") is True
        assert user.check_password("wrongpassword") is False
    
    def test_user_relationships(self, session, entrepreneur_user, ally_user):
        """Probar relaciones del modelo de usuario."""
        # Verificar que el usuario emprendedor tenga un perfil de emprendedor
        entrepreneur_profile = entrepreneur_user.entrepreneur_profile
        assert entrepreneur_profile is not None
        assert entrepreneur_profile.user_id == entrepreneur_user.id
        
        # Verificar que el usuario aliado tenga un perfil de aliado
        ally_profile = ally_user.ally_profile
        assert ally_profile is not None
        assert ally_profile.user_id == ally_user.id


class TestEntrepreneurModel:
    """Pruebas para el modelo Entrepreneur."""
    
    def test_create_entrepreneur(self, session, entrepreneur_user):
        """Probar creación de perfil de emprendedor."""
        entrepreneur = entrepreneur_user.entrepreneur_profile
        
        assert entrepreneur.business_name == "Test Business"
        assert entrepreneur.business_sector == "Technology"
        assert entrepreneur.business_stage == "Early"
        assert entrepreneur.employee_count == 5
    
    def test_entrepreneur_relationships(self, session, entrepreneur_user, ally_user):
        """Probar relaciones del emprendedor con aliados."""
        entrepreneur = entrepreneur_user.entrepreneur_profile
        ally = ally_user.ally_profile
        
        # Crear una relación entre emprendedor y aliado
        relationship = Relationship(
            entrepreneur_id=entrepreneur.id,
            ally_id=ally.id,
            start_date=datetime.now(),
            status="active"
        )
        session.add(relationship)
        session.commit()
        
        # Verificar que la relación exista
        assert len(entrepreneur.relationships) == 1
        assert entrepreneur.relationships[0].ally_id == ally.id
        assert ally.relationships[0].entrepreneur_id == entrepreneur.id


class TestAllyModel:
    """Pruebas para el modelo Ally."""
    
    def test_create_ally(self, session, ally_user):
        """Probar creación de perfil de aliado."""
        ally = ally_user.ally_profile
        
        assert ally.specialty == "Business Development"
        assert ally.experience_years == 5
        assert ally.organization == "Test Organization"
    
    def test_ally_hours_tracking(self, session, entrepreneur_user, ally_user):
        """Probar el registro de horas de un aliado."""
        from app.models.ally import AllyHours
        
        entrepreneur = entrepreneur_user.entrepreneur_profile
        ally = ally_user.ally_profile
        
        # Crear una relación para poder registrar horas
        relationship = Relationship(
            entrepreneur_id=entrepreneur.id,
            ally_id=ally.id,
            start_date=datetime.now(),
            status="active"
        )
        session.add(relationship)
        session.commit()
        
        # Registrar horas
        hours_entry = AllyHours(
            ally_id=ally.id,
            entrepreneur_id=entrepreneur.id,
            date=datetime.now().date(),
            hours=2.5,
            description="Asesoría en plan de negocios"
        )
        session.add(hours_entry)
        session.commit()
        
        # Verificar el registro
        assert len(ally.hours_entries) == 1
        assert ally.hours_entries[0].hours == 2.5
        assert ally.hours_entries[0].entrepreneur_id == entrepreneur.id


class TestClientModel:
    """Pruebas para el modelo Client."""
    
    def test_create_client(self, session, client_user):
        """Probar creación de perfil de cliente."""
        client = client_user.client_profile
        
        assert client.organization == "Test Client Org"
        assert client.industry == "Technology"
        assert client.contact_person == "John Doe"


class TestMessageModel:
    """Pruebas para el modelo Message."""
    
    def test_send_message(self, session, entrepreneur_user, ally_user):
        """Probar envío de mensajes entre usuarios."""
        # Crear un mensaje
        message = Message(
            sender_id=entrepreneur_user.id,
            recipient_id=ally_user.id,
            content="Hola, ¿cómo va la asesoría?",
            timestamp=datetime.now()
        )
        session.add(message)
        session.commit()
        
        # Verificar el mensaje
        assert message.id is not None
        assert message.sender_id == entrepreneur_user.id
        assert message.recipient_id == ally_user.id
        assert message.content == "Hola, ¿cómo va la asesoría?"
        assert message.read is False  # Por defecto no leído
        
        # Marcar como leído
        message.read = True
        session.commit()
        
        # Verificar que se marcó como leído
        assert message.read is True


class TestMeetingModel:
    """Pruebas para el modelo Meeting."""
    
    def test_create_meeting(self, session, entrepreneur_user, ally_user):
        """Probar creación de reuniones."""
        entrepreneur = entrepreneur_user.entrepreneur_profile
        ally = ally_user.ally_profile
        
        # Crear una reunión
        start_time = datetime.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting(
            title="Revisión de plan de negocios",
            start_time=start_time,
            end_time=end_time,
            location="Google Meet",
            meeting_link="https://meet.google.com/abc-defg-hij",
            description="Revisaremos el avance del plan de negocios",
            status="scheduled"
        )
        
        # Agregar participantes
        meeting.participants.append(entrepreneur_user)
        meeting.participants.append(ally_user)
        
        session.add(meeting)
        session.commit()
        
        # Verificar la reunión
        assert meeting.id is not None
        assert meeting.title == "Revisión de plan de negocios"
        assert len(meeting.participants) == 2
        
        # Verificar que los usuarios tengan la reunión
        assert meeting in entrepreneur_user.meetings
        assert meeting in ally_user.meetings


class TestDocumentModel:
    """Pruebas para el modelo Document."""
    
    def test_upload_document(self, session, entrepreneur_user):
        """Probar carga de documentos."""
        # Crear un documento
        document = Document(
            title="Plan de Negocios",
            filename="plan_negocios.pdf",
            file_path="/uploads/documents/plan_negocios.pdf",
            file_type="application/pdf",
            file_size=1024 * 1024,  # 1MB
            upload_date=datetime.now(),
            uploader_id=entrepreneur_user.id
        )
        session.add(document)
        session.commit()
        
        # Verificar el documento
        assert document.id is not None
        assert document.title == "Plan de Negocios"
        assert document.filename == "plan_negocios.pdf"
        assert document.uploader_id == entrepreneur_user.id
        assert document.uploader == entrepreneur_user


class TestTaskModel:
    """Pruebas para el modelo Task."""
    
    def test_create_task(self, session, entrepreneur_user, ally_user):
        """Probar creación y asignación de tareas."""
        # Crear una tarea
        due_date = datetime.now() + timedelta(days=7)
        
        task = Task(
            title="Completar análisis FODA",
            description="Realizar un análisis FODA para el plan de negocios",
            status="pending",
            priority="high",
            due_date=due_date,
            creator_id=ally_user.id,
            assignee_id=entrepreneur_user.id
        )
        session.add(task)
        session.commit()
        
        # Verificar la tarea
        assert task.id is not None
        assert task.title == "Completar análisis FODA"
        assert task.creator_id == ally_user.id
        assert task.assignee_id == entrepreneur_user.id
        assert task.status == "pending"
        
        # Marcar como completada
        task.status = "completed"
        task.completed_date = datetime.now()
        session.commit()
        
        # Verificar que se marcó como completada
        assert task.status == "completed"
        assert task.completed_date is not None