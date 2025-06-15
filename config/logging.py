# -*- coding: utf-8 -*-
"""
Configuración de Logging Empresarial del Ecosistema de Emprendimiento
====================================================================

Sistema de logging empresarial robusto y escalable que proporciona:
- Logging estructurado con soporte JSON
- Múltiples handlers y formatters especializados
- Rotación automática de archivos con compresión
- Integration con servicios externos (Sentry, ELK, etc.)
- Correlation IDs para tracing distribuido
- Configuración específica por ambiente y módulo
- Métricas de performance y auditoría
- Support para containers y microservicios
- Filtros avanzados y sampling
- Configuración dinámica sin restart

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import sys
import json
import logging
import logging.config
import logging.handlers
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from pathlib import Path
import gzip
import shutil
from threading import current_thread
import uuid


class CorrelationFilter(logging.Filter):
    """
    Filtro para agregar correlation ID a todos los logs.
    Permite tracing distribuido y seguimiento de requests.
    """
    
    def filter(self, record):
        """
        Agrega correlation ID y información contextual al record.
        
        Args:
            record: LogRecord a filtrar
            
        Returns:
            True para permitir el log
        """
        # Obtener correlation ID del contexto (Flask g, thread local, etc.)
        correlation_id = getattr(record, 'correlation_id', None)
        if not correlation_id:
            try:
                from flask import g, has_request_context
                if has_request_context() and hasattr(g, 'correlation_id'):
                    correlation_id = g.correlation_id
                else:
                    correlation_id = str(uuid.uuid4())[:8]
            except ImportError:
                correlation_id = str(uuid.uuid4())[:8]
        
        record.correlation_id = correlation_id
        
        # Agregar información del thread
        record.thread_name = current_thread().name
        record.thread_id = current_thread().ident
        
        # Agregar timestamp UTC
        record.utc_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Agregar información del proceso
        record.process_id = os.getpid()
        record.hostname = os.environ.get('HOSTNAME', 'unknown')
        
        # Agregar información del ambiente
        record.environment = os.environ.get('ENVIRONMENT', 'unknown')
        record.service_name = os.environ.get('SERVICE_NAME', 'ecosistema')
        
        return True


class PerformanceFilter(logging.Filter):
    """
    Filtro para logs de performance que incluye métricas de timing.
    """
    
    def filter(self, record):
        """
        Agrega métricas de performance al record si están disponibles.
        
        Args:
            record: LogRecord a filtrar
            
        Returns:
            True para permitir el log
        """
        # Agregar información de performance si está disponible
        try:
            from flask import g, has_request_context
            if has_request_context():
                if hasattr(g, 'request_start_time'):
                    record.request_duration = (
                        datetime.now(timezone.utc) - g.request_start_time
                    ).total_seconds()
                
                if hasattr(g, 'db_query_count'):
                    record.db_query_count = g.db_query_count
                
                if hasattr(g, 'cache_hit_count'):
                    record.cache_hit_count = g.cache_hit_count
                    record.cache_miss_count = getattr(g, 'cache_miss_count', 0)
        except ImportError:
            pass
        
        return True


class SensitiveDataFilter(logging.Filter):
    """
    Filtro para eliminar datos sensibles de los logs.
    Remueve passwords, tokens, emails parcialmente, etc.
    """
    
    SENSITIVE_FIELDS = [
        'password', 'token', 'secret', 'key', 'authorization',
        'credential', 'auth_token', 'api_key', 'private_key'
    ]
    
    def filter(self, record):
        """
        Filtra datos sensibles del mensaje de log.
        
        Args:
            record: LogRecord a filtrar
            
        Returns:
            True para permitir el log
        """
        if hasattr(record, 'args') and record.args:
            record.args = self._sanitize_args(record.args)
        
        if hasattr(record, 'msg'):
            record.msg = self._sanitize_message(str(record.msg))
        
        return True
    
    def _sanitize_args(self, args):
        """
        Sanitiza argumentos del log.
        
        Args:
            args: Argumentos del log
            
        Returns:
            Argumentos sanitizados
        """
        if isinstance(args, dict):
            return {k: self._sanitize_value(k, v) for k, v in args.items()}
        elif isinstance(args, (list, tuple)):
            return [self._sanitize_value('', v) for v in args]
        return args
    
    def _sanitize_value(self, key: str, value: Any) -> Any:
        """
        Sanitiza un valor específico.
        
        Args:
            key: Clave del valor
            value: Valor a sanitizar
            
        Returns:
            Valor sanitizado
        """
        if isinstance(key, str) and any(field in key.lower() for field in self.SENSITIVE_FIELDS):
            if isinstance(value, str) and len(value) > 4:
                return f"{value[:2]}***{value[-2:]}"
            return "***"
        
        if isinstance(value, str) and '@' in value and '.' in value:
            # Posible email - parcialmente ocultar
            try:
                local, domain = value.split('@', 1)
                if len(local) > 2:
                    return f"{local[:2]}***@{domain}"
                return f"***@{domain}"
            except:
                pass
        
        return value
    
    def _sanitize_message(self, message: str) -> str:
        """
        Sanitiza el mensaje de log.
        
        Args:
            message: Mensaje a sanitizar
            
        Returns:
            Mensaje sanitizado
        """
        import re
        
        # Patrones para detectar datos sensibles
        patterns = [
            (r'password["\']?\s*[:=]\s*["\']([^"\']+)["\']', r'password="***"'),
            (r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', r'token="***"'),
            (r'secret["\']?\s*[:=]\s*["\']([^"\']+)["\']', r'secret="***"'),
            (r'key["\']?\s*[:=]\s*["\']([^"\']+)["\']', r'key="***"'),
        ]
        
        for pattern, replacement in patterns:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        
        return message


class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Handler de archivos con rotación y compresión automática.
    Extiende RotatingFileHandler para comprimir archivos rotados.
    """
    
    def doRollover(self):
        """
        Ejecuta rotación y compresión del archivo.
        """
        # Cerrar archivo actual
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # Rotar archivos
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename(f"{self.baseFilename}.{i}.gz")
                dfn = self.rotation_filename(f"{self.baseFilename}.{i + 1}.gz")
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            
            # Comprimir archivo actual
            dfn = self.rotation_filename(f"{self.baseFilename}.1.gz")
            if os.path.exists(dfn):
                os.remove(dfn)
            
            # Comprimir el archivo actual
            with open(self.baseFilename, 'rb') as f_in:
                with gzip.open(dfn, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Eliminar archivo original
            os.remove(self.baseFilename)
        
        # No llamar super().doRollover() porque ya manejamos la rotación
        if not self.delay:
            self.stream = self._open()


class JsonFormatter(logging.Formatter):
    """
    Formatter JSON para logging estructurado.
    Optimizado para agregación y análisis de logs.
    """
    
    def __init__(self, *args, **kwargs):
        """
        Inicializa el formatter JSON.
        
        Args:
            *args: Argumentos del formatter base
            **kwargs: Argumentos adicionales
        """
        super().__init__()
        self.hostname = os.environ.get('HOSTNAME', 'unknown')
        self.service_name = os.environ.get('SERVICE_NAME', 'ecosistema')
        self.environment = os.environ.get('ENVIRONMENT', 'unknown')
        self.version = os.environ.get('APP_VERSION', '1.0.0')
    
    def format(self, record):
        """
        Formatea el record como JSON.
        
        Args:
            record: LogRecord a formatear
            
        Returns:
            String JSON con el log formateado
        """
        # Datos base del log
        log_entry = {
            'timestamp': getattr(record, 'utc_timestamp', datetime.now(timezone.utc).isoformat()),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread_name': getattr(record, 'thread_name', ''),
            'thread_id': getattr(record, 'thread_id', ''),
            'process_id': getattr(record, 'process_id', os.getpid()),
            'correlation_id': getattr(record, 'correlation_id', ''),
            'hostname': getattr(record, 'hostname', self.hostname),
            'service_name': getattr(record, 'service_name', self.service_name),
            'environment': getattr(record, 'environment', self.environment),
            'version': self.version,
        }
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Agregar métricas de performance si existen
        performance_fields = ['request_duration', 'db_query_count', 'cache_hit_count', 'cache_miss_count']
        performance_data = {}
        for field in performance_fields:
            if hasattr(record, field):
                performance_data[field] = getattr(record, field)
        
        if performance_data:
            log_entry['performance'] = performance_data
        
        # Agregar campos personalizados
        custom_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                          'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage',
                          'exc_info', 'exc_text', 'stack_info'] and not key.startswith('_'):
                if key not in log_entry and key not in performance_fields:
                    custom_fields[key] = value
        
        if custom_fields:
            log_entry['custom'] = custom_fields
        
        try:
            return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            # Fallback si hay error en serialización JSON
            fallback_entry = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': 'ERROR',
                'logger': 'logging.JsonFormatter',
                'message': f'Error serializing log entry: {str(e)}',
                'original_message': str(record.getMessage()),
                'hostname': self.hostname,
                'service_name': self.service_name,
            }
            return json.dumps(fallback_entry, ensure_ascii=False, separators=(',', ':'))


