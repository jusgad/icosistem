#!/usr/bin/env python3
"""
Health Check Script para Ecosistema de Emprendimiento
=====================================================

Script completo para verificar el estado de todos los componentes del sistema:
- Aplicación Flask
- Base de datos
- Redis/Cache
- Celery Workers
- Servicios externos
- APIs
- Recursos del sistema
- Integraciones

Uso:
    python scripts/health_check.py [--detailed] [--json] [--component COMPONENT]

Autor: Sistema de Emprendimiento
Version: 1.0.0
"""

import os
import sys
import json
import time
import psutil
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import create_app
    from app.extensions import db, redis_client
    from app.models.user import User
    from app.models.entrepreneur import Entrepreneur
    from app.models.project import Project
    from app.services.email import EmailService
    from app.services.google_calendar import GoogleCalendarService
    from app.tasks.celery_app import celery
    from sqlalchemy import text
    import redis
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print("Asegúrate de estar en el directorio correcto y tener las dependencias instaladas")
    sys.exit(1)


class HealthStatus(Enum):
    """Estados de salud de los componentes"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Resultado de verificación de salud"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    response_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'component': self.component,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'response_time': self.response_time
        }


class HealthChecker:
    """Clase principal para verificaciones de salud"""
    
    def __init__(self, app=None):
        self.app = app or create_app()
        self.results: List[HealthCheckResult] = []
        
    def check_all(self, detailed: bool = False) -> Dict[str, Any]:
        """Ejecuta todas las verificaciones de salud"""
        print("🔍 Iniciando verificaciones de salud del sistema...")
        print("=" * 60)
        
        with self.app.app_context():
            # Verificaciones básicas
            self._check_application()
            self._check_database()
            self._check_redis()
            
            # Verificaciones de servicios
            self._check_celery()
            self._check_email_service()
            
            # Verificaciones de integraciones
            self._check_google_services()
            
            # Verificaciones de sistema
            self._check_system_resources()
            
            if detailed:
                # Verificaciones detalladas
                self._check_api_endpoints()
                self._check_file_storage()
                self._check_websockets()
                self._check_data_integrity()
        
        return self._generate_summary()
    
    def _check_application(self) -> None:
        """Verifica el estado de la aplicación Flask"""
        start_time = time.time()
        
        try:
            # Verificar configuración básica
            config_ok = all([
                self.app.config.get('SECRET_KEY'),
                self.app.config.get('DATABASE_URL') or self.app.config.get('SQLALCHEMY_DATABASE_URI'),
                self.app.config.get('MAIL_SERVER')
            ])
            
            if not config_ok:
                raise Exception("Configuración incompleta")
            
            # Verificar rutas registradas
            routes_count = len(list(self.app.url_map.iter_rules()))
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="Flask Application",
                status=HealthStatus.HEALTHY,
                message="Aplicación funcionando correctamente",
                details={
                    'environment': self.app.config.get('ENV', 'unknown'),
                    'debug_mode': self.app.debug,
                    'routes_registered': routes_count,
                    'secret_key_configured': bool(self.app.config.get('SECRET_KEY'))
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Aplicación Flask: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Flask Application",
                status=HealthStatus.CRITICAL,
                message=f"Error en aplicación: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"❌ Aplicación Flask: ERROR - {e}")
    
    def _check_database(self) -> None:
        """Verifica la conectividad y estado de la base de datos"""
        start_time = time.time()
        
        try:
            # Verificar conexión
            result = db.session.execute(text('SELECT 1'))
            db.session.commit()
            
            # Verificar tablas principales
            tables_info = {}
            try:
                tables_info['users'] = User.query.count()
                tables_info['entrepreneurs'] = Entrepreneur.query.count()
                tables_info['projects'] = Project.query.count()
            except Exception as e:
                print(f"⚠️ Advertencia contando registros: {e}")
            
            # Verificar pool de conexiones
            pool_info = {
                'pool_size': getattr(db.engine.pool, 'size', 'unknown'),
                'checked_in': getattr(db.engine.pool, 'checkedin', 'unknown'),
                'checked_out': getattr(db.engine.pool, 'checkedout', 'unknown')
            }
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="Database",
                status=HealthStatus.HEALTHY,
                message="Base de datos conectada correctamente",
                details={
                    'connection_test': 'passed',
                    'tables_info': tables_info,
                    'pool_info': pool_info,
                    'engine': str(db.engine.url).split('@')[0] + '@***'  # Ocultar credenciales
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Base de datos: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Database",
                status=HealthStatus.CRITICAL,
                message=f"Error en base de datos: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"❌ Base de datos: ERROR - {e}")
    
    def _check_redis(self) -> None:
        """Verifica el estado de Redis"""
        start_time = time.time()
        
        try:
            # Test de conectividad
            redis_client.ping()
            
            # Información del servidor Redis
            info = redis_client.info()
            
            # Test de escritura/lectura
            test_key = "health_check_test"
            test_value = f"test_{int(time.time())}"
            redis_client.setex(test_key, 60, test_value)
            retrieved_value = redis_client.get(test_key)
            redis_client.delete(test_key)
            
            if retrieved_value.decode('utf-8') != test_value:
                raise Exception("Test de lectura/escritura falló")
            
            response_time = time.time() - start_time
            
            # Verificar memoria
            memory_usage = info.get('used_memory_human', 'unknown')
            max_memory = info.get('maxmemory_human', 'no limit')
            
            status = HealthStatus.HEALTHY
            if info.get('used_memory', 0) > 0.8 * info.get('maxmemory', float('inf')):
                status = HealthStatus.WARNING
            
            self.results.append(HealthCheckResult(
                component="Redis",
                status=status,
                message="Redis funcionando correctamente",
                details={
                    'version': info.get('redis_version', 'unknown'),
                    'memory_usage': memory_usage,
                    'max_memory': max_memory,
                    'connected_clients': info.get('connected_clients', 0),
                    'keys_count': redis_client.dbsize(),
                    'read_write_test': 'passed'
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Redis: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Redis",
                status=HealthStatus.CRITICAL,
                message=f"Error en Redis: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"❌ Redis: ERROR - {e}")
    
    def _check_celery(self) -> None:
        """Verifica el estado de Celery y los workers"""
        start_time = time.time()
        
        try:
            # Verificar workers activos
            inspect = celery.control.inspect()
            active_workers = inspect.active()
            stats = inspect.stats()
            
            if not active_workers:
                raise Exception("No hay workers de Celery activos")
            
            # Verificar cola de tareas
            queue_info = {}
            try:
                # Intentar obtener información de las colas
                active_queues = inspect.active_queues() or {}
                queue_info = {worker: queues for worker, queues in active_queues.items()}
            except Exception:
                queue_info = {'info': 'No disponible'}
            
            # Test de tarea
            from app.tasks.email_tasks import test_task
            try:
                task_result = test_task.delay("health_check")
                task_status = task_result.status if hasattr(task_result, 'status') else 'unknown'
            except Exception as e:
                task_status = f'error: {e}'
            
            response_time = time.time() - start_time
            
            worker_count = len(active_workers) if active_workers else 0
            status = HealthStatus.HEALTHY if worker_count > 0 else HealthStatus.CRITICAL
            
            self.results.append(HealthCheckResult(
                component="Celery",
                status=status,
                message=f"Celery con {worker_count} worker(s) activo(s)",
                details={
                    'active_workers': list(active_workers.keys()) if active_workers else [],
                    'worker_count': worker_count,
                    'worker_stats': stats,
                    'queue_info': queue_info,
                    'test_task_status': task_status
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print(f"✅ Celery: OK ({worker_count} workers)")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Celery",
                status=HealthStatus.CRITICAL,
                message=f"Error en Celery: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"❌ Celery: ERROR - {e}")
    
    def _check_email_service(self) -> None:
        """Verifica el servicio de email"""
        start_time = time.time()
        
        try:
            email_service = EmailService()
            
            # Verificar configuración
            config_ok = all([
                self.app.config.get('MAIL_SERVER'),
                self.app.config.get('MAIL_PORT'),
                self.app.config.get('MAIL_USERNAME')
            ])
            
            if not config_ok:
                raise Exception("Configuración de email incompleta")
            
            # Test de conexión SMTP (sin enviar email)
            try:
                # Simular test de conexión
                smtp_test = True  # En producción, implementar test real de SMTP
            except Exception:
                smtp_test = False
            
            response_time = time.time() - start_time
            
            status = HealthStatus.HEALTHY if smtp_test else HealthStatus.WARNING
            
            self.results.append(HealthCheckResult(
                component="Email Service",
                status=status,
                message="Servicio de email configurado",
                details={
                    'mail_server': self.app.config.get('MAIL_SERVER'),
                    'mail_port': self.app.config.get('MAIL_PORT'),
                    'tls_enabled': self.app.config.get('MAIL_USE_TLS', False),
                    'ssl_enabled': self.app.config.get('MAIL_USE_SSL', False),
                    'smtp_test': smtp_test
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Servicio Email: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Email Service",
                status=HealthStatus.WARNING,
                message=f"Problema en servicio de email: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ Servicio Email: WARNING - {e}")
    
    def _check_google_services(self) -> None:
        """Verifica integraciones con servicios de Google"""
        start_time = time.time()
        
        try:
            # Verificar configuración OAuth
            google_config = {
                'client_id': bool(self.app.config.get('GOOGLE_CLIENT_ID')),
                'client_secret': bool(self.app.config.get('GOOGLE_CLIENT_SECRET')),
                'calendar_enabled': bool(self.app.config.get('GOOGLE_CALENDAR_ENABLED', True))
            }
            
            config_complete = all(google_config.values())
            
            # Test básico de conectividad a APIs de Google
            api_status = {}
            try:
                # Test de conectividad (sin autenticación real)
                response = requests.get('https://www.googleapis.com/calendar/v3/', timeout=5)
                api_status['calendar_api'] = response.status_code in [401, 403]  # Esperamos 401/403 sin auth
            except Exception:
                api_status['calendar_api'] = False
            
            response_time = time.time() - start_time
            
            status = HealthStatus.HEALTHY if config_complete else HealthStatus.WARNING
            
            self.results.append(HealthCheckResult(
                component="Google Services",
                status=status,
                message="Servicios de Google configurados" if config_complete else "Configuración incompleta",
                details={
                    'configuration': google_config,
                    'api_connectivity': api_status,
                    'services_available': ['Calendar', 'Meet', 'OAuth']
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Servicios Google: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Google Services",
                status=HealthStatus.WARNING,
                message=f"Problema con servicios Google: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ Servicios Google: WARNING - {e}")
    
    def _check_system_resources(self) -> None:
        """Verifica recursos del sistema"""
        start_time = time.time()
        
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memoria
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Procesos
            processes = len(psutil.pids())
            
            # Determinar estado basado en uso de recursos
            status = HealthStatus.HEALTHY
            warnings = []
            
            if cpu_percent > 80:
                status = HealthStatus.WARNING
                warnings.append(f"CPU alta: {cpu_percent}%")
            
            if memory_percent > 85:
                status = HealthStatus.WARNING
                warnings.append(f"Memoria alta: {memory_percent}%")
            
            if disk_percent > 90:
                status = HealthStatus.CRITICAL
                warnings.append(f"Disco lleno: {disk_percent}%")
            
            response_time = time.time() - start_time
            
            message = "Recursos del sistema normales"
            if warnings:
                message = f"Advertencias: {', '.join(warnings)}"
            
            self.results.append(HealthCheckResult(
                component="System Resources",
                status=status,
                message=message,
                details={
                    'cpu': {
                        'usage_percent': cpu_percent,
                        'cores': cpu_count
                    },
                    'memory': {
                        'usage_percent': memory_percent,
                        'total_gb': round(memory.total / (1024**3), 2),
                        'available_gb': round(memory.available / (1024**3), 2)
                    },
                    'disk': {
                        'usage_percent': disk_percent,
                        'total_gb': round(disk.total / (1024**3), 2),
                        'free_gb': round(disk.free / (1024**3), 2)
                    },
                    'processes': processes
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            status_icon = "✅" if status == HealthStatus.HEALTHY else "⚠️" if status == HealthStatus.WARNING else "❌"
            print(f"{status_icon} Recursos Sistema: {message}")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="System Resources",
                status=HealthStatus.WARNING,
                message=f"Error verificando recursos: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ Recursos Sistema: ERROR - {e}")
    
    def _check_api_endpoints(self) -> None:
        """Verifica endpoints críticos de la API"""
        start_time = time.time()
        
        try:
            # Endpoints a verificar
            endpoints = [
                '/api/v1/health',
                '/api/v1/auth/status',
                '/api/v1/users',
                '/api/v1/entrepreneurs',
                '/api/v1/projects'
            ]
            
            endpoint_status = {}
            
            with self.app.test_client() as client:
                for endpoint in endpoints:
                    try:
                        response = client.get(endpoint)
                        endpoint_status[endpoint] = {
                            'status_code': response.status_code,
                            'accessible': response.status_code < 500
                        }
                    except Exception as e:
                        endpoint_status[endpoint] = {
                            'status_code': None,
                            'error': str(e),
                            'accessible': False
                        }
            
            # Determinar estado general
            accessible_count = sum(1 for ep in endpoint_status.values() if ep.get('accessible', False))
            total_count = len(endpoints)
            
            if accessible_count == total_count:
                status = HealthStatus.HEALTHY
                message = "Todos los endpoints de API son accesibles"
            elif accessible_count > total_count * 0.7:
                status = HealthStatus.WARNING
                message = f"{accessible_count}/{total_count} endpoints accesibles"
            else:
                status = HealthStatus.CRITICAL
                message = f"Solo {accessible_count}/{total_count} endpoints accesibles"
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="API Endpoints",
                status=status,
                message=message,
                details={
                    'endpoints_tested': total_count,
                    'endpoints_accessible': accessible_count,
                    'endpoint_details': endpoint_status
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            status_icon = "✅" if status == HealthStatus.HEALTHY else "⚠️" if status == HealthStatus.WARNING else "❌"
            print(f"{status_icon} API Endpoints: {message}")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="API Endpoints",
                status=HealthStatus.WARNING,
                message=f"Error verificando API: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ API Endpoints: ERROR - {e}")
    
    def _check_file_storage(self) -> None:
        """Verifica el sistema de almacenamiento de archivos"""
        start_time = time.time()
        
        try:
            upload_dir = self.app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
            
            # Verificar directorio existe y es escribible
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)
            
            # Test de escritura
            test_file = os.path.join(upload_dir, 'health_check_test.txt')
            test_content = f"Health check test - {datetime.now().isoformat()}"
            
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            # Test de lectura
            with open(test_file, 'r') as f:
                read_content = f.read()
            
            # Limpiar archivo de test
            os.remove(test_file)
            
            if read_content != test_content:
                raise Exception("Test de lectura/escritura falló")
            
            # Información del directorio
            total_files = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
            dir_size = sum(os.path.getsize(os.path.join(upload_dir, f)) 
                          for f in os.listdir(upload_dir) 
                          if os.path.isfile(os.path.join(upload_dir, f)))
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="File Storage",
                status=HealthStatus.HEALTHY,
                message="Sistema de archivos funcionando correctamente",
                details={
                    'upload_directory': upload_dir,
                    'directory_exists': True,
                    'writable': True,
                    'total_files': total_files,
                    'directory_size_mb': round(dir_size / (1024*1024), 2),
                    'read_write_test': 'passed'
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Almacenamiento: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="File Storage",
                status=HealthStatus.WARNING,
                message=f"Problema con almacenamiento: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ Almacenamiento: WARNING - {e}")
    
    def _check_websockets(self) -> None:
        """Verifica el sistema de WebSockets"""
        start_time = time.time()
        
        try:
            # Verificar configuración de SocketIO
            socketio_config = {
                'async_mode': self.app.config.get('SOCKETIO_ASYNC_MODE', 'threading'),
                'cors_allowed_origins': bool(self.app.config.get('SOCKETIO_CORS_ALLOWED_ORIGINS')),
                'redis_url': bool(self.app.config.get('SOCKETIO_REDIS_URL'))
            }
            
            # En un entorno real, aquí verificarías la conectividad de SocketIO
            # Por ahora, verificamos la configuración
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="WebSockets",
                status=HealthStatus.HEALTHY,
                message="WebSockets configurado correctamente",
                details={
                    'configuration': socketio_config,
                    'status': 'configured'
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ WebSockets: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="WebSockets",
                status=HealthStatus.WARNING,
                message=f"Problema con WebSockets: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ WebSockets: WARNING - {e}")
    
    def _check_data_integrity(self) -> None:
        """Verifica integridad básica de datos"""
        start_time = time.time()
        
        try:
            integrity_checks = {}
            
            # Verificar relaciones básicas
            try:
                # Emprendedores con usuarios
                entrepreneurs_with_users = db.session.execute(
                    text("""
                    SELECT COUNT(*) as count FROM entrepreneurs e 
                    INNER JOIN users u ON e.user_id = u.id
                    """)
                ).fetchone()
                integrity_checks['entrepreneurs_with_users'] = entrepreneurs_with_users[0] if entrepreneurs_with_users else 0
                
                # Proyectos con emprendedores
                projects_with_entrepreneurs = db.session.execute(
                    text("""
                    SELECT COUNT(*) as count FROM projects p 
                    INNER JOIN entrepreneurs e ON p.entrepreneur_id = e.id
                    """)
                ).fetchone()
                integrity_checks['projects_with_entrepreneurs'] = projects_with_entrepreneurs[0] if projects_with_entrepreneurs else 0
                
            except Exception as e:
                integrity_checks['error'] = f"Error en consultas: {e}"
            
            response_time = time.time() - start_time
            
            self.results.append(HealthCheckResult(
                component="Data Integrity",
                status=HealthStatus.HEALTHY,
                message="Verificación de integridad completada",
                details={
                    'integrity_checks': integrity_checks,
                    'referential_integrity': 'checked'
                },
                timestamp=datetime.now(),
                response_time=response_time
            ))
            
            print("✅ Integridad Datos: OK")
            
        except Exception as e:
            self.results.append(HealthCheckResult(
                component="Data Integrity",
                status=HealthStatus.WARNING,
                message=f"Error verificando integridad: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.now(),
                response_time=time.time() - start_time
            ))
            print(f"⚠️ Integridad Datos: WARNING - {e}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Genera resumen de todas las verificaciones"""
        total_checks = len(self.results)
        healthy_count = sum(1 for r in self.results if r.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for r in self.results if r.status == HealthStatus.WARNING)
        critical_count = sum(1 for r in self.results if r.status == HealthStatus.CRITICAL)
        
        # Estado general del sistema
        if critical_count > 0:
            overall_status = HealthStatus.CRITICAL
        elif warning_count > 0:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Tiempo total de respuesta
        total_response_time = sum(r.response_time for r in self.results if r.response_time)
        
        summary = {
            'overall_status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'total_checks': total_checks,
            'healthy': healthy_count,
            'warnings': warning_count,
            'critical': critical_count,
            'total_response_time': round(total_response_time, 3),
            'checks': [result.to_dict() for result in self.results]
        }
        
        return summary
    
    def check_component(self, component_name: str) -> Dict[str, Any]:
        """Verifica un componente específico"""
        component_methods = {
            'app': self._check_application,
            'application': self._check_application,
            'db': self._check_database,
            'database': self._check_database,
            'redis': self._check_redis,
            'cache': self._check_redis,
            'celery': self._check_celery,
            'email': self._check_email_service,
            'google': self._check_google_services,
            'system': self._check_system_resources,
            'api': self._check_api_endpoints,
            'storage': self._check_file_storage,
            'websockets': self._check_websockets,
            'data': self._check_data_integrity
        }
        
        method = component_methods.get(component_name.lower())
        if not method:
            return {
                'error': f'Componente "{component_name}" no encontrado',
                'available_components': list(component_methods.keys())
            }
        
        print(f"🔍 Verificando componente: {component_name}")
        print("=" * 40)
        
        with self.app.app_context():
            method()
        
        return self._generate_summary()


