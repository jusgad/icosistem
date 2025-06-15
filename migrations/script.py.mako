"""
${message}

Ecosistema de Emprendimiento - Database Migration
================================================

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
Migration Type: ${'Auto-generated' if up_revision else 'Manual'}
Author: ${author if author else 'Sistema Automático'}
Environment: ${environment if environment else 'development'}

Description:
${message}

Schema Changes Summary:
- Tables: ${tables_modified if tables_modified else 'TBD'}
- Columns: ${columns_modified if columns_modified else 'TBD'}  
- Indexes: ${indexes_modified if indexes_modified else 'TBD'}
- Constraints: ${constraints_modified if constraints_modified else 'TBD'}

Migration Safety Level: ${'HIGH' if 'DROP' in message.upper() or 'DELETE' in message.upper() else 'MEDIUM' if 'ALTER' in message.upper() else 'LOW'}

Prerequisites:
- Database backup completed: ${backup_required if backup_required else 'No'}
- Downtime required: ${downtime_required if downtime_required else 'No'}
- Data migration needed: ${data_migration if data_migration else 'No'}

Post-Migration Tasks:
- Update application cache: ${clear_cache if clear_cache else 'No'}
- Restart services: ${restart_services if restart_services else 'No'}
- Run data validation: ${validate_data if validate_data else 'No'}

Rollback Instructions:
- This migration CAN be rolled back safely
- Estimated rollback time: ${rollback_time if rollback_time else '< 1 minute'}
- Data loss potential: ${data_loss_risk if data_loss_risk else 'None'}

Contact Information:
- Technical Lead: devops@ecosistema.com
- Database Admin: dba@ecosistema.com
- Emergency Contact: oncall@ecosistema.com

"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
${imports if imports else ""}

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

# Configurar logger específico para esta migración
logger = logging.getLogger(f'alembic.migration.${up_revision}')
logger.setLevel(logging.INFO)

# Handler para consola si no existe
if not logger.handlers:
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ============================================================================
# METADATA DE LA MIGRACIÓN
# ============================================================================

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

# Migration metadata
migration_info = {
    'id': revision,
    'description': ${repr(message)},
    'created_at': '${create_date}',
    'author': '${author if author else "Sistema Automático"}',
    'environment': os.getenv('ALEMBIC_ENV', 'development'),
    'safety_level': '${'HIGH' if 'DROP' in message.upper() or 'DELETE' in message.upper() else 'MEDIUM' if 'ALTER' in message.upper() else 'LOW'}',
}

# Configuración específica de la migración
MIGRATION_CONFIG = {
    'requires_backup': ${str('DROP' in message.upper() or 'DELETE' in message.upper()).lower()},
    'requires_downtime': ${str('ADD COLUMN' not in message.upper() and 'ALTER' in message.upper()).lower()},
    'batch_size': 1000,
    'timeout_seconds': 300,
    'validate_data_integrity': True,
    'clear_cache_after': ${str('INDEX' in message.upper() or 'CONSTRAINT' in message.upper()).lower()},
}


# ============================================================================
# UTILIDADES DE MIGRACIÓN
# ============================================================================

def get_connection() -> Connection:
    """Obtiene la conexión actual de Alembic."""
    return op.get_bind()


def log_migration_start(operation: str) -> None:
    """Registra el inicio de una operación de migración."""
    logger.info(f"="*60)
    logger.info(f"INICIANDO {operation.upper()} - Migración {revision}")
    logger.info(f"Descripción: ${message}")
    logger.info(f"Ambiente: {migration_info['environment']}")
    logger.info(f"Nivel de seguridad: {migration_info['safety_level']}")
    logger.info(f"="*60)


def log_migration_end(operation: str, success: bool = True) -> None:
    """Registra el final de una operación de migración."""
    status = "COMPLETADO" if success else "FALLIDO"
    logger.info(f"="*60)
    logger.info(f"{operation.upper()} {status} - Migración {revision}")
    logger.info(f"Tiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"="*60)


def validate_prerequisites() -> bool:
    """
    Valida que se cumplan todos los prerequisitos antes de la migración.
    """
    try:
        logger.info("Validando prerequisitos de migración...")
        
        connection = get_connection()
        
        # Validar conexión a base de datos
        result = connection.execute(text("SELECT 1"))
        result.fetchone()
        logger.info("✓ Conexión a base de datos validada")
        
        # Validar que no hay procesos bloqueantes
        locks_query = text("""
            SELECT count(*) as lock_count 
            FROM pg_locks l 
            JOIN pg_stat_activity a ON l.pid = a.pid 
            WHERE l.granted = false
        """)
        result = connection.execute(locks_query)
        lock_count = result.fetchone()[0]
        
        if lock_count > 0:
            logger.warning(f"Se detectaron {lock_count} bloqueos en la base de datos")
            
        logger.info("✓ Prerequisitos validados exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error validando prerequisitos: {e}")
        return False


def validate_data_integrity_pre() -> bool:
    """
    Valida la integridad de los datos antes de la migración.
    """
    try:
        logger.info("Validando integridad de datos pre-migración...")
        
        connection = get_connection()
        
        # Validar constraints principales
        constraints_query = text("""
            SELECT 
                conname as constraint_name,
                contype as constraint_type,
                conrelid::regclass as table_name
            FROM pg_constraint 
            WHERE contype IN ('f', 'c', 'u', 'p')
            AND NOT convalidated
        """)
        
        result = connection.execute(constraints_query)
        invalid_constraints = result.fetchall()
        
        if invalid_constraints:
            logger.warning(f"Se encontraron {len(invalid_constraints)} constraints no validados")
            for constraint in invalid_constraints:
                logger.warning(f"  - {constraint.constraint_name} en {constraint.table_name}")
        else:
            logger.info("✓ Todos los constraints están validados")
        
        # Validar integridad referencial básica (ejemplo para el ecosistema)
        orphan_checks = [
            ("Usuarios huérfanos", """
                SELECT COUNT(*) FROM users u 
                LEFT JOIN entrepreneurs e ON u.id = e.user_id 
                LEFT JOIN allies a ON u.id = a.user_id 
                LEFT JOIN clients c ON u.id = c.user_id 
                WHERE u.role_type IN ('entrepreneur', 'ally', 'client') 
                AND e.id IS NULL AND a.id IS NULL AND c.id IS NULL
            """),
            ("Proyectos sin emprendedor", """
                SELECT COUNT(*) FROM projects p 
                LEFT JOIN entrepreneurs e ON p.entrepreneur_id = e.id 
                WHERE e.id IS NULL
            """),
            ("Reuniones sin participantes", """
                SELECT COUNT(*) FROM meetings m 
                LEFT JOIN meeting_participants mp ON m.id = mp.meeting_id 
                WHERE mp.id IS NULL
            """),
        ]
        
        for check_name, query in orphan_checks:
            try:
                result = connection.execute(text(query))
                count = result.fetchone()[0]
                if count > 0:
                    logger.warning(f"  - {check_name}: {count} registros")
                else:
                    logger.info(f"✓ {check_name}: OK")
            except Exception as e:
                logger.warning(f"No se pudo ejecutar validación '{check_name}': {e}")
        
        logger.info("✓ Validación de integridad completada")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error validando integridad de datos: {e}")
        return False


def validate_data_integrity_post() -> bool:
    """
    Valida la integridad de los datos después de la migración.
    """
    try:
        logger.info("Validando integridad de datos post-migración...")
        
        connection = get_connection()
        
        # Verificar que no se perdieron datos críticos
        critical_tables = ['users', 'entrepreneurs', 'allies', 'clients', 'projects']
        
        for table in critical_tables:
            try:
                result = connection.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                logger.info(f"✓ Tabla {table}: {count} registros")
            except Exception as e:
                logger.error(f"✗ Error verificando tabla {table}: {e}")
                return False
        
        # Ejecutar ANALYZE para actualizar estadísticas
        connection.execute(text("ANALYZE"))
        logger.info("✓ Estadísticas de tablas actualizadas")
        
        logger.info("✓ Validación post-migración completada")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error en validación post-migración: {e}")
        return False


def backup_critical_data() -> Optional[str]:
    """
    Realiza backup de datos críticos antes de operaciones peligrosas.
    """
    if not MIGRATION_CONFIG['requires_backup']:
        return None
        
    try:
        logger.info("Realizando backup de datos críticos...")
        
        connection = get_connection()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_schema = f"backup_{timestamp}"
        
        # Crear schema de backup
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {backup_schema}"))
        
        # Tablas críticas a respaldar
        critical_tables = ['users', 'entrepreneurs', 'allies', 'projects', 'meetings']
        
        for table in critical_tables:
            try:
                backup_table = f"{backup_schema}.{table}_backup"
                connection.execute(text(f"""
                    CREATE TABLE {backup_table} AS 
                    SELECT * FROM {table}
                """))
                logger.info(f"✓ Backup creado: {backup_table}")
            except Exception as e:
                logger.warning(f"No se pudo respaldar {table}: {e}")
        
        logger.info(f"✓ Backup completado en schema: {backup_schema}")
        return backup_schema
        
    except Exception as e:
        logger.error(f"✗ Error creando backup: {e}")
        return None


def cleanup_backup(backup_schema: Optional[str]) -> None:
    """
    Limpia el backup temporal después de una migración exitosa.
    """
    if not backup_schema:
        return
        
    try:
        # En producción, mantener backups por más tiempo
        env = migration_info['environment']
        if env == 'production':
            logger.info(f"Manteniendo backup {backup_schema} para producción")
            return
            
        connection = get_connection()
        connection.execute(text(f"DROP SCHEMA IF EXISTS {backup_schema} CASCADE"))
        logger.info(f"✓ Backup temporal {backup_schema} eliminado")
        
    except Exception as e:
        logger.warning(f"No se pudo limpiar backup {backup_schema}: {e}")


def execute_with_retry(operation_func, max_retries: int = 3, delay: int = 1) -> bool:
    """
    Ejecuta una operación con reintentos en caso de error.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            operation_func()
            return True
        except Exception as e:
            logger.warning(f"Intento {attempt + 1}/{max_retries} falló: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # Backoff exponencial
            else:
                logger.error(f"Operación falló después de {max_retries} intentos")
                raise
    return False


def clear_application_cache() -> None:
    """
    Limpia caché de aplicación si es necesario.
    """
    if not MIGRATION_CONFIG['clear_cache_after']:
        return
        
    try:
        logger.info("Limpiando caché de aplicación...")
        
        connection = get_connection()
        
        # Limpiar cache de sesiones si existe
        try:
            connection.execute(text("DELETE FROM cache_data WHERE expires_at < NOW()"))
            logger.info("✓ Cache de datos limpiado")
        except Exception:
            pass  # La tabla podría no existir
        
        # Invalidar cache de aplicación (Redis, Memcached, etc.)
        # Aquí se integraría con el sistema de cache específico
        
        logger.info("✓ Cache de aplicación limpiado")
        
    except Exception as e:
        logger.warning(f"Error limpiando cache: {e}")


def send_migration_notification(operation: str, success: bool, details: str = "") -> None:
    """
    Envía notificación sobre el estado de la migración.
    """
    try:
        env = migration_info['environment']
        if env == 'testing':
            return  # No enviar notificaciones en testing
            
        status = "EXITOSA" if success else "FALLIDA"
        message = f"""
🔄 Migración {operation.upper()} {status}

📋 **Detalles:**
- Revision: `{revision}`
- Ambiente: `{env.upper()}`
- Descripción: ${message}
- Tiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{details}
        """
        
        # Aquí se integraría con Slack, Teams, email, etc.
        logger.info(f"Notificación: {message.strip()}")
        
    except Exception as e:
        logger.warning(f"Error enviando notificación: {e}")


# ============================================================================
# FUNCIÓN DE UPGRADE
# ============================================================================

def upgrade() -> None:
    """
    Ejecuta la migración hacia adelante (upgrade).
    
    Esta función contiene todas las operaciones DDL para actualizar
    la base de datos a la nueva versión del esquema.
    """
    backup_schema = None
    
    try:
        log_migration_start("UPGRADE")
        
        # 1. Validar prerequisitos
        if not validate_prerequisites():
            raise Exception("Prerequisitos no cumplidos")
        
        # 2. Validar integridad pre-migración
        if MIGRATION_CONFIG['validate_data_integrity']:
            if not validate_data_integrity_pre():
                logger.warning("Advertencias en validación de integridad pre-migración")
        
        # 3. Crear backup si es necesario
        backup_schema = backup_critical_data()
        
        # 4. Ejecutar operaciones de migración
        logger.info("Ejecutando operaciones de migración...")
        
        # ====================================================================
        # OPERACIONES DE MIGRACIÓN - GENERADAS AUTOMÁTICAMENTE
        # ====================================================================
        ${upgrades if upgrades else "# TODO: Agregar operaciones de migración"}
        
        # Ejemplo de operaciones comunes:
        # 
        # # Crear nueva tabla
        # op.create_table('nueva_tabla',
        #     sa.Column('id', sa.Integer, primary_key=True),
        #     sa.Column('nombre', sa.String(255), nullable=False),
        #     sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        # )
        # 
        # # Agregar columna
        # op.add_column('tabla_existente', 
        #     sa.Column('nueva_columna', sa.String(100), nullable=True)
        # )
        # 
        # # Crear índice
        # op.create_index('idx_tabla_columna', 'tabla', ['columna'])
        # 
        # # Agregar constraint
        # op.create_foreign_key('fk_tabla_referencia', 'tabla', 'referencia', 
        #                      ['referencia_id'], ['id'])
        
        logger.info("✓ Operaciones de migración completadas")
        
        # 5. Validar integridad post-migración
        if MIGRATION_CONFIG['validate_data_integrity']:
            if not validate_data_integrity_post():
                raise Exception("Fallo en validación de integridad post-migración")
        
        # 6. Limpiar cache si es necesario
        clear_application_cache()
        
        # 7. Limpiar backup temporal
        cleanup_backup(backup_schema)
        
        # 8. Enviar notificación de éxito
        send_migration_notification("upgrade", True, 
            f"✅ Migración aplicada exitosamente en {migration_info['environment']}")
        
        log_migration_end("UPGRADE", True)
        
    except Exception as e:
        logger.error(f"✗ Error durante upgrade: {e}")
        
        # Mantener backup en caso de error
        if backup_schema:
            logger.info(f"Backup preservado para recuperación: {backup_schema}")
        
        # Enviar notificación de error
        send_migration_notification("upgrade", False, 
            f"❌ Error: {str(e)}\n💾 Backup disponible: {backup_schema or 'No'}")
        
        log_migration_end("UPGRADE", False)
        raise


# ============================================================================
# FUNCIÓN DE DOWNGRADE
# ============================================================================

def downgrade() -> None:
    """
    Ejecuta la migración hacia atrás (downgrade/rollback).
    
    Esta función revierte todas las operaciones realizadas en upgrade()
    para restaurar la base de datos al estado anterior.
    """
    backup_schema = None
    
    try:
        log_migration_start("DOWNGRADE")
        
        # 1. Validar prerequisitos
        if not validate_prerequisites():
            raise Exception("Prerequisitos no cumplidos para rollback")
        
        # 2. Advertencia especial para rollback en producción
        env = migration_info['environment']
        if env == 'production':
            logger.warning("⚠️  ROLLBACK EN PRODUCCIÓN - Procediendo con precaución")
        
        # 3. Validar integridad pre-rollback
        if MIGRATION_CONFIG['validate_data_integrity']:
            if not validate_data_integrity_pre():
                logger.warning("Advertencias en validación pre-rollback")
        
        # 4. Crear backup antes del rollback
        backup_schema = backup_critical_data()
        
        # 5. Ejecutar operaciones de rollback
        logger.info("Ejecutando operaciones de rollback...")
        
        # ====================================================================
        # OPERACIONES DE ROLLBACK - ORDEN INVERSO AL UPGRADE
        # ====================================================================
        ${downgrades if downgrades else "# TODO: Agregar operaciones de rollback"}
        
        # Ejemplo de operaciones de rollback (orden inverso):
        # 
        # # Eliminar constraint
        # op.drop_constraint('fk_tabla_referencia', 'tabla', type_='foreignkey')
        # 
        # # Eliminar índice
        # op.drop_index('idx_tabla_columna')
        # 
        # # Eliminar columna
        # op.drop_column('tabla_existente', 'nueva_columna')
        # 
        # # Eliminar tabla
        # op.drop_table('nueva_tabla')
        
        logger.info("✓ Operaciones de rollback completadas")
        
        # 6. Validar integridad post-rollback
        if MIGRATION_CONFIG['validate_data_integrity']:
            if not validate_data_integrity_post():
                raise Exception("Fallo en validación de integridad post-rollback")
        
        # 7. Limpiar cache
        clear_application_cache()
        
        # 8. Limpiar backup temporal
        cleanup_backup(backup_schema)
        
        # 9. Enviar notificación de éxito
        send_migration_notification("downgrade", True, 
            f"↩️ Rollback ejecutado exitosamente en {migration_info['environment']}")
        
        log_migration_end("DOWNGRADE", True)
        
    except Exception as e:
        logger.error(f"✗ Error durante downgrade: {e}")
        
        # Mantener backup en caso de error
        if backup_schema:
            logger.info(f"Backup preservado para recuperación: {backup_schema}")
        
        # Enviar notificación de error crítico
        send_migration_notification("downgrade", False, 
            f"🚨 ERROR CRÍTICO EN ROLLBACK: {str(e)}\n💾 Backup: {backup_schema or 'No'}\n📞 Contactar DBA inmediatamente")
        
        log_migration_end("DOWNGRADE", False)
        raise


# ============================================================================
# FUNCIONES AUXILIARES ESPECÍFICAS DEL ECOSISTEMA
# ============================================================================

def migrate_user_data_batch(batch_size: int = 1000) -> None:
    """
    Migra datos de usuarios en lotes para operaciones grandes.
    """
    connection = get_connection()
    
    # Obtener total de registros
    result = connection.execute(text("SELECT COUNT(*) FROM users"))
    total_users = result.fetchone()[0]
    
    logger.info(f"Migrando {total_users} usuarios en lotes de {batch_size}")
    
    offset = 0
    while offset < total_users:
        # Procesar lote
        logger.info(f"Procesando lote {offset//batch_size + 1}: registros {offset}-{offset+batch_size}")
        
        # Aquí iría la lógica específica de migración de datos
        # Por ejemplo:
        # connection.execute(text(f"""
        #     UPDATE users 
        #     SET new_column = old_column 
        #     WHERE id IN (
        #         SELECT id FROM users 
        #         ORDER BY id 
        #         LIMIT {batch_size} OFFSET {offset}
        #     )
        # """))
        
        offset += batch_size


def update_entrepreneur_metrics() -> None:
    """
    Actualiza métricas de emprendedores después de cambios estructurales.
    """
    try:
        connection = get_connection()
        
        # Actualizar métricas agregadas
        connection.execute(text("""
            INSERT INTO analytics.entrepreneur_metrics (entrepreneur_id, metric_date, projects_count, meetings_count)
            SELECT 
                e.id,
                CURRENT_DATE,
                COUNT(DISTINCT p.id),
                COUNT(DISTINCT m.id)
            FROM entrepreneurs e
            LEFT JOIN projects p ON e.id = p.entrepreneur_id
            LEFT JOIN meetings m ON e.user_id = m.created_by
            GROUP BY e.id
            ON CONFLICT (entrepreneur_id, metric_date) 
            DO UPDATE SET 
                projects_count = EXCLUDED.projects_count,
                meetings_count = EXCLUDED.meetings_count,
                updated_at = NOW()
        """))
        
        logger.info("✓ Métricas de emprendedores actualizadas")
        
    except Exception as e:
        logger.warning(f"Error actualizando métricas de emprendedores: {e}")


def refresh_materialized_views() -> None:
    """
    Actualiza vistas materializadas del ecosistema.
    """
    materialized_views = [
        'analytics.user_activity_summary',
        'analytics.project_status_overview', 
        'analytics.monthly_metrics',
        'reporting.entrepreneur_performance',
    ]
    
    connection = get_connection()
    
    for view in materialized_views:
        try:
            connection.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            logger.info(f"✓ Vista materializada actualizada: {view}")
        except Exception as e:
            logger.warning(f"Error actualizando vista {view}: {e}")


# ============================================================================
# METADATA FINAL
# ============================================================================

# Información adicional para auditoria
__migration_metadata__ = {
    'revision': revision,
    'description': ${repr(message)},
    'created_at': '${create_date}',
    'file_template_version': '2.1.0',
    'ecosistema_version': '1.0.0',
    'safety_checks_enabled': True,
    'auto_backup_enabled': MIGRATION_CONFIG['requires_backup'],
    'notifications_enabled': True,
}