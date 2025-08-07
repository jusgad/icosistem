"""
Comandos CLI personalizados para el ecosistema de emprendimiento.
Este módulo define comandos Flask-CLI para automatizar tareas administrativas.
"""

import os
import sys
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
import click
from flask import current_app
from flask.cli import with_appcontext, AppGroup

# Importar modelos
from app.extensions import db
from app.models.user import User
from app.models.admin import Admin
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.organization import Organization
from app.models.program import Program
from app.models.project import Project

# Importar servicios
from app.services.user_service import UserService
from app.services.email import EmailService
from app.services.analytics_service import AnalyticsService

# Importar utilidades
from app.utils.export_utils import ExportUtils
from app.utils.import_utils import ImportUtils


# ====================================
# GRUPOS DE COMANDOS
# ====================================

# Grupo para comandos de base de datos
db_cli = AppGroup('db', help='Comandos de base de datos')

# Grupo para comandos de usuarios
user_cli = AppGroup('user', help='Comandos de gestión de usuarios')

# Grupo para comandos de datos
data_cli = AppGroup('data', help='Comandos de importación/exportación de datos')

# Grupo para comandos de reportes
report_cli = AppGroup('report', help='Comandos de generación de reportes')

# Grupo para comandos de mantenimiento
maintenance_cli = AppGroup('maintenance', help='Comandos de mantenimiento')

# Grupo para comandos de desarrollo
dev_cli = AppGroup('dev', help='Comandos de desarrollo')


# ====================================
# COMANDOS DE BASE DE DATOS
# ====================================

@db_cli.command('init')
@with_appcontext
def init_db():
    """Inicializar la base de datos con tablas y datos básicos."""
    try:
        # Crear todas las tablas
        db.create_all()
        click.echo('✅ Tablas de base de datos creadas exitosamente.')
        
        # Crear datos básicos
        create_default_data()
        click.echo('✅ Datos básicos creados exitosamente.')
        
    except Exception as e:
        click.echo(f'❌ Error al inicializar la base de datos: {str(e)}', err=True)
        sys.exit(1)


@db_cli.command('reset')
@click.option('--force', is_flag=True, help='Forzar reset sin confirmación')
@with_appcontext
def reset_db(force):
    """Resetear completamente la base de datos."""
    if not force:
        if not click.confirm('¿Estás seguro de que quieres resetear la base de datos? Esto eliminará todos los datos.'):
            click.echo('Operación cancelada.')
            return
    
    try:
        # Eliminar todas las tablas
        db.drop_all()
        click.echo('🗑️  Tablas eliminadas.')
        
        # Recrear tablas
        db.create_all()
        click.echo('🔄 Tablas recreadas.')
        
        # Crear datos básicos
        create_default_data()
        click.echo('✅ Base de datos reseteada exitosamente.')
        
    except Exception as e:
        click.echo(f'❌ Error al resetear la base de datos: {str(e)}', err=True)
        sys.exit(1)


@db_cli.command('seed')
@click.option('--type', default='basic', help='Tipo de datos: basic, demo, full')
@with_appcontext
def seed_db(type):
    """Llenar la base de datos con datos de prueba."""
    try:
        if type == 'basic':
            create_basic_seed_data()
        elif type == 'demo':
            create_demo_data()
        elif type == 'full':
            create_full_seed_data()
        else:
            click.echo('❌ Tipo no válido. Usa: basic, demo, full')
            return
            
        click.echo(f'✅ Datos de tipo "{type}" creados exitosamente.')
        
    except Exception as e:
        click.echo(f'❌ Error al crear datos: {str(e)}', err=True)


@db_cli.command('backup')
@click.option('--output', default='backup.sql', help='Archivo de salida')
@with_appcontext
def backup_db(output):
    """Crear backup de la base de datos."""
    try:
        # Determinar tipo de base de datos
        database_url = current_app.config['SQLALCHEMY_DATABASE_URI']
        
        if database_url.startswith('sqlite'):
            backup_sqlite(database_url, output)
        elif database_url.startswith('postgresql'):
            backup_postgresql(database_url, output)
        else:
            click.echo('❌ Tipo de base de datos no soportado para backup')
            return
            
        click.echo(f'✅ Backup creado: {output}')
        
    except Exception as e:
        click.echo(f'❌ Error al crear backup: {str(e)}', err=True)


