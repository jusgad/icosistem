"""
Sistema de Tareas Asíncronas - Ecosistema de Emprendimiento
==========================================================

Este módulo inicializa y configura el sistema completo de tareas asíncronas
usando Celery para el ecosistema de emprendimiento. Proporciona procesamiento
en background para operaciones pesadas, notificaciones, análisis y mantenimiento.

Funcionalidades principales:
- Configuración y inicialización de Celery
- Registro automático de tareas
- Sistema de colas con prioridades
- Monitoreo y métricas de tareas
- Retry policies y manejo de errores
- Scheduling de tareas periódicas
- Task routing y load balancing
- Integración con Flask y base de datos
"""

import logging
import os
import inspect
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from functools import wraps
from collections import defaultdict

from celery import Celery, Task, group, chain, chord
from celery.signals import (
    task_prerun, task_postrun, task_failure, task_success,
    worker_ready, worker_shutdown, beat_init
)
from celery.schedules import crontab
from kombu import Queue, Exchange
from flask import Flask, current_app

from app.core.exceptions import TaskError, TaskRetryError, TaskTimeoutError
from app.core.constants import TASK_PRIORITIES, QUEUE_NAMES, RETRY_POLICIES
from app.services.analytics_service import AnalyticsService
from app.services.notification_service import NotificationService
from app.utils.formatters import format_datetime
from app.utils.cache_utils import cache_set, cache_get, cache_delete

logger = logging.getLogger(__name__)

# Instancia global de Celery
celery: Optional[Celery] = None

# Registro de tareas y métricas
task_registry: Dict[str, Dict[str, Any]] = {}
task_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    'total_runs': 0,
    'successful_runs': 0,
    'failed_runs': 0,
    'average_runtime': 0.0,
    'last_run': None,
    'last_success': None,
    'last_failure': None
})

