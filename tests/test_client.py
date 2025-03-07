import unittest
from flask import url_for
from datetime import datetime, timedelta

from app import create_app, db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.relationship import Relationship


class TestClientViews(unittest.TestCase):
    def setUp(self):
        """Configuración previa a cada test."""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client_app = self.app.test_client(use_cookies=True)
        
        # Crear usuario cliente para pruebas
        self.user = User(
            email='cliente@test.com',
            username='cliente_test',
            password='password',
            role='client'
        )
        
        # Crear perfil de cliente asociado
        self.client = Client(
            user=self.user,
            company_name="Empresa Patrocinadora S.A.",
            industry="Banca y Finanzas",
            contact_name="Juan Pérez",
            contact_position="Director de Innovación",
            subscription_level="premium",
            subscription_start=datetime.now() - timedelta(days=30),
            subscription_end=datetime.now() + timedelta(days=335)
        )
        
        # Crear algunos emprendedores para mostrar en el directorio
        self.entrepreneur_user1 = User(
            email='emprendedor1@test.com',
            username='emprendedor_test1',
            password='password',
            role='entrepreneur'
        )
        
        self.entrepreneur1 = Entrepreneur(
            user=self.entrepreneur_user1,
            business_name="Negocio Test 1",
            industry="Tecnología",
            business_stage="Inicial",
            employee_count=5,
            annual_revenue=50000,
            foundation_date=datetime.now() - timedelta(days=365),
            description="Empresa de tecnología para tests",
            is_featured=True,  # Destacado en el directorio
            showcase_in_directory=True  # Visible en el directorio
        )
        
        self.entrepreneur_user2 = User(
            email='emprendedor2@test.com',
            username='emprendedor_test2',
            password='password',
            role='entrepreneur'
        )
        
        self.entrepreneur2 = Entrepreneur(
            user=self.entrepreneur_user2,
            business_name="Negocio Test 2",
            industry="Agricultura",
            business_stage="Crecimiento",
            employee_count=12,
            annual_revenue=120000,
            foundation_date=datetime.now() - timedelta(days=730),
            description="Empresa agrícola para tests",
            is_featured=False,  # No destacado
            showcase_in_directory=True  # Visible en el directorio
        )
        
        # Crear un aliado para las relaciones
        self.ally_user = User(
            email='aliado@test.com',
            username='aliado_test',
            password='password',
            role='ally'
        )
        
        self.ally = Ally(
            user=self.ally_user,
            specialty="Finanzas y estrategia",
            years_experience=8
        )
        
        # Crear relaciones
        self.relationship1 = Relationship(
            entrepreneur=self.entrepreneur1,
            ally=self.ally,
            start_date=datetime.now() - timedelta(days=90),
            status="active",
            impact_metrics={
                "jobs_created": 3,
                "revenue_increase": 15000,
                "funding_secured": 50000
            }
        )
        
        self.relationship2 = Relationship(
            entrepreneur=self.entrepreneur2,
            ally=self.ally,
            start_date=datetime.now() - timedelta(days=180),
            status="active",
            impact_metrics={
                "jobs_created": 5,
                "revenue_increase": 45000,
                "funding_secured": 75000
            }
        )
        
        # Guardar todo en la BD
        db.session.add(self.user)
        db.session.add(self.client)
        db.session.add(self.entrepreneur_user1)
        db.session.add(self.entrepreneur1)
        db.session.add(self.entrepreneur_user2)
        db.session.add(self.entrepreneur2)
        db.session.add(self.ally_user)
        db.session.add(self.ally)
        db.session.add(self.relationship1)
        db.session.add(self.relationship2)
        db.session.commit()
        
        # Login como cliente para las pruebas
        with self.client_app:
            response = self.client_app.post('/auth/login', data={
                'email': 'cliente@test.com',
                'password': 'password'
            }, follow_redirects=True)

    def tearDown(self):
        """Limpieza después de cada test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_dashboard_access(self):
        """Prueba el acceso al dashboard del cliente."""
        response = self.client_app.get('/client/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Panel de Control del Cliente', response.data)
        self.assertIn(b'Empresa Patrocinadora S.A.', response.data)

    def test_impact_dashboard_access(self):
        """Prueba el acceso al dashboard de impacto."""
        response = self.client_app.get('/client/impact')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard de Impacto', response.data)
        # Verificar presencia de indicadores de impacto
        self.assertIn(b'Emprendimientos Apoyados', response.data)
        self.assertIn(b'Empleos Creados', response.data)
        self.assertIn(b'Aumento en Ingresos', response.data)

    def test_impact_metrics_content(self):
        """Prueba que las métricas de impacto se muestren correctamente."""
        response = self.client_app.get('/client/impact')
        self.assertEqual(response.status_code, 200)
        
        # Verificar que las métricas acumuladas estén presentes
        self.assertIn(b'8', response.data)  # Total de empleos creados (3+5)
        self.assertIn(b'60000', response.data)  # Aumento total en ingresos (15000+45000)
        self.assertIn(b'125000', response.data)  # Fondos asegurados (50000+75000)

    def test_entrepreneurs_directory_access(self):
        """Prueba el acceso al directorio de emprendimientos."""
        response = self.client_app.get('/client/entrepreneurs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Directorio de Emprendimientos', response.data)
        
        # Verificar que los emprendedores aparezcan en el directorio
        self.assertIn(b'Negocio Test 1', response.data)
        self.assertIn(b'Negocio Test 2', response.data)
        self.assertIn(b'Tecnolog\xc3\xada', response.data)
        self.assertIn(b'Agricultura', response.data)

    def test_entrepreneur_detail(self):
        """Prueba la visualización detallada de un emprendimiento."""
        response = self.client_app.get(f'/client/entrepreneurs/{self.entrepreneur1.id}')
        self.assertEqual(response.status_code, 200)
        
        # Verificar contenido detallado
        self.assertIn(b'Negocio Test 1', response.data)
        self.assertIn(b'Empresa de tecnolog\xc3\xada para tests', response.data)
        self.assertIn(b'Etapa: Inicial', response.data)
        self.assertIn(b'Empleados: 5', response.data)

    def test_reports_access(self):
        """Prueba el acceso a los reportes."""
        response = self.client_app.get('/client/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Reportes de Impacto', response.data)

    def test_generate_report(self):
        """Prueba la generación de un reporte personalizado."""
        data = {
            'report_type': 'impact',
            'date_from': (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d'),
            'industries': ['Tecnología', 'Agricultura'],
            'format': 'pdf'
        }
        
        response = self.client_app.post('/client/reports/generate', 
                                      data=data,
                                      follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Verificar que se indique la generación exitosa
        self.assertIn(b'Reporte generado exitosamente', response.data)

    def test_profile_access(self):
        """Prueba el acceso al perfil del cliente."""
        response = self.client_app.get('/client/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Empresa Patrocinadora S.A.', response.data)
        self.assertIn(b'Juan P\xc3\xa9rez', response.data)
        self.assertIn(b'Director de Innovaci\xc3\xb3n', response.data)

    def test_profile_update(self):
        """Prueba la actualización del perfil del cliente."""
        response = self.client_app.post('/client/profile', data={
            'company_name': 'Empresa Patrocinadora Actualizada',
            'industry': 'Banca y Finanzas',
            'contact_name': 'María González',
            'contact_position': 'Gerente de Programas',
            'contact_phone': '555-1234'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que los cambios se guardaron en la BD
        updated_client = Client.query.filter_by(user_id=self.user.id).first()
        self.assertEqual(updated_client.company_name, 'Empresa Patrocinadora Actualizada')
        self.assertEqual(updated_client.contact_name, 'María González')
        self.assertEqual(updated_client.contact_position, 'Gerente de Programas')

    def test_filter_entrepreneur_directory(self):
        """Prueba el filtrado del directorio de emprendimientos."""
        data = {
            'industry': 'Tecnología',
            'stage': 'all',
            'sort_by': 'name'
        }
        
        response = self.client_app.get('/client/entrepreneurs', 
                                     query_string=data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar que solo aparece el emprendimiento de tecnología
        self.assertIn(b'Negocio Test 1', response.data)
        self.assertNotIn(b'Negocio Test 2', response.data)

    def test_export_entrepreneur_list(self):
        """Prueba la exportación de la lista de emprendimientos."""
        data = {
            'format': 'excel',
            'fields': ['business_name', 'industry', 'business_stage', 'employee_count', 'contact_info']
        }
        
        response = self.client_app.post('/client/entrepreneurs/export', 
                                       data=data)
        
        # Verificar que la respuesta contiene un archivo adjunto
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename=', response.headers.get('Content-Disposition', ''))
        self.assertIn('application/vnd.ms-excel', response.headers.get('Content-Type', ''))

    def test_subscription_status(self):
        """Prueba la visualización del estado de suscripción."""
        response = self.client_app.get('/client/subscription')
        self.assertEqual(response.status_code, 200)
        
        # Verificar información de suscripción
        self.assertIn(b'Plan Premium', response.data)
        self.assertIn(b'Activa', response.data)
        
        # Verificar fechas (esto puede ser complicado debido al formato)
        # Se puede verificar que al menos esté el año actual
        current_year = str(datetime.now().year)
        self.assertIn(current_year.encode(), response.data)

    def test_unauthorized_access(self):
        """Prueba que un emprendedor no puede acceder a las rutas de cliente."""
        # Cerrar sesión actual
        self.client_app.get('/auth/logout')
        
        # Iniciar sesión como emprendedor
        self.client_app.post('/auth/login', data={
            'email': 'emprendedor1@test.com',
            'password': 'password'
        })
        
        # Intentar acceder a una ruta de cliente
        response = self.client_app.get('/client/dashboard')
        self.assertNotEqual(response.status_code, 200)  # Debería redirigir o mostrar error


if __name__ == '__main__':
    unittest.main()