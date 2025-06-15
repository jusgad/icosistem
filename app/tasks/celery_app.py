"""
Configuración Principal de Celery - Ecosistema de Emprendimiento
===============================================================

Este módulo contiene la configuración específica y inicialización de la
aplicación Celery para el ecosistema de emprendimiento. Maneja toda la
configuración del broker, backend, workers, routing, seguridad y monitoreo.

Características principales:
- Configuración multi-entorno (desarrollo, producción, testing)
- Integración completa con Flask
- Configuración optimizada de Redis/RabbitMQ
- Sistema de logging avanzado
- Monitoreo y métricas integradas
- Configuración de seguridad robusta
- Routing inteligente de tareas
- Optimizaciones de rendimiento
"""

import os
import ssl
import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any, Union
from functools import lru_cache

from celery import Celery, __version__ as celery_version
from celery.schedules import crontab
from celery.signals import setup_logging
from kombu import Queue, Exchange
from kombu.serialization import register
import redis
from redis.sentinel import Sentinel

from app.core.constants import (
    ENVIRONMENTS,
    CELERY_TASK_PRIORITIES,
    DEFAULT_RETRY_DELAYS,
    QUEUE_ROUTING_KEYS
)
from app.core.exceptions import CeleryConfigurationError
from app.utils.cache_utils import get_redis_connection
from app.utils.crypto_utils import encrypt_sensitive_data, decrypt_sensitive_data

logger = logging.getLogger(__name__)

# Configuración de entornos
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
IS_DEVELOPMENT = ENVIRONMENT == 'development'
IS_PRODUCTION = ENVIRONMENT == 'production'
IS_TESTING = ENVIRONMENT == 'testing'

# Configuración base del broker
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Configuración de Redis Sentinel (para alta disponibilidad en producción)
REDIS_SENTINEL_HOSTS = os.getenv('REDIS_SENTINEL_HOSTS', '').split(',') if os.getenv('REDIS_SENTINEL_HOSTS') else []
REDIS_SENTINEL_SERVICE = os.getenv('REDIS_SENTINEL_SERVICE', 'mymaster')

# Configuración de SSL para producción
BROKER_USE_SSL = os.getenv('CELERY_BROKER_USE_SSL', 'False').lower() == 'true'
REDIS_SSL_CERT_REQS = ssl.CERT_REQUIRED if IS_PRODUCTION else ssl.CERT_NONE