# Configuración de colas con prioridades
CELERY_QUEUES = [
    # Cola de alta prioridad para tareas críticas
    Queue('high_priority', Exchange('high_priority'), routing_key='high_priority',
          queue_arguments={'x-max-priority': 10}),
    
    # Cola normal para tareas estándar
    Queue('normal', Exchange('normal'), routing_key='normal',
          queue_arguments={'x-max-priority': 5}),
    
    # Cola de baja prioridad para tareas en background
    Queue('low_priority', Exchange('low_priority'), routing_key='low_priority',
          queue_arguments={'x-max-priority': 1}),
    
    # Colas especializadas
    Queue('emails', Exchange('emails'), routing_key='emails'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications'),
    Queue('analytics', Exchange('analytics'), routing_key='analytics'),
    Queue('reports', Exchange('reports'), routing_key='reports'),
    Queue('maintenance', Exchange('maintenance'), routing_key='maintenance'),
    Queue('backups', Exchange('backups'), routing_key='backups'),
]

# Configuración de scheduling para tareas periódicas
CELERY_BEAT_SCHEDULE = {
    # Tareas diarias
    'daily-analytics-report': {
        'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM
        'options': {'queue': 'analytics', 'priority': 7}
    },
    
    'daily-backup': {
        'task': 'app.tasks.backup_tasks.daily_database_backup',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM
        'options': {'queue': 'backups', 'priority': 8}
    },
    
    'daily-cleanup': {
        'task': 'app.tasks.maintenance_tasks.daily_cleanup',
        'schedule': crontab(hour=3, minute=0),  # 3:00 AM
        'options': {'queue': 'maintenance', 'priority': 6}
    },
    
    # Tareas semanales
    'weekly-entrepreneur-report': {
        'task': 'app.tasks.analytics_tasks.generate_weekly_entrepreneur_report',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Lunes 8:00 AM
        'options': {'queue': 'reports', 'priority': 6}
    },
    
    'weekly-mentor-summary': {
        'task': 'app.tasks.analytics_tasks.generate_weekly_mentor_summary',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Lunes 9:00 AM
        'options': {'queue': 'reports', 'priority': 6}
    },
    
    # Tareas mensuales
    'monthly-ecosystem-report': {
        'task': 'app.tasks.analytics_tasks.generate_monthly_ecosystem_report',
        'schedule': crontab(hour=7, minute=0, day_of_month=1),  # Primer día del mes 7:00 AM
        'options': {'queue': 'reports', 'priority': 8}
    },
    
    # Tareas cada hora
    'hourly-notifications-digest': {
        'task': 'app.tasks.notification_tasks.process_pending_notifications',
        'schedule': crontab(minute=0),  # Cada hora en punto
        'options': {'queue': 'notifications', 'priority': 5}
    },
    
    # Tareas cada 15 minutos
    'process-email-queue': {
        'task': 'app.tasks.email_tasks.process_email_queue',
        'schedule': crontab(minute='*/15'),  # Cada 15 minutos
        'options': {'queue': 'emails', 'priority': 7}
    },
    
    # Tareas cada 5 minutos
    'health-check': {
        'task': 'app.tasks.maintenance_tasks.system_health_check',
        'schedule': crontab(minute='*/5'),  # Cada 5 minutos
        'options': {'queue': 'maintenance', 'priority': 9}
    },
    
    # Métricas en tiempo real
    'realtime-metrics-update': {
        'task': 'app.tasks.analytics_tasks.update_realtime_metrics',
        'schedule': 60.0,  # Cada minuto
        'options': {'queue': 'analytics', 'priority': 4}
    }
}


class BaseTask(Task):
    """
    Clase base personalizada para todas las tareas
    
    Proporciona funcionalidades comunes como logging,
    manejo de errores, métricas y contexto de aplicación.
    """
    
    abstract = True
    
    def __init__(self):
        super().__init__()
        self.start_time = None
        self.execution_context = {}
    
    def __call__(self, *args, **kwargs):
        """Override para añadir contexto y métricas"""
        self.start_time = datetime.utcnow()
        
        try:
            # Registrar inicio de tarea
            self._log_task_start()
            
            # Ejecutar tarea
            result = super().__call__(*args, **kwargs)
            
            # Registrar éxito
            self._log_task_success(result)
            
            return result
            
        except Exception as exc:
            # Registrar fallo
            self._log_task_failure(exc)
            raise
    
    def retry(self, args=None, kwargs=None, exc=None, throw=True, eta=None, countdown=None, max_retries=None, **options):
        """Override retry para logging personalizado"""
        retry_count = self.request.retries
        max_retries = max_retries or self.max_retries
        
        logger.warning(f"Reintentando tarea {self.name} (intento {retry_count + 1}/{max_retries + 1})")
        
        if exc:
            logger.warning(f"Razón del reintento: {str(exc)}")
        
        # Actualizar métricas
        task_metrics[self.name]['retry_count'] = task_metrics[self.name].get('retry_count', 0) + 1
        
        return super().retry(args, kwargs, exc, throw, eta, countdown, max_retries, **options)
    
    def _log_task_start(self):
        """Registra el inicio de la tarea"""
        logger.info(f"Iniciando tarea: {self.name} (ID: {self.request.id})")
        
        # Actualizar métricas
        task_metrics[self.name]['total_runs'] += 1
        task_metrics[self.name]['last_run'] = self.start_time
    
    def _log_task_success(self, result):
        """Registra el éxito de la tarea"""
        execution_time = (datetime.utcnow() - self.start_time).total_seconds()
        
        logger.info(f"Tarea completada exitosamente: {self.name} en {execution_time:.2f}s")
        
        # Actualizar métricas
        metrics = task_metrics[self.name]
        metrics['successful_runs'] += 1
        metrics['last_success'] = datetime.utcnow()
        
        # Calcular tiempo promedio
        current_avg = metrics.get('average_runtime', 0.0)
        total_successful = metrics['successful_runs']
        metrics['average_runtime'] = ((current_avg * (total_successful - 1)) + execution_time) / total_successful
    
    def _log_task_failure(self, exc):
        """Registra el fallo de la tarea"""
        execution_time = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0
        
        logger.error(f"Tarea falló: {self.name} después de {execution_time:.2f}s - Error: {str(exc)}")
        
        # Actualizar métricas
        metrics = task_metrics[self.name]
        metrics['failed_runs'] += 1
        metrics['last_failure'] = datetime.utcnow()
        metrics['last_error'] = str(exc)


def create_celery_app(app: Flask = None) -> Celery:
    """
    Crea y configura la aplicación Celery
    
    Args:
        app: Instancia de Flask (opcional)
        
    Returns:
        Celery: Instancia configurada de Celery
    """
    global celery
    
    # Configuración base de Celery
    celery_config = {
        # Broker y backend
        'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        
        # Serialización
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
        
        # Configuración de workers
        'worker_prefetch_multiplier': 1,
        'task_acks_late': True,
        'worker_disable_rate_limits': False,
        'worker_max_tasks_per_child': 1000,
        'worker_max_memory_per_child': 200000,  # 200MB
        
        # Configuración de tareas
        'task_always_eager': False,
        'task_eager_propagates': True,
        'task_ignore_result': False,
        'task_store_eager_result': True,
        'task_track_started': True,
        'task_time_limit': 300,  # 5 minutos
        'task_soft_time_limit': 240,  # 4 minutos
        
        # Configuración de retry
        'task_annotations': {
            '*': {
                'rate_limit': '100/m',
                'time_limit': 300,
                'soft_time_limit': 240,
            }
        },
        
        # Colas y routing
        'task_default_queue': 'normal',
        'task_default_exchange': 'normal',
        'task_default_exchange_type': 'direct',
        'task_default_routing_key': 'normal',
        'task_queues': CELERY_QUEUES,
        
        # Beat scheduling
        'beat_schedule': CELERY_BEAT_SCHEDULE,
        'beat_scheduler': 'django_celery_beat.schedulers:DatabaseScheduler',
        
        # Monitoreo
        'worker_send_task_events': True,
        'task_send_sent_event': True,
        'result_expires': 3600,  # 1 hora
        
        # Configuración de Redis específica
        'broker_transport_options': {
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True
        },
        
        # Security
        'worker_hijack_root_logger': False,
        'worker_log_color': True,
    }
    
    # Crear instancia de Celery
    celery = Celery(
        'ecosistema_emprendimiento',
        task_cls=BaseTask,
        include=[
            'app.tasks.email_tasks',
            'app.tasks.notification_tasks',
            'app.tasks.analytics_tasks',
            'app.tasks.backup_tasks',
            'app.tasks.maintenance_tasks'
        ]
    )
    
    # Configurar Celery
    celery.config_from_object(celery_config)
    
    # Configurar integración con Flask si se proporciona
    if app is not None:
        init_celery(app, celery)
    
    # Registrar signals
    register_celery_signals()
    
    # Configurar task routing
    configure_task_routing()
    
    logger.info("Aplicación Celery creada y configurada exitosamente")
    
    return celery


def init_celery(app: Flask, celery_app: Celery):
    """
    Inicializa Celery con la aplicación Flask
    
    Args:
        app: Instancia de Flask
        celery_app: Instancia de Celery
    """
    
    class ContextTask(BaseTask):
        """Tarea que ejecuta dentro del contexto de Flask"""
        
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)
    
    celery_app.Task = ContextTask
    
    # Actualizar configuración desde Flask config
    celery_app.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND'),
        timezone=app.config.get('TIMEZONE', 'UTC'),
        task_always_eager=app.config.get('TESTING', False)
    )
    
    logger.info("Celery integrado con Flask exitosamente")