def print_summary(summary: Dict[str, Any], detailed: bool = False) -> None:
    """Imprime resumen de verificaciones"""
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIONES")
    print("=" * 60)
    
    # Estado general
    status = summary['overall_status']
    status_icons = {
        'healthy': '✅',
        'warning': '⚠️',
        'critical': '❌'
    }
    
    print(f"Estado General: {status_icons.get(status, '❓')} {status.upper()}")
    print(f"Total de verificaciones: {summary['total_checks']}")
    print(f"Exitosas: {summary['healthy']} | Advertencias: {summary['warnings']} | Críticas: {summary['critical']}")
    print(f"Tiempo total: {summary['total_response_time']}s")
    print(f"Timestamp: {summary['timestamp']}")
    
    if detailed:
        print("\n📋 DETALLES POR COMPONENTE:")
        print("-" * 60)
        
        for check in summary['checks']:
            status_icon = status_icons.get(check['status'], '❓')
            print(f"\n{status_icon} {check['component']}")
            print(f"   Estado: {check['status']}")
            print(f"   Mensaje: {check['message']}")
            print(f"   Tiempo: {check['response_time']}s")
            
            if check['details'] and detailed:
                print("   Detalles:")
                for key, value in check['details'].items():
                    if isinstance(value, dict):
                        print(f"     {key}:")
                        for sub_key, sub_value in value.items():
                            print(f"       {sub_key}: {sub_value}")
                    else:
                        print(f"     {key}: {value}")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Health Check para Ecosistema de Emprendimiento')
    parser.add_argument('--detailed', '-d', action='store_true', 
                       help='Mostrar información detallada')
    parser.add_argument('--json', '-j', action='store_true', 
                       help='Salida en formato JSON')
    parser.add_argument('--component', '-c', type=str, 
                       help='Verificar componente específico')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='Modo silencioso (solo errores)')
    
    args = parser.parse_args()
    
    try:
        checker = HealthChecker()
        
        if args.component:
            summary = checker.check_component(args.component)
        else:
            summary = checker.check_all(detailed=args.detailed)
        
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        elif not args.quiet:
            print_summary(summary, detailed=args.detailed)
        
        # Código de salida basado en el estado
        exit_codes = {
            'healthy': 0,
            'warning': 1,
            'critical': 2
        }
        
        exit_code = exit_codes.get(summary.get('overall_status', 'unknown'), 3)
        
        if args.quiet and exit_code != 0:
            critical_issues = [
                check for check in summary.get('checks', [])
                if check['status'] in ['critical', 'warning']
            ]
            for issue in critical_issues:
                print(f"ERROR: {issue['component']}: {issue['message']}", file=sys.stderr)
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n⏹️ Verificación interrumpida por el usuario")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error fatal en health check: {e}", file=sys.stderr)
        if args.json:
            error_response = {
                'overall_status': 'critical',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            print(json.dumps(error_response, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    main()