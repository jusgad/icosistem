import unittest
from flask import url_for
from datetime import datetime, timedelta
import io

from app import create_app, db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.relationship import Relationship
from app.models.message import Message
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.document import Document


class TestAllyViews(unittest.TestCase):
    def setUp(self):
        """Configuración previa a cada test."""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client(use_cookies=True)
        
        # Crear usuario aliado para pruebas
        self.user = User(
            email='aliado@test.com',
            username='aliado_test',
            password='password',
            role='ally'
        )
        
        # Crear perfil de aliado asociado
        self.ally = Ally(
            user=self.user,
            specialty="Finanzas y estrategia",
            years_experience=8,
            biography="Experto en finanzas con amplia experiencia",
            availability="Lunes a Viernes, 9am-5pm",
            max_entrepreneurs=5
        )
        
        # Crear emprendedor para pruebas de interacción
        self.entrepreneur_user = User(
            email='emprendedor@test.com',
            username='emprendedor_test',
            password='password',
            role='entrepreneur'
        )
        
        self.entrepreneur = Entrepreneur(
            user=self.entrepreneur_user,
            business_name="Negocio Test",
            industry="Tecnología",
            business_stage="Inicial",
            employee_count=5,
            annual_revenue=50000,
            foundation_date=datetime.now() - timedelta(days=365),
            description="Empresa de prueba para tests"
        )
        
        # Crear relación entre ellos
        self.relationship = Relationship(
            entrepreneur=self.entrepreneur,
            ally=self.ally,
            start_date=datetime.now() - timedelta(days=30),
            status="active"
        )
        
        # Crear una reunión para pruebas
        self.meeting = Meeting(
            title="Reunión de seguimiento",
            description="Revisión de avances mensuales",
            meeting_datetime=datetime.now() + timedelta(days=2),
            duration=60,  # 60 minutos
            meeting_link="https://meet.google.com/abc-defg-hij",
            status="scheduled",
            ally=self.ally,
            entrepreneur=self.entrepreneur
        )
        
        # Crear una tarea para pruebas
        self.task = Task(
            title="Completar plan de negocio",
            description="Finalizar secciones financieras del plan",
            due_date=datetime.now() + timedelta(days=7),
            status="pending",
            entrepreneur=self.entrepreneur,
            created_by=self.user
        )
        
        # Guardar todo en la BD
        db.session.add(self.user)
        db.session.add(self.ally)
        db.session.add(self.entrepreneur_user)
        db.session.add(self.entrepreneur)
        db.session.add(self.relationship)
        db.session.add(self.meeting)
        db.session.add(self.task)
        db.session.commit()
        
        # Login como aliado para la mayoría de las pruebas
        with self.client:
            response = self.client.post('/auth/login', data={
                'email': 'aliado@test.com',
                'password': 'password'
            }, follow_redirects=True)

    def tearDown(self):
        """Limpieza después de cada test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_dashboard_access(self):
        """Prueba el acceso al dashboard del aliado."""
        response = self.client.get('/ally/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Panel de Control de Aliado', response.data)
        # Verificar presencia de indicadores clave
        self.assertIn(b'Emprendedores asignados', response.data)
        self.assertIn(b'Pr\xc3\xb3ximas reuniones', response.data)

    def test_profile_access(self):
        """Prueba el acceso y visualización del perfil del aliado."""
        response = self.client.get('/ally/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Finanzas y estrategia', response.data)
        self.assertIn(b'Experto en finanzas', response.data)

    def test_profile_update(self):
        """Prueba la actualización del perfil del aliado."""
        response = self.client.post('/ally/profile', data={
            'specialty': 'Marketing y ventas',
            'years_experience': 10,
            'biography': 'Perfil actualizado para pruebas',
            'availability': 'Lunes a Jueves, 10am-6pm',
            'max_entrepreneurs': 7
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Verificar que los cambios se guardaron en la BD
        updated_ally = Ally.query.filter_by(user_id=self.user.id).first()
        self.assertEqual(updated_ally.specialty, 'Marketing y ventas')
        self.assertEqual(updated_ally.years_experience, 10)
        self.assertEqual(updated_ally.max_entrepreneurs, 7)

    def test_entrepreneurs_list(self):
        """Prueba la visualización de la lista de emprendedores asignados."""
        response = self.client.get('/ally/entrepreneurs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Negocio Test', response.data)
        self.assertIn(b'Tecnolog\xc3\xada', response.data)

    def test_entrepreneur_detail(self):
        """Prueba la visualización detallada de un emprendedor asignado."""
        response = self.client.get(f'/ally/entrepreneurs/{self.entrepreneur.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Negocio Test', response.data)
        self.assertIn(b'Empresa de prueba para tests', response.data)
        # Verificar secciones de detalle
        self.assertIn(b'Informaci\xc3\xb3n del negocio', response.data)
        self.assertIn(b'Tareas asignadas', response.data)
        self.assertIn(b'Pr\xc3\xb3ximas reuniones', response.data)

    def test_register_hours(self):
        """Prueba el registro de horas dedicadas a un emprendedor."""
        data = {
            'entrepreneur_id': self.entrepreneur.id,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'hours': 2.5,
            'activity_type': 'mentoring',
            'description': 'Sesión de mentoría sobre finanzas'
        }
        
        response = self.client.post('/ally/hours/register', 
                                   data=data,
                                   follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que las horas se registraron correctamente
        # (Depende de cómo esté implementado el modelo de horas)
        response = self.client.get('/ally/hours')
        self.assertIn(b'2.5', response.data)
        self.assertIn(b'Sesi\xc3\xb3n de mentor\xc3\xada sobre finanzas', response.data)

    def test_calendar_access(self):
        """Prueba el acceso al calendario."""
        response = self.client.get('/ally/calendar')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reuni\xc3\xb3n de seguimiento', response.data)

    def test_create_meeting(self):
        """Prueba la creación de una reunión con un emprendedor."""
        tomorrow = datetime.now() + timedelta(days=1)
        data = {
            'entrepreneur_id': self.entrepreneur.id,
            'title': 'Nueva reunión de prueba',
            'description': 'Descripción de la reunión de prueba',
            'meeting_datetime': tomorrow.strftime('%Y-%m-%d %H:%M'),
            'duration': 45
        }
        
        response = self.client.post('/ally/meetings/create', 
                                   data=data,
                                   follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que la reunión se creó en la BD
        meeting = Meeting.query.filter_by(title='Nueva reunión de prueba').first()
        self.assertIsNotNone(meeting)
        self.assertEqual(meeting.duration, 45)
        self.assertEqual(meeting.entrepreneur_id, self.entrepreneur.id)

    def test_messages_access(self):
        """Prueba el acceso a la mensajería."""
        response = self.client.get('/ally/messages')
        self.assertEqual(response.status_code, 200)

    def test_send_message(self):
        """Prueba el envío de mensajes a un emprendedor."""
        data = {
            'recipient_id': self.entrepreneur_user.id,
            'content': 'Mensaje de prueba desde el aliado'
        }
        
        response = self.client.post('/ally/messages/send', 
                                  data=data,
                                  follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el mensaje se guardó en la BD
        message = Message.query.filter_by(
            sender_id=self.user.id, 
            recipient_id=self.entrepreneur_user.id
        ).first()
        
        self.assertIsNotNone(message)
        self.assertEqual(message.content, 'Mensaje de prueba desde el aliado')

    def test_task_creation(self):
        """Prueba la creación de tareas para un emprendedor."""
        data = {
            'entrepreneur_id': self.entrepreneur.id,
            'title': 'Nueva tarea de prueba',
            'description': 'Descripción de la tarea creada por test',
            'due_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'priority': 'high'
        }
        
        response = self.client.post('/ally/tasks/create', 
                                   data=data,
                                   follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que la tarea se creó en la BD
        task = Task.query.filter_by(title='Nueva tarea de prueba').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.priority, 'high')
        self.assertEqual(task.entrepreneur_id, self.entrepreneur.id)
        self.assertEqual(task.created_by_id, self.user.id)

    def test_desktop_access(self):
        """Prueba el acceso al escritorio de acompañamiento."""
        response = self.client.get('/ally/desktop')
        self.assertEqual(response.status_code, 200)

    def test_document_review(self):
        """Prueba la revisión de documentos de un emprendedor."""
        # Primero crear un documento para el emprendedor
        document = Document(
            title="Plan de negocios para revisión",
            category="business",
            description="Documento para prueba de revisión",
            file_path="test_files/test_doc.pdf",
            upload_date=datetime.now(),
            entrepreneur=self.entrepreneur,
            uploaded_by=self.entrepreneur_user
        )
        db.session.add(document)
        db.session.commit()
        
        # Ahora probar la funcionalidad de revisión
        data = {
            'document_id': document.id,
            'comments': 'Comentarios de revisión de prueba',
            'status': 'reviewed'
        }
        
        response = self.client.post(f'/ally/documents/{document.id}/review', 
                                   data=data,
                                   follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que el documento se actualizó correctamente
        updated_doc = Document.query.get(document.id)
        self.assertEqual(updated_doc.status, 'reviewed')
        self.assertIn('Comentarios de revisión de prueba', updated_doc.review_comments)

    def test_unauthorized_access(self):
        """Prueba que un emprendedor no puede acceder a las rutas de aliado."""
        # Cerrar sesión actual
        self.client.get('/auth/logout')
        
        # Iniciar sesión como emprendedor
        self.client.post('/auth/login', data={
            'email': 'emprendedor@test.com',
            'password': 'password'
        })
        
        # Intentar acceder a una ruta de aliado
        response = self.client.get('/ally/dashboard')
        self.assertNotEqual(response.status_code, 200)  # Debería redirigir o mostrar error


if __name__ == '__main__':
    unittest.main()