# ====================================
# COMANDOS DE USUARIOS
# ====================================

@user_cli.command('create')
@click.option('--email', prompt=True, help='Email del usuario')
@click.option('--password', prompt=True, hide_input=True, help='Contraseña')
@click.option('--role', type=click.Choice(['admin', 'entrepreneur', 'ally', 'client']), 
              prompt=True, help='Rol del usuario')
@click.option('--name', prompt=True, help='Nombre completo')
@with_appcontext
def create_user(email, password, role, name):
    """Crear un nuevo usuario."""
    try:
        user_data = {
            'email': email,
            'password': password,
            'first_name': name.split()[0],
            'last_name': ' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
            'role': role,
            'is_active': True,
            'email_verified': True
        }
        
        user = UserService.create_user(user_data)
        click.echo(f'✅ Usuario creado exitosamente: {user.email} ({user.role})')
        
    except Exception as e:
        click.echo(f'❌ Error al crear usuario: {str(e)}', err=True)


@user_cli.command('activate')
@click.argument('email')
@with_appcontext
def activate_user(email):
    """Activar un usuario."""
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f'❌ Usuario no encontrado: {email}')
            return
            
        user.is_active = True
        user.email_verified = True
        db.session.commit()
        
        click.echo(f'✅ Usuario activado: {email}')
        
    except Exception as e:
        click.echo(f'❌ Error al activar usuario: {str(e)}', err=True)


@user_cli.command('deactivate')
@click.argument('email')
@with_appcontext
def deactivate_user(email):
    """Desactivar un usuario."""
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f'❌ Usuario no encontrado: {email}')
            return
            
        user.is_active = False
        db.session.commit()
        
        click.echo(f'✅ Usuario desactivado: {email}')
        
    except Exception as e:
        click.echo(f'❌ Error al desactivar usuario: {str(e)}', err=True)


@user_cli.command('list')
@click.option('--role', help='Filtrar por rol')
@click.option('--active', is_flag=True, help='Solo usuarios activos')
@with_appcontext
def list_users(role, active):
    """Listar usuarios."""
    try:
        query = User.query
        
        if role:
            query = query.filter_by(role=role)
        if active:
            query = query.filter_by(is_active=True)
            
        users = query.all()
        
        click.echo(f'\n📋 Lista de usuarios ({len(users)} encontrados):')
        click.echo('-' * 80)
        
        for user in users:
            status = '🟢' if user.is_active else '🔴'
            verified = '✅' if user.email_verified else '❌'
            click.echo(f'{status} {user.email:<30} {user.role:<15} {verified} {user.full_name}')
            
    except Exception as e:
        click.echo(f'❌ Error al listar usuarios: {str(e)}', err=True)


@user_cli.command('change-password')
@click.argument('email')
@click.option('--password', prompt=True, hide_input=True, help='Nueva contraseña')
@with_appcontext
def change_password(email, password):
    """Cambiar contraseña de un usuario."""
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f'❌ Usuario no encontrado: {email}')
            return
            
        user.set_password(password)
        db.session.commit()
        
        click.echo(f'✅ Contraseña cambiada para: {email}')
        
    except Exception as e:
        click.echo(f'❌ Error al cambiar contraseña: {str(e)}', err=True)


# ====================================
# COMANDOS DE DATOS
# ====================================

@data_cli.command('export')
@click.option('--type', type=click.Choice(['users', 'entrepreneurs', 'projects', 'all']),
              default='all', help='Tipo de datos a exportar')
@click.option('--format', type=click.Choice(['json', 'csv', 'excel']),
              default='json', help='Formato de exportación')
@click.option('--output', help='Archivo de salida')
@with_appcontext
def export_data(type, format, output):
    """Exportar datos del sistema."""
    try:
        if not output:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output = f'export_{type}_{timestamp}.{format}'
        
        export_utils = ExportUtils(current_app)
        
        if type == 'users':
            export_utils.export_users(output, format)
        elif type == 'entrepreneurs':
            export_utils.export_entrepreneurs(output, format)
        elif type == 'projects':
            export_utils.export_projects(output, format)
        elif type == 'all':
            export_utils.export_all(output, format)
            
        click.echo(f'✅ Datos exportados a: {output}')
        
    except Exception as e:
        click.echo(f'❌ Error al exportar datos: {str(e)}', err=True)


