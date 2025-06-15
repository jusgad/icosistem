#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
ECOSISTEMA DE EMPRENDIMIENTO - CELERY WORKER
============================================================================
Celery worker entry point for background task processing in the
entrepreneurship ecosystem platform.

This module configures and starts Celery workers with comprehensive
monitoring, error handling, and production optimizations.

Author: DevOps Team
Last Updated: 2025-06-14
Python Version: 3.11+

Usage:
    Development: python celery_worker.py
    Production: celery -A celery_worker.celery worker --loglevel=info
    Docker: CMD ["python", "celery_worker.py"]
    Systemd: ExecStart=/path/to/venv/bin/python celery_worker.py

Supported Configurations:
    - Redis broker
    - RabbitMQ broker
    - Multiple worker types
    - Priority queues
    - Rate limiting
    - Task routing
    - Auto-scaling
============================================================================
"""

import atexit
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from celery import Celery, Task
from celery.signals import (
    beat_init,
    celeryd_after_setup,
    celeryd_init,
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_success,
    worker_init,
    worker_process_init,
    worker_ready,
    worker_shutdown,
    worker_shutting_down
)
from celery.utils.log import get_task_logger
from kombu import Queue, Exchange

# Import application components
from app import create_app
from app.extensions import db
from app.utils.logging import setup_logging
from app.utils.monitoring import CeleryMonitor

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Environment configuration
CELERY_ENV = os.environ.get('CELERY_ENV', os.environ.get('FLASK_ENV', 'development')).lower()
DEBUG = os.environ.get('CELERY_DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')
TESTING = os.environ.get('TESTING', 'false').lower() in ('true', '1', 'yes', 'on')

# Broker configuration
BROKER_URL = os.environ.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/1'))
RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', 'redis://localhost:6379/2'))

# Worker configuration
WORKER_NAME = os.environ.get('CELERY_WORKER_NAME', f'worker-{os.getpid()}')
WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '4'))
WORKER_PREFETCH_MULTIPLIER = int(os.environ.get('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))
WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get('CELERY_WORKER_MAX_TASKS_PER_CHILD', '1000'))
WORKER_MAX_MEMORY_PER_CHILD = int(os.environ.get('CELERY_WORKER_MAX_MEMORY_PER_CHILD', '200000'))  # KB

# Queue configuration
DEFAULT_QUEUE = os.environ.get('CELERY_DEFAULT_QUEUE', 'default')
WORKER_QUEUES = os.environ.get('CELERY_WORKER_QUEUES', 'default,email,notifications,analytics,reports').split(',')

# Monitoring configuration
FLOWER_ENABLED = os.environ.get('FLOWER_ENABLED', 'false').lower() in ('true', '1', 'yes', 'on')
FLOWER_PORT = int(os.environ.get('FLOWER_PORT', '5555'))
METRICS_ENABLED = os.environ.get('CELERY_METRICS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')

# Task configuration
TASK_SOFT_TIME_LIMIT = int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '300'))  # 5 minutes
TASK_TIME_LIMIT = int(os.environ.get('CELERY_TASK_TIME_LIMIT', '600'))  # 10 minutes
TASK_ACKS_LATE = os.environ.get('CELERY_TASK_ACKS_LATE', 'true').lower() in ('true', '1', 'yes', 'on')
TASK_REJECT_ON_WORKER_LOST = os.environ.get('CELERY_TASK_REJECT_ON_WORKER_LOST', 'true').lower() in ('true', '1', 'yes', 'on')

# Application metadata
APP_NAME = "Ecosistema de Emprendimiento"
CELERY_APP_NAME = "ecosistema_celery"

# Global variables
_flask_app: Optional[Any] = None
_celery_app: Optional[Celery] = None
_monitor: Optional[CeleryMonitor] = None
_shutdown_requested = False

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def configure_celery_logging() -> None:
    """Configure logging for Celery workers."""
    log_level = logging.INFO
    
    if CELERY_ENV == 'development':
        log_level = logging.DEBUG
    elif CELERY_ENV == 'production':
        log_level = logging.WARNING
    elif TESTING:
        log_level = logging.ERROR
    
    # Setup structured logging
    setup_logging(
        level=log_level,
        format_json=CELERY_ENV == 'production',
        include_request_id=False,
        log_file=f"logs/celery_{CELERY_ENV}.log" if not TESTING else None
    )
    
    # Configure Celery-specific loggers
    logging.getLogger('celery').setLevel(log_level)
    logging.getLogger('celery.worker').setLevel(log_level)
    logging.getLogger('celery.task').setLevel(log_level)
    logging.getLogger('celery.redirected').setLevel(log_level)
    
    # Configure third-party loggers
    logging.getLogger('kombu').setLevel(logging.WARNING)
    logging.getLogger('amqp').setLevel(logging.WARNING)
    logging.getLogger('redis').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Celery logging configured for {CELERY_ENV} environment")

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

class CeleryConfig:
    """Celery configuration class."""
    
    # Broker settings
    broker_url = BROKER_URL
    result_backend = RESULT_BACKEND
    
    # Task settings
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    result_accept_content = ['json']
    timezone = 'America/Bogota'
    enable_utc = True
    
    # Task execution settings
    task_acks_late = TASK_ACKS_LATE
    task_reject_on_worker_lost = TASK_REJECT_ON_WORKER_LOST
    task_soft_time_limit = TASK_SOFT_TIME_LIMIT
    task_time_limit = TASK_TIME_LIMIT
    task_track_started = True
    task_send_sent_event = True
    
    # Worker settings
    worker_prefetch_multiplier = WORKER_PREFETCH_MULTIPLIER
    worker_max_tasks_per_child = WORKER_MAX_TASKS_PER_CHILD
    worker_max_memory_per_child = WORKER_MAX_MEMORY_PER_CHILD
    worker_disable_rate_limits = False
    worker_enable_remote_control = True
    worker_send_task_events = True
    
    # Result backend settings
    result_expires = 3600  # 1 hour
    result_persistent = True
    result_compression = 'gzip'
    
    # Broker connection settings
    broker_connection_retry_on_startup = True
    broker_connection_retry = True
    broker_connection_max_retries = 5
    broker_heartbeat = 30
    broker_pool_limit = 10
    
    # Task routing
    task_routes = {
        'app.tasks.email.*': {'queue': 'email'},
        'app.tasks.notifications.*': {'queue': 'notifications'},
        'app.tasks.analytics.*': {'queue': 'analytics'},
        'app.tasks.reports.*': {'queue': 'reports'},
        'app.tasks.backup.*': {'queue': 'maintenance'},
        'app.tasks.cleanup.*': {'queue': 'maintenance'},
    }
    
    # Task priorities (Redis only)
    task_default_priority = 5
    worker_disable_rate_limits = False
    
    # Beat schedule (if running beat)
    beat_schedule = {
        'cleanup-expired-sessions': {
            'task': 'app.tasks.maintenance.cleanup_expired_sessions',
            'schedule': 3600.0,  # Every hour
            'options': {'queue': 'maintenance'}
        },
        'generate-daily-analytics': {
            'task': 'app.tasks.analytics.generate_daily_analytics',
            'schedule': 86400.0,  # Every day
            'options': {'queue': 'analytics'}
        },
        'send-weekly-reports': {
            'task': 'app.tasks.reports.send_weekly_reports',
            'schedule': 604800.0,  # Every week
            'options': {'queue': 'reports'}
        },
        'backup-database': {
            'task': 'app.tasks.backup.backup_database',
            'schedule': 86400.0,  # Every day
            'options': {'queue': 'maintenance'}
        },
        'health-check-external-services': {
            'task': 'app.tasks.monitoring.health_check_external_services',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'monitoring'}
        }
    }
    
    # Security settings
    worker_hijack_root_logger = False
    worker_log_color = CELERY_ENV != 'production'
    
    # Monitoring settings
    worker_send_task_events = METRICS_ENABLED
    task_send_sent_event = METRICS_ENABLED
    
    # Error handling
    task_reject_on_worker_lost = True
    task_acks_late = True

# ============================================================================
# QUEUE CONFIGURATION
# ============================================================================

def setup_queues() -> List[Queue]:
    """
    Setup Celery queues with proper configuration.
    
    Returns:
        List of configured Queue objects
    """
    # Define exchanges
    default_exchange = Exchange('default', type='direct')
    priority_exchange = Exchange('priority', type='direct')
    
    # Define queues with different priorities and configurations
    queues = [
        # Default queue
        Queue('default', default_exchange, routing_key='default'),
        
        # High priority queues
        Queue(
            'email',
            priority_exchange,
            routing_key='email',
            queue_arguments={'x-max-priority': 10}
        ),
        Queue(
            'notifications',
            priority_exchange,
            routing_key='notifications',
            queue_arguments={'x-max-priority': 8}
        ),
        
        # Normal priority queues
        Queue('analytics', default_exchange, routing_key='analytics'),
        Queue('reports', default_exchange, routing_key='reports'),
        
        # Low priority queues
        Queue('maintenance', default_exchange, routing_key='maintenance'),
        Queue('monitoring', default_exchange, routing_key='monitoring'),
        
        # Dead letter queue
        Queue(
            'dlq',
            default_exchange,
            routing_key='dlq',
            queue_arguments={
                'x-message-ttl': 86400000,  # 24 hours
                'x-max-length': 1000
            }
        )
    ]
    
    return queues

# ============================================================================
# CUSTOM TASK CLASS
# ============================================================================

class EcosistemaTask(Task):
    """Custom task class with enhanced error handling and monitoring."""
    
    def __init__(self):
        self.logger = get_task_logger(self.__class__.__name__)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        self.logger.error(
            f"Task {self.name} failed: {exc}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'task_args': args,
                'task_kwargs': kwargs,
                'exception': str(exc),
                'traceback': str(einfo)
            }
        )
        
        # Send failure notification for critical tasks
        if hasattr(self, 'critical') and self.critical:
            from app.tasks.notifications import send_critical_task_failure
            send_critical_task_failure.delay(task_id, self.name, str(exc))
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        self.logger.info(
            f"Task {self.name} succeeded",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'result': str(retval)[:200]  # Truncate large results
            }
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        self.logger.warning(
            f"Task {self.name} retrying: {exc}",
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'retry_count': self.request.retries,
                'max_retries': self.max_retries,
                'exception': str(exc)
            }
        )

# ============================================================================
# FLASK APPLICATION INTEGRATION
# ============================================================================

def create_flask_app() -> Any:
    """
    Create Flask application for Celery workers.
    
    Returns:
        Flask application instance
    """
    global _flask_app
    
    if _flask_app is None:
        logger = logging.getLogger(__name__)
        logger.info("Creating Flask application for Celery workers")
        
        try:
            _flask_app = create_app(config_name=CELERY_ENV)
            logger.info("Flask application created successfully")
        except Exception as e:
            logger.error(f"Failed to create Flask application: {e}")
            raise
    
    return _flask_app

def make_celery(flask_app: Any) -> Celery:
    """
    Create Celery instance with Flask integration.
    
    Args:
        flask_app: Flask application instance
        
    Returns:
        Configured Celery instance
    """
    celery = Celery(
        CELERY_APP_NAME,
        broker=BROKER_URL,
        backend=RESULT_BACKEND,
        include=[
            'app.tasks.email',
            'app.tasks.notifications',
            'app.tasks.analytics',
            'app.tasks.reports',
            'app.tasks.backup',
            'app.tasks.maintenance',
            'app.tasks.monitoring'
        ]
    )
    
    # Configure Celery
    celery.config_from_object(CeleryConfig)
    
    # Setup queues
    celery.conf.task_queues = setup_queues()
    
    # Set custom task base class
    celery.Task = EcosistemaTask
    
    # Integrate with Flask app context
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    return celery

# ============================================================================
# CELERY SIGNALS AND HOOKS
# ============================================================================

@worker_init.connect
def worker_init_handler(sender=None, **kwargs):
    """Handle worker initialization."""
    logger = logging.getLogger('celery.worker')
    logger.info(f"Worker {WORKER_NAME} initializing...")
    
    # Setup Flask app context
    flask_app = create_flask_app()
    with flask_app.app_context():
        # Initialize database connections
        db.engine.pool.invalidate()
        
        # Setup monitoring
        global _monitor
        if METRICS_ENABLED:
            _monitor = CeleryMonitor()
            _monitor.start()
    
    logger.info(f"Worker {WORKER_NAME} initialized successfully")

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal."""
    logger = logging.getLogger('celery.worker')
    logger.info(f"Worker {WORKER_NAME} is ready to process tasks")

