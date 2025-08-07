"""
Inicialización de modelos para el ecosistema de emprendimiento.
Este módulo centraliza la importación y configuración de todos los modelos de datos.
"""

import logging
from flask import current_app
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

# Configurar logger para modelos
models_logger = logging.getLogger('ecosistema.models')

# ====================================
# IMPORTACIÓN DE MODELOS BASE
# ====================================

# Modelo base y mixins
from .base import BaseModel, TimestampMixin, AuditMixin, SoftDeleteMixin
from .mixins import (
    SearchableMixin, CacheableMixin, ExportableMixin, 
    NotifiableMixin, ValidatableMixin, StateMachineMixin
)

# ====================================
# IMPORTACIÓN DE MODELOS DE USUARIOS
# ====================================

# Usuario base y roles específicos
from .user import User
from .admin import Admin
from .entrepreneur import Entrepreneur
from .ally import Ally
from .client import Client

# ====================================
# IMPORTACIÓN DE MODELOS DE NEGOCIO
# ====================================

# Organizaciones y programas
from .organization import Organization
from .program import Program

# Proyectos de emprendedores
from .project import Project

# Sistema de mentoría
from .mentorship import Mentorship

# Reuniones y eventos
from .meeting import Meeting

# Sistema de mensajería
from .message import Message

# Gestión de documentos
from .document import Document

# Sistema de tareas
from .task import Task

# Notificaciones
from .notification import Notification

# Log de actividades
from .activity_log import ActivityLog

# Analytics y métricas
from .analytics import Analytics

# ====================================
# MODELOS AUXILIARES
# ====================================

# Tablas de relación many-to-many (comentadas temporalmente)
# from .associations import (
#     user_organization_association,
#     project_tag_association, 
#     meeting_participant_association,
#     program_entrepreneur_association
# )

# ====================================
# CONFIGURACIÓN DE BASE DE DATOS
# ====================================

def configure_database_events():
    """Configurar eventos de base de datos para optimización y logging."""
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Configurar SQLite para mejor performance."""
        if 'sqlite' in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            # Habilitar foreign keys
            cursor.execute("PRAGMA foreign_keys=ON")
            # Configurar WAL mode para mejor concurrencia
            cursor.execute("PRAGMA journal_mode=WAL")
            # Optimizar sincronización
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
            models_logger.debug("SQLite pragmas configured")
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log de queries SQL en desarrollo."""
        if current_app and current_app.debug:
            models_logger.debug(f"SQL Query: {statement}")
            if parameters:
                models_logger.debug(f"Parameters: {parameters}")
    
    @event.listens_for(Pool, "connect")
    def set_postgresql_settings(dbapi_connection, connection_record):
        """Configurar PostgreSQL para mejor performance."""
        if 'postgresql' in str(dbapi_connection):
            with dbapi_connection.cursor() as cursor:
                # Configurar timezone
                cursor.execute("SET timezone TO 'America/Bogota'")
                # Configurar encoding
                cursor.execute("SET client_encoding TO 'UTF8'")
            models_logger.debug("PostgreSQL settings configured")