@data_cli.command('import')
@click.argument('file_path')
@click.option('--type', type=click.Choice(['users', 'entrepreneurs', 'projects']),
              required=True, help='Tipo de datos a importar')
@click.option('--dry-run', is_flag=True, help='Simulación sin cambios reales')
@with_appcontext
def import_data(file_path, type, dry_run):
    """Importar datos al sistema."""
    try:
        if not os.path.exists(file_path):
            click.echo(f'❌ Archivo no encontrado: {file_path}')
            return
            
        import_utils = ImportUtils(current_app)
        
        if dry_run:
            click.echo('🔍 Modo simulación - sin cambios reales')
        
        if type == 'users':
            result = import_utils.import_users(file_path, dry_run=dry_run)
        elif type == 'entrepreneurs':
            result = import_utils.import_entrepreneurs(file_path, dry_run=dry_run)
        elif type == 'projects':
            result = import_utils.import_projects(file_path, dry_run=dry_run)
            
        click.echo(f'✅ Importación completada: {result["success"]} éxitos, {result["errors"]} errores')
        
        if result["errors"] > 0:
            click.echo('⚠️  Revisa los logs para detalles de errores')
            
    except Exception as e:
        click.echo(f'❌ Error al importar datos: {str(e)}', err=True)


# ====================================
# COMANDOS DE REPORTES
# ====================================

@report_cli.command('analytics')
@click.option('--period', type=click.Choice(['daily', 'weekly', 'monthly']),
              default='monthly', help='Período del reporte')
@click.option('--output', help='Archivo de salida (opcional)')
@with_appcontext
def generate_analytics(period, output):
    """Generar reporte de analytics."""
    try:
        analytics_service = AnalyticsService()
        
        if period == 'daily':
            report = analytics_service.generate_daily_report()
        elif period == 'weekly':
            report = analytics_service.generate_weekly_report()
        elif period == 'monthly':
            report = analytics_service.generate_monthly_report()
            
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            click.echo(f'✅ Reporte guardado en: {output}')
        else:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            
    except Exception as e:
        click.echo(f'❌ Error al generar reporte: {str(e)}', err=True)


@report_cli.command('users')
@click.option('--detailed', is_flag=True, help='Reporte detallado')
@with_appcontext
def user_report(detailed):
    """Generar reporte de usuarios."""
    try:
        users = User.query.all()
        
        # Estadísticas básicas
        total_users = len(users)
        active_users = len([u for u in users if u.is_active])
        by_role = {}
        
        for user in users:
            by_role[user.role] = by_role.get(user.role, 0) + 1
        
        click.echo('\n📊 REPORTE DE USUARIOS')
        click.echo('=' * 50)
        click.echo(f'Total de usuarios: {total_users}')
        click.echo(f'Usuarios activos: {active_users}')
        click.echo(f'Usuarios inactivos: {total_users - active_users}')
        click.echo('\nPor rol:')
        for role, count in by_role.items():
            click.echo(f'  - {role.capitalize()}: {count}')
        
        if detailed:
            click.echo('\n📋 DETALLE DE USUARIOS:')
            click.echo('-' * 80)
            for user in users:
                status = '🟢 Activo' if user.is_active else '🔴 Inactivo'
                click.echo(f'{user.email:<30} {user.role:<15} {status}')
                
    except Exception as e:
        click.echo(f'❌ Error al generar reporte: {str(e)}', err=True)


@report_cli.command('projects')
@with_appcontext
def project_report():
    """Generar reporte de proyectos."""
    try:
        projects = Project.query.all()
        
        total_projects = len(projects)
        by_status = {}
        
        for project in projects:
            by_status[project.status] = by_status.get(project.status, 0) + 1
        
        click.echo('\n📊 REPORTE DE PROYECTOS')
        click.echo('=' * 50)
        click.echo(f'Total de proyectos: {total_projects}')
        click.echo('\nPor estado:')
        for status, count in by_status.items():
            click.echo(f'  - {status.capitalize()}: {count}')
            
    except Exception as e:
        click.echo(f'❌ Error al generar reporte: {str(e)}', err=True)


# ====================================
# COMANDOS DE MANTENIMIENTO
# ====================================

