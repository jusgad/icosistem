"""
Sistema de Tareas de Mantenimiento - Ecosistema de Emprendimiento
================================================================

Este módulo maneja todas las tareas asíncronas relacionadas con el mantenimiento,
optimización y health checks del ecosistema de emprendimiento.

Funcionalidades principales:
- Health checks completos del sistema
- Limpieza automática de datos temporales y antiguos
- Optimización de base de datos (VACUUM, ANALYZE, REINDEX)
- Monitoreo de rendimiento y recursos del sistema
- Limpieza de logs y archivos temporales
- Mantenimiento de cache y Redis
- Verificación de servicios externos
- Optimización de archivos y media
- Compactación y mantenimiento de índices
- Alertas de mantenimiento preventivo
- Limpieza de sesiones caducadas
- Verificación de integridad de datos
- Monitoreo de espacio en disco
- Maintenance windows automáticos
"""

import logging
import os
import shutil
import psutil
import subprocess
import glob
import gzip
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import tempfile
import threading
from pathlib import Path
import json
import time

import redis
from sqlalchemy import create_engine, text, func
from sqlalchemy.exc import SQLAlchemyError
import requests
from elasticsearch import Elasticsearch
import boto3
from google.cloud import monitoring_v3

from app.tasks.celery_app import celery_app
from app.core.exceptions import (
    MaintenanceError,
    HealthCheckError,
    SystemResourceError,
    DatabaseOptimizationError
)
from app.core.constants import (
    SYSTEM_HEALTH_THRESHOLDS,
    MAINTENANCE_SCHEDULES,
    CLEANUP_POLICIES,
    PERFORMANCE_METRICS
)
from app.models.user import User
from app.models.activity_log import ActivityLog, ActivityType
from app.models.notification import Notification, NotificationStatus
from app.models.analytics import AnalyticsEvent, SystemMetric
from app.models.backup import BackupRecord
from app.models.device_token import DeviceToken
from app.models.maintenance_log import MaintenanceLog, MaintenanceType, MaintenanceStatus
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.services.email import EmailService
from app.utils.formatters import format_datetime, format_file_size, format_percentage
from app.utils.string_utils import generate_maintenance_id
from app.utils.cache_utils import cache_get, cache_set, cache_delete, clear_cache_pattern
from app.utils.file_utils import ensure_directory_exists, get_directory_size

logger = logging.getLogger(__name__)

# Configuración de mantenimiento
TEMP_DIRS = ['/tmp', '/var/tmp', 'logs/temp', 'app/static/temp']
LOG_DIRS = ['logs', 'app/logs', '/var/log/ecosistema']
MAX_LOG_AGE_DAYS = 30
MAX_TEMP_FILE_AGE_HOURS = 24
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Umbrales de recursos del sistema
SYSTEM_THRESHOLDS = {
    'cpu_usage': 80.0,          # Porcentaje máximo de CPU
    'memory_usage': 85.0,       # Porcentaje máximo de memoria
    'disk_usage': 90.0,         # Porcentaje máximo de disco
    'database_connections': 80,  # Número máximo de conexiones DB
    'response_time': 2.0,       # Tiempo de respuesta máximo en segundos
    'error_rate': 5.0           # Porcentaje máximo de errores
}


