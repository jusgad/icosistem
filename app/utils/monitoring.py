"""
Sistema de monitoreo y métricas para el ecosistema de emprendimiento.
Integra Prometheus, health checks y métricas de negocio.
"""

import os
import time
import psutil
from typing import Dict, List, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, request, g, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


# ====================================
# MÉTRICAS PROMETHEUS
# ====================================

# Métricas de HTTP
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Métricas de usuarios
active_users_gauge = Gauge(
    'active_users_total',
    'Number of active users',
    ['role']
)

user_sessions_total = Counter(
    'user_sessions_total',
    'Total user sessions',
    ['role']
)

# Métricas de negocio
projects_created_total = Counter(
    'projects_created_total',
    'Total projects created',
    ['status']
)

mentorship_sessions_total = Counter(
    'mentorship_sessions_total',
    'Total mentorship sessions',
    ['type']
)

meetings_scheduled_total = Counter(
    'meetings_scheduled_total',
    'Total meetings scheduled',
    ['type']
)

# Métricas de sistema
system_cpu_usage = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

system_memory_usage = Gauge(
    'system_memory_usage_percent',
    'System memory usage percentage'
)

database_connections = Gauge(
    'database_connections_total',
    'Number of database connections'
)

# Métricas de errores
application_errors_total = Counter(
    'application_errors_total',
    'Total application errors',
    ['error_type', 'endpoint']
)

# Métricas de integración
integration_requests_total = Counter(
    'integration_requests_total',
    'Total integration requests',
    ['service', 'operation', 'status']
)