class DetailedFormatter(logging.Formatter):
    """
    Formatter detallado para development y debugging.
    Incluye información extendida y colores para console.
    """
    
    # Códigos ANSI para colores
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'ENDC': '\033[0m',        # End color
        'BOLD': '\033[1m',        # Bold
    }
    
    def __init__(self, use_colors=False, *args, **kwargs):
        """
        Inicializa el formatter detallado.
        
        Args:
            use_colors: Si usar colores ANSI
            *args: Argumentos del formatter base
            **kwargs: Argumentos adicionales
        """
        super().__init__(*args, **kwargs)
        self.use_colors = use_colors and hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    
    def format(self, record):
        """
        Formatea el record con información detallada.
        
        Args:
            record: LogRecord a formatear
            
        Returns:
            String con el log formateado
        """
        # Formatear timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Información del logger
        logger_info = f"{record.name}:{record.funcName}:{record.lineno}"
        
        # Correlation ID si existe
        correlation_id = getattr(record, 'correlation_id', '')
        correlation_part = f" [{correlation_id}]" if correlation_id else ""
        
        # Thread information
        thread_info = f" ({current_thread().name})" if current_thread().name != 'MainThread' else ""
        
        # Nivel con colores si está habilitado
        level = record.levelname
        if self.use_colors:
            color = self.COLORS.get(level, '')
            level = f"{color}{self.COLORS['BOLD']}{level}{self.COLORS['ENDC']}"
        
        # Mensaje principal
        message = record.getMessage()
        
        # Construir formato base
        formatted = f"{timestamp} {level:20} {logger_info:50}{correlation_part}{thread_info} | {message}"
        
        # Agregar información de performance si existe
        performance_info = []
        if hasattr(record, 'request_duration'):
            performance_info.append(f"duration={record.request_duration:.3f}s")
        if hasattr(record, 'db_query_count'):
            performance_info.append(f"db_queries={record.db_query_count}")
        if hasattr(record, 'cache_hit_count'):
            hit_rate = record.cache_hit_count / (record.cache_hit_count + getattr(record, 'cache_miss_count', 0))
            performance_info.append(f"cache_hit_rate={hit_rate:.2%}")
        
        if performance_info:
            formatted += f" | Performance: {', '.join(performance_info)}"
        
        # Agregar excepción si existe
        if record.exc_info:
            formatted += '\n' + self.formatException(record.exc_info)
        
        return formatted