def register_celery_signals():
    """Registra signals personalizados de Celery"""
    
    @task_prerun.connect
    def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Se ejecuta antes de cada tarea"""
        logger.debug(f"Preparando ejecución de tarea: {task.name} (ID: {task_id})")
        
        # Guardar contexto de ejecución
        cache_set(f"task_context_{task_id}", {
            'name': task.name,
            'args': args,
            'kwargs': kwargs,
            'started_at': datetime.utcnow().isoformat()
        }, timeout=3600)
    
    @task_postrun.connect
    def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
        """Se ejecuta después de cada tarea"""
        logger.debug(f"Finalizando tarea: {task.name} (ID: {task_id}) - Estado: {state}")
        
        # Limpiar contexto de ejecución
        cache_delete(f"task_context_{task_id}")
        
        # Notificar finalización si es tarea crítica
        if task.name in get_critical_tasks():
            notify_task_completion(task.name, task_id, state, retval)
    
    @task_success.connect
    def task_success_handler(sender=None, result=None, **kwds):
        """Se ejecuta cuando una tarea se completa exitosamente"""
        task_name = sender.name if sender else 'unknown'
        logger.info(f"Tarea completada exitosamente: {task_name}")
        
        # Actualizar métricas de éxito
        _update_success_metrics(task_name)
    
    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
        """Se ejecuta cuando una tarea falla"""
        task_name = sender.name if sender else 'unknown'
        logger.error(f"Fallo en tarea: {task_name} (ID: {task_id}) - Error: {str(exception)}")
        
        # Actualizar métricas de fallo
        _update_failure_metrics(task_name, exception)
        
        # Notificar fallo crítico
        if task_name in get_critical_tasks():
            notify_critical_task_failure(task_name, task_id, exception)
    
    @worker_ready.connect
    def worker_ready_handler(sender=None, **kwds):
        """Se ejecuta cuando un worker está listo"""
        logger.info(f"Worker listo: {sender.hostname}")
        
        # Notificar que el worker está operativo
        notify_worker_status(sender.hostname, 'ready')
    
    @worker_shutdown.connect
    def worker_shutdown_handler(sender=None, **kwds):
        """Se ejecuta cuando un worker se apaga"""
        logger.info(f"Worker apagándose: {sender.hostname}")
        
        # Notificar shutdown del worker
        notify_worker_status(sender.hostname, 'shutdown')
    
    @beat_init.connect
    def beat_init_handler(sender=None, **kwargs):
        """Se ejecuta cuando Celery Beat se inicializa"""
        logger.info("Celery Beat inicializado - Scheduling activado")


def configure_task_routing():
    """Configura el routing automático de tareas a colas específicas"""
    
    task_routes = {
        # Tareas de email
        'app.tasks.email_tasks.*': {'queue': 'emails', 'priority': 7},
        
        # Tareas de notificaciones
        'app.tasks.notification_tasks.*': {'queue': 'notifications', 'priority': 6},
        
        # Tareas de analytics
        'app.tasks.analytics_tasks.*': {'queue': 'analytics', 'priority': 5},
        
        # Tareas de backup (alta prioridad)
        'app.tasks.backup_tasks.*': {'queue': 'backups', 'priority': 8},
        
        # Tareas de mantenimiento
        'app.tasks.maintenance_tasks.*': {'queue': 'maintenance', 'priority': 4},
        
        # Tareas críticas (alta prioridad)
        'app.tasks.*.urgent_*': {'queue': 'high_priority', 'priority': 9},
        'app.tasks.*.critical_*': {'queue': 'high_priority', 'priority': 10},
        
        # Tareas de reportes (baja prioridad)
        'app.tasks.*.generate_report_*': {'queue': 'low_priority', 'priority': 2},
    }
    
    if celery:
        celery.conf.task_routes = task_routes
        logger.info("Task routing configurado exitosamente")


# Decoradores para tareas

def entrepreneur_task(
    bind: bool = True,
    priority: int = 5,
    max_retries: int = 3,
    default_retry_delay: int = 60,
    queue: str = 'normal'
):
    """
    Decorador para tareas relacionadas con emprendedores
    
    Args:
        bind: Binding de la tarea
        priority: Prioridad de la tarea (1-10)
        max_retries: Número máximo de reintentos
        default_retry_delay: Delay por defecto entre reintentos
        queue: Cola de destino
    """
    def decorator(func: Callable) -> Callable:
        @celery.task(
            bind=bind,
            priority=priority,
            max_retries=max_retries,
            default_retry_delay=default_retry_delay,
            queue=queue
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Ejecutando tarea de emprendedor: {func.__name__}")
            return func(*args, **kwargs)
        
        # Registrar tarea
        register_task(wrapper, 'entrepreneur', {
            'priority': priority,
            'max_retries': max_retries,
            'queue': queue
        })
        
        return wrapper
    return decorator


def mentor_task(
    bind: bool = True,
    priority: int = 6,
    max_retries: int = 3,
    default_retry_delay: int = 60,
    queue: str = 'normal'
):
    """
    Decorador para tareas relacionadas con mentores
    """
    def decorator(func: Callable) -> Callable:
        @celery.task(
            bind=bind,
            priority=priority,
            max_retries=max_retries,
            default_retry_delay=default_retry_delay,
            queue=queue
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Ejecutando tarea de mentor: {func.__name__}")
            return func(*args, **kwargs)
        
        register_task(wrapper, 'mentor', {
            'priority': priority,
            'max_retries': max_retries,
            'queue': queue
        })
        
        return wrapper
    return decorator


def system_task(
    bind: bool = True,
    priority: int = 8,
    max_retries: int = 5,
    default_retry_delay: int = 30,
    queue: str = 'high_priority'
):
    """
    Decorador para tareas críticas del sistema
    """
    def decorator(func: Callable) -> Callable:
        @celery.task(
            bind=bind,
            priority=priority,
            max_retries=max_retries,
            default_retry_delay=default_retry_delay,
            queue=queue
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Ejecutando tarea del sistema: {func.__name__}")
            return func(*args, **kwargs)
        
        register_task(wrapper, 'system', {
            'priority': priority,
            'max_retries': max_retries,
            'queue': queue,
            'critical': True
        })
        
        return wrapper
    return decorator


def periodic_task(
    cron_schedule: str,
    priority: int = 5,
    queue: str = 'normal',
    enabled: bool = True
):
    """
    Decorador para tareas periódicas
    
    Args:
        cron_schedule: Programación en formato cron
        priority: Prioridad de la tarea
        queue: Cola de destino
        enabled: Si la tarea está habilitada
    """
    def decorator(func: Callable) -> Callable:
        @celery.task(priority=priority, queue=queue)
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not enabled:
                logger.info(f"Tarea periódica deshabilitada: {func.__name__}")
                return
            
            logger.info(f"Ejecutando tarea periódica: {func.__name__}")
            return func(*args, **kwargs)
        
        # Registrar en schedule si está habilitado
        if enabled:
            schedule_name = f"periodic-{func.__name__}"
            CELERY_BEAT_SCHEDULE[schedule_name] = {
                'task': f"{func.__module__}.{wrapper.name}",
                'schedule': cron_schedule,
                'options': {'queue': queue, 'priority': priority}
            }
        
        register_task(wrapper, 'periodic', {
            'schedule': cron_schedule,
            'priority': priority,
            'queue': queue,
            'enabled': enabled
        })
        
        return wrapper
    return decorator


# Utilidades de gestión de tareas

def register_task(task: Callable, category: str, metadata: Dict[str, Any]):
    """
    Registra una tarea en el registro interno
    
    Args:
        task: Función de la tarea
        category: Categoría de la tarea
        metadata: Metadatos adicionales
    """
    task_registry[task.name] = {
        'function': task,
        'category': category,
        'metadata': metadata,
        'registered_at': datetime.utcnow()
    }
    
    logger.debug(f"Tarea registrada: {task.name} (categoría: {category})")


def get_task_info(task_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de una tarea registrada
    
    Args:
        task_name: Nombre de la tarea
        
    Returns:
        Dict con información de la tarea o None si no existe
    """
    return task_registry.get(task_name)