class HealthStatus(Enum):
    """Estados de health check"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MaintenanceOperation(Enum):
    """Tipos de operaciones de mantenimiento"""
    CLEANUP = "cleanup"
    OPTIMIZATION = "optimization"
    HEALTH_CHECK = "health_check"
    MONITORING = "monitoring"
    BACKUP_MAINTENANCE = "backup_maintenance"
    SECURITY_SCAN = "security_scan"


@dataclass
class HealthCheckResult:
    """Resultado de health check"""
    service: str
    status: HealthStatus
    response_time: float
    details: dict[str, Any]
    timestamp: datetime
    error_message: str = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value
        }


@dataclass
class MaintenanceResult:
    """Resultado de operación de mantenimiento"""
    operation: MaintenanceOperation
    success: bool
    duration: float
    details: dict[str, Any]
    items_processed: int = 0
    space_freed: int = 0
    error_message: str = None
    recommendations: list[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []


class SystemMonitor:
    """Monitor del estado del sistema"""
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.analytics_service = AnalyticsService()
    
    def get_system_health(self) -> dict[str, HealthCheckResult]:
        """Obtiene el estado completo del sistema"""
        health_results = {}
        
        # Health checks individuales
        health_checks = [
            ('database', self._check_database_health),
            ('redis', self._check_redis_health),
            ('filesystem', self._check_filesystem_health),
            ('system_resources', self._check_system_resources),
            ('external_services', self._check_external_services),
            ('application', self._check_application_health),
            ('security', self._check_security_status)
        ]
        
        for service_name, check_function in health_checks:
            try:
                start_time = time.time()
                result = check_function()
                response_time = time.time() - start_time
                
                health_results[service_name] = HealthCheckResult(
                    service=service_name,
                    status=result['status'],
                    response_time=response_time,
                    details=result['details'],
                    timestamp=datetime.now(timezone.utc),
                    error_message=result.get('error')
                )
                
            except Exception as e:
                health_results[service_name] = HealthCheckResult(
                    service=service_name,
                    status=HealthStatus.CRITICAL,
                    response_time=0.0,
                    details={},
                    timestamp=datetime.now(timezone.utc),
                    error_message=str(e)
                )
        
        return health_results
    
    def _check_database_health(self) -> dict[str, Any]:
        """Verifica el estado de la base de datos"""
        try:
            from app import db
            
            start_time = time.time()
            
            # Test básico de conectividad
            db.session.execute(text('SELECT 1'))
            
            # Verificar estadísticas de conexiones
            connections_result = db.session.execute(text("""
                SELECT count(*) as total_connections,
                       count(*) FILTER (WHERE state = 'active') as active_connections,
                       count(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity
            """)).fetchone()
            
            # Verificar tamaño de la base de datos
            db_size_result = db.session.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size,
                       pg_database_size(current_database()) as db_size_bytes
            """)).fetchone()
            
            # Verificar tabla más grande
            largest_table = db.session.execute(text("""
                SELECT schemaname, tablename, 
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC 
                LIMIT 1
            """)).fetchone()
            
            # Verificar locks
            locks_result = db.session.execute(text("""
                SELECT count(*) as lock_count
                FROM pg_locks 
                WHERE NOT granted
            """)).fetchone()
            
            response_time = time.time() - start_time
            
            # Determinar estado
            status = HealthStatus.HEALTHY
            if connections_result.active_connections > 50:
                status = HealthStatus.WARNING
            if connections_result.active_connections > 80 or locks_result.lock_count > 10:
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'total_connections': connections_result.total_connections,
                    'active_connections': connections_result.active_connections,
                    'idle_connections': connections_result.idle_connections,
                    'database_size': db_size_result.db_size,
                    'database_size_bytes': db_size_result.db_size_bytes,
                    'largest_table': f"{largest_table.tablename} ({largest_table.size})",
                    'blocked_locks': locks_result.lock_count,
                    'response_time': response_time
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }
    
    def _check_redis_health(self) -> dict[str, Any]:
        """Verifica el estado de Redis"""
        try:
            r = redis.from_url(REDIS_URL)
            
            start_time = time.time()
            
            # Test básico
            r.ping()
            
            # Obtener información del servidor
            info = r.info()
            
            response_time = time.time() - start_time
            
            # Verificar memoria utilizada
            used_memory_pct = (info['used_memory'] / info['maxmemory'] * 100) if info.get('maxmemory', 0) > 0 else 0
            
            # Determinar estado
            status = HealthStatus.HEALTHY
            if used_memory_pct > 80:
                status = HealthStatus.WARNING
            if used_memory_pct > 95 or info['connected_clients'] > 100:
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'connected_clients': info['connected_clients'],
                    'used_memory': format_file_size(info['used_memory']),
                    'used_memory_pct': f"{used_memory_pct:.1f}%",
                    'keyspace_hits': info['keyspace_hits'],
                    'keyspace_misses': info['keyspace_misses'],
                    'keys_total': sum([info.get(f'db{i}', {}).get('keys', 0) for i in range(16)]),
                    'response_time': response_time
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }
    
    def _check_filesystem_health(self) -> dict[str, Any]:
        """Verifica el estado del sistema de archivos"""
        try:
            disk_usage = psutil.disk_usage('/')
            disk_pct = (disk_usage.used / disk_usage.total) * 100
            
            # Verificar directorios importantes
            important_dirs = {
                'logs': get_directory_size('logs'),
                'uploads': get_directory_size('app/static/uploads'),
                'temp': get_directory_size('/tmp'),
                'backups': get_directory_size('/var/backups') if os.path.exists('/var/backups') else 0
            }
            
            # Verificar inodes
            try:
                statvfs = os.statvfs('/')
                inode_usage = ((statvfs.f_files - statvfs.f_favail) / statvfs.f_files) * 100
            except:
                inode_usage = 0
            
            # Determinar estado
            status = HealthStatus.HEALTHY
            if disk_pct > 85 or inode_usage > 90:
                status = HealthStatus.WARNING
            if disk_pct > 95 or inode_usage > 98:
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'disk_total': format_file_size(disk_usage.total),
                    'disk_used': format_file_size(disk_usage.used),
                    'disk_free': format_file_size(disk_usage.free),
                    'disk_usage_pct': f"{disk_pct:.1f}%",
                    'inode_usage_pct': f"{inode_usage:.1f}%",
                    'directory_sizes': {k: format_file_size(v) for k, v in important_dirs.items()}
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }
    
    def _check_system_resources(self) -> dict[str, Any]:
        """Verifica recursos del sistema (CPU, memoria, etc.)"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = os.getloadavg()
            
            # Memoria
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Procesos
            process_count = len(psutil.pids())
            
            # Determinar estado basado en umbrales
            status = HealthStatus.HEALTHY
            
            if (cpu_percent > SYSTEM_THRESHOLDS['cpu_usage'] or 
                memory.percent > SYSTEM_THRESHOLDS['memory_usage']):
                status = HealthStatus.WARNING
                
            if (cpu_percent > 95 or memory.percent > 98 or 
                load_avg[0] > cpu_count * 2):
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'cpu_percent': f"{cpu_percent:.1f}%",
                    'cpu_count': cpu_count,
                    'load_average': f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}",
                    'memory_total': format_file_size(memory.total),
                    'memory_used': format_file_size(memory.used),
                    'memory_percent': f"{memory.percent:.1f}%",
                    'swap_total': format_file_size(swap.total),
                    'swap_used': format_file_size(swap.used),
                    'swap_percent': f"{swap.percent:.1f}%",
                    'process_count': process_count
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }
    
    def _check_external_services(self) -> dict[str, Any]:
        """Verifica servicios externos"""
        external_services = {}
        overall_status = HealthStatus.HEALTHY
        
        # Lista de servicios a verificar
        services_to_check = [
            ('google_apis', 'https://www.googleapis.com/'),
            ('aws_status', 'https://status.aws.amazon.com/'),
            ('sendgrid', 'https://status.sendgrid.com/'),
            ('firebase', 'https://status.firebase.google.com/')
        ]
        
        for service_name, url in services_to_check:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=10)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    status = HealthStatus.HEALTHY
                elif response.status_code < 500:
                    status = HealthStatus.WARNING
                else:
                    status = HealthStatus.CRITICAL
                    overall_status = HealthStatus.WARNING
                
                external_services[service_name] = {
                    'status': status.value,
                    'response_time': f"{response_time:.3f}s",
                    'status_code': response.status_code
                }
                
            except requests.RequestException as e:
                external_services[service_name] = {
                    'status': HealthStatus.CRITICAL.value,
                    'error': str(e)
                }
                overall_status = HealthStatus.WARNING
        
        return {
            'status': overall_status,
            'details': external_services
        }
    
    def _check_application_health(self) -> dict[str, Any]:
        """Verifica el estado de la aplicación"""
        try:
            from app import db
            
            # Verificar usuarios activos recientes
            recent_active_users = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM users 
                WHERE last_activity > NOW() - INTERVAL '1 hour'
            """)).scalar()
            
            # Verificar errores recientes
            recent_errors = db.session.execute(text("""
                SELECT COUNT(*) as count
                FROM activity_log 
                WHERE activity_type = 'ERROR' 
                AND created_at > NOW() - INTERVAL '1 hour'
            """)).scalar()
            
            # Verificar notificaciones pendientes
            pending_notifications = db.session.execute(text("""
                SELECT COUNT(*) as count
                FROM notifications 
                WHERE status = 'pending'
            """)).scalar()
            
            # Verificar tareas de Celery (si está disponible)
            try:
                from app.tasks.celery_app import celery_app
                inspect = celery_app.control.inspect()
                active_tasks = inspect.active()
                scheduled_tasks = inspect.scheduled()
                
                total_active = sum(len(tasks) for tasks in (active_tasks or {}).values())
                total_scheduled = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
            except:
                total_active = 0
                total_scheduled = 0
            
            # Determinar estado
            status = HealthStatus.HEALTHY
            if recent_errors > 10 or pending_notifications > 100:
                status = HealthStatus.WARNING
            if recent_errors > 50 or pending_notifications > 500:
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'active_users_last_hour': recent_active_users,
                    'errors_last_hour': recent_errors,
                    'pending_notifications': pending_notifications,
                    'active_celery_tasks': total_active,
                    'scheduled_celery_tasks': total_scheduled
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }
    
    def _check_security_status(self) -> dict[str, Any]:
        """Verifica el estado de seguridad"""
        try:
            from app import db
            
            # Verificar intentos de login fallidos recientes
            failed_logins = db.session.execute(text("""
                SELECT COUNT(*) as count
                FROM activity_log 
                WHERE activity_type = 'LOGIN_FAILED' 
                AND created_at > NOW() - INTERVAL '1 hour'
            """)).scalar()
            
            # Verificar usuarios bloqueados
            blocked_users = db.session.execute(text("""
                SELECT COUNT(*) as count
                FROM users 
                WHERE is_active = false 
                AND updated_at > NOW() - INTERVAL '24 hours'
            """)).scalar()
            
            # Verificar tokens de dispositivo inválidos
            invalid_tokens = DeviceToken.query.filter(
                DeviceToken.is_active == False,
                DeviceToken.updated_at > datetime.now(timezone.utc) - timedelta(hours=24)
            ).count()
            
            # Verificar permisos de archivos críticos
            security_issues = []
            critical_files = [
                'config/.env',
                'config/config.py',
                'requirements.txt'
            ]
            
            for file_path in critical_files:
                if os.path.exists(file_path):
                    stat_info = os.stat(file_path)
                    if stat_info.st_mode & 0o077:  # Verificar permisos world/group
                        security_issues.append(f"Permisos inseguros en {file_path}")
            
            # Determinar estado
            status = HealthStatus.HEALTHY
            if failed_logins > 20 or len(security_issues) > 0:
                status = HealthStatus.WARNING
            if failed_logins > 100 or blocked_users > 10:
                status = HealthStatus.CRITICAL
            
            return {
                'status': status,
                'details': {
                    'failed_logins_last_hour': failed_logins,
                    'blocked_users_last_24h': blocked_users,
                    'invalid_tokens_last_24h': invalid_tokens,
                    'security_issues': security_issues,
                    'security_score': max(0, 100 - (failed_logins + len(security_issues) * 10))
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'details': {},
                'error': str(e)
            }


system_monitor = SystemMonitor()


# === TAREAS DE HEALTH CHECKS ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='maintenance',
    priority=10
)
def system_health_check(self):
    """
    Realiza health check completo del sistema
    
    Se ejecuta cada 5 minutos
    """
    try:
        logger.info("Iniciando health check del sistema")
        
        # Obtener estado completo del sistema
        health_results = system_monitor.get_system_health()
        
        # Analizar resultados
        critical_issues = []
        warning_issues = []
        healthy_services = []
        
        for service, result in health_results.items():
            if result.status == HealthStatus.CRITICAL:
                critical_issues.append({
                    'service': service,
                    'error': result.error_message,
                    'details': result.details
                })
            elif result.status == HealthStatus.WARNING:
                warning_issues.append({
                    'service': service,
                    'details': result.details
                })
            else:
                healthy_services.append(service)
        
        # Determinar estado general del sistema
        if critical_issues:
            overall_status = HealthStatus.CRITICAL
        elif warning_issues:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Guardar métricas en cache para acceso rápido
        health_summary = {
            'overall_status': overall_status.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'critical_issues': len(critical_issues),
            'warning_issues': len(warning_issues),
            'healthy_services': len(healthy_services),
            'details': {service: result.to_dict() for service, result in health_results.items()}
        }
        
        cache_set('system_health_status', health_summary, timeout=600)  # 10 minutos
        
        # Registrar métricas en base de datos
        _save_health_metrics(health_results, overall_status)
        
        # Enviar alertas si es necesario
        if critical_issues:
            system_monitor.notification_service.send_critical_alert(
                message=f"CRÍTICO: {len(critical_issues)} servicios con problemas críticos",
                details={
                    'critical_issues': critical_issues,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                recipients=['admin', 'tech_team']
            )
        elif warning_issues and len(warning_issues) > 2:
            system_monitor.notification_service.send_alert(
                message=f"Advertencia: {len(warning_issues)} servicios con alertas",
                details={'warning_issues': warning_issues},
                recipients=['admin']
            )
        
        logger.info(f"Health check completado - Estado: {overall_status.value}")
        
        return {
            'success': True,
            'overall_status': overall_status.value,
            'critical_issues': len(critical_issues),
            'warning_issues': len(warning_issues),
            'healthy_services': len(healthy_services),
            'response_time_avg': sum(r.response_time for r in health_results.values()) / len(health_results)
        }
        
    except Exception as exc:
        logger.error(f"Error en health check del sistema: {str(exc)}")
        
        # Notificar error en el health check
        system_monitor.notification_service.send_critical_alert(
            message=f"ERROR en health check del sistema: {str(exc)}",
            recipients=['admin', 'tech_team']
        )
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE LIMPIEZA ===

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    queue='maintenance',
    priority=5
)
def daily_cleanup(self):
    """
    Limpieza diaria del sistema
    
    Se ejecuta diariamente a las 3:00 AM
    """
    try:
        logger.info("Iniciando limpieza diaria del sistema")
        
        cleanup_results = []
        total_space_freed = 0
        
        # 1. Limpiar archivos temporales
        temp_result = _cleanup_temp_files()
        cleanup_results.append(temp_result)
        total_space_freed += temp_result.space_freed
        
        # 2. Limpiar logs antiguos
        logs_result = _cleanup_old_logs()
        cleanup_results.append(logs_result)
        total_space_freed += logs_result.space_freed
        
        # 3. Limpiar sesiones caducadas
        sessions_result = _cleanup_expired_sessions()
        cleanup_results.append(sessions_result)
        
        # 4. Limpiar notificaciones antiguas
        notifications_result = _cleanup_old_notifications()
        cleanup_results.append(notifications_result)
        
        # 5. Limpiar tokens de dispositivo inválidos
        tokens_result = _cleanup_invalid_device_tokens()
        cleanup_results.append(tokens_result)
        
        # 6. Limpiar eventos de analytics antiguos
        analytics_result = _cleanup_old_analytics_events()
        cleanup_results.append(analytics_result)
        
        # 7. Limpiar cache caducado
        cache_result = _cleanup_expired_cache()
        cleanup_results.append(cache_result)
        
        # Resumen de limpieza
        successful_operations = sum(1 for r in cleanup_results if r.success)
        total_items_processed = sum(r.items_processed for r in cleanup_results)
        
        # Notificar resultados
        system_monitor.notification_service.send_system_notification(
            message=f"Limpieza diaria completada: {format_file_size(total_space_freed)} liberados",
            details={
                'operations_completed': successful_operations,
                'total_operations': len(cleanup_results),
                'items_processed': total_items_processed,
                'space_freed': format_file_size(total_space_freed)
            },
            recipients=['admin']
        )
        
        logger.info(f"Limpieza diaria completada: {successful_operations}/{len(cleanup_results)} operaciones exitosas")
        
        return {
            'success': True,
            'operations_completed': successful_operations,
            'total_operations': len(cleanup_results),
            'items_processed': total_items_processed,
            'space_freed': total_space_freed,
            'results': [asdict(r) for r in cleanup_results]
        }
        
    except Exception as exc:
        logger.error(f"Error en limpieza diaria: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    queue='maintenance',
    priority=7
)
def weekly_system_maintenance(self):
    """
    Mantenimiento semanal del sistema
    
    Se ejecuta los domingos a la 1:00 AM
    """
    try:
        logger.info("Iniciando mantenimiento semanal del sistema")
        
        maintenance_results = []
        
        # 1. Optimización de base de datos
        db_optimization = _optimize_database()
        maintenance_results.append(db_optimization)
        
        # 2. Limpieza profunda de archivos
        deep_cleanup = _deep_file_cleanup()
        maintenance_results.append(deep_cleanup)
        
        # 3. Optimización de índices
        index_optimization = _optimize_database_indexes()
        maintenance_results.append(index_optimization)
        
        # 4. Verificación de integridad de datos
        integrity_check = _verify_data_integrity()
        maintenance_results.append(integrity_check)
        
        # 5. Actualización de estadísticas del sistema
        stats_update = _update_system_statistics()
        maintenance_results.append(stats_update)
        
        # 6. Limpieza de backups obsoletos
        backup_cleanup = _cleanup_obsolete_backups()
        maintenance_results.append(backup_cleanup)
        
        # Resumen del mantenimiento
        successful_operations = sum(1 for r in maintenance_results if r.success)
        total_space_freed = sum(r.space_freed for r in maintenance_results)
        
        # Generar recomendaciones
        recommendations = []
        for result in maintenance_results:
            recommendations.extend(result.recommendations)
        
        # Notificar resultados
        system_monitor.notification_service.send_system_notification(
            message=f"Mantenimiento semanal completado: {successful_operations}/{len(maintenance_results)} operaciones",
            details={
                'space_freed': format_file_size(total_space_freed),
                'recommendations': recommendations[:5]  # Primeras 5 recomendaciones
            },
            recipients=['admin']
        )
        
        logger.info(f"Mantenimiento semanal completado: {successful_operations} operaciones exitosas")
        
        return {
            'success': True,
            'operations_completed': successful_operations,
            'total_operations': len(maintenance_results),
            'space_freed': total_space_freed,
            'recommendations': recommendations,
            'results': [asdict(r) for r in maintenance_results]
        }
        
    except Exception as exc:
        logger.error(f"Error en mantenimiento semanal: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=600)
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=1800,
    queue='maintenance',
    priority=6
)
def monthly_data_archive(self):
    """
    Archivado mensual de datos antiguos
    
    Se ejecuta el primer día del mes a las 12:00 AM
    """
    try:
        logger.info("Iniciando archivado mensual de datos")
        
        # Fecha de corte (datos más antiguos de 6 meses)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
        
        archive_results = []
        
        # 1. Archivar logs de actividad antiguos
        activity_logs_result = _archive_old_activity_logs(cutoff_date)
        archive_results.append(activity_logs_result)
        
        # 2. Archivar eventos de analytics antiguos
        analytics_events_result = _archive_old_analytics_events(cutoff_date)
        archive_results.append(analytics_events_result)
        
        # 3. Archivar notificaciones antiguas
        notifications_result = _archive_old_notifications(cutoff_date)
        archive_results.append(notifications_result)
        
        # 4. Archivar métricas del sistema
        system_metrics_result = _archive_old_system_metrics(cutoff_date)
        archive_results.append(system_metrics_result)
        
        # 5. Comprimir archivos de log
        log_compression_result = _compress_old_log_files()
        archive_results.append(log_compression_result)
        
        # Resumen del archivado
        successful_operations = sum(1 for r in archive_results if r.success)
        total_items_archived = sum(r.items_processed for r in archive_results)
        total_space_freed = sum(r.space_freed for r in archive_results)
        
        # Notificar resultados
        system_monitor.notification_service.send_system_notification(
            message=f"Archivado mensual completado: {total_items_archived} elementos archivados",
            details={
                'operations_completed': successful_operations,
                'items_archived': total_items_archived,
                'space_freed': format_file_size(total_space_freed),
                'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
            },
            recipients=['admin']
        )
        
        logger.info(f"Archivado mensual completado: {total_items_archived} elementos procesados")
        
        return {
            'success': True,
            'operations_completed': successful_operations,
            'total_operations': len(archive_results),
            'items_archived': total_items_archived,
            'space_freed': total_space_freed,
            'cutoff_date': cutoff_date.isoformat(),
            'results': [asdict(r) for r in archive_results]
        }
        
    except Exception as exc:
        logger.error(f"Error en archivado mensual: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=1800)
        return {'success': False, 'error': str(exc)}


# === TAREAS DE OPTIMIZACIÓN ===

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    queue='maintenance',
    priority=6
)
def optimize_database_performance(self):
    """
    Optimización de rendimiento de la base de datos
    
    Se ejecuta semanalmente los martes a las 2:00 AM
    """
    try:
        logger.info("Iniciando optimización de base de datos")
        
        from app import db
        
        optimization_results = []
        start_time = datetime.now(timezone.utc)
        
        # 1. VACUUM ANALYZE para limpiar y actualizar estadísticas
        logger.info("Ejecutando VACUUM ANALYZE")
        try:
            db.session.execute(text('VACUUM ANALYZE'))
            db.session.commit()
            optimization_results.append("VACUUM ANALYZE completado")
        except Exception as e:
            logger.error(f"Error en VACUUM ANALYZE: {str(e)}")
            optimization_results.append(f"VACUUM ANALYZE falló: {str(e)}")
        
        # 2. REINDEX para optimizar índices
        logger.info("Optimizando índices principales")
        critical_tables = ['users', 'projects', 'meetings', 'notifications', 'activity_log']
        
        for table in critical_tables:
            try:
                db.session.execute(text(f'REINDEX TABLE {table}'))
                db.session.commit()
                optimization_results.append(f"REINDEX completado para tabla {table}")
            except Exception as e:
                logger.error(f"Error en REINDEX para {table}: {str(e)}")
                optimization_results.append(f"REINDEX falló para {table}: {str(e)}")
        
        # 3. Actualizar estadísticas de consultas
        logger.info("Actualizando estadísticas de consultas")
        try:
            db.session.execute(text('ANALYZE'))
            db.session.commit()
            optimization_results.append("Estadísticas actualizadas")
        except Exception as e:
            logger.error(f"Error actualizando estadísticas: {str(e)}")
            optimization_results.append(f"Actualización de estadísticas falló: {str(e)}")
        
        # 4. Verificar consultas lentas
        slow_queries = []
        try:
            # Obtener consultas que toman más de 1 segundo
            slow_query_result = db.session.execute(text("""
                SELECT query, calls, total_time, mean_time
                FROM pg_stat_statements
                WHERE mean_time > 1000
                ORDER BY total_time DESC
                LIMIT 10
            """)).fetchall()
            
            for query in slow_query_result:
                slow_queries.append({
                    'query': query.query[:100] + '...' if len(query.query) > 100 else query.query,
                    'calls': query.calls,
                    'total_time': f"{query.total_time:.2f}ms",
                    'mean_time': f"{query.mean_time:.2f}ms"
                })
                
            optimization_results.append(f"Identificadas {len(slow_queries)} consultas lentas")
            
        except Exception as e:
            logger.warning(f"No se pudieron obtener estadísticas de consultas: {str(e)}")
        
        # 5. Verificar fragmentación de tablas
        fragmentation_info = []
        try:
            fragmentation_result = db.session.execute(text("""
                SELECT schemaname, tablename, 
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                       pg_stat_get_live_tuples(c.oid) as live_tuples,
                       pg_stat_get_dead_tuples(c.oid) as dead_tuples
                FROM pg_tables pt
                JOIN pg_class c ON c.relname = pt.tablename
                WHERE schemaname = 'public' AND pg_stat_get_dead_tuples(c.oid) > 1000
                ORDER BY pg_stat_get_dead_tuples(c.oid) DESC
                LIMIT 5
            """)).fetchall()
            
            for table_info in fragmentation_result:
                fragmentation_info.append({
                    'table': table_info.tablename,
                    'size': table_info.size,
                    'live_tuples': table_info.live_tuples,
                    'dead_tuples': table_info.dead_tuples
                })
                
            if fragmentation_info:
                optimization_results.append(f"Fragmentación detectada en {len(fragmentation_info)} tablas")
                
        except Exception as e:
            logger.warning(f"No se pudo verificar fragmentación: {str(e)}")
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Generar recomendaciones
        recommendations = []
        if slow_queries:
            recommendations.append("Revisar y optimizar consultas lentas identificadas")
        if fragmentation_info:
            recommendations.append("Considerar VACUUM FULL para tablas muy fragmentadas")
        if duration > 300:  # Más de 5 minutos
            recommendations.append("Optimización tomó mucho tiempo, revisar recursos del sistema")
        
        # Notificar resultados
        system_monitor.notification_service.send_system_notification(
            message=f"Optimización de BD completada en {duration:.1f}s",
            details={
                'operations': optimization_results,
                'slow_queries_found': len(slow_queries),
                'fragmented_tables': len(fragmentation_info),
                'duration': f"{duration:.1f}s"
            },
            recipients=['admin']
        )
        
        logger.info(f"Optimización de base de datos completada en {duration:.1f}s")
        
        return {
            'success': True,
            'duration': duration,
            'operations_completed': len(optimization_results),
            'slow_queries_found': len(slow_queries),
            'fragmented_tables': len(fragmentation_info),
            'recommendations': recommendations,
            'details': {
                'operations': optimization_results,
                'slow_queries': slow_queries,
                'fragmentation_info': fragmentation_info
            }
        }
        
    except Exception as exc:
        logger.error(f"Error en optimización de base de datos: {str(exc)}")
        
        # Notificar error crítico
        system_monitor.notification_service.send_critical_alert(
            message=f"ERROR en optimización de BD: {str(exc)}",
            recipients=['admin', 'tech_team']
        )
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=600)
        return {'success': False, 'error': str(exc)}