@worker_process_init.connect
def worker_process_init_handler(sender=None, **kwargs):
    """Handle worker process initialization."""
    logger = logging.getLogger('celery.worker')
    logger.info(f"Worker process {os.getpid()} initialized")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    
    logger = logging.getLogger('celery.worker')
    logger.info(f"Worker {WORKER_NAME} shutting down...")
    
    # Stop monitoring
    global _monitor
    if _monitor:
        _monitor.stop()
    
    # Close database connections
    try:
        with create_flask_app().app_context():
            db.session.close()
            db.engine.dispose()
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    logger.info(f"Worker {WORKER_NAME} shutdown complete")

@worker_shutting_down.connect
def worker_shutting_down_handler(sender=None, **kwargs):
    """Handle worker shutting down signal."""
    logger = logging.getLogger('celery.worker')
    logger.info(f"Worker {WORKER_NAME} is shutting down...")

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task pre-run."""
    logger = get_task_logger(task.name)
    logger.debug(f"Task {task.name} starting", extra={'task_id': task_id})

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Handle task post-run."""
    logger = get_task_logger(task.name)
    logger.debug(f"Task {task.name} completed", extra={'task_id': task_id, 'state': state})

@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Handle task success."""
    if _monitor:
        _monitor.record_task_success(sender.name)

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, einfo=None, **kwargs):
    """Handle task failure."""
    logger = get_task_logger(sender.name)
    logger.error(f"Task {sender.name} failed: {exception}", extra={'task_id': task_id})
    
    if _monitor:
        _monitor.record_task_failure(sender.name, str(exception))

@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """Handle task retry."""
    logger = get_task_logger(sender.name)
    logger.warning(f"Task {sender.name} retrying: {reason}", extra={'task_id': task_id})
    
    if _monitor:
        _monitor.record_task_retry(sender.name, str(reason))

@beat_init.connect
def beat_init_handler(sender=None, **kwargs):
    """Handle beat initialization."""
    logger = logging.getLogger('celery.beat')
    logger.info("Celery Beat scheduler initialized")

@celeryd_init.connect
def celeryd_init_handler(sender=None, conf=None, **kwargs):
    """Handle celeryd initialization."""
    logger = logging.getLogger('celery.worker')
    logger.info("Celery daemon initialized")

@celeryd_after_setup.connect
def celeryd_after_setup_handler(sender=None, instance=None, **kwargs):
    """Handle post-setup configuration."""
    logger = logging.getLogger('celery.worker')
    logger.info("Celery worker setup completed")

# ============================================================================
# WORKER MONITORING AND HEALTH CHECKS
# ============================================================================

def setup_worker_monitoring():
    """Setup worker monitoring and health checks."""
    logger = logging.getLogger('celery.monitoring')
    
    def health_check_thread():
        """Background thread for health checks."""
        while not _shutdown_requested:
            try:
                # Check database connection
                with create_flask_app().app_context():
                    db.session.execute('SELECT 1')
                
                # Check broker connection
                celery_app = get_celery_app()
                celery_app.control.ping(timeout=5)
                
                logger.debug("Health check passed")
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            
            time.sleep(30)  # Check every 30 seconds
    
    # Start health check thread
    health_thread = threading.Thread(target=health_check_thread, daemon=True)
    health_thread.start()
    
    logger.info("Worker monitoring setup completed")

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    logger = logging.getLogger('celery.signals')
    
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        global _shutdown_requested
        _shutdown_requested = True
        
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        
        # Stop accepting new tasks
        celery_app = get_celery_app()
        celery_app.control.cancel_consumer('default')
        
        # Wait for current tasks to complete
        time.sleep(5)
        
        logger.info("Graceful shutdown completed")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Signal handlers configured")

# ============================================================================
# CELERY APPLICATION FACTORY
# ============================================================================

def create_celery_app() -> Celery:
    """
    Create and configure Celery application.
    
    Returns:
        Configured Celery instance
    """
    global _celery_app
    
    if _celery_app is None:
        logger = logging.getLogger(__name__)
        logger.info(f"Creating Celery application: {CELERY_APP_NAME}")
        
        try:
            # Create Flask app
            flask_app = create_flask_app()
            
            # Create Celery app
            _celery_app = make_celery(flask_app)
            
            logger.info("Celery application created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Celery application: {e}")
            raise
    
    return _celery_app

def get_celery_app() -> Celery:
    """Get or create Celery application instance."""
    if _celery_app is None:
        return create_celery_app()
    return _celery_app

# ============================================================================
# WORKER STARTUP AND MANAGEMENT
# ============================================================================

def validate_worker_environment():
    """Validate worker environment configuration."""
    logger = logging.getLogger('celery.validation')
    
    # Check required environment variables
    required_vars = ['DATABASE_URL', 'REDIS_URL']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        if CELERY_ENV == 'production':
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        else:
            logger.warning(f"Missing environment variables: {missing_vars}")
    
    # Check broker connectivity
    try:
        celery_app = get_celery_app()
        celery_app.control.ping(timeout=5)
        logger.info("Broker connectivity verified")
    except Exception as e:
        logger.error(f"Broker connectivity check failed: {e}")
        if CELERY_ENV == 'production':
            raise
    
    # Create required directories
    required_dirs = ['logs', 'profiles']
    for dir_path in required_dirs:
        Path(dir_path).mkdir(exist_ok=True)
    
    logger.info("Worker environment validation completed")

def print_worker_banner():
    """Print worker startup banner."""
    if not TESTING:
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         CELERY WORKER STARTING                              ║
║                     {APP_NAME:<45}           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Worker: {WORKER_NAME:<19} │ Environment: {CELERY_ENV:<15} │ Debug: {DEBUG:<10} ║
║ Concurrency: {WORKER_CONCURRENCY:<12} │ Prefetch: {WORKER_PREFETCH_MULTIPLIER:<15} │ Queues: {len(WORKER_QUEUES):<9} ║
║ Broker: {BROKER_URL[:25]:<25} │ Backend: {RESULT_BACKEND[:25]:<25} ║
║ Max Tasks: {WORKER_MAX_TASKS_PER_CHILD:<14} │ Max Memory: {WORKER_MAX_MEMORY_PER_CHILD:<12} KB │ Flower: {FLOWER_ENABLED:<8} ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        print(banner)

def start_worker():
    """Start Celery worker with proper configuration."""
    logger = logging.getLogger(__name__)
    
    try:
        # Print startup banner
        print_worker_banner()
        
        # Configure logging
        configure_celery_logging()
        
        # Validate environment
        validate_worker_environment()
        
        # Setup signal handlers
        setup_signal_handlers()
        
        # Setup monitoring
        setup_worker_monitoring()
        
        # Get Celery app
        celery_app = get_celery_app()
        
        # Start worker
        logger.info(f"Starting Celery worker: {WORKER_NAME}")
        
        celery_app.worker_main([
            'worker',
            f'--loglevel={logging.getLevelName(logging.getLogger().level).lower()}',
            f'--concurrency={WORKER_CONCURRENCY}',
            f'--hostname={WORKER_NAME}@%h',
            f'--queues={",".join(WORKER_QUEUES)}',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat' if CELERY_ENV == 'development' else '',
        ])
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker startup failed: {e}")
        sys.exit(1)

# ============================================================================
# CLI COMMANDS
# ============================================================================

@click.group()
def cli():
    """Celery worker management CLI."""
    pass

@cli.command()
@click.option('--worker-name', default=WORKER_NAME, help='Worker name')
@click.option('--concurrency', default=WORKER_CONCURRENCY, help='Worker concurrency')
@click.option('--queues', default=','.join(WORKER_QUEUES), help='Queues to process')
@click.option('--loglevel', default='info', help='Log level')
def worker(worker_name, concurrency, queues, loglevel):
    """Start Celery worker."""
    global WORKER_NAME, WORKER_CONCURRENCY, WORKER_QUEUES
    
    WORKER_NAME = worker_name
    WORKER_CONCURRENCY = concurrency
    WORKER_QUEUES = queues.split(',')
    
    start_worker()

@cli.command()
@click.option('--port', default=FLOWER_PORT, help='Flower port')
def flower(port):
    """Start Flower monitoring."""
    celery_app = get_celery_app()
    
    from flower.command import FlowerCommand
    
    flower_cmd = FlowerCommand()
    flower_cmd.execute_from_commandline([
        'flower',
        f'--broker={BROKER_URL}',
        f'--port={port}',
        '--basic_auth=admin:admin123',  # Change in production
        '--url_prefix=flower'
    ])

@cli.command()
def beat():
    """Start Celery beat scheduler."""
    celery_app = get_celery_app()
    
    celery_app.worker_main([
        'beat',
        '--loglevel=info',
        '--pidfile=/tmp/celerybeat.pid',
        '--schedule=/tmp/celerybeat-schedule'
    ])

@cli.command()
def status():
    """Show worker status."""
    celery_app = get_celery_app()
    
    # Get worker stats
    stats = celery_app.control.inspect().stats()
    if stats:
        for worker, worker_stats in stats.items():
            print(f"Worker: {worker}")
            print(f"  Pool: {worker_stats.get('pool', {})}")
            print(f"  Total tasks: {worker_stats.get('total', {})}")
            print(f"  Active tasks: {len(worker_stats.get('active', []))}")
            print(f"  Scheduled tasks: {len(worker_stats.get('scheduled', []))}")
            print()
    else:
        print("No workers found")

@cli.command()
def purge():
    """Purge all tasks from queues."""
    celery_app = get_celery_app()
    celery_app.control.purge()
    print("All tasks purged from queues")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point."""
    try:
        if len(sys.argv) > 1:
            # CLI mode
            cli()
        else:
            # Direct worker start
            start_worker()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Celery worker failed: {e}")
        sys.exit(1)