@maintenance_cli.command('cleanup')
@click.option('--type', type=click.Choice(['temp', 'logs', 'sessions', 'all']),
              default='all', help='Tipo de limpieza')
@with_appcontext
def cleanup(type):
    """Limpiar archivos temporales y datos obsoletos."""
    try:
        cleaned_items = 0
        
        if type in ['temp', 'all']:
            temp_cleaned = cleanup_temp_files()
            cleaned_items += temp_cleaned
            click.echo(f'🧹 Archivos temporales limpiados: {temp_cleaned}')
        
        if type in ['logs', 'all']:
            logs_cleaned = cleanup_old_logs()
            cleaned_items += logs_cleaned
            click.echo(f'📋 Logs antiguos limpiados: {logs_cleaned}')
        
        if type in ['sessions', 'all']:
            sessions_cleaned = cleanup_expired_sessions()
            cleaned_items += sessions_cleaned
            click.echo(f'🔐 Sesiones expiradas limpiadas: {sessions_cleaned}')
        
        click.echo(f'✅ Limpieza completada. Total de elementos limpiados: {cleaned_items}')
        
    except Exception as e:
        click.echo(f'❌ Error durante la limpieza: {str(e)}', err=True)


@maintenance_cli.command('health-check')
@with_appcontext
def health_check():
    """Verificar el estado del sistema."""
    try:
        issues = []
        
        # Verificar conexión a base de datos
        try:
            db.session.execute('SELECT 1')
            click.echo('✅ Base de datos: OK')
        except Exception as e:
            issues.append(f'Base de datos: {str(e)}')
            click.echo('❌ Base de datos: ERROR')
        
        # Verificar configuración de email
        if current_app.config.get('MAIL_USERNAME'):
            click.echo('✅ Configuración de email: OK')
        else:
            issues.append('Email no configurado')
            click.echo('⚠️  Configuración de email: ADVERTENCIA')
        
        # Verificar directorios de uploads
        upload_dir = current_app.config.get('UPLOAD_FOLDER')
        if upload_dir and os.path.exists(upload_dir):
            click.echo('✅ Directorio de uploads: OK')
        else:
            issues.append('Directorio de uploads no existe')
            click.echo('❌ Directorio de uploads: ERROR')
        
        if issues:
            click.echo(f'\n⚠️  Se encontraron {len(issues)} problemas:')
            for issue in issues:
                click.echo(f'  - {issue}')
        else:
            click.echo('\n🎉 Sistema saludable - no se encontraron problemas')
            
    except Exception as e:
        click.echo(f'❌ Error durante verificación de salud: {str(e)}', err=True)


# ====================================
# COMANDOS DE DESARROLLO
# ====================================

@dev_cli.command('routes')
@with_appcontext
def show_routes():
    """Mostrar todas las rutas de la aplicación."""
    from flask import url_for
    
    click.echo('\n🛣️  RUTAS DE LA APLICACIÓN')
    click.echo('=' * 80)
    
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': rule.rule
        })
    
    # Ordenar por endpoint
    routes.sort(key=lambda x: x['endpoint'])
    
    for route in routes:
        methods = ', '.join([m for m in route['methods'] if m not in ['HEAD', 'OPTIONS']])
        click.echo(f"{route['endpoint']:<40} {methods:<20} {route['rule']}")


@dev_cli.command('config')
@with_appcontext
def show_config():
    """Mostrar configuración actual de la aplicación."""
    click.echo('\n⚙️  CONFIGURACIÓN DE LA APLICACIÓN')
    click.echo('=' * 60)
    
    # Configuraciones seguras para mostrar
    safe_keys = [
        'DEBUG', 'TESTING', 'FLASK_ENV', 'SQLALCHEMY_DATABASE_URI',
        'MAIL_SERVER', 'MAIL_PORT', 'WTF_CSRF_ENABLED', 'CACHE_TYPE'
    ]
    
    for key in sorted(current_app.config.keys()):
        if key in safe_keys:
            value = current_app.config[key]
            # Ocultar passwords en URLs de base de datos
            if 'DATABASE_URI' in key and isinstance(value, str):
                value = value.split('@')[-1] if '@' in value else value
            click.echo(f'{key:<30} = {value}')


# ====================================
# FUNCIONES AUXILIARES
# ====================================