class CeleryConfig:
    """
    Configuración centralizada de Celery
    
    Proporciona configuración específica por entorno con
    optimizaciones para el ecosistema de emprendimiento.
    """
    
    def __init__(self, environment: str = None):
        self.environment = environment or ENVIRONMENT
        self.setup_logging_config()
        self.setup_broker_config()
        self.setup_task_config()
        self.setup_worker_config()
        self.setup_monitoring_config()
        self.setup_security_config()
    
    def setup_logging_config(self):
        """Configuración de logging para Celery"""
        self.worker_hijack_root_logger = False
        self.worker_log_color = not IS_PRODUCTION
        self.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
        self.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
        
        # Configuración específica por entorno
        if IS_PRODUCTION:
            self.worker_log_level = 'INFO'
            self.worker_redirect_stdouts = True
            self.worker_redirect_stdouts_level = 'INFO'
        elif IS_DEVELOPMENT:
            self.worker_log_level = 'DEBUG'
            self.worker_redirect_stdouts = True
            self.worker_redirect_stdouts_level = 'DEBUG'
        else:  # Testing
            self.worker_log_level = 'WARNING'
            self.worker_redirect_stdouts = False
    
    def setup_broker_config(self):
        """Configuración del broker (Redis/RabbitMQ)"""
        # Configuración básica
        self.broker_url = self._get_broker_url()
        self.result_backend = self._get_result_backend_url()
        
        # Configuración de conexiones
        self.broker_connection_retry_on_startup = True
        self.broker_connection_retry = True
        self.broker_connection_max_retries = 10
        self.broker_heartbeat = 30
        self.broker_pool_limit = 10
        
        # Configuración específica de Redis
        if 'redis' in self.broker_url:
            self.setup_redis_config()
        
        # Configuración de RabbitMQ (alternativa)
        elif 'amqp' in self.broker_url:
            self.setup_rabbitmq_config()
    
    def setup_redis_config(self):
        """Configuración específica de Redis"""
        self.redis_max_connections = 20
        self.redis_socket_keepalive = True
        self.redis_socket_keepalive_options = {
            'TCP_KEEPINTVL': 1,
            'TCP_KEEPCNT': 3,
            'TCP_KEEPIDLE': 1,
        }
        
        # Configuración de Redis Cluster/Sentinel para producción
        if IS_PRODUCTION and REDIS_SENTINEL_HOSTS:
            self.broker_transport_options = {
                'sentinels': [(host.strip(), 26379) for host in REDIS_SENTINEL_HOSTS],
                'service_name': REDIS_SENTINEL_SERVICE,
                'socket_keepalive': True,
                'socket_keepalive_options': self.redis_socket_keepalive_options,
                'health_check_interval': 30,
            }
        else:
            self.broker_transport_options = {
                'socket_keepalive': True,
                'socket_keepalive_options': self.redis_socket_keepalive_options,
                'health_check_interval': 30,
                'retry_on_timeout': True,
                'max_connections': self.redis_max_connections,
            }
        
        # Configuración SSL para Redis
        if BROKER_USE_SSL:
            self.broker_use_ssl = {
                'ssl_cert_reqs': REDIS_SSL_CERT_REQS,
                'ssl_ca_certs': os.getenv('REDIS_SSL_CA_CERTS'),
                'ssl_certfile': os.getenv('REDIS_SSL_CERTFILE'),
                'ssl_keyfile': os.getenv('REDIS_SSL_KEYFILE'),
            }
            self.redis_backend_use_ssl = self.broker_use_ssl
    
    def setup_rabbitmq_config(self):
        """Configuración específica de RabbitMQ"""
        self.broker_transport_options = {
            'priority_steps': list(range(10)),
            'sep': ':',
            'queue_order_strategy': 'priority',
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True
        }
    
    def setup_task_config(self):
        """Configuración de tareas"""
        # Serialización
        self.task_serializer = 'json'
        self.accept_content = ['json']
        self.result_serializer = 'json'
        self.result_accept_content = ['json']
        
        # Compresión para tareas grandes
        self.task_compression = 'gzip' if IS_PRODUCTION else None
        self.result_compression = 'gzip' if IS_PRODUCTION else None
        
        # Configuración de resultados
        self.result_expires = 3600  # 1 hora
        self.task_ignore_result = False
        self.task_store_eager_result = True
        self.task_track_started = True
        self.task_acks_late = True
        self.task_reject_on_worker_lost = True
        
        # Configuración de tiempo
        self.timezone = 'UTC'
        self.enable_utc = True
        
        # Configuración de retry y timeout
        self.task_soft_time_limit = 300  # 5 minutos
        self.task_time_limit = 360      # 6 minutos
        self.task_max_retries = 3
        self.task_default_retry_delay = 60
        
        # Configuración específica por entorno
        if IS_TESTING:
            self.task_always_eager = True
            self.task_eager_propagates = True
            self.task_store_eager_result = True
        else:
            self.task_always_eager = False
            self.task_eager_propagates = False
    
    def setup_worker_config(self):
        """Configuración de workers"""
        # Configuración básica de workers
        self.worker_prefetch_multiplier = 1 if IS_PRODUCTION else 4
        self.worker_max_tasks_per_child = 1000
        self.worker_max_memory_per_child = 200000  # 200MB
        self.worker_disable_rate_limits = False
        self.worker_enable_remote_control = not IS_PRODUCTION
        
        # Configuración de concurrencia
        if IS_PRODUCTION:
            self.worker_concurrency = os.cpu_count() * 2
        elif IS_DEVELOPMENT:
            self.worker_concurrency = 2
        else:  # Testing
            self.worker_concurrency = 1
        
        # Configuración de eventos
        self.worker_send_task_events = True
        self.task_send_sent_event = True
        
        # Configuración de control remoto
        if not IS_PRODUCTION:
            self.worker_enable_remote_control = True
            self.worker_send_task_events = True
    
    def setup_monitoring_config(self):
        """Configuración de monitoreo"""
        # Eventos y estadísticas
        self.worker_send_task_events = True
        self.task_send_sent_event = True
        self.worker_timer_precision = 0.1
        
        # Configuración de Flower (herramienta de monitoreo)
        self.flower_basic_auth = os.getenv('CELERY_FLOWER_BASIC_AUTH', '')
        self.flower_address = os.getenv('CELERY_FLOWER_ADDRESS', '0.0.0.0')
        self.flower_port = int(os.getenv('CELERY_FLOWER_PORT', '5555'))
        
        # Configuración de métricas personalizadas
        self.task_annotations = {
            '*': {
                'rate_limit': '100/m',
            },
            'app.tasks.email_tasks.*': {
                'rate_limit': '50/m',
                'time_limit': 120,
                'soft_time_limit': 90,
            },
            'app.tasks.analytics_tasks.*': {
                'rate_limit': '20/m',
                'time_limit': 600,
                'soft_time_limit': 540,
            },
            'app.tasks.backup_tasks.*': {
                'rate_limit': '5/m',
                'time_limit': 1800,
                'soft_time_limit': 1620,
                'priority': 9,
            },
            'app.tasks.maintenance_tasks.system_health_check': {
                'rate_limit': '12/m',  # Cada 5 minutos
                'priority': 10,
            }
        }
    
    def setup_security_config(self):
        """Configuración de seguridad"""
        # Configuración de autenticación y autorización
        self.worker_hijack_root_logger = False
        self.worker_log_color = not IS_PRODUCTION
        
        # En producción, deshabilitar funciones de desarrollo
        if IS_PRODUCTION:
            self.worker_enable_remote_control = False
            self.worker_send_task_events = False
            self.task_send_sent_event = False
        
        # Configuración de cifrado para datos sensibles
        self.task_serializer_options = {
            'ensure_ascii': True,
            'encoding': 'utf-8'
        }
        
        # Lista de módulos permitidos para importar
        self.imports = [
            'app.tasks.email_tasks',
            'app.tasks.notification_tasks',
            'app.tasks.analytics_tasks',
            'app.tasks.backup_tasks',
            'app.tasks.maintenance_tasks'
        ]
    
    def _get_broker_url(self) -> str:
        """Obtiene la URL del broker según el entorno"""
        if IS_TESTING:
            return 'memory://'
        
        base_url = BROKER_URL
        
        # Añadir parámetros específicos para Redis
        if 'redis' in base_url:
            if IS_PRODUCTION:
                # Configuración optimizada para producción
                if '?' not in base_url:
                    base_url += '?'
                else:
                    base_url += '&'
                base_url += 'health_check_interval=30&socket_keepalive=true'
        
        return base_url
    
    def _get_result_backend_url(self) -> str:
        """Obtiene la URL del backend de resultados"""
        if IS_TESTING:
            return 'cache+memory://'
        
        return RESULT_BACKEND
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario"""
        config = {}
        for attr in dir(self):
            if not attr.startswith('_') and not callable(getattr(self, attr)):
                config[attr] = getattr(self, attr)
        return config


class EcosistemaEmprendimientoCelery(Celery):
    """
    Clase personalizada de Celery para el ecosistema de emprendimiento
    
    Extiende Celery con funcionalidades específicas del dominio,
    logging personalizado y manejo de errores avanzado.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_custom_logging()
        self.setup_error_handlers()
        self.setup_custom_serializers()
    
    def setup_custom_logging(self):
        """Configura logging personalizado para el ecosistema"""
        @setup_logging.connect
        def config_loggers(*args, **kwargs):
            from logging.config import dictConfig
            
            logging_config = {
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'detailed': {
                        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
                    },
                    'celery': {
                        'format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
                    },
                    'task': {
                        'format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
                    }
                },
                'handlers': {
                    'console': {
                        'class': 'logging.StreamHandler',
                        'level': 'DEBUG' if IS_DEVELOPMENT else 'INFO',
                        'formatter': 'celery',
                        'stream': 'ext://sys.stdout'
                    },
                    'file': {
                        'class': 'logging.handlers.RotatingFileHandler',
                        'level': 'INFO',
                        'formatter': 'detailed',
                        'filename': 'logs/celery.log',
                        'maxBytes': 10485760,  # 10MB
                        'backupCount': 5
                    }
                },
                'loggers': {
                    'celery': {
                        'handlers': ['console', 'file'] if not IS_TESTING else ['console'],
                        'level': 'DEBUG' if IS_DEVELOPMENT else 'INFO',
                        'propagate': False
                    },
                    'celery.task': {
                        'handlers': ['console', 'file'] if not IS_TESTING else ['console'],
                        'level': 'INFO',
                        'propagate': False
                    },
                    'app.tasks': {
                        'handlers': ['console', 'file'] if not IS_TESTING else ['console'],
                        'level': 'DEBUG' if IS_DEVELOPMENT else 'INFO',
                        'propagate': False
                    }
                },
                'root': {
                    'level': 'INFO',
                    'handlers': ['console']
                }
            }
            
            # Crear directorio de logs si no existe
            os.makedirs('logs', exist_ok=True)
            
            dictConfig(logging_config)
    
    def setup_error_handlers(self):
        """Configura manejadores de errores personalizados"""
        from celery.signals import task_failure, task_retry, worker_process_init
        
        @task_failure.connect
        def on_task_failure(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
            """Maneja fallos de tareas"""
            logger.error(f"Fallo en tarea {sender.name if sender else 'unknown'} ({task_id}): {exception}")
            
            # Enviar notificación para tareas críticas
            if sender and hasattr(sender, 'is_critical') and sender.is_critical:
                self._send_critical_failure_notification(sender.name, task_id, exception)
        
        @task_retry.connect
        def on_task_retry(sender=None, task_id=None, reason=None, einfo=None, **kwds):
            """Maneja reintentos de tareas"""
            logger.warning(f"Reintentando tarea {sender.name if sender else 'unknown'} ({task_id}): {reason}")
        
        @worker_process_init.connect
        def on_worker_process_init(**kwargs):
            """Inicialización de proceso worker"""
            logger.info(f"Worker process inicializado - PID: {os.getpid()}")
    
    def setup_custom_serializers(self):
        """Configura serializadores personalizados para datos sensibles"""
        def encrypt_serializer(obj):
            """Serializer que cifra datos sensibles"""
            import json
            data = json.dumps(obj)
            if isinstance(obj, dict) and obj.get('sensitive', False):
                data = encrypt_sensitive_data(data)
            return data
        
        def decrypt_serializer(data):
            """Deserializer que descifra datos sensibles"""
            import json
            try:
                # Intentar descifrar primero
                decrypted = decrypt_sensitive_data(data)
                return json.loads(decrypted)
            except:
                # Si falla, asumir que no está cifrado
                return json.loads(data)
        
        # Registrar serializadores personalizados
        register('encrypted_json', encrypt_serializer, decrypt_serializer,
                content_type='application/x-encrypted-json')
    
    def _send_critical_failure_notification(self, task_name: str, task_id: str, exception: Exception):
        """Envía notificación para fallos críticos"""
        try:
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            notification_service.send_critical_alert(
                title=f"Fallo crítico en tarea: {task_name}",
                message=f"La tarea crítica {task_name} (ID: {task_id}) ha fallado: {str(exception)}",
                recipients=['admin', 'tech_team'],
                metadata={
                    'task_name': task_name,
                    'task_id': task_id,
                    'error': str(exception),
                    'environment': ENVIRONMENT
                }
            )
        except Exception as e:
            logger.error(f"Error enviando notificación crítica: {str(e)}")


def create_celery_app(app=None) -> EcosistemaEmprendimientoCelery:
    """
    Factory para crear la aplicación Celery
    
    Args:
        app: Instancia de Flask (opcional)
        
    Returns:
        EcosistemaEmprendimientoCelery: Instancia configurada de Celery
    """
    try:
        # Validar dependencias
        _validate_dependencies()
        
        # Crear configuración
        config = CeleryConfig(ENVIRONMENT)
        
        # Crear instancia de Celery
        celery_app = EcosistemaEmprendimientoCelery(
            'ecosistema_emprendimiento',
            include=config.imports
        )
        
        # Aplicar configuración
        celery_app.config_from_object(config.to_dict())
        
        # Configurar colas y routing
        _setup_queues_and_routing(celery_app)
        
        # Configurar beat schedule
        _setup_beat_schedule(celery_app)
        
        # Integrar con Flask si se proporciona
        if app is not None:
            _integrate_with_flask(celery_app, app)
        
        # Verificar conectividad
        _test_broker_connection(celery_app)
        
        logger.info(f"Celery inicializado exitosamente en entorno: {ENVIRONMENT}")
        logger.info(f"Broker: {config.broker_url}")
        logger.info(f"Backend: {config.result_backend}")
        
        return celery_app
        
    except Exception as e:
        logger.error(f"Error creando aplicación Celery: {str(e)}")
        raise CeleryConfigurationError(f"Failed to create Celery app: {str(e)}")


def _validate_dependencies():
    """Valida que las dependencias necesarias estén disponibles"""
    try:
        import redis
        import kombu
        logger.debug("Dependencias de Celery validadas correctamente")
    except ImportError as e:
        raise CeleryConfigurationError(f"Missing dependency: {str(e)}")


def _setup_queues_and_routing(celery_app: EcosistemaEmprendimientoCelery):
    """Configura las colas y routing de tareas"""
    
    # Definir exchanges
    default_exchange = Exchange('default', type='direct')
    priority_exchange = Exchange('priority', type='direct')
    topic_exchange = Exchange('topic', type='topic')
    
    # Definir colas con prioridades
    queues = [
        # Cola de alta prioridad
        Queue('high_priority', 
              exchange=priority_exchange, 
              routing_key='high',
              queue_arguments={'x-max-priority': 10}),
        
        # Cola normal
        Queue('normal', 
              exchange=default_exchange, 
              routing_key='normal',
              queue_arguments={'x-max-priority': 5}),
        
        # Cola de baja prioridad
        Queue('low_priority', 
              exchange=default_exchange, 
              routing_key='low',
              queue_arguments={'x-max-priority': 1}),
        
        # Colas especializadas
        Queue('emails', 
              exchange=topic_exchange, 
              routing_key='emails.*',
              queue_arguments={'x-max-priority': 7}),
        
        Queue('notifications', 
              exchange=topic_exchange, 
              routing_key='notifications.*',
              queue_arguments={'x-max-priority': 6}),
        
        Queue('analytics', 
              exchange=topic_exchange, 
              routing_key='analytics.*',
              queue_arguments={'x-max-priority': 4}),
        
        Queue('reports', 
              exchange=topic_exchange, 
              routing_key='reports.*',
              queue_arguments={'x-max-priority': 3}),
        
        Queue('backups', 
              exchange=topic_exchange, 
              routing_key='backups.*',
              queue_arguments={'x-max-priority': 8}),
        
        Queue('maintenance', 
              exchange=topic_exchange, 
              routing_key='maintenance.*',
              queue_arguments={'x-max-priority': 5}),
    ]
    
    # Configurar colas
    celery_app.conf.task_queues = queues
    
    # Configurar routing
    task_routes = {
        # Routing por patrones de nombres
        'app.tasks.email_tasks.*': {
            'queue': 'emails',
            'routing_key': 'emails.send',
            'priority': 7
        },
        'app.tasks.notification_tasks.*': {
            'queue': 'notifications',
            'routing_key': 'notifications.send',
            'priority': 6
        },
        'app.tasks.analytics_tasks.*': {
            'queue': 'analytics',
            'routing_key': 'analytics.process',
            'priority': 4
        },
        'app.tasks.backup_tasks.*': {
            'queue': 'backups',
            'routing_key': 'backups.create',
            'priority': 8
        },
        'app.tasks.maintenance_tasks.*': {
            'queue': 'maintenance',
            'routing_key': 'maintenance.run',
            'priority': 5
        },
        
        # Routing por prioridad
        'app.tasks.*.urgent_*': {
            'queue': 'high_priority',
            'routing_key': 'high',
            'priority': 9
        },
        'app.tasks.*.critical_*': {
            'queue': 'high_priority',
            'routing_key': 'high',
            'priority': 10
        },
    }
    
    celery_app.conf.task_routes = task_routes
    
    logger.info(f"Configuradas {len(queues)} colas y routing de tareas")


def _setup_beat_schedule(celery_app: EcosistemaEmprendimientoCelery):
    """Configura el schedule de Celery Beat"""
    
    beat_schedule = {
        # === TAREAS CRÍTICAS DEL SISTEMA ===
        'system-health-check': {
            'task': 'app.tasks.maintenance_tasks.system_health_check',
            'schedule': crontab(minute='*/5'),  # Cada 5 minutos
            'options': {
                'queue': 'maintenance',
                'priority': 10,
                'expires': 240
            }
        },
        
        'database-backup-hourly': {
            'task': 'app.tasks.backup_tasks.incremental_backup',
            'schedule': crontab(minute=30),  # Cada hora a los 30 minutos
            'options': {
                'queue': 'backups',
                'priority': 9,
                'expires': 3300  # 55 minutos
            }
        },
        
        # === TAREAS DIARIAS ===
        'daily-full-backup': {
            'task': 'app.tasks.backup_tasks.full_database_backup',
            'schedule': crontab(hour=2, minute=0),  # 2:00 AM
            'options': {
                'queue': 'backups',
                'priority': 9
            }
        },
        
        'daily-analytics-report': {
            'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
            'schedule': crontab(hour=6, minute=0),  # 6:00 AM
            'options': {
                'queue': 'analytics',
                'priority': 6
            }
        },
        
        'daily-cleanup': {
            'task': 'app.tasks.maintenance_tasks.daily_cleanup',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM
            'options': {
                'queue': 'maintenance',
                'priority': 5
            }
        },
        
        'daily-user-engagement-report': {
            'task': 'app.tasks.analytics_tasks.generate_user_engagement_report',
            'schedule': crontab(hour=7, minute=0),  # 7:00 AM
            'options': {
                'queue': 'analytics',
                'priority': 5
            }
        },
        
        # === TAREAS SEMANALES ===
        'weekly-entrepreneur-report': {
            'task': 'app.tasks.analytics_tasks.generate_weekly_entrepreneur_report',
            'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Lunes 8:00 AM
            'options': {
                'queue': 'reports',
                'priority': 6
            }
        },
        
        'weekly-mentor-summary': {
            'task': 'app.tasks.analytics_tasks.generate_weekly_mentor_summary',
            'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Lunes 9:00 AM
            'options': {
                'queue': 'reports',
                'priority': 6
            }
        },
        
        'weekly-system-maintenance': {
            'task': 'app.tasks.maintenance_tasks.weekly_system_maintenance',
            'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Domingo 1:00 AM
            'options': {
                'queue': 'maintenance',
                'priority': 7
            }
        },
        
        # === TAREAS MENSUALES ===
        'monthly-ecosystem-report': {
            'task': 'app.tasks.analytics_tasks.generate_monthly_ecosystem_report',
            'schedule': crontab(hour=7, minute=0, day_of_month=1),  # Primer día del mes 7:00 AM
            'options': {
                'queue': 'reports',
                'priority': 8
            }
        },
        
        'monthly-data-archive': {
            'task': 'app.tasks.maintenance_tasks.monthly_data_archive',
            'schedule': crontab(hour=0, minute=0, day_of_month=1),  # Primer día del mes 12:00 AM
            'options': {
                'queue': 'maintenance',
                'priority': 6
            }
        },
        
        # === TAREAS FRECUENTES ===
        'process-email-queue': {
            'task': 'app.tasks.email_tasks.process_email_queue',
            'schedule': crontab(minute='*/10'),  # Cada 10 minutos
            'options': {
                'queue': 'emails',
                'priority': 7,
                'expires': 540  # 9 minutos
            }
        },
        
        'process-notification-queue': {
            'task': 'app.tasks.notification_tasks.process_notification_queue',
            'schedule': crontab(minute='*/15'),  # Cada 15 minutos
            'options': {
                'queue': 'notifications',
                'priority': 6,
                'expires': 840  # 14 minutos
            }
        },
        
        'update-realtime-metrics': {
            'task': 'app.tasks.analytics_tasks.update_realtime_metrics',
            'schedule': 60.0,  # Cada minuto
            'options': {
                'queue': 'analytics',
                'priority': 4,
                'expires': 50
            }
        },
        
        # === TAREAS DE NOTIFICACIONES ===
        'send-daily-digest': {
            'task': 'app.tasks.notification_tasks.send_daily_digest',
            'schedule': crontab(hour=18, minute=0),  # 6:00 PM
            'options': {
                'queue': 'notifications',
                'priority': 5
            }
        },
        
        'reminder-upcoming-meetings': {
            'task': 'app.tasks.notification_tasks.send_meeting_reminders',
            'schedule': crontab(minute='*/30'),  # Cada 30 minutos
            'options': {
                'queue': 'notifications',
                'priority': 7,
                'expires': 1740  # 29 minutos
            }
        },
    }
    
    # Configurar solo en entornos apropiados
    if not IS_TESTING:
        celery_app.conf.beat_schedule = beat_schedule
        logger.info(f"Configuradas {len(beat_schedule)} tareas programadas")


def _integrate_with_flask(celery_app: EcosistemaEmprendimientoCelery, app):
    """Integra Celery con Flask"""
    
    class ContextTask(celery_app.Task):
        """Tarea que se ejecuta dentro del contexto de Flask"""
        
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery_app.Task = ContextTask
    
    # Actualizar configuración desde Flask
    flask_config_mapping = {
        'CELERY_BROKER_URL': 'broker_url',
        'CELERY_RESULT_BACKEND': 'result_backend',
        'CELERY_TIMEZONE': 'timezone',
        'CELERY_ENABLE_UTC': 'enable_utc',
        'CELERY_TASK_SERIALIZER': 'task_serializer',
        'CELERY_RESULT_SERIALIZER': 'result_serializer'
    }
    
    flask_celery_config = {}
    for flask_key, celery_key in flask_config_mapping.items():
        if flask_key in app.config:
            flask_celery_config[celery_key] = app.config[flask_key]
    
    if flask_celery_config:
        celery_app.conf.update(flask_celery_config)
    
    logger.info("Celery integrado exitosamente con Flask")


def _test_broker_connection(celery_app: EcosistemaEmprendimientoCelery):
    """Prueba la conexión con el broker"""
    if IS_TESTING:
        return  # Skip en testing
    
    try:
        # Intentar conexión con el broker
        with celery_app.connection_or_acquire() as conn:
            conn.ensure_connection(max_retries=3)
        
        logger.info("Conexión con broker establecida exitosamente")
        
    except Exception as e:
        logger.error(f"Error conectando con broker: {str(e)}")
        if IS_PRODUCTION:
            raise CeleryConfigurationError(f"Cannot connect to broker: {str(e)}")
        else:
            logger.warning("Continuando sin conexión al broker (modo desarrollo)")


@lru_cache(maxsize=1)
def get_celery_app() -> EcosistemaEmprendimientoCelery:
    """
    Obtiene la instancia singleton de Celery
    
    Returns:
        EcosistemaEmprendimientoCelery: Instancia configurada
    """
    return create_celery_app()


def get_celery_info() -> Dict[str, Any]:
    """
    Obtiene información completa de la configuración de Celery
    
    Returns:
        Dict con información de configuración y estado
    """
    celery_app = get_celery_app()
    
    info = {
        'version': celery_version,
        'environment': ENVIRONMENT,
        'broker_url': celery_app.conf.broker_url,
        'result_backend': celery_app.conf.result_backend,
        'worker_concurrency': celery_app.conf.worker_concurrency,
        'task_serializer': celery_app.conf.task_serializer,
        'result_serializer': celery_app.conf.result_serializer,
        'timezone': celery_app.conf.timezone,
        'total_queues': len(celery_app.conf.task_queues) if celery_app.conf.task_queues else 0,
        'total_scheduled_tasks': len(celery_app.conf.beat_schedule) if celery_app.conf.beat_schedule else 0,
        'registered_tasks': len(celery_app.tasks),
        'task_routes_configured': len(celery_app.conf.task_routes) if celery_app.conf.task_routes else 0
    }
    
    # Añadir información de estado si no estamos en testing
    if not IS_TESTING:
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            if stats:
                info['active_workers'] = len(stats)
                info['worker_stats'] = stats
            else:
                info['active_workers'] = 0
                info['worker_stats'] = {}
        except Exception as e:
            info['worker_connection_error'] = str(e)
    
    return info


# Crear instancia global por defecto
celery_app = create_celery_app()

# Exportar para uso en otros módulos
__all__ = [
    'celery_app',
    'create_celery_app',
    'get_celery_app',
    'get_celery_info',
    'CeleryConfig',
    'EcosistemaEmprendimientoCelery',
    'ENVIRONMENT',
    'IS_DEVELOPMENT',
    'IS_PRODUCTION',
    'IS_TESTING'
]