def configure_model_events():
    """Configurar eventos específicos de modelos."""
    
    # Eventos de auditoría automática
    @event.listens_for(User, 'after_insert')
    def log_user_creation(mapper, connection, target):
        """Log creación de usuarios."""
        models_logger.info(f"User created: {target.email} (ID: {target.id}, Role: {target.role})")
    
    @event.listens_for(User, 'after_update')
    def log_user_update(mapper, connection, target):
        """Log actualización de usuarios."""
        # Solo log cambios significativos
        if target.role or target.is_active:
            models_logger.info(f"User updated: {target.email} (ID: {target.id})")
    
    @event.listens_for(Project, 'after_insert')
    def log_project_creation(mapper, connection, target):
        """Log creación de proyectos."""
        models_logger.info(f"Project created: {target.name} by entrepreneur {target.entrepreneur_id}")
    
    @event.listens_for(Project, 'after_update')
    def log_project_status_change(mapper, connection, target):
        """Log cambios de estado de proyectos."""
        # Verificar si cambió el estado
        history = target.__dict__.get('_sa_instance_state').attrs.status.history
        if history.has_changes():
            old_status = history.deleted[0] if history.deleted else None
            new_status = history.added[0] if history.added else target.status
            models_logger.info(f"Project status changed: {target.name} from {old_status} to {new_status}")
    
    @event.listens_for(Meeting, 'after_insert')
    def log_meeting_creation(mapper, connection, target):
        """Log creación de reuniones."""
        models_logger.info(f"Meeting scheduled: {target.title} by user {target.organizer_id}")
    
    # Eventos de validación automática
    @event.listens_for(User, 'before_insert')
    @event.listens_for(User, 'before_update')
    def validate_user_data(mapper, connection, target):
        """Validar datos de usuario antes de guardar."""
        if not target.email or '@' not in target.email:
            raise ValueError("Email inválido")
        
        if not target.role or target.role not in ['admin', 'entrepreneur', 'ally', 'client']:
            raise ValueError("Rol inválido")
    
    @event.listens_for(Project, 'before_insert')
    @event.listens_for(Project, 'before_update')
    def validate_project_data(mapper, connection, target):
        """Validar datos de proyecto antes de guardar."""
        if not target.name or len(target.name.strip()) < 3:
            raise ValueError("Nombre de proyecto muy corto")
        
        if target.status not in ['idea', 'validation', 'development', 'launch', 'growth', 'scale', 'exit', 'paused', 'cancelled']:
            raise ValueError("Estado de proyecto inválido")


