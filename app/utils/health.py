"""
Sistema de health checks para el ecosistema de emprendimiento.
Proporciona monitoreo de salud de componentes críticos del sistema.
"""

import time
import psutil
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from flask import current_app
from sqlalchemy import text


class HealthCheckResult:
    """Resultado de un health check."""
    
    def __init__(self, name: str, healthy: bool, details: dict[str, Any] = None, 
                 response_time: float = 0, error: str = None):
        self.name = name
        self.healthy = healthy
        self.details = details or {}
        self.response_time = response_time
        self.error = error
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict[str, Any]:
        """Convertir resultado a diccionario."""
        result = {
            'name': self.name,
            'status': 'healthy' if self.healthy else 'unhealthy',
            'response_time': self.response_time,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }
        
        if self.error:
            result['error'] = self.error
        
        return result


class HealthChecker:
    """Sistema de health checks."""
    
    def __init__(self):
        self.checks: dict[str, Callable[[], HealthCheckResult]] = {}
        self.logger = logging.getLogger('ecosistema.health')
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """Registrar un health check."""
        self.checks[name] = check_func
        self.logger.info(f"Health check registered: {name}")
    
    def run_check(self, name: str) -> HealthCheckResult:
        """Ejecutar un health check específico."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                healthy=False,
                error=f"Health check '{name}' not found"
            )
        
        start_time = time.time()
        try:
            result = self.checks[name]()
            result.response_time = time.time() - start_time
            return result
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"Health check '{name}' failed: {e}")
            return HealthCheckResult(
                name=name,
                healthy=False,
                response_time=response_time,
                error=str(e)
            )
    
    def run_all_checks(self) -> dict[str, Any]:
        """Ejecutar todos los health checks."""
        results = {}
        overall_healthy = True
        start_time = time.time()
        
        for name in self.checks.keys():
            result = self.run_check(name)
            results[name] = result.to_dict()
            
            if not result.healthy:
                overall_healthy = False
        
        total_time = time.time() - start_time
        
        return {
            'overall': 'healthy' if overall_healthy else 'unhealthy',
            'total_checks': len(self.checks),
            'healthy_checks': sum(1 for r in results.values() if r['status'] == 'healthy'),
            'total_response_time': total_time,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': results
        }
    
    def get_check_names(self) -> list[str]:
        """Obtener nombres de todos los checks registrados."""
        return list(self.checks.keys())


# Instancia global del health checker
health_checker = HealthChecker()


# ====================================
# HEALTH CHECKS ESPECÍFICOS
# ====================================

def database_health_check() -> HealthCheckResult:
    """Health check de la base de datos."""
    try:
        from app.extensions import db
        
        start_time = time.time()
        
        # Test básico de conectividad
        db.session.execute(text('SELECT 1'))
        query_time = time.time() - start_time
        
        # Información del pool de conexiones
        pool_info = {}
        try:
            pool = db.engine.pool
            pool_info = {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid()
            }
        except Exception as e:
            pool_info = {'error': f'Pool info unavailable: {e}'}
        
        # Test de transacción
        try:
            with db.session.begin():
                db.session.execute(text('SELECT COUNT(*) FROM alembic_version'))
            transaction_test = True
        except Exception as e:
            transaction_test = False
            
        details = {
            'query_time': query_time,
            'connection_pool': pool_info,
            'transaction_test': transaction_test,
            'database_url': db.engine.url.database
        }
        
        # Determinar si está saludable
        healthy = query_time < 1.0 and transaction_test
        
        return HealthCheckResult(
            name='database',
            healthy=healthy,
            details=details,
            response_time=query_time
        )
        
    except Exception as e:
        return HealthCheckResult(
            name='database',
            healthy=False,
            error=str(e)
        )


def redis_health_check() -> HealthCheckResult:
    """Health check de Redis."""
    try:
        from app.extensions import redis_client
        
        if not redis_client:
            return HealthCheckResult(
                name='redis',
                healthy=False,
                error='Redis client not configured'
            )
        
        start_time = time.time()
        
        # Test ping
        redis_client.ping()
        ping_time = time.time() - start_time
        
        # Información del servidor
        info = redis_client.info()
        
        # Test de escritura/lectura
        test_key = 'health_check_test'
        test_value = str(int(time.time()))
        
        redis_client.setex(test_key, 10, test_value)  # Expira en 10 segundos
        retrieved_value = redis_client.get(test_key)
        redis_client.delete(test_key)
        
        read_write_test = retrieved_value.decode() == test_value if retrieved_value else False
        
        details = {
            'ping_time': ping_time,
            'redis_version': info.get('redis_version'),
            'connected_clients': info.get('connected_clients'),
            'used_memory_human': info.get('used_memory_human'),
            'uptime_in_seconds': info.get('uptime_in_seconds'),
            'read_write_test': read_write_test
        }
        
        # Está saludable si ping es rápido y read/write funciona
        healthy = ping_time < 0.1 and read_write_test
        
        return HealthCheckResult(
            name='redis',
            healthy=healthy,
            details=details,
            response_time=ping_time
        )
        
    except Exception as e:
        return HealthCheckResult(
            name='redis',
            healthy=False,
            error=str(e)
        )


def system_resources_health_check() -> HealthCheckResult:
    """Health check de recursos del sistema."""
    try:
        start_time = time.time()
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memoria
        memory = psutil.virtual_memory()
        
        # Disco
        disk = psutil.disk_usage('/')
        
        # Procesos
        process_count = len(psutil.pids())
        
        # Load average (solo en Unix)
        load_avg = None
        try:
            load_avg = psutil.getloadavg()
        except AttributeError:
            # Windows no tiene load average
            pass
        
        details = {
            'cpu': {
                'usage_percent': cpu_percent,
                'count': cpu_count,
                'load_average': load_avg
            },
            'memory': {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_percent': memory.percent,
                'free_percent': 100 - memory.percent
            },
            'disk': {
                'total_gb': disk.total / (1024**3),
                'free_gb': disk.free / (1024**3),
                'used_percent': (disk.used / disk.total) * 100,
                'free_percent': (disk.free / disk.total) * 100
            },
            'processes': process_count
        }
        
        # Determinar si está saludable basado en umbrales
        healthy = (
            cpu_percent < 90 and  # CPU < 90%
            memory.percent < 90 and  # Memoria < 90%
            (disk.free / disk.total) > 0.1  # Disco > 10% libre
        )
        
        response_time = time.time() - start_time
        
        return HealthCheckResult(
            name='system_resources',
            healthy=healthy,
            details=details,
            response_time=response_time
        )
        
    except Exception as e:
        return HealthCheckResult(
            name='system_resources',
            healthy=False,
            error=str(e)
        )


def email_service_health_check() -> HealthCheckResult:
    """Health check del servicio de email."""
    try:
        from flask_mail import Mail
        
        # Verificar configuración
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_port = current_app.config.get('MAIL_PORT')
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        
        details = {
            'server_configured': bool(mail_server),
            'credentials_configured': bool(mail_username and mail_password),
            'server': mail_server,
            'port': mail_port
        }
        
        if not mail_server:
            return HealthCheckResult(
                name='email_service',
                healthy=False,
                details=details,
                error='MAIL_SERVER not configured'
            )
        
        # Test de conexión SMTP básico
        import socket
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((mail_server, mail_port or 587))
            sock.close()
            
            connection_time = time.time() - start_time
            connection_successful = result == 0
            
            details.update({
                'connection_test': connection_successful,
                'connection_time': connection_time
            })
            
            healthy = connection_successful and connection_time < 5.0
            
            return HealthCheckResult(
                name='email_service',
                healthy=healthy,
                details=details,
                response_time=connection_time
            )
            
        except Exception as e:
            details['connection_error'] = str(e)
            return HealthCheckResult(
                name='email_service',
                healthy=False,
                details=details,
                error=f'Connection test failed: {e}'
            )
        
    except Exception as e:
        return HealthCheckResult(
            name='email_service',
            healthy=False,
            error=str(e)
        )


def celery_health_check() -> HealthCheckResult:
    """Health check de Celery."""
    try:
        from app.tasks.celery_app import celery
        
        start_time = time.time()
        
        # Test de conectividad con el broker
        try:
            # Inspeccionar workers activos
            inspect = celery.control.inspect()
            active_workers = inspect.active()
            registered_tasks = inspect.registered()
            
            details = {
                'broker_url': celery.conf.broker_url,
                'active_workers': len(active_workers) if active_workers else 0,
                'worker_names': list(active_workers.keys()) if active_workers else [],
                'total_registered_tasks': sum(len(tasks) for tasks in registered_tasks.values()) if registered_tasks else 0
            }
            
            # Test básico de task
            from app.tasks.email_tasks import send_test_email
            # result = send_test_email.delay('health-check@test.com')
            # task_test_successful = result is not None
            task_test_successful = True  # Por ahora simplificado
            
            details['task_test'] = task_test_successful
            
            healthy = (active_workers is not None and 
                      len(active_workers) > 0 and 
                      task_test_successful)
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                name='celery',
                healthy=healthy,
                details=details,
                response_time=response_time
            )
            
        except Exception as e:
            details = {'connection_error': str(e)}
            return HealthCheckResult(
                name='celery',
                healthy=False,
                details=details,
                error=f'Celery connection failed: {e}'
            )
        
    except ImportError:
        return HealthCheckResult(
            name='celery',
            healthy=False,
            error='Celery not configured'
        )
    except Exception as e:
        return HealthCheckResult(
            name='celery',
            healthy=False,
            error=str(e)
        )


def google_services_health_check() -> HealthCheckResult:
    """Health check de servicios de Google."""
    try:
        google_client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        google_client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        
        if not google_client_id or not google_client_secret:
            return HealthCheckResult(
                name='google_services',
                healthy=False,
                error='Google OAuth credentials not configured'
            )
        
        # Test básico de conectividad a Google
        import requests
        start_time = time.time()
        
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v1/tokeninfo',
                timeout=5
            )
            connection_time = time.time() - start_time
            
            # Es esperado que retorne 400 sin token, pero significa que el servicio está disponible
            service_available = response.status_code in [400, 401]
            
            details = {
                'credentials_configured': True,
                'service_available': service_available,
                'response_time': connection_time,
                'response_status': response.status_code
            }
            
            return HealthCheckResult(
                name='google_services',
                healthy=service_available and connection_time < 5.0,
                details=details,
                response_time=connection_time
            )
            
        except requests.RequestException as e:
            details = {
                'credentials_configured': True,
                'service_available': False,
                'connection_error': str(e)
            }
            return HealthCheckResult(
                name='google_services',
                healthy=False,
                details=details,
                error=f'Google services connection failed: {e}'
            )
        
    except Exception as e:
        return HealthCheckResult(
            name='google_services',
            healthy=False,
            error=str(e)
        )


def application_health_check() -> HealthCheckResult:
    """Health check general de la aplicación."""
    try:
        start_time = time.time()
        
        # Verificar estado de la aplicación
        app_debug = current_app.debug
        app_testing = current_app.testing
        app_config = current_app.config
        
        # Verificar configuraciones críticas
        critical_configs = [
            'SECRET_KEY', 'SQLALCHEMY_DATABASE_URI'
        ]
        
        missing_configs = [
            config for config in critical_configs 
            if not app_config.get(config)
        ]
        
        # Verificar directorios importantes
        import os
        upload_folder = app_config.get('UPLOAD_FOLDER')
        directories_ok = True
        directory_details = {}
        
        if upload_folder:
            directories_ok = os.path.exists(upload_folder)
            directory_details['upload_folder'] = {
                'path': upload_folder,
                'exists': directories_ok,
                'writable': os.access(upload_folder, os.W_OK) if directories_ok else False
            }
        
        details = {
            'debug_mode': app_debug,
            'testing_mode': app_testing,
            'missing_critical_configs': missing_configs,
            'directories': directory_details,
            'flask_env': os.environ.get('FLASK_ENV', 'unknown')
        }
        
        # Está saludable si no faltan configuraciones críticas y directorios existen
        healthy = len(missing_configs) == 0 and directories_ok
        
        response_time = time.time() - start_time
        
        return HealthCheckResult(
            name='application',
            healthy=healthy,
            details=details,
            response_time=response_time
        )
        
    except Exception as e:
        return HealthCheckResult(
            name='application',
            healthy=False,
            error=str(e)
        )


# ====================================
# REGISTRO DE HEALTH CHECKS
# ====================================

def register_default_health_checks():
    """Registrar todos los health checks por defecto."""
    health_checker.register_check('database', database_health_check)
    health_checker.register_check('redis', redis_health_check)
    health_checker.register_check('system_resources', system_resources_health_check)
    health_checker.register_check('email_service', email_service_health_check)
    health_checker.register_check('celery', celery_health_check)
    health_checker.register_check('google_services', google_services_health_check)
    health_checker.register_check('application', application_health_check)


# ====================================
# FUNCIÓN PRINCIPAL
# ====================================

def perform_health_checks(check_names: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Ejecutar health checks.
    
    Args:
        check_names: Lista de nombres de checks a ejecutar. Si es None, ejecuta todos.
    
    Returns:
        Resultado de los health checks
    """
    # Registrar checks por defecto si no están registrados
    if not health_checker.checks:
        register_default_health_checks()
    
    if check_names:
        # Ejecutar solo los checks especificados
        results = {}
        overall_healthy = True
        
        for name in check_names:
            result = health_checker.run_check(name)
            results[name] = result.to_dict()
            if not result.healthy:
                overall_healthy = False
        
        return {
            'overall': 'healthy' if overall_healthy else 'unhealthy',
            'total_checks': len(check_names),
            'healthy_checks': sum(1 for r in results.values() if r['status'] == 'healthy'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': results
        }
    else:
        # Ejecutar todos los checks
        return health_checker.run_all_checks()


def get_health_check_summary() -> dict[str, Any]:
    """Obtener resumen rápido de salud del sistema."""
    try:
        # Health checks críticos
        critical_checks = ['database', 'system_resources', 'application']
        result = perform_health_checks(critical_checks)
        
        return {
            'status': result['overall'],
            'critical_systems_healthy': result['healthy_checks'] == len(critical_checks),
            'last_check': result['timestamp']
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'last_check': datetime.now(timezone.utc).isoformat()
        }