class SamplingFilter(logging.Filter):
    """
    Filtro de sampling para reducir volumen de logs en producción.
    Permite configurar diferentes rates de sampling por nivel.
    """
    
    def __init__(self, sample_rates: Dict[str, float]):
        """
        Inicializa el filtro de sampling.
        
        Args:
            sample_rates: Diccionario con rates de sampling por nivel
                         Ejemplo: {'DEBUG': 0.1, 'INFO': 0.5, 'WARNING': 1.0}
        """
        super().__init__()
        self.sample_rates = sample_rates
        self.counters = {level: 0 for level in sample_rates.keys()}
    
    def filter(self, record):
        """
        Aplica sampling al record.
        
        Args:
            record: LogRecord a filtrar
            
        Returns:
            True si el log debe ser procesado
        """
        level = record.levelname
        sample_rate = self.sample_rates.get(level, 1.0)
        
        if sample_rate >= 1.0:
            return True
        
        self.counters[level] = (self.counters[level] + 1) % int(1 / sample_rate)
        return self.counters[level] == 0


class LoggingConfig:
    """
    Configurador principal del sistema de logging.
    Maneja configuración dinámica y setup de handlers.
    """
    
    def __init__(self, environment: str = 'development'):
        """
        Inicializa la configuración de logging.
        
        Args:
            environment: Ambiente de ejecución
        """
        self.environment = environment
        self.log_dir = Path(os.environ.get('LOG_DIR', 'logs'))
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        self.json_logging = os.environ.get('JSON_LOGGING', 'False').lower() == 'true'
        self.enable_colors = os.environ.get('ENABLE_LOG_COLORS', 'True').lower() == 'true'
        self.enable_compression = os.environ.get('ENABLE_LOG_COMPRESSION', 'True').lower() == 'true'
        
        # Configuración específica por ambiente
        self._setup_environment_defaults()
    
    def _setup_environment_defaults(self):
        """
        Configura defaults específicos por ambiente.
        """
        env_configs = {
            'development': {
                'json_logging': False,
                'enable_colors': True,
                'log_level': 'DEBUG',
                'enable_file_logging': True,
                'enable_console_logging': True,
                'enable_sampling': False,
            },
            'testing': {
                'json_logging': False,
                'enable_colors': False,
                'log_level': 'WARNING',
                'enable_file_logging': False,
                'enable_console_logging': False,
                'enable_sampling': False,
            },
            'production': {
                'json_logging': True,
                'enable_colors': False,
                'log_level': 'INFO',
                'enable_file_logging': True,
                'enable_console_logging': False,
                'enable_sampling': True,
            },
            'docker': {
                'json_logging': True,
                'enable_colors': False,
                'log_level': 'INFO',
                'enable_file_logging': False,
                'enable_console_logging': True,
                'enable_sampling': False,
            }
        }
        
        config = env_configs.get(self.environment, env_configs['development'])
        
        # Override con variables de entorno si están definidas
        self.json_logging = os.environ.get('JSON_LOGGING', str(config['json_logging'])).lower() == 'true'
        self.enable_colors = os.environ.get('ENABLE_LOG_COLORS', str(config['enable_colors'])).lower() == 'true'
        self.log_level = os.environ.get('LOG_LEVEL', config['log_level']).upper()
        self.enable_file_logging = os.environ.get('ENABLE_FILE_LOGGING', str(config['enable_file_logging'])).lower() == 'true'
        self.enable_console_logging = os.environ.get('ENABLE_CONSOLE_LOGGING', str(config['enable_console_logging'])).lower() == 'true'
        self.enable_sampling = os.environ.get('ENABLE_LOG_SAMPLING', str(config['enable_sampling'])).lower() == 'true'
    
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Genera la configuración completa de logging.
        
        Returns:
            Diccionario con configuración de logging
        """
        # Crear directorio de logs si no existe
        if self.enable_file_logging:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Formatters
        formatters = self._get_formatters()
        
        # Filters
        filters = self._get_filters()
        
        # Handlers
        handlers = self._get_handlers()
        
        # Loggers específicos
        loggers = self._get_loggers()
        
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': formatters,
            'filters': filters,
            'handlers': handlers,
            'loggers': loggers,
            'root': {
                'level': self.log_level,
                'handlers': self._get_root_handlers(),
            }
        }
        
        return config
    
    def _get_formatters(self) -> Dict[str, Dict[str, Any]]:
        """
        Configura formatters disponibles.
        
        Returns:
            Diccionario con configuración de formatters
        """
        formatters = {}
        
        if self.json_logging:
            formatters['json'] = {
                '()': JsonFormatter,
            }
        else:
            formatters['detailed'] = {
                '()': DetailedFormatter,
                'use_colors': self.enable_colors,
            }
            
            formatters['simple'] = {
                'format': '%(asctime)s %(levelname)s %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            }
        
        # Formatter específico para performance logs
        formatters['performance'] = {
            '()': JsonFormatter,
        }
        
        # Formatter para auditoría
        formatters['audit'] = {
            '()': JsonFormatter,
        }
        
        return formatters
    
    def _get_filters(self) -> Dict[str, Dict[str, Any]]:
        """
        Configura filtros disponibles.
        
        Returns:
            Diccionario con configuración de filtros
        """
        filters = {
            'correlation': {
                '()': CorrelationFilter,
            },
            'performance': {
                '()': PerformanceFilter,
            },
            'sensitive_data': {
                '()': SensitiveDataFilter,
            },
        }
        
        # Agregar sampling filter si está habilitado
        if self.enable_sampling:
            sample_rates = {
                'DEBUG': float(os.environ.get('DEBUG_SAMPLE_RATE', '0.1')),
                'INFO': float(os.environ.get('INFO_SAMPLE_RATE', '0.5')),
                'WARNING': 1.0,
                'ERROR': 1.0,
                'CRITICAL': 1.0,
            }
            filters['sampling'] = {
                '()': SamplingFilter,
                'sample_rates': sample_rates,
            }
        
        return filters
    
    def _get_handlers(self) -> Dict[str, Dict[str, Any]]:
        """
        Configura handlers disponibles.
        
        Returns:
            Diccionario con configuración de handlers
        """
        handlers = {}
        
        # Console handler
        if self.enable_console_logging:
            formatter = 'json' if self.json_logging else 'detailed'
            filters = ['correlation', 'performance', 'sensitive_data']
            
            if self.enable_sampling:
                filters.append('sampling')
            
            handlers['console'] = {
                'class': 'logging.StreamHandler',
                'level': self.log_level,
                'formatter': formatter,
                'filters': filters,
                'stream': 'ext://sys.stdout',
            }
        
        # File handlers
        if self.enable_file_logging:
            # Handler principal
            handler_class = CompressedRotatingFileHandler if self.enable_compression else logging.handlers.RotatingFileHandler
            
            handlers['file'] = {
                '()': handler_class,
                'level': self.log_level,
                'formatter': 'json' if self.json_logging else 'simple',
                'filters': ['correlation', 'performance', 'sensitive_data'],
                'filename': str(self.log_dir / f'{self.environment}.log'),
                'maxBytes': int(os.environ.get('LOG_MAX_BYTES', str(50 * 1024 * 1024))),  # 50MB
                'backupCount': int(os.environ.get('LOG_BACKUP_COUNT', '10')),
                'encoding': 'utf8',
            }
            
            # Handler para errores
            handlers['error_file'] = {
                '()': handler_class,
                'level': 'ERROR',
                'formatter': 'json' if self.json_logging else 'detailed',
                'filters': ['correlation', 'performance', 'sensitive_data'],
                'filename': str(self.log_dir / 'errors.log'),
                'maxBytes': int(os.environ.get('ERROR_LOG_MAX_BYTES', str(10 * 1024 * 1024))),  # 10MB
                'backupCount': int(os.environ.get('ERROR_LOG_BACKUP_COUNT', '5')),
                'encoding': 'utf8',
            }
            
            # Handler para performance
            handlers['performance_file'] = {
                '()': handler_class,
                'level': 'INFO',
                'formatter': 'performance',
                'filters': ['correlation', 'performance'],
                'filename': str(self.log_dir / 'performance.log'),
                'maxBytes': int(os.environ.get('PERF_LOG_MAX_BYTES', str(25 * 1024 * 1024))),  # 25MB
                'backupCount': int(os.environ.get('PERF_LOG_BACKUP_COUNT', '3')),
                'encoding': 'utf8',
            }
            
            # Handler para auditoría
            handlers['audit_file'] = {
                '()': handler_class,
                'level': 'INFO',
                'formatter': 'audit',
                'filters': ['correlation', 'sensitive_data'],
                'filename': str(self.log_dir / 'audit.log'),
                'maxBytes': int(os.environ.get('AUDIT_LOG_MAX_BYTES', str(100 * 1024 * 1024))),  # 100MB
                'backupCount': int(os.environ.get('AUDIT_LOG_BACKUP_COUNT', '20')),
                'encoding': 'utf8',
            }
        
        # Sentry handler si está configurado
        sentry_dsn = os.environ.get('SENTRY_DSN')
        if sentry_dsn:
            try:
                handlers['sentry'] = {
                    'class': 'sentry_sdk.integrations.logging.SentryHandler',
                    'level': 'WARNING',
                    'filters': ['sensitive_data'],
                }
            except ImportError:
                pass
        
        return handlers
    
    def _get_loggers(self) -> Dict[str, Dict[str, Any]]:
        """
        Configura loggers específicos.
        
        Returns:
            Diccionario con configuración de loggers
        """
        loggers = {
            # Logger principal de la aplicación
            'app': {
                'level': self.log_level,
                'handlers': self._get_app_handlers(),
                'propagate': False,
            },
            
            # Logger para performance
            'app.performance': {
                'level': 'INFO',
                'handlers': ['performance_file'] if self.enable_file_logging else [],
                'propagate': False,
            },
            
            # Logger para auditoría
            'app.audit': {
                'level': 'INFO',
                'handlers': ['audit_file'] if self.enable_file_logging else [],
                'propagate': False,
            },
            
            # Flask
            'flask': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True,
            },
            
            # Werkzeug
            'werkzeug': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True,
            },
            
            # SQLAlchemy
            'sqlalchemy.engine': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True,
            },
            
            'sqlalchemy.pool': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True,
            },
            
            # Celery
            'celery': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True,
            },
            
            'celery.task': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True,
            },
            
            # Gunicorn
            'gunicorn.error': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True,
            },
            
            'gunicorn.access': {
                'level': 'INFO',
                'handlers': [],
                'propagate': True,
            },
            
            # Requests
            'requests.packages.urllib3': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True,
            },
            
            # Redis
            'redis': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': True,
            },
        }
        
        return loggers
    
    def _get_root_handlers(self) -> List[str]:
        """
        Obtiene handlers para el logger root.
        
        Returns:
            Lista de nombres de handlers
        """
        handlers = []
        
        if self.enable_console_logging:
            handlers.append('console')
        
        if self.enable_file_logging:
            handlers.extend(['file', 'error_file'])
        
        # Agregar Sentry si está disponible
        if os.environ.get('SENTRY_DSN'):
            handlers.append('sentry')
        
        return handlers
    
    def _get_app_handlers(self) -> List[str]:
        """
        Obtiene handlers específicos para la aplicación.
        
        Returns:
            Lista de nombres de handlers
        """
        handlers = []
        
        if self.enable_console_logging:
            handlers.append('console')
        
        if self.enable_file_logging:
            handlers.extend(['file', 'error_file'])
        
        return handlers
    
    def setup_logging(self):
        """
        Configura el sistema de logging completo.
        """
        config = self.get_logging_config()
        logging.config.dictConfig(config)
        
        # Configurar logging específico para el ambiente
        logger = logging.getLogger('app')
        logger.info(f"Logging configurado para ambiente: {self.environment}")
        logger.info(f"Nivel de log: {self.log_level}")
        logger.info(f"JSON logging: {self.json_logging}")
        logger.info(f"File logging: {self.enable_file_logging}")
        logger.info(f"Console logging: {self.enable_console_logging}")
        
        return logger


# Función de utilidad para configurar logging
def setup_logging(environment: str = None, **kwargs) -> logging.Logger:
    """
    Configura el sistema de logging.
    
    Args:
        environment: Ambiente de ejecución
        **kwargs: Argumentos adicionales para LoggingConfig
        
    Returns:
        Logger principal configurado
    """
    if environment is None:
        environment = os.environ.get('ENVIRONMENT', 'development')
    
    config = LoggingConfig(environment, **kwargs)
    return config.setup_logging()


# Función para obtener logger con correlation ID
def get_logger(name: str, correlation_id: str = None) -> logging.Logger:
    """
    Obtiene un logger con correlation ID opcional.
    
    Args:
        name: Nombre del logger
        correlation_id: ID de correlación para tracing
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    
    if correlation_id:
        # Crear adapter que agrega correlation ID automáticamente
        logger = logging.LoggerAdapter(logger, {'correlation_id': correlation_id})
    
    return logger