def configure_search_indexes():
    """Configurar índices de búsqueda para modelos searchable."""
    try:
        # Configurar índices de texto completo para PostgreSQL
        from sqlalchemy import text
        from app.extensions import db
        
        if 'postgresql' in current_app.config.get('SQLALCHEMY_DATABASE_URI', ''):
            with db.engine.connect() as conn:
                # Índice para búsqueda de usuarios
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_search 
                    ON users USING gin(to_tsvector('spanish', first_name || ' ' || last_name || ' ' || email))
                """))
                
                # Índice para búsqueda de proyectos
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_project_search 
                    ON projects USING gin(to_tsvector('spanish', name || ' ' || COALESCE(description, '')))
                """))
                
                # Índice para búsqueda de organizaciones
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_organization_search 
                    ON organizations USING gin(to_tsvector('spanish', name || ' ' || COALESCE(description, '')))
                """))
                
                conn.commit()
                models_logger.info("Search indexes created successfully")
                
    except Exception as e:
        models_logger.warning(f"Could not create search indexes: {str(e)}")


# ====================================
# UTILIDADES DE MODELOS
# ====================================

def get_model_by_name(model_name: str):
    """
    Obtener clase de modelo por nombre.
    
    Args:
        model_name: Nombre del modelo
        
    Returns:
        Clase del modelo o None
    """
    model_map = {
        'user': User,
        'admin': Admin,
        'entrepreneur': Entrepreneur,
        'ally': Ally,
        'client': Client,
        'organization': Organization,
        'program': Program,
        'project': Project,
        'mentorship': Mentorship,
        'meeting': Meeting,
        'message': Message,
        'document': Document,
        'task': Task,
        'notification': Notification,
        'activity_log': ActivityLog,
        'analytics': Analytics
    }
    
    return model_map.get(model_name.lower())


def get_all_models():
    """
    Obtener lista de todas las clases de modelos.
    
    Returns:
        Lista de clases de modelos
    """
    return [
        User, Admin, Entrepreneur, Ally, Client,
        Organization, Program, Project, Mentorship,
        Meeting, Message, Document, Task,
        Notification, ActivityLog, Analytics
    ]


def create_sample_data():
    """Crear datos de ejemplo para desarrollo y testing."""
    from app.extensions import db
    from app.services.user_service import UserService
    from datetime import datetime, timedelta
    import secrets
    
    try:
        # Verificar si ya existen datos
        if User.query.count() > 1:  # Más de 1 usuario (admin default)
            models_logger.info("Sample data already exists, skipping creation")
            return
        
        models_logger.info("Creating sample data...")
        
        # Crear usuarios de ejemplo
        sample_users = [
            {
                'email': 'juan.emprendedor@ejemplo.com',
                'password': 'Password123!',
                'first_name': 'Juan',
                'last_name': 'Emprendedor',
                'role': 'entrepreneur',
                'phone': '+573001234567',
                'is_active': True,
                'email_verified': True
            },
            {
                'email': 'maria.mentora@ejemplo.com',
                'password': 'Password123!',
                'first_name': 'María',
                'last_name': 'Mentora',
                'role': 'ally',
                'phone': '+573007654321',
                'is_active': True,
                'email_verified': True
            },
            {
                'email': 'carlos.cliente@ejemplo.com',
                'password': 'Password123!',
                'first_name': 'Carlos',
                'last_name': 'Cliente',
                'role': 'client',
                'phone': '+573005555555',
                'is_active': True,
                'email_verified': True
            }
        ]
        
        created_users = []
        for user_data in sample_users:
            try:
                user = UserService.create_user(user_data)
                created_users.append(user)
                models_logger.info(f"Created sample user: {user.email}")
            except Exception as e:
                models_logger.error(f"Error creating sample user: {str(e)}")
        
        # Crear organización de ejemplo
        if created_users:
            sample_org = Organization(
                name="Incubadora Ejemplo",
                description="Incubadora de ejemplo para el ecosistema",
                website="https://incubadora-ejemplo.com",
                owner_id=created_users[1].id,  # Mentor como propietario
                is_active=True
            )
            db.session.add(sample_org)
        
        # Crear proyecto de ejemplo
        entrepreneur = next((u for u in created_users if u.role == 'entrepreneur'), None)
        if entrepreneur:
            sample_project = Project(
                name="App Delivery Sostenible",
                description="Aplicación de delivery que prioriza restaurantes locales y packaging ecológico",
                status="development",
                entrepreneur_id=entrepreneur.id,
                start_date=datetime.utcnow() - timedelta(days=30),
                target_market="Estudiantes universitarios y trabajadores jóvenes",
                business_model="Comisión por pedido + suscripción premium"
            )
            db.session.add(sample_project)
        
        # Crear programa de ejemplo
        ally = next((u for u in created_users if u.role == 'ally'), None)
        if ally:
            sample_program = Program(
                name="Aceleración Tech 2024",
                description="Programa de aceleración para startups tecnológicas",
                creator_id=ally.id,
                start_date=datetime.utcnow() + timedelta(days=15),
                end_date=datetime.utcnow() + timedelta(days=105),  # 3 meses
                max_participants=20,
                is_active=True
            )
            db.session.add(sample_program)
        
        # Confirmar cambios
        db.session.commit()
        models_logger.info("Sample data created successfully")
        
    except Exception as e:
        db.session.rollback()
        models_logger.error(f"Error creating sample data: {str(e)}")


def validate_database_schema():
    """Validar integridad del esquema de base de datos."""
    from app.extensions import db
    from sqlalchemy import inspect
    
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Tablas requeridas
        required_tables = [
            'users', 'entrepreneurs', 'allies', 'clients', 'admins',
            'organizations', 'programs', 'projects', 'mentorships',
            'meetings', 'messages', 'documents', 'tasks',
            'notifications', 'activity_logs', 'analytics'
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            models_logger.error(f"Missing database tables: {missing_tables}")
            return False
        
        # Verificar índices críticos
        for table in ['users', 'projects', 'meetings']:
            indexes = inspector.get_indexes(table)
            if not indexes:
                models_logger.warning(f"No indexes found for table {table}")
        
        models_logger.info("Database schema validation passed")
        return True
        
    except Exception as e:
        models_logger.error(f"Database schema validation failed: {str(e)}")
        return False


def optimize_database():
    """Optimizar base de datos ejecutando análisis y limpieza."""
    from app.extensions import db
    from sqlalchemy import text
    
    try:
        with db.engine.connect() as conn:
            
            # PostgreSQL optimizations
            if 'postgresql' in current_app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                # Actualizar estadísticas
                conn.execute(text("ANALYZE;"))
                
                # Vacuum automático si es necesario
                result = conn.execute(text("""
                    SELECT schemaname, tablename, n_dead_tup, n_live_tup 
                    FROM pg_stat_user_tables 
                    WHERE n_dead_tup > 100
                """))
                
                for row in result:
                    if row.n_dead_tup > row.n_live_tup * 0.1:  # 10% de registros muertos
                        table_name = f"{row.schemaname}.{row.tablename}"
                        conn.execute(text(f"VACUUM {table_name};"))
                        models_logger.info(f"Vacuumed table: {table_name}")
            
            # SQLite optimizations
            elif 'sqlite' in current_app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                # Rebuild indexes
                conn.execute(text("REINDEX;"))
                
                # Analyze database
                conn.execute(text("ANALYZE;"))
                
                # Vacuum if needed
                conn.execute(text("VACUUM;"))
            
            conn.commit()
            models_logger.info("Database optimization completed")
            
    except Exception as e:
        models_logger.error(f"Database optimization failed: {str(e)}")


# ====================================
# FUNCIÓN DE INICIALIZACIÓN PRINCIPAL
# ====================================

def init_models(app):
    """
    Inicializar completamente el sistema de modelos.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    
    # Configurar eventos de base de datos
    configure_database_events()
    
    # Configurar eventos de modelos
    configure_model_events()
    
    # Crear índices de búsqueda
    if not app.testing:
        configure_search_indexes()
    
    # Registrar comandos CLI
    @app.cli.command()
    def create_sample_data_cmd():
        """Crear datos de ejemplo."""
        create_sample_data()
        
    @app.cli.command()
    def validate_schema():
        """Validar esquema de base de datos."""
        if validate_database_schema():
            click.echo("✅ Database schema is valid")
        else:
            click.echo("❌ Database schema validation failed")
            
    @app.cli.command()
    def optimize_db():
        """Optimizar base de datos."""
        optimize_database()
        click.echo("✅ Database optimization completed")
    
    @app.cli.command()
    def model_info():
        """Mostrar información de modelos."""
        models = get_all_models()
        click.echo(f"📊 Total models: {len(models)}")
        
        for model in models:
            table_name = model.__tablename__
            columns = len(model.__table__.columns)
            click.echo(f"  - {model.__name__}: {table_name} ({columns} columns)")
    
    app.logger.info(f"Models system initialized with {len(get_all_models())} models")