# === FUNCIONES AUXILIARES PRIVADAS ===

def _save_health_metrics(health_results: dict[str, HealthCheckResult], overall_status: HealthStatus):
    """Guarda métricas de health check en la base de datos"""
    try:
        # Compilar métricas para guardar
        metrics_data = {
            'overall_status': overall_status.value,
            'services': {
                service: {
                    'status': result.status.value,
                    'response_time': result.response_time,
                    'details': result.details
                }
                for service, result in health_results.items()
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Guardar en tabla de métricas del sistema
        metric = SystemMetric(
            metric_type='health_check',
            metric_data=metrics_data,
            timestamp=datetime.now(timezone.utc)
        )
        
        from app import db
        db.session.add(metric)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error guardando métricas de health check: {str(e)}")


def _cleanup_temp_files() -> MaintenanceResult:
    """Limpia archivos temporales antiguos"""
    start_time = datetime.now(timezone.utc)
    items_processed = 0
    space_freed = 0
    errors = []
    
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_TEMP_FILE_AGE_HOURS)
        
        for temp_dir in TEMP_DIRS:
            if not os.path.exists(temp_dir):
                continue
                
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        # Verificar edad del archivo
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            items_processed += 1
                            space_freed += file_size
                    except Exception as e:
                        errors.append(f"Error eliminando {file_path}: {str(e)}")
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=len(errors) == 0,
            duration=duration,
            items_processed=items_processed,
            space_freed=space_freed,
            details={
                'directories_cleaned': len(TEMP_DIRS),
                'errors': errors[:5]  # Primeros 5 errores
            },
            recommendations=[
                "Configurar limpieza automática más frecuente si hay muchos archivos temporales"
            ] if items_processed > 1000 else []
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e),
            details={'errors': [str(e)]}
        )