def create_default_data():
    """Crear datos básicos necesarios para el funcionamiento."""
    
    # Crear usuario administrador por defecto
    admin_email = 'admin@ecosistema.com'
    if not User.query.filter_by(email=admin_email).first():
        admin_data = {
            'email': admin_email,
            'password': 'admin123',
            'first_name': 'Administrador',
            'last_name': 'Sistema',
            'role': 'admin',
            'is_active': True,
            'email_verified': True
        }
        UserService.create_user(admin_data)
        click.echo(f'👤 Usuario administrador creado: {admin_email}')


def create_basic_seed_data():
    """Crear datos básicos para pruebas."""
    
    # Crear algunos usuarios de ejemplo
    sample_users = [
        {
            'email': 'emprendedor@test.com',
            'password': 'test123',
            'first_name': 'Juan',
            'last_name': 'Emprendedor',
            'role': 'entrepreneur'
        },
        {
            'email': 'mentor@test.com',
            'password': 'test123',
            'first_name': 'María',
            'last_name': 'Mentora',
            'role': 'ally'
        }
    ]
    
    for user_data in sample_users:
        if not User.query.filter_by(email=user_data['email']).first():
            user_data.update({'is_active': True, 'email_verified': True})
            UserService.create_user(user_data)


def create_demo_data():
    """Crear datos de demostración completos."""
    create_basic_seed_data()
    # Aquí se pueden agregar más datos de demostración
    pass


def create_full_seed_data():
    """Crear conjunto completo de datos para desarrollo."""
    create_demo_data()
    # Aquí se pueden agregar datos exhaustivos para desarrollo
    pass


def backup_sqlite(database_url, output):
    """Crear backup de base de datos SQLite."""
    import shutil
    db_path = database_url.replace('sqlite:///', '')
    shutil.copy2(db_path, output)


def backup_postgresql(database_url, output):
    """Crear backup de base de datos PostgreSQL."""
    import subprocess
    cmd = f'pg_dump {database_url} > {output}'
    subprocess.run(cmd, shell=True, check=True)


def cleanup_temp_files():
    """Limpiar archivos temporales."""
    temp_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    temp_path = os.path.join(temp_dir, 'temp')
    
    if not os.path.exists(temp_path):
        return 0
    
    count = 0
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    for file in os.listdir(temp_path):
        file_path = os.path.join(temp_path, file)
        if os.path.isfile(file_path):
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_time < cutoff_time:
                os.remove(file_path)
                count += 1
    
    return count


def cleanup_old_logs():
    """Limpiar logs antiguos."""
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        return 0
    
    count = 0
    cutoff_time = datetime.now() - timedelta(days=30)
    
    for file in os.listdir(logs_dir):
        if file.endswith('.log') and file != 'app.log':
            file_path = os.path.join(logs_dir, file)
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_time < cutoff_time:
                os.remove(file_path)
                count += 1
    
    return count


def cleanup_expired_sessions():
    """Limpiar sesiones expiradas."""
    # Implementar según el backend de sesiones usado
    return 0


# ====================================
# REGISTRO DE COMANDOS
# ====================================

def register_commands(app):
    """Registrar todos los comandos CLI con la aplicación Flask."""
    
    # Registrar grupos de comandos
    app.cli.add_command(db_cli)
    app.cli.add_command(user_cli)
    app.cli.add_command(data_cli)
    app.cli.add_command(report_cli)
    app.cli.add_command(maintenance_cli)
    app.cli.add_command(dev_cli)
    
    # Comando de setup inicial
    @app.cli.command()
    @with_appcontext
    def setup():
        """Configuración inicial completa del sistema."""
        click.echo('🚀 Iniciando configuración del ecosistema de emprendimiento...')
        
        try:
            # Crear base de datos
            db.create_all()
            click.echo('✅ Base de datos inicializada')
            
            # Crear datos básicos
            create_default_data()
            click.echo('✅ Datos básicos creados')
            
            # Crear directorios necesarios
            upload_dir = app.config.get('UPLOAD_FOLDER', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            os.makedirs('logs', exist_ok=True)
            click.echo('✅ Directorios creados')
            
            click.echo('\n🎉 ¡Configuración completada exitosamente!')
            click.echo('👤 Usuario admin: admin@ecosistema.com / admin123')
            
        except Exception as e:
            click.echo(f'❌ Error durante la configuración: {str(e)}', err=True)
            sys.exit(1)