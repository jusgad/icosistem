# -*- coding: utf-8 -*-
"""
Módulo de configuración centralizada para el Ecosistema de Emprendimiento
=======================================================================

Este módulo proporciona un sistema robusto de configuración que maneja:
- Configuraciones por ambiente (desarrollo, producción, testing, docker)
- Validación de variables de entorno críticas
- Configuración dinámica de logging
- Gestión segura de secretos y credenciales
- Configuración de servicios externos (Google, email, storage, etc.)

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import warnings
from typing import Type, Any, Optional
from urllib.parse import urlparse

# Configuraciones específicas por ambiente
from .base import BaseConfig
from .development import DevelopmentConfig
from .production import ProductionConfig
from .testing import TestingConfig
from .docker import DockerConfig

# Importar también desde config.py de la raíz para compatibilidad
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import Config, DevelopmentConfig as RootDevConfig, ProductionConfig as RootProdConfig, TestingConfig as RootTestConfig, DockerConfig as RootDockerConfig
    
    # Crear mapeo de compatibilidad con la estructura anterior
    config = {
        'development': RootDevConfig,
        'testing': RootTestConfig,
        'production': RootProdConfig,
        'docker': RootDockerConfig,
        'default': RootDevConfig
    }
    
except ImportError:
    # Fallback al sistema moderno si no existe el archivo raíz
    config = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
        'docker': DockerConfig,
        'default': DevelopmentConfig
    }


class ConfigurationError(Exception):
    """Excepción personalizada para errores de configuración."""
    pass


class ConfigManager:
    """
    Gestor centralizado de configuración del ecosistema.
    
    Proporciona una interfaz unificada para:
    - Selección automática de configuración por ambiente
    - Validación de configuraciones críticas
    - Acceso seguro a variables sensibles
    - Configuración dinámica de servicios
    """
    
    # Mapeo de ambientes a clases de configuración
    _config_map: dict[str, Type[BaseConfig]] = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
        'docker': DockerConfig,
    }
    
    # Variables críticas que deben estar presentes
    _critical_vars = {
        'production': [
            'SECRET_KEY',
            'DATABASE_URL',
            'REDIS_URL',
            'EMAIL_API_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET'
        ],
        'development': [
            'SECRET_KEY',
            'DATABASE_URL'
        ],
        'testing': [
            'SECRET_KEY',
            'TEST_DATABASE_URL'
        ],
        'docker': [
            'SECRET_KEY',
            'DATABASE_URL',
            'REDIS_URL'
        ]
    }
    
    def __init__(self):
        self._current_config: Optional[BaseConfig] = None
        self._environment: Optional[str] = None
        
    def get_config(self, environment: Optional[str] = None) -> BaseConfig:
        """
        Obtiene la configuración para el ambiente especificado.
        
        Args:
            environment: Nombre del ambiente (development, production, testing, docker)
                        Si no se especifica, se detecta automáticamente.
        
        Returns:
            Instancia de configuración apropiada para el ambiente
            
        Raises:
            ConfigurationError: Si el ambiente no es válido o faltan variables críticas
        """
        if environment is None:
            environment = self._detect_environment()
            
        if environment not in self._config_map:
            available = ', '.join(self._config_map.keys())
            raise ConfigurationError(
                f"Ambiente '{environment}' no válido. "
                f"Ambientes disponibles: {available}"
            )
        
        # Validar variables críticas antes de cargar configuración
        self._validate_critical_vars(environment)
        
        # Crear instancia de configuración
        config_class = self._config_map[environment]
        config_instance = config_class()
        
        # Validar configuración después de instanciar
        self._validate_config_instance(config_instance, environment)
        
        # Almacenar referencia
        self._current_config = config_instance
        self._environment = environment
        
        return config_instance
    
    def _detect_environment(self) -> str:
        """
        Detecta automáticamente el ambiente basado en variables de entorno.
        
        Returns:
            Nombre del ambiente detectado
        """
        # Prioridad: FLASK_ENV > APP_ENV > detección automática
        env = os.environ.get('FLASK_ENV') or os.environ.get('APP_ENV')
        
        if env:
            # Normalizar nombres comunes
            env_mapping = {
                'dev': 'development',
                'develop': 'development',
                'prod': 'production',
                'test': 'testing',
                'tests': 'testing',
            }
            return env_mapping.get(env.lower(), env.lower())
        
        # Detección automática basada en indicadores
        if os.environ.get('DOCKER_CONTAINER'):
            return 'docker'
        elif os.environ.get('PYTEST_CURRENT_TEST'):
            return 'testing'
        elif os.environ.get('HEROKU_APP_NAME') or os.environ.get('DYNO'):
            return 'production'
        elif os.environ.get('RAILWAY_ENVIRONMENT'):
            return 'production'
        elif os.environ.get('VERCEL_ENV'):
            return 'production'
        else:
            # Por defecto desarrollo
            return 'development'
    
    def _validate_critical_vars(self, environment: str) -> None:
        """
        Valida que las variables críticas estén presentes para el ambiente.
        
        Args:
            environment: Ambiente a validar
            
        Raises:
            ConfigurationError: Si faltan variables críticas
        """
        critical_vars = self._critical_vars.get(environment, [])
        missing_vars = []
        
        for var in critical_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            vars_str = ', '.join(missing_vars)
            raise ConfigurationError(
                f"Variables de entorno críticas faltantes para '{environment}': {vars_str}"
            )
    
    def _validate_config_instance(self, config: BaseConfig, environment: str) -> None:
        """
        Valida la instancia de configuración después de crearla.
        
        Args:
            config: Instancia de configuración a validar
            environment: Ambiente correspondiente
            
        Raises:
            ConfigurationError: Si la configuración es inválida
        """
        errors = []
        
        # Validar SECRET_KEY
        if not config.SECRET_KEY or len(config.SECRET_KEY) < 32:
            errors.append("SECRET_KEY debe tener al menos 32 caracteres")
        
        # Validar DATABASE_URL
        if hasattr(config, 'SQLALCHEMY_DATABASE_URI'):
            db_url = config.SQLALCHEMY_DATABASE_URI
            if db_url:
                try:
                    parsed = urlparse(db_url)
                    if not parsed.scheme or not parsed.netloc:
                        errors.append("DATABASE_URL tiene formato inválido")
                except Exception:
                    errors.append("Error al parsear DATABASE_URL")
        
        # Validaciones específicas por ambiente
        if environment == 'production':
            # En producción, DEBUG debe ser False
            if getattr(config, 'DEBUG', True):
                warnings.warn(
                    "DEBUG está activado en producción. "
                    "Esto puede ser un riesgo de seguridad.",
                    UserWarning
                )
            
            # Validar SSL en producción
            if not getattr(config, 'SSL_REDIRECT', False):
                warnings.warn(
                    "SSL_REDIRECT está desactivado en producción. "
                    "Considere activarlo para mayor seguridad.",
                    UserWarning
                )
        
        if errors:
            error_str = '\n'.join(f"- {error}" for error in errors)
            raise ConfigurationError(
                f"Errores de validación en configuración '{environment}':\n{error_str}"
            )
    
    def get_database_info(self) -> dict[str, Any]:
        """
        Obtiene información de la base de datos de forma segura.
        
        Returns:
            Diccionario con información de la base de datos (sin credenciales)
        """
        if not self._current_config:
            raise ConfigurationError("No hay configuración cargada")
        
        db_url = getattr(self._current_config, 'SQLALCHEMY_DATABASE_URI', '')
        if not db_url:
            return {}
        
        try:
            parsed = urlparse(db_url)
            return {
                'scheme': parsed.scheme,
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path.lstrip('/') if parsed.path else None,
                'username': parsed.username,
                'has_password': bool(parsed.password)
            }
        except Exception:
            return {'error': 'No se pudo parsear la URL de base de datos'}
    
    def get_redis_info(self) -> dict[str, Any]:
        """
        Obtiene información de Redis de forma segura.
        
        Returns:
            Diccionario con información de Redis (sin credenciales)
        """
        if not self._current_config:
            raise ConfigurationError("No hay configuración cargada")
        
        redis_url = getattr(self._current_config, 'REDIS_URL', '')
        if not redis_url:
            return {}
        
        try:
            parsed = urlparse(redis_url)
            return {
                'scheme': parsed.scheme,
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path.lstrip('/') if parsed.path else '0',
                'has_password': bool(parsed.password)
            }
        except Exception:
            return {'error': 'No se pudo parsear la URL de Redis'}
    
    def is_feature_enabled(self, feature: str) -> bool:
        """
        Verifica si una característica específica está habilitada.
        
        Args:
            feature: Nombre de la característica
            
        Returns:
            True si la característica está habilitada, False en caso contrario
        """
        if not self._current_config:
            return False
        
        # Mapeo de características a configuraciones
        feature_map = {
            'debug': 'DEBUG',
            'testing': 'TESTING',
            'ssl_redirect': 'SSL_REDIRECT',
            'csrf_protection': 'WTF_CSRF_ENABLED',
            'rate_limiting': 'RATELIMIT_ENABLED',
            'google_oauth': 'GOOGLE_OAUTH_ENABLED',
            'email_verification': 'EMAIL_VERIFICATION_REQUIRED',
            'sms_notifications': 'SMS_ENABLED',
            'file_uploads': 'UPLOAD_ENABLED',
            'analytics': 'ANALYTICS_ENABLED',
            'maintenance_mode': 'MAINTENANCE_MODE'
        }
        
        config_key = feature_map.get(feature.lower())
        if config_key:
            return getattr(self._current_config, config_key, False)
        
        return False
    
    @property
    def current_environment(self) -> Optional[str]:
        """Retorna el ambiente actual."""
        return self._environment
    
    @property
    def current_config(self) -> Optional[BaseConfig]:
        """Retorna la configuración actual."""
        return self._current_config


# Instancia global del gestor de configuración
config_manager = ConfigManager()


def get_config(environment: Optional[str] = None) -> BaseConfig:
    """
    Función de conveniencia para obtener configuración.
    
    Args:
        environment: Ambiente específico (opcional)
        
    Returns:
        Instancia de configuración
    """
    return config_manager.get_config(environment)


def init_app_config(app, environment: Optional[str] = None) -> BaseConfig:
    """
    Inicializa la configuración de una aplicación Flask.
    
    Args:
        app: Instancia de aplicación Flask
        environment: Ambiente específico (opcional)
        
    Returns:
        Configuración aplicada
    """
    config = get_config(environment)
    app.config.from_object(config)
    
    # Agregar información adicional al contexto de la app
    app.config['ENVIRONMENT_NAME'] = config_manager.current_environment
    app.config['CONFIG_CLASS'] = config.__class__.__name__
    
    return config


def validate_environment() -> dict[str, Any]:
    """
    Valida el ambiente actual y retorna un reporte de estado.
    
    Returns:
        Diccionario con información del estado del ambiente
    """
    try:
        config = get_config()
        
        return {
            'status': 'valid',
            'environment': config_manager.current_environment,
            'config_class': config.__class__.__name__,
            'features': {
                'debug': config_manager.is_feature_enabled('debug'),
                'testing': config_manager.is_feature_enabled('testing'),
                'ssl_redirect': config_manager.is_feature_enabled('ssl_redirect'),
                'google_oauth': config_manager.is_feature_enabled('google_oauth'),
                'analytics': config_manager.is_feature_enabled('analytics'),
            },
            'database': config_manager.get_database_info(),
            'redis': config_manager.get_redis_info(),
        }
    except ConfigurationError as e:
        return {
            'status': 'error',
            'error': str(e),
            'environment': config_manager.current_environment,
        }


# Exportaciones públicas
__all__ = [
    'ConfigManager',
    'ConfigurationError',
    'config_manager',
    'get_config',
    'init_app_config',
    'validate_environment',
    'BaseConfig',
    'DevelopmentConfig',
    'ProductionConfig',
    'TestingConfig',
    'DockerConfig'
]


# Configuración de logging para el módulo
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())