integration_request_duration_seconds = Histogram(
    'integration_request_duration_seconds',
    'Integration request duration in seconds',
    ['service', 'operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)


# ====================================
# DECORADORES PARA MÉTRICAS
# ====================================

def track_time(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator para rastrear tiempo de ejecución."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                raise
            finally:
                duration = time.time() - start_time
                # Aquí se podría usar la métrica específica según metric_name
                # Por simplicidad, usamos la métrica de integración
                if metric_name == 'integration':
                    service = labels.get('service', 'unknown') if labels else 'unknown'
                    operation = labels.get('operation', 'unknown') if labels else 'unknown'
                    integration_request_duration_seconds.labels(
                        service=service,
                        operation=operation
                    ).observe(duration)
        
        return wrapper
    return decorator


def count_calls(metric: Counter, labels: Optional[Dict[str, str]] = None):
    """Decorator para contar llamadas a funciones."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                metric.labels(**(labels or {})).inc()
                return result
            except Exception:
                # También contar errores si se desea
                raise
        
        return wrapper
    return decorator


# ====================================
# MIDDLEWARE DE MONITOREO
# ====================================

def setup_monitoring(app: Flask) -> None:
    """
    Configurar el sistema de monitoreo para la aplicación Flask.
    
    Args:
        app: Instancia de la aplicación Flask
    """
    
    @app.before_request
    def start_timer():
        """Iniciar temporizador para la request."""
        g.start_time = time.time()
        g.request_id = generate_request_id()
    
    @app.after_request
    def record_request_data(response):
        """Registrar métricas de la request."""
        if hasattr(g, 'start_time'):
            # Calcular duración
            duration = time.time() - g.start_time
            
            # Obtener información de la request
            method = request.method
            endpoint = request.endpoint or 'unknown'
            status = str(response.status_code)
            
            # Actualizar métricas
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            # Log de request si es necesario
            if duration > 5.0:  # Requests lentas
                app.logger.warning(f"Slow request: {method} {request.url} took {duration:.2f}s")
        
        return response
    
    @app.errorhandler(Exception)
    def track_errors(error):
        """Rastrear errores de aplicación."""
        error_type = error.__class__.__name__
        endpoint = request.endpoint or 'unknown'
        
        application_errors_total.labels(
            error_type=error_type,
            endpoint=endpoint
        ).inc()
        
        # Re-raise la excepción para que sea manejada normalmente
        raise error
    
    # Endpoint para métricas de Prometheus
    @app.route('/metrics')
    def metrics():
        """Endpoint para exportar métricas de Prometheus."""
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    # Inicializar collector de métricas del sistema
    start_system_metrics_collection()
    
    app.logger.info("Monitoring system initialized")


def generate_request_id() -> str:
    """Generar ID único para la request."""
    import uuid
    return str(uuid.uuid4())[:8]


# ====================================
# MÉTRICAS DEL SISTEMA
# ====================================

def start_system_metrics_collection():
    """Iniciar recolección de métricas del sistema."""
    import threading
    import time
    
    def collect_system_metrics():
        """Recolectar métricas del sistema en background."""
        while True:
            try:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                system_cpu_usage.set(cpu_percent)
                
                # Memoria
                memory = psutil.virtual_memory()
                system_memory_usage.set(memory.percent)
                
                # Dormir antes de la siguiente recolección
                time.sleep(30)  # Cada 30 segundos
                
            except Exception as e:
                # Log error pero continuar
                import logging
                logger = logging.getLogger('app')
                logger.error(f"Error collecting system metrics: {e}")
                time.sleep(60)  # Esperar más tiempo si hay error
    
    # Iniciar thread en background
    thread = threading.Thread(target=collect_system_metrics, daemon=True)
    thread.start()


# ====================================
# MÉTRICAS DE NEGOCIO
# ====================================

def update_user_metrics():
    """Actualizar métricas de usuarios."""
    try:
        from app.models.user import User
        from app.extensions import db
        
        # Contar usuarios activos por rol
        roles = ['admin', 'entrepreneur', 'ally', 'client']
        for role in roles:
            count = db.session.query(User).filter_by(
                role=role,
                is_active=True
            ).count()
            active_users_gauge.labels(role=role).set(count)
            
    except Exception as e:
        import logging
        logger = logging.getLogger('app')
        logger.error(f"Error updating user metrics: {e}")


def track_user_login(user_role: str):
    """Rastrear login de usuario."""
    user_sessions_total.labels(role=user_role).inc()


def track_project_created(status: str = 'draft'):
    """Rastrear creación de proyecto."""
    projects_created_total.labels(status=status).inc()


def track_mentorship_session(session_type: str = 'individual'):
    """Rastrear sesión de mentoría."""
    mentorship_sessions_total.labels(type=session_type).inc()


def track_meeting_scheduled(meeting_type: str = 'mentorship'):
    """Rastrear reunión programada."""
    meetings_scheduled_total.labels(type=meeting_type).inc()


def track_integration_call(service: str, operation: str, success: bool, duration: float):
    """Rastrear llamada a integración externa."""
    status = 'success' if success else 'error'
    
    integration_requests_total.labels(
        service=service,
        operation=operation,
        status=status
    ).inc()
    
    integration_request_duration_seconds.labels(
        service=service,
        operation=operation
    ).observe(duration)


# ====================================
# HEALTH CHECKS
# ====================================

class HealthCheck:
    """Sistema de health checks."""
    
    def __init__(self):
        self.checks = {}
    
    def add_check(self, name: str, check_func: Callable[[], Dict[str, Any]]):
        """Agregar un check de salud."""
        self.checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """Ejecutar todos los checks de salud."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                result = check_func()
                duration = time.time() - start_time
                
                results[name] = {
                    'status': 'healthy' if result.get('healthy', True) else 'unhealthy',
                    'details': result,
                    'response_time': duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                if not result.get('healthy', True):
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                overall_healthy = False
        
        return {
            'overall': 'healthy' if overall_healthy else 'unhealthy',
            'checks': results,
            'timestamp': datetime.utcnow().isoformat()
        }


# Instancia global de health checker
health_checker = HealthCheck()


def check_database():
    """Check de salud de la base de datos."""
    try:
        from app.extensions import db
        
        # Ejecutar query simple
        start_time = time.time()
        result = db.session.execute('SELECT 1')
        query_time = time.time() - start_time
        
        # Obtener información de conexiones si es posible
        try:
            pool = db.engine.pool
            pool_info = {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout()
            }
            database_connections.set(pool.checkedout())
        except:
            pool_info = {'info': 'Pool info not available'}
        
        return {
            'healthy': True,
            'query_time': query_time,
            'connection_pool': pool_info
        }
        
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }


def check_redis():
    """Check de salud de Redis."""
    try:
        from app.extensions import redis_client
        
        if not redis_client:
            return {'healthy': False, 'error': 'Redis client not configured'}
        
        start_time = time.time()
        redis_client.ping()
        response_time = time.time() - start_time
        
        # Información adicional de Redis
        info = redis_client.info()
        
        return {
            'healthy': True,
            'response_time': response_time,
            'version': info.get('redis_version'),
            'connected_clients': info.get('connected_clients'),
            'used_memory_human': info.get('used_memory_human')
        }
        
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }


def check_disk_space():
    """Check de espacio en disco."""
    try:
        usage = psutil.disk_usage('/')
        free_percent = (usage.free / usage.total) * 100
        
        return {
            'healthy': free_percent > 10,  # Saludable si hay más del 10% libre
            'free_percent': free_percent,
            'free_gb': usage.free / (1024**3),
            'total_gb': usage.total / (1024**3)
        }
        
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }


def check_email_service():
    """Check del servicio de email."""
    try:
        from flask import current_app
        
        # Verificar configuración
        mail_server = current_app.config.get('MAIL_SERVER')
        mail_username = current_app.config.get('MAIL_USERNAME')
        
        if not mail_server or not mail_username:
            return {
                'healthy': False,
                'error': 'Email service not configured'
            }
        
        # Aquí se podría hacer un test real de SMTP
        # Por ahora solo verificamos configuración
        return {
            'healthy': True,
            'server': mail_server,
            'configured': True
        }
        
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }


# Registrar checks por defecto
health_checker.add_check('database', check_database)
health_checker.add_check('redis', check_redis)
health_checker.add_check('disk_space', check_disk_space)
health_checker.add_check('email_service', check_email_service)


def perform_health_checks() -> Dict[str, Any]:
    """
    Ejecutar todos los health checks registrados.
    
    Returns:
        Resultado de todos los health checks
    """
    return health_checker.run_checks()


# ====================================
# DASHBOARD DE MÉTRICAS
# ====================================

def get_metrics_summary() -> Dict[str, Any]:
    """Obtener resumen de métricas para dashboard."""
    try:
        from app.models.user import User
        from app.models.project import Project
        from app.models.meeting import Meeting
        from app.extensions import db
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        # Métricas de usuarios
        total_users = db.session.query(User).count()
        active_users = db.session.query(User).filter_by(is_active=True).count()
        new_users_24h = db.session.query(User).filter(User.created_at >= last_24h).count()
        
        # Métricas de proyectos
        total_projects = db.session.query(Project).count()
        active_projects = db.session.query(Project).filter_by(status='active').count()
        new_projects_24h = db.session.query(Project).filter(Project.created_at >= last_24h).count()
        
        # Métricas de reuniones
        total_meetings = db.session.query(Meeting).count()
        meetings_24h = db.session.query(Meeting).filter(Meeting.created_at >= last_24h).count()
        
        # Métricas del sistema
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        
        return {
            'users': {
                'total': total_users,
                'active': active_users,
                'new_24h': new_users_24h
            },
            'projects': {
                'total': total_projects,
                'active': active_projects,
                'new_24h': new_projects_24h
            },
            'meetings': {
                'total': total_meetings,
                'new_24h': meetings_24h
            },
            'system': {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage
            },
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger('app')
        logger.error(f"Error getting metrics summary: {e}")
        return {'error': str(e)}


# ====================================
# ALERTAS
# ====================================

class AlertManager:
    """Gestor de alertas del sistema."""
    
    def __init__(self):
        self.thresholds = {
            'cpu_usage': 80,  # %
            'memory_usage': 85,  # %
            'disk_usage': 90,  # %
            'response_time': 5.0,  # seconds
            'error_rate': 5,  # %
        }
        self.alert_handlers = []
    
    def add_alert_handler(self, handler: Callable[[str, Dict], None]):
        """Agregar handler para alertas."""
        self.alert_handlers.append(handler)
    
    def check_thresholds(self, metrics: Dict[str, Any]):
        """Verificar umbrales y enviar alertas si es necesario."""
        alerts = []
        
        # Check CPU
        cpu = metrics.get('system', {}).get('cpu_usage', 0)
        if cpu > self.thresholds['cpu_usage']:
            alerts.append({
                'type': 'cpu_high',
                'message': f'High CPU usage: {cpu}%',
                'value': cpu,
                'threshold': self.thresholds['cpu_usage']
            })
        
        # Check Memory
        memory = metrics.get('system', {}).get('memory_usage', 0)
        if memory > self.thresholds['memory_usage']:
            alerts.append({
                'type': 'memory_high',
                'message': f'High memory usage: {memory}%',
                'value': memory,
                'threshold': self.thresholds['memory_usage']
            })
        
        # Enviar alertas
        for alert in alerts:
            self._send_alert(alert)
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Enviar alerta a todos los handlers registrados."""
        for handler in self.alert_handlers:
            try:
                handler(alert['type'], alert)
            except Exception as e:
                import logging
                logger = logging.getLogger('app')
                logger.error(f"Error sending alert: {e}")


# Instancia global del gestor de alertas
alert_manager = AlertManager()


def email_alert_handler(alert_type: str, alert: Dict[str, Any]):
    """Handler para enviar alertas por email."""
    try:
        from flask_mail import Message
        from app.extensions import mail
        from flask import current_app
        
        msg = Message(
            subject=f'[ALERT] {alert_type.upper()} - {current_app.config.get("APP_NAME", "App")}',
            recipients=[current_app.config.get('ADMIN_EMAIL')],
            body=f"""
Alert: {alert['message']}
Value: {alert['value']}
Threshold: {alert['threshold']}
Time: {datetime.utcnow().isoformat()}
            """
        )
        
        mail.send(msg)
        
    except Exception as e:
        import logging
        logger = logging.getLogger('app')
        logger.error(f"Error sending email alert: {e}")


# Registrar handler de alertas por email por defecto
alert_manager.add_alert_handler(email_alert_handler)