# Context manager para logging con correlation ID
class LoggingContext:
    """
    Context manager para logging con correlation ID automático.
    """
    
    def __init__(self, correlation_id: str = None, logger_name: str = 'app'):
        """
        Inicializa el contexto de logging.
        
        Args:
            correlation_id: ID de correlación
            logger_name: Nombre del logger base
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self.logger_name = logger_name
        self.logger = None
    
    def __enter__(self):
        """
        Entra al contexto de logging.
        
        Returns:
            Logger con correlation ID configurado
        """
        self.logger = get_logger(self.logger_name, self.correlation_id)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Sale del contexto de logging.
        
        Args:
            exc_type: Tipo de excepción
            exc_val: Valor de excepción
            exc_tb: Traceback de excepción
        """
        if exc_type:
            self.logger.exception(f"Exception in logging context: {exc_val}")


# Decorador para logging automático de funciones
def log_function_call(logger_name: str = 'app', log_args: bool = False, log_result: bool = False):
    """
    Decorador para logging automático de llamadas a funciones.
    
    Args:
        logger_name: Nombre del logger a usar
        log_args: Si loggear argumentos de la función
        log_result: Si loggear resultado de la función
        
    Returns:
        Decorador configurado
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name)
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log de entrada
            log_msg = f"Calling {func_name}"
            if log_args:
                # Sanitizar argumentos sensibles
                safe_args = SensitiveDataFilter()._sanitize_args(args)
                safe_kwargs = SensitiveDataFilter()._sanitize_args(kwargs)
                log_msg += f" with args={safe_args}, kwargs={safe_kwargs}"
            
            logger.debug(log_msg)
            
            start_time = datetime.now(timezone.utc)
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                
                # Log de salida exitosa
                log_msg = f"Completed {func_name} in {duration:.3f}s"
                if log_result:
                    safe_result = SensitiveDataFilter()._sanitize_value('result', result)
                    log_msg += f" with result={safe_result}"
                
                logger.debug(log_msg)
                return result
                
            except Exception as e:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.exception(f"Error in {func_name} after {duration:.3f}s: {str(e)}")
                raise
        
        return wrapper
    return decorator


# Exportaciones públicas
__all__ = [
    'LoggingConfig',
    'JsonFormatter',
    'DetailedFormatter',
    'CorrelationFilter',
    'PerformanceFilter',
    'SensitiveDataFilter',
    'CompressedRotatingFileHandler',
    'SamplingFilter',
    'LoggingContext',
    'setup_logging',
    'get_logger',
    'log_function_call',
]