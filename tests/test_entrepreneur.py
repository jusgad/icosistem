import unittest
from flask import url_for
from datetime import datetime, timedelta
import io

from app import create_app, db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.models.task import Task
from app.models.document import Document
from app.models.message import Message

class TestEntrepreneurViews(unittest.TestCase):
    def setUp(self):
        """Configuración previa a cada test."""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client(use_cookies=True)
        
        # Crear usuario emprendedor para pruebas
        self.user = User(
            email='emprendedor@test.com',
            username='emprendedor_test',
            password='password',
            role='entrepreneur'
        )
        
        # Crear perfil de emprendedor asociado
        self.entrepreneur = Entrepreneur(
            user=self.user,
            business_name="Negocio Test",
            industry="Tecnología",
            business_stage="Inicial",
            employee_count=5,
            annual_revenue=50000,
            foundation_date=datetime.now() - timedelta(days=365),
            description="Empresa de prueba para tests"
        )
        
        # Crear aliado para pruebas de interacción
        self.ally_user = User(
            email='aliado@test.com',
            username='aliado_test',
            password='password',
            role='ally'
        )
        
        self.ally = Ally(
            user=self.ally_user,
            specialty="Desarrollo de negocios",
            years_experience=5
        )
        
        # Crear relación entre ellos
        self.relationship = Relationship(
            entrepreneur=self.entrepreneur,
            ally=self.ally,
            start_date=datetime.now() - timedelta(days=30),
            status="active"
        )
        
        # Agregar tareas para pruebas
        self.task = Task(
            title="Tarea de prueba",
            description="Descripción de la tarea de prueba",
            due_date=datetime.now() + timedelta(days=7),
            status="pending",
            entrepreneur=self.entrepreneur,
            created_by=self.ally_user
        )
        
        # Guardar todo en la BD
        db.session.add(self.user)
        db.session.add(self.entrepreneur)
        db.session.add(self.ally_user)
        db.session.add(self.ally)
        db.session.add(self.relationship)
        db.session.add(self.task)
        db.session.commit()
        
        # Login como emprendedor para la mayoría de las pruebas
        with self.client:
            response = self.client.post('/auth/login', data={
                'email': 'emprendedor@test.com',
                'password': 'password'
            }, follow_redirects=True)

    def tearDown(self):
        """Limpieza después de cada test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_dashboard_access(self):
        """Prueba el acceso al dashboard del emprendedor."""
        response = self.client.get('/entrepreneur/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Bienvenido al panel de control', response.data)

    def test_profile_access(self):
        """Prueba el acceso y visualización del perfil del emprendedor."""
        response = self.client.get('/entrepreneur/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Negocio Test', response.data)
        self.assertIn(b'Tecnolog\xc3\xada', response.data)

    def test_profile_update(self):
        """Prueba la actualización del perfil del emprendedor."""
        response = self.client.post('/entrepreneur/profile', data={
            'business_name': 'Negocio Actualizado',
            'industry': 'Tecnología',
            'business_stage': 'Crecimiento',
            'employee_count': 10,
            'annual_revenue': 100000,
            'description': 'Descripción actualizada'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Verificar que los cambios se guardaron en la BD
        updated_entrepreneur = Entrepreneur.query.filter_by(user_id=self.user.id).first()
        self.assertEqual(updated_entrepreneur.business_name, 'Negocio Actualizado')
        self.assertEqual(updated_entrepreneur.business_stage, 'Crecimiento')

    def test_tasks_list(self):
        """Prueba la visualización de la lista de tareas."""
        response = self.client.get('/entrepreneur/tasks')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Tarea de prueba', response.data)

    def test_task_completion(self):
        """Prueba el marcado de una tarea como completada."""
        response = self.client.post(f'/entrepreneur/tasks/{self.task.id}/complete', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verificar que la tarea se marcó como completada
        updated_task = Task.query.get(self.task.id)
        self.assertEqual(updated_task.status, 'completed')

    def test_documents_list(self):
        """Prueba el acceso a la lista de documentos."""
        response = self.client.get('/entrepreneur/documents')
        self.assertEqual(response.status_code, 200)

    def test_document_upload(self):
        """Prueba la subida de un documento."""
        data = {
            'title': 'Documento de prueba',
            'category': 'legal',
            'description': 'Descripción del documento de prueba',
            'file': (io.BytesIO(b"contenido del archivo"), 'test_file.pdf')
        }
        
        response = self.client.post('/entrepreneur/documents/upload', 
                                   data=data,
                                   content_type='multipart/form-data', 
                                   follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el documento se agregó a la BD
        doc = Document.query.filter_by(title='Documento de prueba').first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.category, 'legal')

    def test_calendar_access(self):
        """Prueba el acceso al calendario."""
        response = self.client.get('/entrepreneur/calendar')
        self.assertEqual(response.status_code, 200)

    def test_messages_access(self):
        """Prueba el acceso a la mensajería."""
        response = self.client.get('/entrepreneur/messages')
        self.assertEqual(response.status_code, 200)

    def test_send_message(self):
        """Prueba el envío de mensajes."""
        data = {
            'recipient_id': self.ally_user.id,
            'content': 'Mensaje de prueba desde test'
        }
        
        response = self.client.post('/entrepreneur/messages/send', 
                                  data=data,
                                  follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el mensaje se guardó en la BD
        message = Message.query.filter_by(
            sender_id=self.user.id, 
            recipient_id=self.ally_user.id
        ).first()
        
        self.assertIsNotNone(message)
        self.assertEqual(message.content, 'Mensaje de prueba desde test')

    def test_desktop_access(self):
        """Prueba el acceso al escritorio de trabajo."""
        response = self.client.get('/entrepreneur/desktop')
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_access(self):
        """Prueba que un aliado no puede acceder a las rutas de emprendedor."""
        # Cerrar sesión actual
        self.client.get('/auth/logout')
        
        # Iniciar sesión como aliado
        self.client.post('/auth/login', data={
            'email': 'aliado@test.com',
            'password': 'password'
        })
        
        # Intentar acceder a una ruta de emprendedor
        response = self.client.get('/entrepreneur/dashboard')
        self.assertNotEqual(response.status_code, 200)  # Debería redirigir o mostrar error

    def test_ally_relationship(self):
        """Prueba la visualización de la relación con el aliado."""
        response = self.client.get('/entrepreneur/allies')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'aliado_test', response.data)
        self.assertIn(b'Desarrollo de negocios', response.data)


if __name__ == '__main__':
    unittest.main()