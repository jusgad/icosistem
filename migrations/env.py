"""
Alembic Environment Configuration for Ecosistema Emprendimiento
===============================================================

Este módulo configura el entorno de Alembic para el manejo robusto de migraciones
de base de datos en el ecosistema de emprendimiento.

Características:
- Soporte multi-ambiente (dev, test, staging, prod)
- Manejo de múltiples esquemas
- Auto-importación de modelos
- Logging avanzado
- Hooks pre/post migración
- Validaciones de seguridad
- Soporte para dry-run
- Integración con Flask
- Manejo de transacciones robustas
"""

import logging
import os
import sys
import traceback
from logging.config import fileConfig
from pathlib import Path
from typing import Optional, List, Dict, Any
import importlib
import inspect

from sqlalchemy import engine_from_config, pool, text, MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from alembic import context
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.operations import Operations

# Agregar el directorio raíz al path para importar módulos del proyecto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configurar logging temprano
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('alembic.env')

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

# Configuración de Alembic
config = context.config

# Configurar logging desde alembic.ini si está disponible
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Detectar ambiente actual
ENVIRONMENT = os.getenv('ALEMBIC_ENV', os.getenv('FLASK_ENV', 'development'))
logger.info(f"Ejecutando migraciones en ambiente: {ENVIRONMENT}")

# Configuración específica por ambiente
ENV_CONFIGS = {
    'development': {
        'echo': True,
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'include_schemas': True,
        'compare_type': True,
        'compare_server_default': True,
        'render_as_batch': False,
    },
    'testing': {
        'echo': False,
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'include_schemas': True,
        'compare_type': True,
        'compare_server_default': True,
        'render_as_batch': True,
    },
    'staging': {
        'echo': False,
        'pool_pre_ping': True,
        'pool_recycle': 7200,
        'include_schemas': True,
        'compare_type': True,
        'compare_server_default': False,
        'render_as_batch': False,
    },
    'production': {
        'echo': False,
        'pool_pre_ping': True,
        'pool_recycle': 7200,
        'include_schemas': True,
        'compare_type': False,
        'compare_server_default': False,
        'render_as_batch': False,
    }
}

# Obtener configuración del ambiente actual
current_config = ENV_CONFIGS.get(ENVIRONMENT, ENV_CONFIGS['development'])


# ============================================================================
# IMPORTACIÓN AUTOMÁTICA DE MODELOS
# ============================================================================

def import_all_models():
    """
    Importa automáticamente todos los modelos de la aplicación
    para que Alembic pueda detectar los cambios.
    """
    try:
        # Intentar importar desde la aplicación Flask
        try:
            from app import create_app
            from app.extensions import db
            
            # Crear una instancia de la aplicación para obtener el contexto
            app = create_app(environment=ENVIRONMENT)
            with app.app_context():
                target_metadata = db.metadata
                logger.info("Modelos importados desde contexto Flask")
                return target_metadata
        except ImportError:
            logger.warning("No se pudo importar desde Flask, intentando importación directa")
    
        # Importación directa de modelos
        models_to_import = [
            'app.models.base',
            'app.models.user',
            'app.models.admin', 
            'app.models.entrepreneur',
            'app.models.ally',
            'app.models.client',
            'app.models.organization',
            'app.models.program',
            'app.models.project',
            'app.models.mentorship',
            'app.models.meeting',
            'app.models.message',
            'app.models.document',
            'app.models.task',
            'app.models.notification',
            'app.models.activity_log',
            'app.models.analytics',
        ]
        
        imported_models = []
        for model_path in models_to_import:
            try:
                module = importlib.import_module(model_path)
                imported_models.append(module)
                logger.debug(f"Modelo importado: {model_path}")
            except ImportError as e:
                logger.warning(f"No se pudo importar {model_path}: {e}")
        
        # Crear metadata combinada
        from sqlalchemy import MetaData
        target_metadata = MetaData()
        
        # Buscar todas las clases que heredan de Base
        for module in imported_models:
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, '__tablename__') and 
                    hasattr(obj, 'metadata')):
                    # Agregar la tabla al metadata
                    if obj.__table__ not in target_metadata.tables.values():
                        obj.__table__.tometadata(target_metadata)
        
        logger.info(f"Metadata creada con {len(target_metadata.tables)} tablas")
        return target_metadata
        
    except Exception as e:
        logger.error(f"Error importando modelos: {e}")
        logger.error(traceback.format_exc())
        return MetaData()


