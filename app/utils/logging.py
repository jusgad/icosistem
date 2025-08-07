"""
Sistema de logging avanzado para el ecosistema de emprendimiento.
Proporciona configuración estructurada de logs con múltiples niveles y salidas.
"""

import os
import sys
import logging
import logging.config
from logging.handlers import RotatingFileHandler, SMTPHandler
from datetime import datetime
import json
import traceback
from typing import Dict, Any, Optional
from flask import request, session, g, has_request_context
from flask_login import current_user


class RequestFormatter(logging.Formatter):
    """Formatter personalizado que incluye información de la request."""
    
    def format(self, record):
        """Formatear el record incluyendo información del contexto."""
        
        # Información básica
        record.timestamp = datetime.utcnow().isoformat()
        record.service = 'ecosistema-emprendimiento'
        
        # Información de request si está disponible
        if has_request_context():
            record.request_id = getattr(g, 'request_id', None)
            record.user_id = current_user.id if current_user.is_authenticated else None
            record.user_email = current_user.email if current_user.is_authenticated else None
            record.ip_address = request.remote_addr
            record.user_agent = request.headers.get('User-Agent', '')[:200]
            record.method = request.method
            record.url = request.url
            record.endpoint = request.endpoint
        else:
            record.request_id = None
            record.user_id = None
            record.user_email = None
            record.ip_address = None
            record.user_agent = None
            record.method = None
            record.url = None
            record.endpoint = None
        
        # Información del sistema
        record.process_id = os.getpid()
        record.thread_name = record.threadName
        
        return super().format(record)


class JSONFormatter(RequestFormatter):
    """Formatter para logs en formato JSON."""
    
    def format(self, record):
        """Formatear el record como JSON estructurado."""
        
        # Llamar al formatter padre para agregar campos adicionales
        super().format(record)
        
        # Construir objeto JSON
        log_data = {
            'timestamp': record.timestamp,
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': record.service,
            'process_id': record.process_id,
            'thread_name': record.thread_name,
        }
        
        # Información de request
        if record.request_id:
            log_data['request'] = {
                'id': record.request_id,
                'method': record.method,
                'url': record.url,
                'endpoint': record.endpoint,
                'ip_address': record.ip_address,
                'user_agent': record.user_agent[:100] if record.user_agent else None
            }
        
        # Información de usuario
        if record.user_id:
            log_data['user'] = {
                'id': record.user_id,
                'email': record.user_email
            }
        
        # Información del módulo
        log_data['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName,
            'module': record.module
        }
        
        # Información de excepción si existe
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Campos extra del record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info', 'timestamp', 'service',
                          'request_id', 'user_id', 'user_email', 'ip_address',
                          'user_agent', 'method', 'url', 'endpoint', 'process_id',
                          'thread_name'}:
                extra_fields[key] = value
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(RequestFormatter):
    """Formatter con colores para desarrollo."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        """Formatear con colores."""
        super().format(record)
        
        # Aplicar color según el nivel
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Formatear con colores
        record.levelname = f"{color}{record.levelname}{reset}"
        record.name = f"\033[94m{record.name}{reset}"  # Blue
        
        return super(RequestFormatter, self).format(record)


class SecurityFilter(logging.Filter):
    """Filtro para remover información sensible de los logs."""
    
    SENSITIVE_KEYS = [
        'password', 'passwd', 'pwd', 'secret', 'key', 'token',
        'authorization', 'cookie', 'session', 'csrf', 'api_key',
        'client_secret', 'private_key', 'credit_card', 'ssn'
    ]
    
    def filter(self, record):
        """Filtrar información sensible del record."""
        
        # Sanitizar el mensaje
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._sanitize_text(record.msg)
        
        # Sanitizar argumentos
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._sanitize_value(arg) for arg in record.args
            )
        
        return True
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitizar texto reemplazando valores sensibles."""
        for key in self.SENSITIVE_KEYS:
            # Buscar patrones como key=value, key:value, "key":"value"
            import re
            patterns = [
                rf'{key}["\']?\s*[=:]\s*["\']?([^"\'\s,}}]+)',
                rf'"{key}":\s*"([^"]+)"',
                rf"'{key}':\s*'([^']+)'"
            ]
            
            for pattern in patterns:
                text = re.sub(pattern, f'{key}=***HIDDEN***', text, flags=re.IGNORECASE)
        
        return text
    
    def _sanitize_value(self, value) -> Any:
        """Sanitizar valor individual."""
        if isinstance(value, dict):
            return {
                k: '***HIDDEN***' if any(sens in k.lower() for sens in self.SENSITIVE_KEYS) else v
                for k, v in value.items()
            }
        elif isinstance(value, str):
            return self._sanitize_text(value)
        else:
            return value


