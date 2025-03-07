import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.relationship import Relationship
from app.models.task import Task
from app.models.document import Document
import os
from datetime import datetime, timedelta
import random
import shutil

def register_commands(app):
    """Registra comandos personalizados para la CLI de Flask"""
    
    @app.cli.command('create-db')
    @with_appcontext
    def create_db():
        """Crea todas las tablas de la base de datos."""
        db.create_all()
        click.echo('Base de datos creada.')
    
    @app.cli.command('drop-db')
    @with_appcontext
    def drop_db():
        """Elimina todas las tablas de la base de datos."""
        if click.confirm('¿Estás seguro? Esta acción eliminará todos los datos.'):
            db.drop_all()
            click.echo('Base de datos eliminada.')
    
    @app.cli.command('reset-db')
    @with_appcontext
    def reset_db():
        """Elimina y vuelve a crear todas las tablas de la base de datos."""
        if click.confirm('¿Estás seguro? Esta acción eliminará todos los datos.'):
            db.drop_all()
            db.create_all()
            click.echo('Base de datos reiniciada.')
    
    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('password')
    @click.argument('name')
    @with_appcontext
    def create_admin(email, password, name):
        """Crea un usuario administrador."""
        if User.query.filter_by(email=email).first():
            click.echo(f'El usuario con email {email} ya existe.')
            return
        
        admin = User(
            email=email,
            name=name,
            role='admin',
            is_active=True,
            created_at=datetime.now()
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        click.echo(f'Administrador {email} creado exitosamente.')
    
    @app.cli.command('seed-db')
    @with_appcontext
    def seed_db():
        """Puebla la base de datos con datos de ejemplo."""
        if not click.confirm('¿Deseas poblar la base de datos con datos de ejemplo?'):
            return
        
        # Crear usuarios de ejemplo
        admin = User(
            email='admin@example.com', 
            name='Administrador', 
            role='admin',
            is_active=True,
            created_at=datetime.now()
        )
        admin.set_password('admin123')
        
        entrepreneur1 = User(
            email='emprendedor1@example.com', 
            name='Emprendedor Uno', 
            role='entrepreneur',
            is_active=True,
            created_at=datetime.now() - timedelta(days=30)
        )
        entrepreneur1.set_password('password')
        
        entrepreneur2 = User(
            email='emprendedor2@example.com', 
            name='Emprendedor Dos', 
            role='entrepreneur',
            is_active=True,
            created_at=datetime.now() - timedelta(days=25)
        )
        entrepreneur2.set_password('password')
        
        ally1 = User(
            email='aliado1@example.com', 
            name='Aliado Uno', 
            role='ally',
            is_active=True,
            created_at=datetime.now() - timedelta(days=20)
        )
        ally1.set_password('password')
        
        ally2 = User(
            email='aliado2@example.com', 
            name='Aliado Dos', 
            role='ally',
            is_active=True,
            created_at=datetime.now() - timedelta(days=15)
        )
        ally2.set_password('password')
        
        client1 = User(
            email='cliente1@example.com', 
            name='Cliente Uno', 
            role='client',
            is_active=True,
            created_at=datetime.now() - timedelta(days=10)
        )
        client1.set_password('password')
        
        db.session.add_all([admin, entrepreneur1, entrepreneur2, ally1, ally2, client1])
        db.session.commit()
        
        # Crear perfiles
        entrepreneur_profile1 = Entrepreneur(
            user_id=entrepreneur1.id,
            business_name='Emprendimiento Uno',
            business_description='Descripción del emprendimiento uno. Este es un negocio innovador en el sector tecnológico que busca revolucionar la forma en que las personas interactúan con la tecnología en su día a día.',
            industry='Tecnología',
            founding_date='2022-01-01',
            website='https://emprendimiento1.com',
            phone='123456789',
            address='Dirección 1',
            city='Ciudad 1',
            country='País 1',
            employees=5,
            stage='growth',
            revenue_range='10k-50k',
            social_media={
                'facebook': 'https://facebook.com/emprendimiento1',
                'instagram': 'https://instagram.com/emprendimiento1',
                'linkedin': 'https://linkedin.com/company/emprendimiento1'
            }
        )
        
        entrepreneur_profile2 = Entrepreneur(
            user_id=entrepreneur2.id,
            business_name='Emprendimiento Dos',
            business_description='Descripción del emprendimiento dos. Este es un negocio innovador en el sector alimenticio que busca ofrecer alternativas saludables y sostenibles para la alimentación diaria.',
            industry='Alimentación',
            founding_date='2021-06-15',
            website='https://emprendimiento2.com',
            phone='987654321',
            address='Dirección 2',
            city='Ciudad 2',
            country='País 2',
            employees=10,
            stage='early',
            revenue_range='0-10k',
            social_media={
                'facebook': 'https://facebook.com/emprendimiento2',
                'instagram': 'https://instagram.com/emprendimiento2',
                'twitter': 'https://twitter.com/emprendimiento2'
            }
        )
        
        ally_profile1 = Ally(
            user_id=ally1.id,
            specialty='Marketing Digital',
            experience='5 años de experiencia en marketing digital para startups y empresas tecnológicas. Especialista en estrategias de crecimiento y posicionamiento de marca.',
            availability='Lunes a Viernes, 9am-5pm',
            phone='123123123',
            linkedin='https://linkedin.com/in/aliado1',
            hourly_rate=50,
            max_entrepreneurs=5,
            areas_of_expertise=['SEO', 'SEM', 'Social Media', 'Content Marketing'],
            languages=['Español', 'Inglés']
        )
        
        ally_profile2 = Ally(
            user_id=ally2.id,
            specialty='Finanzas',
            experience='10 años de experiencia en finanzas corporativas y asesoría financiera para emprendimientos en etapa temprana y de crecimiento.',
            availability='Martes y Jueves, 10am-6pm',
            phone='456456456',
            linkedin='https://linkedin.com/in/aliado2',
            hourly_rate=75,
            max_entrepreneurs=3,
            areas_of_expertise=['Planificación Financiera', 'Valoración', 'Captación de Fondos', 'Contabilidad'],
            languages=['Español', 'Inglés', 'Francés']
        )
        
        client_profile1 = Client(
            user_id=client1.id,
            company_name='Empresa Cliente',
            industry='Consultoría',
            phone='789789789',
            website='https://cliente1.com',
            address='Dirección Cliente 1',
            city='Ciudad Cliente',
            country='País Cliente',
            company_size='medium',
            interests=['Tecnología', 'Innovación', 'Sostenibilidad'],
            contact_person='Contacto Principal'
        )
        
        db.session.add_all([
            entrepreneur_profile1, 
            entrepreneur_profile2, 
            ally_profile1, 
            ally_profile2, 
            client_profile1
        ])
        db.session.commit()
        
        # Crear relaciones entre emprendedores y aliados
        relationship1 = Relationship(
            entrepreneur_id=entrepreneur_profile1.id,
            ally_id=ally_profile1.id,
            status='active',
            start_date=datetime.now() - timedelta(days=15),
            hours_assigned=20,
            hours_used=5,
            notes='Relación de mentoría en marketing digital para mejorar la presencia online del emprendimiento.'
        )
        
        relationship2 = Relationship(
            entrepreneur_id=entrepreneur_profile1.id,
            ally_id=ally_profile2.id,
            status='active',
            start_date=datetime.now() - timedelta(days=10),
            hours_assigned=15,
            hours_used=2,
            notes='Asesoría financiera para planificación de crecimiento y búsqueda de inversión.'
        )
        
        relationship3 = Relationship(
            entrepreneur_id=entrepreneur_profile2.id,
            ally_id=ally_profile1.id,
            status='pending',
            start_date=None,
            hours_assigned=10,
            hours_used=0,
            notes='Pendiente de aprobación para iniciar mentoría en marketing digital.'
        )
        
        db.session.add_all([relationship1, relationship2, relationship3])
        db.session.commit()
        
        # Crear tareas
        task_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        task_priorities = ['low', 'medium', 'high']
        
        for i in range(1, 11):
            task = Task(
                title=f'Tarea de ejemplo {i}',
                description=f'Descripción detallada de la tarea de ejemplo {i}',
                status=random.choice(task_statuses),
                priority=random.choice(task_priorities),
                due_date=datetime.now() + timedelta(days=random.randint(1, 30)),
                created_at=datetime.now() - timedelta(days=random.randint(1, 15)),
                updated_at=datetime.now() - timedelta(days=random.randint(0, 5)),
                created_by_id=random.choice([ally1.id, ally2.id, entrepreneur1.id, entrepreneur2.id]),
                assigned_to_id=random.choice([ally1.id, ally2.id, entrepreneur1.id, entrepreneur2.id]),
                relationship_id=random.choice([relationship1.id, relationship2.id])
            )
            db.session.add(task)
        
        # Crear documentos
        document_types = ['report', 'contract', 'presentation', 'other']
        
        for i in range(1, 6):
            document = Document(
                title=f'Documento de ejemplo {i}',
                description=f'Descripción del documento de ejemplo {i}',
                file_path=f'/static/uploads/documents/example_{i}.pdf',
                file_type='application/pdf',
                file_size=random.randint(100, 5000),
                document_type=random.choice(document_types),
                uploaded_at=datetime.now() - timedelta(days=random.randint(1, 30)),
                uploaded_by_id=random.choice([ally1.id, ally2.id, entrepreneur1.id, entrepreneur2.id]),
                relationship_id=random.choice([relationship1.id, relationship2.id])
            )
            db.session.add(document)
        
        db.session.commit()
        
        click.echo('Base de datos poblada con datos de ejemplo.')
    
    @app.cli.command('clean-uploads')
    @with_appcontext
    def clean_uploads():
        """Limpia archivos huérfanos en la carpeta de uploads."""
        upload_folder = app.config['UPLOAD_FOLDER']
        
        # Obtener todos los documentos registrados en la base de datos
        documents = Document.query.all()
        registered_files = set(doc.file_path.split('/')[-1] for doc in documents)
        
        # Verificar archivos en el sistema de archivos
        file_count = 0
        deleted_count = 0
        
        for root, dirs, files in os.walk(upload_folder):
            for file in files:
                file_count += 1
                if file not in registered_files:
                    # El archivo no está registrado en la base de datos
                    file_path = os.path.join(root, file)
                    # Verificar si el archivo tiene más de 24 horas
                    file_age = datetime.now() - datetime.fromtimestamp(os.path.getctime(file_path))
                    if file_age > timedelta(hours=24):
                        os.remove(file_path)
                        deleted_count += 1
        
        click.echo(f'Limpieza de archivos completada. {deleted_count} archivos huérfanos eliminados de un total de {file_count} archivos.')
    
    @app.cli.command('export-users')
    @click.argument('output_file', type=click.Path())
    @with_appcontext
    def export_users(output_file):
        """Exporta la lista de usuarios a un archivo CSV."""
        import csv
        
        users = User.query.all()
        
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['id', 'email', 'name', 'role', 'is_active', 'created_at', 'last_login']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for user in users:
                writer.writerow({
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role,
                    'is_active': user.is_active,
                    'created_at': user.created_at,
                    'last_login': user.last_login
                })
        
        click.echo(f'Usuarios exportados a {output_file}')
    
    @app.cli.command('check-health')
    @with_appcontext
    def check_health():
        """Verifica el estado de la aplicación y sus dependencias."""
        # Verificar conexión a la base de datos
        try:
            db.session.execute('SELECT 1')
            click.echo('Base de datos: OK')
        except Exception as e:
            click.echo(f'Base de datos: ERROR - {str(e)}')
        
        # Verificar directorios de almacenamiento
        upload_folder = app.config['UPLOAD_FOLDER']
        if os.path.exists(upload_folder) and os.access(upload_folder, os.W_OK):
            click.echo('Directorio de uploads: OK')
        else:
            click.echo('Directorio de uploads: ERROR - No existe o no tiene permisos de escritura')
        
        # Verificar configuración de correo
        mail_config = {
            'MAIL_SERVER': app.config.get('MAIL_SERVER'),
            'MAIL_PORT': app.config.get('MAIL_PORT'),
            'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
            'MAIL_PASSWORD': app.config.get('MAIL_PASSWORD'),
            'MAIL_DEFAULT_SENDER': app.config.get('MAIL_DEFAULT_SENDER')
        }
        
        if all(mail_config.values()):
            click.echo('Configuración de correo: OK')
        else:
            missing = [k for k, v in mail_config.items() if not v]
            click.echo(f'Configuración de correo: ADVERTENCIA - Faltan valores: {", ".join(missing)}')
        
        # Verificar configuración de Socket.IO
        if app.config.get('SECRET_KEY'):
            click.echo('Configuración de Socket.IO: OK')
        else:
            click.echo('Configuración de Socket.IO: ERROR - Falta SECRET_KEY')
        
        # Verificar espacio en disco
        try:
            total, used, free = shutil.disk_usage('/')
            free_gb = free // (2**30)
            if free_gb < 1:
                click.echo(f'Espacio en disco: CRÍTICO - Solo {free_gb} GB disponibles')
            elif free_gb < 5:
                click.echo(f'Espacio en disco: ADVERTENCIA - Solo {free_gb} GB disponibles')
            else:
                click.echo(f'Espacio en disco: OK - {free_gb} GB disponibles')
        except Exception as e:
            click.echo(f'Espacio en disco: ERROR - {str(e)}')
        
        # Resumen
        click.echo('Verificación de salud completada.')