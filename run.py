#!/usr/bin/env python
import os
import click
from app import create_app, db
from app.models import user, entrepreneur, ally, client, relationship, message, meeting, document, task, config
from flask_migrate import Migrate
from flask_socketio import SocketIO

# Determinar el entorno desde la variable de entorno o usar 'default'
app_env = os.environ.get('FLASK_ENV', 'default')
app = create_app(app_env)
migrate = Migrate(app, db)
socketio = SocketIO(app)

# Importar los eventos de Socket.IO
from app.sockets import events

# Registrar los modelos para el shell de Flask
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': user.User,
        'Entrepreneur': entrepreneur.Entrepreneur,
        'Ally': ally.Ally,
        'Client': client.Client,
        'Relationship': relationship.Relationship,
        'Message': message.Message,
        'Meeting': meeting.Meeting, 
        'Document': document.Document,
        'Task': task.Task,
        'ConfigSetting': config.ConfigSetting
    }

# Registrar comandos CLI adicionales
from app.commands import register_commands
register_commands(app)

@app.cli.command()
@click.option('--test-type', default='all', help='Tipo de pruebas a ejecutar (all, models, views, integration)')
def test(test_type):
    """Ejecutar las pruebas unitarias."""
    import unittest
    
    if test_type == 'all':
        tests = unittest.TestLoader().discover('tests')
    else:
        tests = unittest.TestLoader().discover('tests', pattern=f'test_{test_type}*.py')
    
    unittest.TextTestRunner(verbosity=2).run(tests)

@app.cli.command()
def deploy():
    """Ejecutar tareas de despliegue."""
    # Migrar base de datos a la última revisión
    from flask_migrate import upgrade
    upgrade()
    
    # Crear roles y usuario admin por defecto si no existen
    from app.models.user import User
    if User.query.filter_by(role='admin').first() is None:
        default_admin_email = app.config['ADMIN_EMAIL']
        default_admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Usar variable de entorno o valor por defecto
        admin = User(
            email=default_admin_email,
            username='admin',
            password=default_admin_password,
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Usuario administrador creado con email: {default_admin_email}")
    
    # Inicializar configuraciones globales por defecto
    from app.models.config import ConfigSetting
    default_settings = [
        ('system_name', 'Plataforma de Emprendimiento'),
        ('system_version', '1.0.0'),
        ('max_allies_per_entrepreneur', '2'),
        ('max_entrepreneurs_per_ally', '10'),
        ('notification_email_enabled', 'True'),
        ('welcome_message', '¡Bienvenido a la plataforma de emprendimiento!')
    ]
    
    for key, value in default_settings:
        if ConfigSetting.query.filter_by(key=key).first() is None:
            setting = ConfigSetting(key=key, value=value)
            db.session.add(setting)
    
    db.session.commit()
    print("Configuraciones iniciales creadas")


if __name__ == '__main__':
    # Ejecutar la aplicación con Socket.IO
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))