def setup_logging(level: int = logging.INFO, 
                 format_json: bool = False,
                 include_request_id: bool = True,
                 log_file: Optional[str] = None,
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 enable_email_alerts: bool = False,
                 smtp_config: Optional[Dict[str, Any]] = None) -> None:
    """
    Configurar el sistema de logging.
    
    Args:
        level: Nivel mínimo de logging
        format_json: Si usar formato JSON
        include_request_id: Si incluir ID de request
        log_file: Archivo de log (opcional)
        max_bytes: Tamaño máximo del archivo de log
        backup_count: Número de archivos de respaldo
        enable_email_alerts: Si enviar alertas por email
        smtp_config: Configuración SMTP para alertas
    """
    
    # Configuración base
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'security_filter': {
                '()': SecurityFilter,
            }
        },
        'formatters': {
            'json': {
                '()': JSONFormatter,
            },
            'colored': {
                '()': ColoredFormatter,
                'format': '%(asctime)s [%(levelname)s] %(name)s (%(request_id)s): %(message)s'
            },
            'standard': {
                '()': RequestFormatter,
                'format': '%(timestamp)s [%(levelname)s] %(name)s (%(request_id)s) - %(user_email)s@%(ip_address)s: %(message)s'
            },
            'simple': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': 'colored' if not format_json else 'json',
                'filters': ['security_filter']
            }
        },
        'loggers': {
            # Logger de la aplicación
            'app': {
                'level': level,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger específico para requests
            'request': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger específico para respuestas
            'response': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger para excepciones del ecosistema
            'ecosistema.exceptions': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger para integración con servicios externos
            'ecosistema.integrations': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger para analytics
            'ecosistema.analytics': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            # Logger para tareas en background
            'ecosistema.tasks': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            # Loggers de terceros (más silenciosos)
            'werkzeug': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'sqlalchemy.engine': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'boto3': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'botocore': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'urllib3': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            },
            'requests': {
                'level': logging.WARNING,
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': level,
            'handlers': ['console']
        }
    }
    
    # Agregar handler de archivo si se especifica
    if log_file:
        # Crear directorio si no existe
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        logging_config['handlers']['file'] = {
            'level': level,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_file,
            'maxBytes': max_bytes,
            'backupCount': backup_count,
            'formatter': 'json' if format_json else 'standard',
            'filters': ['security_filter'],
            'encoding': 'utf-8'
        }
        
        # Agregar handler de archivo a todos los loggers
        for logger_name in logging_config['loggers']:
            logging_config['loggers'][logger_name]['handlers'].append('file')
        
        logging_config['root']['handlers'].append('file')
    
    # Agregar handler de email si se especifica
    if enable_email_alerts and smtp_config:
        logging_config['handlers']['email'] = {
            'level': logging.ERROR,
            'class': 'logging.handlers.SMTPHandler',
            'mailhost': (smtp_config['host'], smtp_config.get('port', 587)),
            'fromaddr': smtp_config['from_addr'],
            'toaddrs': smtp_config['to_addrs'],
            'subject': f"[{smtp_config.get('app_name', 'EcosistemaApp')}] Error Crítico",
            'credentials': (smtp_config.get('username'), smtp_config.get('password')),
            'secure': () if smtp_config.get('use_tls', True) else None,
            'formatter': 'json' if format_json else 'standard',
            'filters': ['security_filter']
        }
        
        # Solo agregar a loggers importantes
        for logger_name in ['app', 'ecosistema.exceptions', 'root']:
            if logger_name in logging_config['loggers']:
                logging_config['loggers'][logger_name]['handlers'].append('email')
            elif logger_name == 'root':
                logging_config['root']['handlers'].append('email')
    
    # Aplicar configuración
    logging.config.dictConfig(logging_config)
    
    # Log de inicio
    logger = logging.getLogger('app')
    logger.info("Logging system initialized successfully", extra={
        'log_level': logging.getLevelName(level),
        'json_format': format_json,
        'log_file': log_file,
        'email_alerts': enable_email_alerts
    })


def get_logger(name: str = 'app') -> logging.Logger:
    """
    Obtener un logger configurado.
    
    Args:
        name: Nombre del logger
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


# Funciones de conveniencia para diferentes tipos de logs
def log_request(method: str, url: str, status_code: int, duration: float, 
               user_id: Optional[int] = None, extra: Optional[Dict] = None):
    """Log estructurado de requests."""
    logger = get_logger('request')
    logger.info(f"{method} {url} - {status_code} ({duration:.3f}s)", extra={
        'method': method,
        'url': url,
        'status_code': status_code,
        'duration_seconds': duration,
        'user_id': user_id,
        **(extra or {})
    })


def log_user_action(action: str, user_id: int, resource_type: Optional[str] = None,
                   resource_id: Optional[int] = None, extra: Optional[Dict] = None):
    """Log estructurado de acciones de usuario."""
    logger = get_logger('app')
    logger.info(f"User action: {action}", extra={
        'action': action,
        'user_id': user_id,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'category': 'user_action',
        **(extra or {})
    })


def log_integration_call(service: str, operation: str, success: bool, 
                        duration: float, extra: Optional[Dict] = None):
    """Log estructurado de llamadas a servicios externos."""
    logger = get_logger('ecosistema.integrations')
    level = logging.INFO if success else logging.WARNING
    status = 'success' if success else 'failed'
    
    logger.log(level, f"{service}.{operation} - {status} ({duration:.3f}s)", extra={
        'service': service,
        'operation': operation,
        'success': success,
        'duration_seconds': duration,
        'category': 'integration',
        **(extra or {})
    })


def log_business_event(event_type: str, description: str, user_id: Optional[int] = None,
                      extra: Optional[Dict] = None):
    """Log estructurado de eventos de negocio."""
    logger = get_logger('app')
    logger.info(f"Business event: {event_type} - {description}", extra={
        'event_type': event_type,
        'description': description,
        'user_id': user_id,
        'category': 'business_event',
        **(extra or {})
    })


def log_security_event(event_type: str, description: str, severity: str = 'medium',
                      ip_address: Optional[str] = None, user_id: Optional[int] = None,
                      extra: Optional[Dict] = None):
    """Log estructurado de eventos de seguridad."""
    logger = get_logger('app')
    
    # Determinar nivel según severidad
    level_map = {
        'low': logging.INFO,
        'medium': logging.WARNING,
        'high': logging.ERROR,
        'critical': logging.CRITICAL
    }
    level = level_map.get(severity, logging.WARNING)
    
    logger.log(level, f"Security event: {event_type} - {description}", extra={
        'event_type': event_type,
        'description': description,
        'severity': severity,
        'ip_address': ip_address,
        'user_id': user_id,
        'category': 'security_event',
        **(extra or {})
    })