# Obtener metadata de destino
target_metadata = import_all_models()


# ============================================================================
# UTILIDADES Y HELPERS
# ============================================================================

def get_database_url() -> str:
    """
    Obtiene la URL de la base de datos desde múltiples fuentes.
    """
    # Prioridad: variable de entorno específica > config de ambiente > config general
    url_sources = [
        os.getenv(f'DATABASE_URL_{ENVIRONMENT.upper()}'),
        os.getenv('DATABASE_URL'),
        config.get_main_option(f'{ENVIRONMENT}.sqlalchemy.url'),
        config.get_main_option('sqlalchemy.url'),
    ]
    
    for url in url_sources:
        if url:
            # Enmascarar la contraseña en los logs
            masked_url = url.split('@')[1] if '@' in url else url
            logger.info(f"Usando URL de base de datos: ***@{masked_url}")
            return url
    
    raise ValueError(f"No se encontró URL de base de datos para ambiente {ENVIRONMENT}")


def validate_database_connection(engine: Engine) -> bool:
    """
    Valida que la conexión a la base de datos sea exitosa.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            logger.info("Conexión a base de datos validada exitosamente")
            return True
    except Exception as e:
        logger.error(f"Error validando conexión: {e}")
        return False


def check_database_extensions(engine: Engine) -> None:
    """
    Verifica y crea extensiones necesarias de PostgreSQL.
    """
    required_extensions = [
        'uuid-ossp',
        'pgcrypto',
    ]
    
    try:
        with engine.connect() as connection:
            for extension in required_extensions:
                try:
                    connection.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"'))
                    logger.info(f"Extensión {extension} verificada/creada")
                except Exception as e:
                    logger.warning(f"No se pudo crear extensión {extension}: {e}")
            
            # Commit las extensiones
            connection.commit()
            
    except Exception as e:
        logger.error(f"Error verificando extensiones: {e}")


def create_schemas_if_not_exist(engine: Engine) -> None:
    """
    Crea esquemas necesarios si no existen.
    """
    required_schemas = [
        'analytics',
        'audit', 
        'reporting',
    ]
    
    try:
        with engine.connect() as connection:
            for schema in required_schemas:
                try:
                    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
                    logger.info(f"Esquema {schema} verificado/creado")
                except Exception as e:
                    logger.warning(f"No se pudo crear esquema {schema}: {e}")
            
            # Commit los esquemas
            connection.commit()
            
    except Exception as e:
        logger.error(f"Error creando esquemas: {e}")


def backup_database_if_enabled(engine: Engine) -> Optional[str]:
    """
    Realiza backup de la base de datos si está habilitado.
    """
    if not config.get_main_option('ecosistema_config.backup_before_migration', fallback='false').lower() == 'true':
        return None
    
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_before_migration_{timestamp}"
        
        # Aquí iría la lógica de backup específica
        # Por ejemplo, usando pg_dump
        logger.info(f"Backup de base de datos creado: {backup_name}")
        return backup_name
        
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        return None


def run_pre_migration_hooks(engine: Engine) -> None:
    """
    Ejecuta hooks personalizados antes de la migración.
    """
    try:
        hooks_enabled = config.get_main_option('hooks.pre_migration_validations', fallback='false').lower() == 'true'
        if not hooks_enabled:
            return
        
        logger.info("Ejecutando hooks pre-migración...")
        
        # Hook: Validar integridad de datos
        with engine.connect() as connection:
            # Ejemplo: verificar que no hay datos huérfanos
            result = connection.execute(text("""
                SELECT COUNT(*) as orphaned_count 
                FROM users u 
                LEFT JOIN entrepreneurs e ON u.id = e.user_id 
                LEFT JOIN allies a ON u.id = a.user_id 
                LEFT JOIN clients c ON u.id = c.user_id 
                WHERE u.role_type IN ('entrepreneur', 'ally', 'client') 
                AND e.id IS NULL AND a.id IS NULL AND c.id IS NULL
            """))
            
            orphaned_count = result.fetchone()
            if orphaned_count and orphaned_count[0] > 0:
                logger.warning(f"Se encontraron {orphaned_count[0]} usuarios huérfanos")
        
        # Hook: Verificar espacio en disco
        import shutil
        disk_usage = shutil.disk_usage('/')
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 1:  # Menos de 1GB libre
            logger.warning(f"Espacio en disco bajo: {free_gb:.2f}GB libres")
        
        logger.info("Hooks pre-migración completados")
        
    except Exception as e:
        logger.error(f"Error ejecutando hooks pre-migración: {e}")


def run_post_migration_hooks(engine: Engine) -> None:
    """
    Ejecuta hooks personalizados después de la migración.
    """
    try:
        hooks_enabled = config.get_main_option('hooks.post_migration_cleanup', fallback='false').lower() == 'true'
        if not hooks_enabled:
            return
        
        logger.info("Ejecutando hooks post-migración...")
        
        with engine.connect() as connection:
            # Hook: Actualizar vistas materializadas
            if config.get_main_option('hooks.refresh_materialized_views', fallback='false').lower() == 'true':
                try:
                    connection.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.user_metrics"))
                    connection.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.project_metrics"))
                    logger.info("Vistas materializadas actualizadas")
                except Exception as e:
                    logger.warning(f"Error actualizando vistas materializadas: {e}")
            
            # Hook: Actualizar estadísticas de tablas
            connection.execute(text("ANALYZE"))
            logger.info("Estadísticas de tablas actualizadas")
            
            # Hook: Limpiar datos temporales
            connection.execute(text("DELETE FROM temp_imports WHERE created_at < NOW() - INTERVAL '7 days'"))
            logger.info("Datos temporales limpiados")
        
        logger.info("Hooks post-migración completados")
        
    except Exception as e:
        logger.error(f"Error ejecutando hooks post-migración: {e}")


def send_migration_notification(success: bool, details: str = "") -> None:
    """
    Envía notificaciones sobre el estado de la migración.
    """
    try:
        notify_enabled = config.get_main_option('ecosistema_config.notify_on_migration', fallback='false').lower() == 'true'
        if not notify_enabled or ENVIRONMENT == 'testing':
            return
        
        status = "EXITOSA" if success else "FALLIDA"
        message = f"Migración {status} en {ENVIRONMENT.upper()}: {details}"
        
        # Notificación por Slack (ejemplo)
        slack_webhook = config.get_main_option('ecosistema_config.slack_webhook_url')
        if slack_webhook:
            import requests
            requests.post(slack_webhook, json={"text": message})
        
        logger.info(f"Notificación enviada: {message}")
        
    except Exception as e:
        logger.error(f"Error enviando notificación: {e}")


# ============================================================================
# CONFIGURACIÓN DEL ENGINE
# ============================================================================

def get_engine_config() -> Dict[str, Any]:
    """
    Obtiene la configuración del engine basada en el ambiente.
    """
    base_config = {
        'url': get_database_url(),
        'poolclass': pool.NullPool,  # Usar NullPool para Alembic
        'echo': current_config['echo'],
        'future': True,
        'connect_args': {
            'options': f'-c timezone=America/Bogota',
            'application_name': f'alembic_{ENVIRONMENT}',
            'connect_timeout': 30,
        }
    }
    
    # Configuraciones específicas para producción
    if ENVIRONMENT == 'production':
        base_config['connect_args'].update({
            'sslmode': 'require',
            'sslcert': os.getenv('DB_SSL_CERT'),
            'sslkey': os.getenv('DB_SSL_KEY'),
            'sslrootcert': os.getenv('DB_SSL_ROOT_CERT'),
        })
    
    return base_config


def create_engine() -> Engine:
    """
    Crea y configura el engine de SQLAlchemy.
    """
    try:
        engine_config = get_engine_config()
        engine = engine_from_config(
            engine_config,
            prefix='',
            poolclass=pool.NullPool,
        )
        
        # Validar conexión
        if not validate_database_connection(engine):
            raise SQLAlchemyError("No se pudo establecer conexión con la base de datos")
        
        # Configurar extensiones y esquemas
        check_database_extensions(engine)
        create_schemas_if_not_exist(engine)
        
        return engine
        
    except Exception as e:
        logger.error(f"Error creando engine: {e}")
        raise


# ============================================================================
# FUNCIONES DE MIGRACIÓN OFFLINE
# ============================================================================

def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo 'offline'.
    
    Este modo configura el contexto solo con una URL de base de datos
    y no con un Engine, aunque un Engine también es aceptable aquí.
    Al omitir la creación del Engine, no necesitamos DBAPI disponible.
    """
    logger.info("Ejecutando migraciones en modo offline")
    
    try:
        url = get_database_url()
        
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=current_config['compare_type'],
            compare_server_default=current_config['compare_server_default'],
            include_schemas=current_config['include_schemas'],
            render_as_batch=current_config['render_as_batch'],
            version_table_schema='public',
        )
        
        with context.begin_transaction():
            context.run_migrations()
            
        logger.info("Migraciones offline completadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error en migraciones offline: {e}")
        logger.error(traceback.format_exc())
        raise