def get_tasks_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Obtiene todas las tareas de una categoría específica
    
    Args:
        category: Categoría de tareas
        
    Returns:
        Lista de tareas en la categoría
    """
    return [
        {'name': name, **info}
        for name, info in task_registry.items()
        if info['category'] == category
    ]


def get_task_metrics(task_name: str = None) -> Dict[str, Any]:
    """
    Obtiene métricas de tareas
    
    Args:
        task_name: Nombre específico de tarea (opcional)
        
    Returns:
        Métricas de la tarea específica o todas las métricas
    """
    if task_name:
        return task_metrics.get(task_name, {})
    return dict(task_metrics)


def get_queue_info() -> Dict[str, Any]:
    """
    Obtiene información de las colas de Celery
    
    Returns:
        Información de las colas configuradas
    """
    return {
        'queues': [
            {
                'name': queue.name,
                'exchange': queue.exchange.name,
                'routing_key': queue.routing_key,
                'priority': queue.queue_arguments.get('x-max-priority', 0)
            }
            for queue in CELERY_QUEUES
        ],
        'total_queues': len(CELERY_QUEUES),
        'default_queue': celery.conf.task_default_queue if celery else 'normal'
    }


def get_active_tasks() -> List[Dict[str, Any]]:
    """
    Obtiene información de tareas actualmente en ejecución
    
    Returns:
        Lista de tareas activas
    """
    if not celery:
        return []
    
    try:
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        
        if not active_tasks:
            return []
        
        all_active = []
        for worker, tasks in active_tasks.items():
            for task in tasks:
                all_active.append({
                    'worker': worker,
                    'task_id': task['id'],
                    'task_name': task['name'],
                    'args': task['args'],
                    'kwargs': task['kwargs'],
                    'time_start': task.get('time_start'),
                    'acknowledged': task.get('acknowledged', False)
                })
        
        return all_active
        
    except Exception as e:
        logger.error(f"Error obteniendo tareas activas: {str(e)}")
        return []


def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """
    Obtiene información de tareas programadas
    
    Returns:
        Lista de tareas programadas
    """
    if not celery:
        return []
    
    try:
        inspect = celery.control.inspect()
        scheduled_tasks = inspect.scheduled()
        
        if not scheduled_tasks:
            return []
        
        all_scheduled = []
        for worker, tasks in scheduled_tasks.items():
            for task in tasks:
                all_scheduled.append({
                    'worker': worker,
                    'task_id': task['request']['id'],
                    'task_name': task['request']['task'],
                    'eta': task['eta'],
                    'priority': task['request'].get('priority', 0)
                })
        
        return all_scheduled
        
    except Exception as e:
        logger.error(f"Error obteniendo tareas programadas: {str(e)}")
        return []


def get_worker_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas de workers
    
    Returns:
        Estadísticas de workers activos
    """
    if not celery:
        return {}
    
    try:
        inspect = celery.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {'active_workers': 0, 'workers': []}
        
        worker_info = []
        for worker_name, worker_stats in stats.items():
            worker_info.append({
                'name': worker_name,
                'status': 'online',
                'processed_tasks': worker_stats.get('total', {}),
                'active_tasks': len(worker_stats.get('active', [])),
                'load_avg': worker_stats.get('rusage', {}).get('utime', 0),
                'memory_usage': worker_stats.get('rusage', {}).get('maxrss', 0)
            })
        
        return {
            'active_workers': len(worker_info),
            'workers': worker_info,
            'total_processed': sum(w.get('processed_tasks', {}).get('total', 0) for w in worker_info)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de workers: {str(e)}")
        return {'error': str(e)}


def purge_queue(queue_name: str) -> Dict[str, Any]:
    """
    Purga una cola específica
    
    Args:
        queue_name: Nombre de la cola a purgar
        
    Returns:
        Resultado de la operación
    """
    if not celery:
        return {'error': 'Celery not initialized'}
    
    try:
        result = celery.control.purge(queue=queue_name)
        logger.info(f"Cola {queue_name} purgada exitosamente")
        return {'success': True, 'queue': queue_name, 'result': result}
        
    except Exception as e:
        logger.error(f"Error purgando cola {queue_name}: {str(e)}")
        return {'error': str(e)}


def revoke_task(task_id: str, terminate: bool = False) -> Dict[str, Any]:
    """
    Revoca una tarea específica
    
    Args:
        task_id: ID de la tarea a revocar
        terminate: Si terminar la tarea inmediatamente
        
    Returns:
        Resultado de la operación
    """
    if not celery:
        return {'error': 'Celery not initialized'}
    
    try:
        celery.control.revoke(task_id, terminate=terminate)
        logger.info(f"Tarea {task_id} revocada {'y terminada' if terminate else ''}")
        return {'success': True, 'task_id': task_id, 'terminated': terminate}
        
    except Exception as e:
        logger.error(f"Error revocando tarea {task_id}: {str(e)}")
        return {'error': str(e)}


# Funciones auxiliares privadas

def get_critical_tasks() -> List[str]:
    """Obtiene lista de tareas críticas"""
    return [
        name for name, info in task_registry.items()
        if info.get('metadata', {}).get('critical', False)
    ]


def notify_task_completion(task_name: str, task_id: str, state: str, result: Any):
    """Notifica la finalización de tareas críticas"""
    try:
        notification_service = NotificationService()
        notification_service.send_system_notification(
            message=f"Tarea crítica completada: {task_name}",
            details={
                'task_id': task_id,
                'state': state,
                'result': str(result)[:200] if result else None
            },
            recipients=['admin']
        )
    except Exception as e:
        logger.error(f"Error enviando notificación de finalización: {str(e)}")


def notify_critical_task_failure(task_name: str, task_id: str, exception: Exception):
    """Notifica fallos en tareas críticas"""
    try:
        notification_service = NotificationService()
        notification_service.send_critical_alert(
            message=f"FALLO CRÍTICO en tarea: {task_name}",
            details={
                'task_id': task_id,
                'error': str(exception),
                'timestamp': format_datetime(datetime.utcnow())
            },
            recipients=['admin', 'tech_team']
        )
    except Exception as e:
        logger.error(f"Error enviando alerta crítica: {str(e)}")


def notify_worker_status(hostname: str, status: str):
    """Notifica cambios de estado de workers"""
    try:
        cache_set(f"worker_status_{hostname}", {
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }, timeout=3600)
        
        logger.info(f"Estado de worker actualizado: {hostname} - {status}")
    except Exception as e:
        logger.error(f"Error actualizando estado de worker: {str(e)}")


def _update_success_metrics(task_name: str):
    """Actualiza métricas de éxito"""
    metrics = task_metrics[task_name]
    metrics['successful_runs'] += 1
    metrics['last_success'] = datetime.utcnow()


def _update_failure_metrics(task_name: str, exception: Exception):
    """Actualiza métricas de fallo"""
    metrics = task_metrics[task_name]
    metrics['failed_runs'] += 1
    metrics['last_failure'] = datetime.utcnow()
    metrics['last_error'] = str(exception)


# Funciones de utilidad para comandos CLI

def start_worker(queues: List[str] = None, concurrency: int = None, loglevel: str = 'info'):
    """
    Inicia un worker de Celery
    
    Args:
        queues: Colas a procesar
        concurrency: Nivel de concurrencia
        loglevel: Nivel de logging
    """
    if not celery:
        logger.error("Celery no está inicializado")
        return
    
    queue_list = queues or ['normal', 'high_priority', 'low_priority']
    concurrency = concurrency or 4
    
    logger.info(f"Iniciando worker para colas: {queue_list}")
    
    celery.worker_main([
        'worker',
        f'--queues={",".join(queue_list)}',
        f'--concurrency={concurrency}',
        f'--loglevel={loglevel}',
        '--without-gossip',
        '--without-mingle',
        '--without-heartbeat'
    ])


def start_beat(loglevel: str = 'info'):
    """
    Inicia Celery Beat para tareas programadas
    
    Args:
        loglevel: Nivel de logging
    """
    if not celery:
        logger.error("Celery no está inicializado")
        return
    
    logger.info("Iniciando Celery Beat")
    
    celery.start([
        'beat',
        f'--loglevel={loglevel}',
        '--detach'
    ])


def monitor_tasks():
    """Inicia el monitor de tareas (Flower)"""
    logger.info("Para monitorear tareas, instala Flower: pip install flower")
    logger.info("Luego ejecuta: celery -A app.tasks flower")


# Exportar funciones principales
__all__ = [
    'celery',
    'create_celery_app',
    'init_celery',
    'BaseTask',
    'entrepreneur_task',
    'mentor_task',
    'system_task',
    'periodic_task',
    'register_task',
    'get_task_info',
    'get_tasks_by_category',
    'get_task_metrics',
    'get_queue_info',
    'get_active_tasks',
    'get_scheduled_tasks',
    'get_worker_stats',
    'purge_queue',
    'revoke_task',
    'start_worker',
    'start_beat',
    'monitor_tasks'
]