# Create Celery app instance for import
celery = create_celery_app()

# Cleanup function
def cleanup():
    """Cleanup function called on exit."""
    global _shutdown_requested
    _shutdown_requested = True

# Register cleanup function
atexit.register(cleanup)

if __name__ == '__main__':
    main()

# ============================================================================
# MODULE METADATA
# ============================================================================

__version__ = "1.0.0"
__author__ = "DevOps Team"
__email__ = "devops@ecosistema-emprendimiento.com"
__status__ = "Production"

# ============================================================================
# END OF CELERY WORKER MODULE
# ============================================================================
# This module provides:
# 
# ✅ Production-ready Celery worker
# ✅ Flask application integration
# ✅ Comprehensive error handling
# ✅ Signal-based graceful shutdown
# ✅ Multi-queue task routing
# ✅ Performance monitoring
# ✅ Health checks and validation
# ✅ Development and production modes
# ✅ CLI management commands
# ✅ Flower monitoring integration
# ✅ Beat scheduler support
# ✅ Custom task base class
# ✅ Database connection management
# ✅ Memory and performance optimization
# 
# Usage examples:
# - Direct: python celery_worker.py
# - CLI: python celery_worker.py worker --concurrency=8 --queues=default,email
# - Production: celery -A celery_worker.celery worker --loglevel=info
# - Flower: python celery_worker.py flower
# - Beat: python celery_worker.py beat
# - Status: python celery_worker.py status
# 
# Environment variables:
# - CELERY_BROKER_URL: Broker URL (Redis/RabbitMQ)
# - CELERY_RESULT_BACKEND: Result backend URL
# - CELERY_WORKER_CONCURRENCY: Worker concurrency
# - CELERY_WORKER_QUEUES: Comma-separated queue list
# - FLOWER_ENABLED: Enable Flower monitoring
# - CELERY_ENV: development|staging|production
# 
# Last updated: 2025-06-14
# Compatible with: Celery 5.3+, Redis 5+, Python 3.11+
# ============================================================================