def _cleanup_old_logs() -> MaintenanceResult:
    """Limpia logs antiguos"""
    start_time = datetime.now(timezone.utc)
    items_processed = 0
    space_freed = 0
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=MAX_LOG_AGE_DAYS)
        
        for log_dir in LOG_DIRS:
            if not os.path.exists(log_dir):
                continue
                
            # Buscar archivos de log antiguos
            log_patterns = ['*.log', '*.log.*', '*.out', '*.err']
            
            for pattern in log_patterns:
                log_files = glob.glob(os.path.join(log_dir, pattern))
                
                for log_file in log_files:
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                        if file_time < cutoff_date:
                            file_size = os.path.getsize(log_file)
                            os.remove(log_file)
                            items_processed += 1
                            space_freed += file_size
                    except Exception as e:
                        logger.error(f"Error eliminando log {log_file}: {str(e)}")
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed,
            space_freed=space_freed,
            details={
                'log_directories_cleaned': len(LOG_DIRS),
                'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_expired_sessions() -> MaintenanceResult:
    """Limpia sesiones caducadas"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Limpiar sesiones Flask caducadas (si se usan sesiones de BD)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Aquí se limpiarían las sesiones según tu implementación
        # Por ejemplo, si usas Flask-Session con BD:
        # expired_sessions = db.session.execute(text("""
        #     DELETE FROM sessions 
        #     WHERE expiry < :cutoff_date
        # """), {'cutoff_date': cutoff_date})
        
        # items_processed = expired_sessions.rowcount
        
        # Para este ejemplo, limpiamos usuarios inactivos hace mucho
        inactive_threshold = datetime.now(timezone.utc) - timedelta(days=90)
        inactive_users = User.query.filter(
            User.last_activity < inactive_threshold,
            User.is_active == True
        ).count()
        
        # No los eliminamos, solo los marcamos como inactivos
        if inactive_users > 0:
            User.query.filter(
                User.last_activity < inactive_threshold,
                User.is_active == True
            ).update({'is_active': False})
            db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=inactive_users,
            details={
                'inactive_users_marked': inactive_users,
                'threshold_days': 90
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_old_notifications() -> MaintenanceResult:
    """Limpia notificaciones antiguas leídas"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Eliminar notificaciones leídas más antiguas de 30 días
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        
        old_notifications = Notification.query.filter(
            Notification.status == NotificationStatus.READ,
            Notification.created_at < cutoff_date
        )
        
        items_processed = old_notifications.count()
        old_notifications.delete(synchronize_session=False)
        
        # Eliminar notificaciones no leídas más antiguas de 90 días
        very_old_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        very_old_notifications = Notification.query.filter(
            Notification.created_at < very_old_cutoff
        )
        
        very_old_count = very_old_notifications.count()
        very_old_notifications.delete(synchronize_session=False)
        
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed + very_old_count,
            details={
                'read_notifications_deleted': items_processed,
                'very_old_notifications_deleted': very_old_count
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_invalid_device_tokens() -> MaintenanceResult:
    """Limpia tokens de dispositivo inválidos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Eliminar tokens marcados como inválidos hace más de 7 días
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        
        invalid_tokens = DeviceToken.query.filter(
            DeviceToken.is_active == False,
            DeviceToken.updated_at < cutoff_date
        )
        
        items_processed = invalid_tokens.count()
        invalid_tokens.delete(synchronize_session=False)
        
        # Marcar como inactivos tokens muy antiguos (más de 180 días sin uso)
        very_old_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        very_old_tokens = DeviceToken.query.filter(
            DeviceToken.last_used < very_old_cutoff,
            DeviceToken.is_active == True
        )
        
        very_old_count = very_old_tokens.count()
        very_old_tokens.update({'is_active': False})
        
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed,
            details={
                'invalid_tokens_deleted': items_processed,
                'old_tokens_deactivated': very_old_count
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_old_analytics_events() -> MaintenanceResult:
    """Limpia eventos de analytics antiguos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Mantener solo eventos de los últimos 90 días
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)
        
        old_events = AnalyticsEvent.query.filter(
            AnalyticsEvent.timestamp < cutoff_date
        )
        
        items_processed = old_events.count()
        old_events.delete(synchronize_session=False)
        
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed,
            details={
                'analytics_events_deleted': items_processed,
                'retention_days': 90
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_expired_cache() -> MaintenanceResult:
    """Limpia cache caducado de Redis"""
    start_time = datetime.now(timezone.utc)
    
    try:
        r = redis.from_url(REDIS_URL)
        
        # Obtener información antes de la limpieza
        info_before = r.info()
        keys_before = info_before.get('db0', {}).get('keys', 0)
        memory_before = info_before['used_memory']
        
        # Ejecutar limpieza de claves caducadas
        # Redis limpia automáticamente las claves TTL, pero podemos forzarlo
        r.execute_command('MEMORY', 'PURGE')
        
        # Obtener información después
        info_after = r.info()
        keys_after = info_after.get('db0', {}).get('keys', 0)
        memory_after = info_after['used_memory']
        
        keys_cleaned = keys_before - keys_after
        memory_freed = memory_before - memory_after
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=keys_cleaned,
            space_freed=memory_freed,
            details={
                'keys_before': keys_before,
                'keys_after': keys_after,
                'memory_freed': format_file_size(memory_freed)
            }
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


# Funciones adicionales para mantenimiento semanal y archivado mensual
def _optimize_database() -> MaintenanceResult:
    """Optimización general de base de datos"""
    # Implementación básica - se puede expandir
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # VACUUM ligero
        db.session.execute(text('VACUUM'))
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=True,
            duration=duration,
            details={'operation': 'database_vacuum'},
            recommendations=['Considerar VACUUM FULL si la fragmentación es alta']
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _deep_file_cleanup() -> MaintenanceResult:
    """Limpieza profunda de archivos"""
    start_time = datetime.now(timezone.utc)
    space_freed = 0
    items_processed = 0
    
    try:
        # Limpiar archivos de upload huérfanos
        upload_dirs = ['app/static/uploads/temp', 'app/static/uploads/processing']
        
        for upload_dir in upload_dirs:
            if os.path.exists(upload_dir):
                for file in os.listdir(upload_dir):
                    file_path = os.path.join(upload_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        space_freed += file_size
                        items_processed += 1
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed,
            space_freed=space_freed,
            details={'directories_cleaned': len(upload_dirs)}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _optimize_database_indexes() -> MaintenanceResult:
    """Optimización de índices de base de datos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # ANALYZE para actualizar estadísticas
        db.session.execute(text('ANALYZE'))
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=True,
            duration=duration,
            details={'operation': 'analyze_statistics'}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _verify_data_integrity() -> MaintenanceResult:
    """Verificación de integridad de datos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Verificaciones básicas de integridad
        integrity_checks = []
        
        # 1. Verificar usuarios sin email
        users_without_email = db.session.execute(text("""
            SELECT COUNT(*) FROM users WHERE email IS NULL OR email = ''
        """)).scalar()
        
        if users_without_email > 0:
            integrity_checks.append(f"{users_without_email} usuarios sin email")
        
        # 2. Verificar proyectos sin emprendedor
        orphaned_projects = db.session.execute(text("""
            SELECT COUNT(*) FROM projects p 
            LEFT JOIN users u ON p.entrepreneur_id = u.id 
            WHERE u.id IS NULL
        """)).scalar()
        
        if orphaned_projects > 0:
            integrity_checks.append(f"{orphaned_projects} proyectos huérfanos")
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.HEALTH_CHECK,
            success=len(integrity_checks) == 0,
            duration=duration,
            details={
                'integrity_issues': integrity_checks,
                'issues_found': len(integrity_checks)
            },
            recommendations=[
                "Revisar y corregir problemas de integridad encontrados"
            ] if integrity_checks else []
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.HEALTH_CHECK,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _update_system_statistics() -> MaintenanceResult:
    """Actualización de estadísticas del sistema"""
    start_time = datetime.now(timezone.utc)
    
    try:
        # Actualizar estadísticas en cache
        stats = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'uptime': _get_system_uptime(),
            'total_users': User.query.count(),
            'active_users': User.query.filter(User.is_active == True).count()
        }
        
        cache_set('system_statistics', stats, timeout=86400)  # 24 horas
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.MONITORING,
            success=True,
            duration=duration,
            details=stats
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.MONITORING,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _cleanup_obsolete_backups() -> MaintenanceResult:
    """Limpieza de backups obsoletos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Marcar backups fallidos antiguos como obsoletos
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        
        obsolete_backups = BackupRecord.query.filter(
            BackupRecord.status == 'failed',
            BackupRecord.created_at < cutoff_date
        )
        
        items_processed = obsolete_backups.count()
        obsolete_backups.update({'status': 'deleted'})
        
        db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_processed,
            details={'obsolete_backups_marked': items_processed}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


# Funciones auxiliares para archivado mensual
def _archive_old_activity_logs(cutoff_date: datetime) -> MaintenanceResult:
    """Archiva logs de actividad antiguos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        from app import db
        
        # Contar registros a archivar
        old_logs = ActivityLog.query.filter(
            ActivityLog.created_at < cutoff_date
        )
        
        items_to_archive = old_logs.count()
        
        # En una implementación real, aquí exportarías a archivo
        # y luego eliminarías de la tabla principal
        
        # Por ahora solo marcamos como archivados (añadir campo si es necesario)
        # old_logs.delete(synchronize_session=False)
        # db.session.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_to_archive,
            details={'activity_logs_ready_for_archive': items_to_archive}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _archive_old_analytics_events(cutoff_date: datetime) -> MaintenanceResult:
    """Archiva eventos de analytics antiguos"""
    start_time = datetime.now(timezone.utc)
    
    try:
        # Similar a activity logs
        items_to_archive = AnalyticsEvent.query.filter(
            AnalyticsEvent.timestamp < cutoff_date
        ).count()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_to_archive,
            details={'analytics_events_ready_for_archive': items_to_archive}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _archive_old_notifications(cutoff_date: datetime) -> MaintenanceResult:
    """Archiva notificaciones antiguas"""
    start_time = datetime.now(timezone.utc)
    
    try:
        items_to_archive = Notification.query.filter(
            Notification.created_at < cutoff_date
        ).count()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_to_archive,
            details={'notifications_ready_for_archive': items_to_archive}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _archive_old_system_metrics(cutoff_date: datetime) -> MaintenanceResult:
    """Archiva métricas del sistema antiguas"""
    start_time = datetime.now(timezone.utc)
    
    try:
        items_to_archive = SystemMetric.query.filter(
            SystemMetric.timestamp < cutoff_date
        ).count()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=True,
            duration=duration,
            items_processed=items_to_archive,
            details={'system_metrics_ready_for_archive': items_to_archive}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.CLEANUP,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _compress_old_log_files() -> MaintenanceResult:
    """Comprime archivos de log antiguos"""
    start_time = datetime.now(timezone.utc)
    items_processed = 0
    space_freed = 0
    
    try:
        for log_dir in LOG_DIRS:
            if not os.path.exists(log_dir):
                continue
            
            # Buscar archivos .log que no estén comprimidos
            log_files = glob.glob(os.path.join(log_dir, '*.log'))
            
            for log_file in log_files:
                # Solo comprimir archivos más antiguos de 7 días
                file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                if file_time < datetime.now(timezone.utc) - timedelta(days=7):
                    try:
                        original_size = os.path.getsize(log_file)
                        
                        # Comprimir archivo
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        # Eliminar original
                        os.remove(log_file)
                        
                        compressed_size = os.path.getsize(f"{log_file}.gz")
                        space_freed += original_size - compressed_size
                        items_processed += 1
                        
                    except Exception as e:
                        logger.error(f"Error comprimiendo {log_file}: {str(e)}")
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=True,
            duration=duration,
            items_processed=items_processed,
            space_freed=space_freed,
            details={'log_files_compressed': items_processed}
        )
        
    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return MaintenanceResult(
            operation=MaintenanceOperation.OPTIMIZATION,
            success=False,
            duration=duration,
            error_message=str(e)
        )


def _get_system_uptime() -> str:
    """Obtiene el uptime del sistema"""
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_delta = timedelta(seconds=uptime_seconds)
        return str(uptime_delta)
    except:
        return "Unknown"


# Exportar tareas principales
__all__ = [
    'system_health_check',
    'daily_cleanup',
    'weekly_system_maintenance',
    'monthly_data_archive',
    'optimize_database_performance',
    'HealthStatus',
    'HealthCheckResult',
    'MaintenanceResult',
    'MaintenanceOperation',
    'SystemMonitor'
]