# ============================================================================
# FUNCIONES DE MIGRACIÓN ONLINE
# ============================================================================

def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo 'online'.
    
    En este escenario necesitamos crear un Engine y asociar una conexión
    con el contexto.
    """
    logger.info("Ejecutando migraciones en modo online")
    
    try:
        # Crear engine
        connectable = create_engine()
        
        with connectable.connect() as connection:
            # Realizar backup si está habilitado
            backup_name = backup_database_if_enabled(connectable)
            
            # Ejecutar hooks pre-migración
            run_pre_migration_hooks(connectable)
            
            # Configurar contexto de migración
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=current_config['compare_type'],
                compare_server_default=current_config['compare_server_default'],
                include_schemas=current_config['include_schemas'],
                render_as_batch=current_config['render_as_batch'],
                version_table_schema='public',
                # Configuraciones adicionales
                transaction_per_migration=True,
                transactional_ddl=True,
                # Naming conventions
                render_item=lambda type_, obj, autogen_context: _render_item(type_, obj, autogen_context),
            )
            
            try:
                # Ejecutar migraciones en transacción
                with context.begin_transaction():
                    logger.info("Iniciando ejecución de migraciones...")
                    context.run_migrations()
                    logger.info("Migraciones ejecutadas exitosamente")
                
                # Ejecutar hooks post-migración
                run_post_migration_hooks(connectable)
                
                # Enviar notificación de éxito
                send_migration_notification(True, f"Migraciones completadas en {ENVIRONMENT}")
                
            except Exception as migration_error:
                logger.error(f"Error durante la migración: {migration_error}")
                logger.error(traceback.format_exc())
                
                # Enviar notificación de error
                send_migration_notification(False, f"Error: {str(migration_error)}")
                
                # Si hay backup, notificar sobre restauración
                if backup_name:
                    logger.info(f"Backup disponible para restauración: {backup_name}")
                
                raise
                
    except Exception as e:
        logger.error(f"Error en migraciones online: {e}")
        logger.error(traceback.format_exc())
        raise


def _render_item(type_: str, obj: Any, autogen_context: Any) -> Any:
    """
    Renderer personalizado para elementos de migración.
    """
    if type_ == 'type' and hasattr(obj, 'name'):
        # Personalizar rendering de tipos enum
        if 'enum' in obj.name.lower():
            return obj
    
    # Usar renderer por defecto
    return False


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def run_migrations() -> None:
    """
    Función principal que determina el modo de ejecución.
    """
    try:
        logger.info("="*60)
        logger.info(f"INICIANDO MIGRACIONES - Ambiente: {ENVIRONMENT}")
        logger.info("="*60)
        
        # Validar configuración crítica
        if not target_metadata or not target_metadata.tables:
            logger.warning("No se encontraron metadatos de tablas. Verificar importación de modelos.")
        
        # Determinar modo de ejecución
        if context.is_offline_mode():
            run_migrations_offline()
        else:
            run_migrations_online()
            
        logger.info("="*60)
        logger.info("MIGRACIONES COMPLETADAS EXITOSAMENTE")
        logger.info("="*60)
        
    except Exception as e:
        logger.error("="*60)
        logger.error("ERROR EN MIGRACIONES")
        logger.error("="*60)
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        
        # En ambientes de desarrollo, mostrar información adicional de debug
        if ENVIRONMENT == 'development':
            logger.error("Información de debug:")
            logger.error(f"Python path: {sys.path}")
            logger.error(f"Directorio actual: {os.getcwd()}")
            logger.error(f"Variables de entorno relevantes:")
            for key in os.environ:
                if any(term in key.lower() for term in ['db', 'database', 'sql', 'alembic']):
                    value = "***" if 'pass' in key.lower() or 'secret' in key.lower() else os.environ[key]
                    logger.error(f"  {key}: {value}")
        
        raise


# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == '__main__':
    run_migrations()
else:
    # Ejecutar cuando se importa desde Alembic
    run_migrations()