# ====================================
# ESTADÍSTICAS DE MODELOS
# ====================================

def get_models_statistics():
    """Obtener estadísticas de todos los modelos."""
    from app.extensions import db
    
    stats = {
        'total_models': len(get_all_models()),
        'table_counts': {},
        'last_updated': datetime.utcnow().isoformat()
    }
    
    try:
        # Contar registros por tabla
        for model in get_all_models():
            try:
                count = db.session.query(model).count()
                stats['table_counts'][model.__name__] = count
            except Exception as e:
                stats['table_counts'][model.__name__] = f"Error: {str(e)}"
        
        return stats
        
    except Exception as e:
        models_logger.error(f"Error getting model statistics: {str(e)}")
        return {'error': str(e)}


# ====================================
# EXPORTACIONES PRINCIPALES
# ====================================

# Modelos base
__all__ = [
    # Base y mixins
    'BaseModel',
    'TimestampMixin',
    'AuditMixin', 
    'SoftDeleteMixin',
    'SearchableMixin',
    'CacheableMixin',
    'ExportableMixin',
    'NotifiableMixin',
    'ValidatableMixin',
    'StateMachineMixin',
    
    # Modelos de usuarios
    'User',
    'Admin',
    'Entrepreneur', 
    'Ally',
    'Client',
    
    # Modelos de negocio
    'Organization',
    'Program',
    'Project',
    'Mentorship',
    'Meeting',
    'Message',
    'Document',
    'Task',
    'Notification',
    'ActivityLog',
    'Analytics',
    
    # Asociaciones
    'user_organization_association',
    'project_tag_association',
    'meeting_participant_association', 
    'program_entrepreneur_association',
    
    # Utilidades
    'get_model_by_name',
    'get_all_models',
    'create_sample_data',
    'validate_database_schema',
    'optimize_database',
    'get_models_statistics',
    
    # Inicialización
    'init_models',
    'configure_database_events',
    'configure_model_events',
    'configure_search_indexes'
]

# Metadata del módulo
__version__ = '1.0.0'
__author__ = 'Ecosistema de Emprendimiento Team'
__description__ = 'Sistema completo de modelos de datos'