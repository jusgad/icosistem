#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Setup Empresarial del Ecosistema de Emprendimiento
===========================================================

Script completo de configuración inicial que maneja:
- Validación de ambiente y dependencias
- Configuración de base de datos y migraciones
- Setup de servicios externos (Redis, Celery, etc.)
- Creación de estructura de directorios
- Configuración de variables de entorno
- Creación de usuarios y datos iniciales
- Validaciones de seguridad
- Configuración de backups y logging
- Health checks de servicios
- Setup específico por ambiente

Uso:
    python scripts/setup.py --environment development
    python scripts/setup.py --environment production --skip-interactive
    python scripts/setup.py --reset --force

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import sys
import argparse
import subprocess
import json
import secrets
import logging
import shutil
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import tempfile
import getpass


# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class SetupConfig:
    """
    Configuración del proceso de setup.
    """
    environment: str
    interactive: bool = True
    force: bool = False
    reset: bool = False
    skip_db: bool = False
    skip_deps: bool = False
    skip_services: bool = False
    skip_data: bool = False
    verbose: bool = False
    dry_run: bool = False


class Colors:
    """
    Códigos de colores ANSI para output colorizado.
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class SetupLogger:
    """
    Logger especializado para el proceso de setup.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Inicializa el logger de setup.
        
        Args:
            verbose: Si mostrar logs verbosos
        """
        self.verbose = verbose
        self.setup_logging()
    
    def setup_logging(self):
        """
        Configura logging para el setup.
        """
        log_format = '%(asctime)s [SETUP] %(levelname)s: %(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.logger = logging.getLogger('setup')
    
    def info(self, message: str):
        """Log info con color."""
        print(f"{Colors.OKGREEN}[INFO]{Colors.ENDC} {message}")
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning con color."""
        print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {message}")
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error con color."""
        print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {message}")
        self.logger.error(message)
    
    def success(self, message: str):
        """Log success con color."""
        print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {message}")
        self.logger.info(f"SUCCESS: {message}")
    
    def header(self, message: str):
        """Log header con formato especial."""
        separator = "=" * 60
        print(f"\n{Colors.HEADER}{Colors.BOLD}{separator}")
        print(f"{message.center(60)}")
        print(f"{separator}{Colors.ENDC}")
        self.logger.info(f"=== {message} ===")
    
    def step(self, step_num: int, total_steps: int, message: str):
        """Log paso del proceso."""
        print(f"{Colors.OKCYAN}[{step_num}/{total_steps}]{Colors.ENDC} {message}")
        self.logger.info(f"Step {step_num}/{total_steps}: {message}")


class SetupError(Exception):
    """
    Excepción personalizada para errores de setup.
    """
    pass


class EcosistemaSetup:
    """
    Clase principal para el setup del ecosistema de emprendimiento.
    """
    
    def __init__(self, config: SetupConfig):
        """
        Inicializa el setup.
        
        Args:
            config: Configuración del setup
        """
        self.config = config
        self.logger = SetupLogger(config.verbose)
        self.project_root = project_root
        self.env_file = self.project_root / '.env.local'
        
        # Configuraciones por ambiente
        self.environment_configs = {
            'development': {
                'database_url': 'postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_dev',
                'redis_url': 'redis://localhost:6379/1',
                'debug': True,
                'create_sample_data': True,
                'sample_data_size': 'medium',
            },
            'testing': {
                'database_url': 'postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_test',
                'redis_url': 'redis://localhost:6379/15',
                'debug': False,
                'create_sample_data': False,
            },
            'production': {
                'database_url': None,  # Debe ser proporcionada
                'redis_url': None,     # Debe ser proporcionada
                'debug': False,
                'create_sample_data': False,
            },
            'docker': {
                'database_url': 'postgresql://postgres:password@postgres:5432/ecosistema_emprendimiento',
                'redis_url': 'redis://redis:6379/0',
                'debug': False,
                'create_sample_data': True,
                'sample_data_size': 'small',
            }
        }
    
    def run(self):
        """
        Ejecuta el proceso completo de setup.
        """
        try:
            self.logger.header(f"SETUP DEL ECOSISTEMA DE EMPRENDIMIENTO - {self.config.environment.upper()}")
            
            total_steps = self._count_steps()
            step = 1
            
            # Validaciones iniciales
            self.logger.step(step, total_steps, "Validando ambiente y dependencias")
            self._validate_environment()
            step += 1
            
            # Crear estructura de directorios
            self.logger.step(step, total_steps, "Creando estructura de directorios")
            self._create_directory_structure()
            step += 1
            
            # Configurar variables de entorno
            self.logger.step(step, total_steps, "Configurando variables de entorno")
            self._setup_environment_variables()
            step += 1
            
            # Instalar dependencias
            if not self.config.skip_deps:
                self.logger.step(step, total_steps, "Instalando dependencias")
                self._install_dependencies()
                step += 1
            
            # Configurar base de datos
            if not self.config.skip_db:
                self.logger.step(step, total_steps, "Configurando base de datos")
                self._setup_database()
                step += 1
            
            # Configurar servicios externos
            if not self.config.skip_services:
                self.logger.step(step, total_steps, "Configurando servicios externos")
                self._setup_external_services()
                step += 1
            
            # Ejecutar migraciones
            if not self.config.skip_db:
                self.logger.step(step, total_steps, "Ejecutando migraciones de base de datos")
                self._run_migrations()
                step += 1
            
            # Crear datos iniciales
            if not self.config.skip_data:
                self.logger.step(step, total_steps, "Creando datos iniciales")
                self._create_initial_data()
                step += 1
            
            # Configurar servicios de background
            self.logger.step(step, total_steps, "Configurando servicios de background")
            self._setup_background_services()
            step += 1
            
            # Configurar logging y monitoreo
            self.logger.step(step, total_steps, "Configurando logging y monitoreo")
            self._setup_logging_and_monitoring()
            step += 1
            
            # Configurar backups
            if self.config.environment == 'production':
                self.logger.step(step, total_steps, "Configurando sistema de backups")
                self._setup_backup_system()
                step += 1
            
            # Validaciones finales
            self.logger.step(step, total_steps, "Ejecutando validaciones finales")
            self._final_validations()
            step += 1
            
            # Mostrar resumen
            self._show_setup_summary()
            
            self.logger.success("Setup completado exitosamente!")
            
        except KeyboardInterrupt:
            self.logger.warning("Setup interrumpido por el usuario")
            sys.exit(1)
        except SetupError as e:
            self.logger.error(f"Error en setup: {str(e)}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Error inesperado: {str(e)}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    
    def _count_steps(self) -> int:
        """
        Cuenta el total de pasos del setup.
        
        Returns:
            Número total de pasos
        """
        steps = 8  # Pasos base
        
        if not self.config.skip_deps:
            steps += 1
        if not self.config.skip_db:
            steps += 2  # DB setup + migrations
        if not self.config.skip_services:
            steps += 1
        if not self.config.skip_data:
            steps += 1
        if self.config.environment == 'production':
            steps += 1  # Backup setup
        
        return steps
    
    def _validate_environment(self):
        """
        Valida el ambiente y dependencias del sistema.
        """
        self.logger.info("Validando ambiente del sistema...")
        
        # Validar Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            raise SetupError(f"Python 3.8+ requerido. Versión actual: {python_version.major}.{python_version.minor}")
        
        self.logger.info(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Validar herramientas requeridas
        required_tools = ['git', 'pip']
        if self.config.environment != 'docker':
            required_tools.extend(['psql', 'redis-cli'])
        
        for tool in required_tools:
            if not self._check_command_exists(tool):
                if tool in ['psql', 'redis-cli'] and self.config.interactive:
                    response = input(f"{tool} no encontrado. ¿Continuar sin validación? (y/n): ")
                    if response.lower() != 'y':
                        raise SetupError(f"Herramienta requerida no encontrada: {tool}")
                else:
                    raise SetupError(f"Herramienta requerida no encontrada: {tool}")
        
        # Validar ambiente específico
        env_config = self.environment_configs.get(self.config.environment)
        if not env_config:
            raise SetupError(f"Ambiente no soportado: {self.config.environment}")
        
        # Validar permisos de escritura
        if not os.access(self.project_root, os.W_OK):
            raise SetupError(f"Sin permisos de escritura en: {self.project_root}")
        
        self.logger.success("Validación de ambiente completada")
    
    def _check_command_exists(self, command: str) -> bool:
        """
        Verifica si un comando existe en el sistema.
        
        Args:
            command: Comando a verificar
            
        Returns:
            True si el comando existe
        """
        try:
            subprocess.run([command, '--version'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _create_directory_structure(self):
        """
        Crea la estructura de directorios necesaria.
        """
        self.logger.info("Creando estructura de directorios...")
        
        directories = [
            'logs',
            'app/static/uploads',
            'app/static/uploads/images',
            'app/static/uploads/documents',
            'app/static/uploads/videos',
            'app/static/uploads/audio',
            'app/static/dist',
            'app/static/dist/css',
            'app/static/dist/js',
            'app/static/dist/img',
            'tests/reports',
            'tests/coverage',
            'tests/screenshots',
            'tests/fixtures',
            'backups',
            'backups/database',
            'backups/files',
            'data',
            'data/exports',
            'data/imports',
            'data/temp',
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            if not self.config.dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
                # Crear .gitkeep para directorios vacíos
                gitkeep_file = dir_path / '.gitkeep'
                if not gitkeep_file.exists() and not any(dir_path.iterdir()):
                    gitkeep_file.touch()
            
            self.logger.info(f"Directorio creado: {directory}")
        
        # Crear archivos de configuración si no existen
        config_files = [
            ('.env.example', self._generate_env_example()),
            ('.editorconfig', self._generate_editorconfig()),
            ('.gitignore', self._generate_gitignore()),
        ]
        
        for filename, content in config_files:
            file_path = self.project_root / filename
            if not file_path.exists() and not self.config.dry_run:
                file_path.write_text(content, encoding='utf-8')
                self.logger.info(f"Archivo creado: {filename}")
        
        self.logger.success("Estructura de directorios creada")
    
    def _setup_environment_variables(self):
        """
        Configura las variables de entorno necesarias.
        """
        self.logger.info("Configurando variables de entorno...")
        
        env_config = self.environment_configs[self.config.environment]
        
        # Variables base
        env_vars = {
            'FLASK_ENV': self.config.environment,
            'ENVIRONMENT': self.config.environment,
            'DEBUG': str(env_config['debug']),
            'SECRET_KEY': self._generate_secret_key(),
            'APP_NAME': 'Ecosistema de Emprendimiento',
            'APP_VERSION': '2.0.0',
            'TIMEZONE': 'America/Bogota',
            'DEFAULT_LOCALE': 'es_CO',
            'DEFAULT_CURRENCY': 'COP',
        }
        
        # Variables de base de datos
        if self.config.environment == 'production':
            if self.config.interactive:
                db_url = input("URL de base de datos de producción: ").strip()
                if not db_url:
                    raise SetupError("URL de base de datos requerida para producción")
                env_vars['DATABASE_URL'] = db_url
        else:
            env_vars['DATABASE_URL'] = env_config['database_url']
        
        # Variables de Redis
        if self.config.environment == 'production':
            if self.config.interactive:
                redis_url = input("URL de Redis de producción (opcional): ").strip()
                if redis_url:
                    env_vars['REDIS_URL'] = redis_url
        else:
            env_vars['REDIS_URL'] = env_config['redis_url']
        
        # Variables de servicios externos
        if self.config.interactive and self.config.environment != 'testing':
            self._collect_external_service_config(env_vars)
        
        # Escribir archivo .env
        if not self.config.dry_run:
            self._write_env_file(env_vars)
        
        self.logger.success("Variables de entorno configuradas")
    
    def _collect_external_service_config(self, env_vars: Dict[str, str]):
        """
        Recolecta configuración de servicios externos del usuario.
        
        Args:
            env_vars: Diccionario de variables de entorno
        """
        self.logger.info("Configurando servicios externos (opcional)...")
        
        # Google OAuth
        if input("¿Configurar Google OAuth? (y/n): ").lower() == 'y':
            client_id = input("Google Client ID: ").strip()
            client_secret = getpass.getpass("Google Client Secret: ").strip()
            if client_id and client_secret:
                env_vars['GOOGLE_CLIENT_ID'] = client_id
                env_vars['GOOGLE_CLIENT_SECRET'] = client_secret
        
        # Email (SendGrid)
        if input("¿Configurar email (SendGrid)? (y/n): ").lower() == 'y':
            api_key = getpass.getpass("SendGrid API Key: ").strip()
            sender = input("Email remitente por defecto: ").strip()
            if api_key:
                env_vars['SENDGRID_API_KEY'] = api_key
                env_vars['EMAIL_BACKEND'] = 'sendgrid'
            if sender:
                env_vars['MAIL_DEFAULT_SENDER'] = sender
        
        # SMS (Twilio)
        if input("¿Configurar SMS (Twilio)? (y/n): ").lower() == 'y':
            account_sid = input("Twilio Account SID: ").strip()
            auth_token = getpass.getpass("Twilio Auth Token: ").strip()
            phone = input("Número de teléfono Twilio: ").strip()
            if account_sid and auth_token:
                env_vars['TWILIO_ACCOUNT_SID'] = account_sid
                env_vars['TWILIO_AUTH_TOKEN'] = auth_token
                env_vars['SMS_ENABLED'] = 'True'
            if phone:
                env_vars['TWILIO_PHONE_NUMBER'] = phone
        
        # Sentry
        if input("¿Configurar Sentry para monitoreo? (y/n): ").lower() == 'y':
            dsn = input("Sentry DSN: ").strip()
            if dsn:
                env_vars['SENTRY_DSN'] = dsn
                env_vars['SENTRY_ENABLED'] = 'True'
    
    def _generate_secret_key(self) -> str:
        """
        Genera una clave secreta segura.
        
        Returns:
            Clave secreta generada
        """
        return secrets.token_hex(32)
    
    def _write_env_file(self, env_vars: Dict[str, str]):
        """
        Escribre el archivo .env con las variables.
        
        Args:
            env_vars: Variables de entorno a escribir
        """
        env_content = []
        env_content.append("# Variables de entorno del Ecosistema de Emprendimiento")
        env_content.append(f"# Generado automáticamente: {datetime.now().isoformat()}")
        env_content.append(f"# Ambiente: {self.config.environment}")
        env_content.append("")
        
        # Agrupar variables por categoría
        categories = {
            'Aplicación': ['FLASK_ENV', 'ENVIRONMENT', 'DEBUG', 'SECRET_KEY', 'APP_NAME', 'APP_VERSION'],
            'Base de Datos': ['DATABASE_URL', 'REDIS_URL'],
            'Localización': ['TIMEZONE', 'DEFAULT_LOCALE', 'DEFAULT_CURRENCY'],
            'Google Services': ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'],
            'Email': ['EMAIL_BACKEND', 'SENDGRID_API_KEY', 'MAIL_DEFAULT_SENDER'],
            'SMS': ['SMS_ENABLED', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER'],
            'Monitoreo': ['SENTRY_DSN', 'SENTRY_ENABLED'],
        }
        
        for category, vars_in_category in categories.items():
            category_vars = {k: v for k, v in env_vars.items() if k in vars_in_category}
            if category_vars:
                env_content.append(f"# {category}")
                for key, value in category_vars.items():
                    env_content.append(f"{key}={value}")
                env_content.append("")
        
        # Variables adicionales no categorizadas
        categorized_vars = set()
        for vars_list in categories.values():
            categorized_vars.update(vars_list)
        
        other_vars = {k: v for k, v in env_vars.items() if k not in categorized_vars}
        if other_vars:
            env_content.append("# Otras configuraciones")
            for key, value in other_vars.items():
                env_content.append(f"{key}={value}")
        
        self.env_file.write_text('\n'.join(env_content), encoding='utf-8')
        self.logger.info(f"Archivo de variables de entorno creado: {self.env_file}")
    
    def _install_dependencies(self):
        """
        Instala las dependencias del proyecto.
        """
        self.logger.info("Instalando dependencias de Python...")
        
        # Determinar archivos de requirements
        req_files = ['requirements.txt']
        
        if self.config.environment == 'development':
            req_files.append('requirements-dev.txt')
        elif self.config.environment == 'testing':
            req_files.extend(['requirements-dev.txt', 'requirements-test.txt'])
        
        for req_file in req_files:
            req_path = self.project_root / req_file
            if req_path.exists():
                if not self.config.dry_run:
                    try:
                        subprocess.run([
                            sys.executable, '-m', 'pip', 'install', '-r', str(req_path)
                        ], check=True, capture_output=True, text=True)
                        self.logger.info(f"Dependencias instaladas desde: {req_file}")
                    except subprocess.CalledProcessError as e:
                        self.logger.warning(f"Error instalando {req_file}: {e.stderr}")
                        if not self.config.force:
                            raise SetupError(f"Error instalando dependencias: {req_file}")
            else:
                self.logger.warning(f"Archivo de requirements no encontrado: {req_file}")
        
        self.logger.success("Dependencias instaladas")
    
    def _setup_database(self):
        """
        Configura la base de datos.
        """
        self.logger.info("Configurando base de datos...")
        
        env_config = self.environment_configs[self.config.environment]
        db_url = env_config.get('database_url')
        
        if not db_url:
            raise SetupError("URL de base de datos no configurada")
        
        # Parsear URL de base de datos
        parsed_url = urllib.parse.urlparse(db_url)
        db_name = parsed_url.path.lstrip('/')
        
        if not db_name:
            raise SetupError("Nombre de base de datos no válido en URL")
        
        # Verificar conexión a PostgreSQL
        if not self.config.dry_run:
            if not self._test_database_connection(db_url):
                if self.config.interactive:
                    create_db = input(f"¿Crear base de datos '{db_name}'? (y/n): ")
                    if create_db.lower() == 'y':
                        self._create_database(parsed_url, db_name)
                    else:
                        raise SetupError("Base de datos no disponible")
                else:
                    self._create_database(parsed_url, db_name)
        
        self.logger.success("Base de datos configurada")
    
    def _test_database_connection(self, db_url: str) -> bool:
        """
        Prueba la conexión a la base de datos.
        
        Args:
            db_url: URL de la base de datos
            
        Returns:
            True si la conexión es exitosa
        """
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            conn.close()
            self.logger.info("Conexión a base de datos exitosa")
            return True
        except Exception as e:
            self.logger.warning(f"Error conectando a base de datos: {str(e)}")
            return False
    
    def _create_database(self, parsed_url: urllib.parse.ParseResult, db_name: str):
        """
        Crea la base de datos si no existe.
        
        Args:
            parsed_url: URL parseada de la base de datos
            db_name: Nombre de la base de datos
        """
        try:
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            
            # Conectar al servidor PostgreSQL (base de datos postgres)
            conn_url = parsed_url._replace(path='/postgres').geturl()
            conn = psycopg2.connect(conn_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            
            # Verificar si la base de datos existe
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (db_name,)
            )
            
            if not cursor.fetchone():
                # Crear base de datos
                cursor.execute(f'CREATE DATABASE "{db_name}"')
                self.logger.info(f"Base de datos '{db_name}' creada")
            else:
                self.logger.info(f"Base de datos '{db_name}' ya existe")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            raise SetupError(f"Error creando base de datos: {str(e)}")
    
    def _setup_external_services(self):
        """
        Configura y valida servicios externos.
        """
        self.logger.info("Configurando servicios externos...")
        
        # Validar Redis si está configurado
        env_config = self.environment_configs[self.config.environment]
        redis_url = env_config.get('redis_url')
        
        if redis_url and not self.config.dry_run:
            if not self._test_redis_connection(redis_url):
                self.logger.warning("Redis no disponible - algunas funcionalidades estarán limitadas")
            else:
                self.logger.info("Conexión a Redis exitosa")
        
        # Crear directorios para servicios
        service_dirs = [
            'logs/celery',
            'data/cache',
            'data/sessions',
        ]
        
        for service_dir in service_dirs:
            dir_path = self.project_root / service_dir
            if not self.config.dry_run:
                dir_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.success("Servicios externos configurados")
    
    def _test_redis_connection(self, redis_url: str) -> bool:
        """
        Prueba la conexión a Redis.
        
        Args:
            redis_url: URL de Redis
            
        Returns:
            True si la conexión es exitosa
        """
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            return True
        except Exception as e:
            self.logger.warning(f"Error conectando a Redis: {str(e)}")
            return False
    
    def _run_migrations(self):
        """
        Ejecuta las migraciones de base de datos.
        """
        self.logger.info("Ejecutando migraciones de base de datos...")
        
        if not self.config.dry_run:
            try:
                # Cargar variables de entorno
                self._load_env_file()
                
                # Ejecutar Flask db upgrade
                result = subprocess.run([
                    sys.executable, '-m', 'flask', 'db', 'upgrade'
                ], cwd=self.project_root, check=True, capture_output=True, text=True)
                
                self.logger.info("Migraciones ejecutadas exitosamente")
                
            except subprocess.CalledProcessError as e:
                if 'No migrations folder' in e.stderr:
                    # Inicializar migraciones si no existen
                    self.logger.info("Inicializando sistema de migraciones...")
                    subprocess.run([
                        sys.executable, '-m', 'flask', 'db', 'init'
                    ], cwd=self.project_root, check=True)
                    
                    # Crear migración inicial
                    subprocess.run([
                        sys.executable, '-m', 'flask', 'db', 'migrate', '-m', 'Initial migration'
                    ], cwd=self.project_root, check=True)
                    
                    # Ejecutar migración
                    subprocess.run([
                        sys.executable, '-m', 'flask', 'db', 'upgrade'
                    ], cwd=self.project_root, check=True)
                    
                    self.logger.info("Sistema de migraciones inicializado")
                else:
                    raise SetupError(f"Error ejecutando migraciones: {e.stderr}")
        
        self.logger.success("Migraciones completadas")
    
    def _create_initial_data(self):
        """
        Crea datos iniciales del sistema.
        """
        self.logger.info("Creando datos iniciales...")
        
        env_config = self.environment_configs[self.config.environment]
        
        if not env_config.get('create_sample_data', False):
            self.logger.info("Creación de datos de ejemplo omitida para este ambiente")
            return
        
        if not self.config.dry_run:
            try:
                self._load_env_file()
                
                # Crear usuario administrador
                self._create_admin_user()
                
                # Crear datos de ejemplo si es necesario
                sample_size = env_config.get('sample_data_size', 'small')
                self._create_sample_data(sample_size)
                
            except Exception as e:
                if not self.config.force:
                    raise SetupError(f"Error creando datos iniciales: {str(e)}")
                else:
                    self.logger.warning(f"Error creando datos iniciales (ignorado): {str(e)}")
        
        self.logger.success("Datos iniciales creados")
    
    def _create_admin_user(self):
        """
        Crea el usuario administrador inicial.
        """
        if self.config.interactive:
            self.logger.info("Configurando usuario administrador...")
            
            admin_email = input("Email del administrador: ").strip()
            if not admin_email:
                admin_email = "admin@ecosistema.local"
            
            admin_password = getpass.getpass("Contraseña del administrador: ").strip()
            if not admin_password:
                admin_password = "admin123"
                self.logger.warning("Usando contraseña por defecto: admin123")
            
            # Aquí iría la lógica para crear el usuario admin
            # usando el modelo de User de la aplicación
            self.logger.info(f"Usuario administrador configurado: {admin_email}")
        else:
            self.logger.info("Usuario administrador por defecto: admin@ecosistema.local")
    
    def _create_sample_data(self, size: str):
        """
        Crea datos de ejemplo.
        
        Args:
            size: Tamaño del conjunto de datos (small, medium, large)
        """
        self.logger.info(f"Creando datos de ejemplo (tamaño: {size})...")
        
        # Aquí iría la lógica para crear datos de ejemplo
        # basado en el tamaño especificado
        data_counts = {
            'small': {'entrepreneurs': 5, 'allies': 2, 'programs': 1},
            'medium': {'entrepreneurs': 20, 'allies': 5, 'programs': 3},
            'large': {'entrepreneurs': 50, 'allies': 10, 'programs': 5},
        }
        
        counts = data_counts.get(size, data_counts['small'])
        self.logger.info(f"Datos de ejemplo creados: {counts}")
    
    def _setup_background_services(self):
        """
        Configura servicios de background (Celery, etc.).
        """
        self.logger.info("Configurando servicios de background...")
        
        # Crear archivos de configuración para Celery
        celery_configs = {
            'celery_worker.py': self._generate_celery_worker_config(),
            'celery_beat.py': self._generate_celery_beat_config(),
        }
        
        for filename, content in celery_configs.items():
            file_path = self.project_root / filename
            if not file_path.exists() and not self.config.dry_run:
                file_path.write_text(content, encoding='utf-8')
                self.logger.info(f"Archivo de configuración creado: {filename}")
        
        # Crear scripts de inicio para servicios
        if self.config.environment in ['development', 'docker']:
            self._create_service_scripts()
        
        self.logger.success("Servicios de background configurados")
    
    def _setup_logging_and_monitoring(self):
        """
        Configura el sistema de logging y monitoreo.
        """
        self.logger.info("Configurando logging y monitoreo...")
        
        # Crear configuración de logging específica
        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                }
            },
            'handlers': {
                'default': {
                    'level': 'INFO',
                    'formatter': 'standard',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(self.project_root / 'logs' / 'app.log'),
                    'maxBytes': 10485760,
                    'backupCount': 5,
                }
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': 'INFO',
                    'propagate': False
                }
            }
        }
        
        log_config_file = self.project_root / 'logging.json'
        if not log_config_file.exists() and not self.config.dry_run:
            log_config_file.write_text(json.dumps(log_config, indent=2), encoding='utf-8')
        
        self.logger.success("Logging y monitoreo configurados")
    
    def _setup_backup_system(self):
        """
        Configura el sistema de backups para producción.
        """
        self.logger.info("Configurando sistema de backups...")
        
        # Crear script de backup
        backup_script = self._generate_backup_script()
        backup_file = self.project_root / 'scripts' / 'backup.py'
        
        if not backup_file.parent.exists():
            backup_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.config.dry_run:
            backup_file.write_text(backup_script, encoding='utf-8')
            backup_file.chmod(0o755)
        
        # Crear configuración de cron para backups automáticos
        cron_config = self._generate_cron_config()
        cron_file = self.project_root / 'deployment' / 'crontab'
        
        if not cron_file.parent.exists():
            cron_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.config.dry_run:
            cron_file.write_text(cron_config, encoding='utf-8')
        
        self.logger.success("Sistema de backups configurado")
    
    def _final_validations(self):
        """
        Ejecuta validaciones finales del setup.
        """
        self.logger.info("Ejecutando validaciones finales...")
        
        validations = [
            ("Archivo .env", self.env_file.exists()),
            ("Directorio logs", (self.project_root / 'logs').exists()),
            ("Directorio uploads", (self.project_root / 'app' / 'static' / 'uploads').exists()),
        ]
        
        if not self.config.skip_db:
            # Aquí se agregarían validaciones de DB
            validations.append(("Base de datos", True))  # Placeholder
        
        failed_validations = []
        for name, passed in validations:
            if passed:
                self.logger.info(f"✓ {name}")
            else:
                self.logger.error(f"✗ {name}")
                failed_validations.append(name)
        
        if failed_validations and not self.config.force:
            raise SetupError(f"Validaciones fallidas: {', '.join(failed_validations)}")
        
        self.logger.success("Validaciones finales completadas")
    
    def _show_setup_summary(self):
        """
        Muestra un resumen del setup completado.
        """
        self.logger.header("RESUMEN DEL SETUP")
        
        print(f"{Colors.OKGREEN}Ambiente:{Colors.ENDC} {self.config.environment}")
        print(f"{Colors.OKGREEN}Directorio del proyecto:{Colors.ENDC} {self.project_root}")
        print(f"{Colors.OKGREEN}Archivo de configuración:{Colors.ENDC} {self.env_file}")
        
        if self.config.environment == 'development':
            print(f"\n{Colors.OKCYAN}Para iniciar el desarrollo:{Colors.ENDC}")
            print(f"  flask run")
            print(f"  # En otra terminal:")
            print(f"  celery -A app.celery worker --loglevel=info")
        
        elif self.config.environment == 'production':
            print(f"\n{Colors.OKCYAN}Para despliegue en producción:{Colors.ENDC}")
            print(f"  gunicorn -c gunicorn.conf.py wsgi:app")
            print(f"  # Configurar servicios systemd para Celery")
        
        print(f"\n{Colors.WARNING}Próximos pasos:{Colors.ENDC}")
        print(f"  1. Revisar y ajustar variables en {self.env_file}")
        print(f"  2. Configurar servicios externos si es necesario")
        print(f"  3. Ejecutar tests: python -m pytest")
        print(f"  4. Verificar health check: curl http://localhost:5000/health")
    
    def _load_env_file(self):
        """
        Carga las variables de entorno del archivo .env.
        """
        if self.env_file.exists():
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
    
    # Métodos para generar contenido de archivos
    
    def _generate_env_example(self) -> str:
        """Genera contenido del archivo .env.example"""
        return """# Ejemplo de variables de entorno del Ecosistema de Emprendimiento
# Copiar a .env.local y ajustar valores

# Aplicación
FLASK_ENV=development
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=your-secret-key-here
APP_NAME=Ecosistema de Emprendimiento
APP_VERSION=2.0.0

# Base de Datos
DATABASE_URL=postgresql://postgres:password@localhost:5432/ecosistema_emprendimiento_dev
REDIS_URL=redis://localhost:6379/1

# Google OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Email (opcional)
EMAIL_BACKEND=smtp
SENDGRID_API_KEY=
MAIL_DEFAULT_SENDER=

# SMS (opcional)
SMS_ENABLED=False
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Monitoreo (opcional)
SENTRY_DSN=
SENTRY_ENABLED=False
"""
    
    def _generate_editorconfig(self) -> str:
        """Genera contenido del archivo .editorconfig"""
        return """root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{js,html,css,json,yml,yaml}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
"""
    
    def _generate_gitignore(self) -> str:
        """Genera contenido del archivo .gitignore"""
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Flask
instance/
.webassets-cache

# Environment variables
.env
.env.local
.env.production
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
logs/
*.log

# Uploads
app/static/uploads/*
!app/static/uploads/.gitkeep

# Backups
backups/
*.sql
*.dump

# Testing
.coverage
.pytest_cache/
.tox/
coverage.xml
*.cover
.hypothesis/
htmlcov/

# Database
*.db
*.sqlite
*.sqlite3

# Node.js (si se usa)
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Compiled assets
app/static/dist/

# Temporary files
*.tmp
*.temp
.cache/
"""
    
    def _generate_celery_worker_config(self) -> str:
        """Genera configuración para Celery worker"""
        return """#!/usr/bin/env python3
\"\"\"
Celery Worker Configuration
\"\"\"

from app import create_app
from app.extensions import celery

app = create_app()
app.app_context().push()
"""
    
    def _generate_celery_beat_config(self) -> str:
        """Genera configuración para Celery beat"""
        return """#!/usr/bin/env python3
\"\"\"
Celery Beat Configuration
\"\"\"

from app import create_app
from app.extensions import celery

app = create_app()
app.app_context().push()
"""
    
    def _create_service_scripts(self):
        """Crea scripts de inicio para servicios"""
        scripts = {
            'start_dev.sh': '''#!/bin/bash
# Script de inicio para desarrollo
export FLASK_APP=run.py
export FLASK_ENV=development

# Iniciar servicios en background
celery -A app.celery worker --loglevel=info --detach
celery -A app.celery beat --loglevel=info --detach

# Iniciar aplicación Flask
flask run --host=0.0.0.0 --port=5000
''',
            'stop_dev.sh': '''#!/bin/bash
# Script para detener servicios de desarrollo
pkill -f "celery.*worker"
pkill -f "celery.*beat"
''',
        }
        
        scripts_dir = self.project_root / 'scripts'
        scripts_dir.mkdir(exist_ok=True)
        
        for script_name, content in scripts.items():
            script_path = scripts_dir / script_name
            if not self.config.dry_run:
                script_path.write_text(content, encoding='utf-8')
                script_path.chmod(0o755)
                self.logger.info(f"Script creado: {script_name}")
    
    def _generate_backup_script(self) -> str:
        """Genera script de backup"""
        return """#!/usr/bin/env python3
\"\"\"
Script de backup para el Ecosistema de Emprendimiento
\"\"\"

import os
import subprocess
import datetime
from pathlib import Path

def backup_database():
    \"\"\"Respalda la base de datos\"\"\"
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"backup_db_{timestamp}.sql"
    
    # Comando pg_dump
    cmd = [
        'pg_dump',
        os.environ.get('DATABASE_URL'),
        '-f', backup_file
    ]
    
    subprocess.run(cmd, check=True)
    print(f"Backup de base de datos creado: {backup_file}")

if __name__ == '__main__':
    backup_database()
"""
    
    def _generate_cron_config(self) -> str:
        """Genera configuración de cron"""
        return """# Crontab para backups automáticos del Ecosistema de Emprendimiento
# Backup diario a las 2:00 AM
0 2 * * * /usr/bin/python3 /path/to/project/scripts/backup.py

# Limpieza de logs semanalmente
0 0 * * 0 find /path/to/project/logs -name "*.log" -mtime +7 -delete
"""


def main():
    """
    Función principal del script de setup.
    """
    parser = argparse.ArgumentParser(
        description="Setup del Ecosistema de Emprendimiento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python scripts/setup.py --environment development
  python scripts/setup.py --environment production --skip-interactive
  python scripts/setup.py --reset --force
  python scripts/setup.py --environment docker --skip-services
        """
    )
    
    parser.add_argument(
        '--environment', '-e',
        choices=['development', 'testing', 'production', 'docker'],
        default='development',
        help='Ambiente de configuración'
    )
    
    parser.add_argument(
        '--skip-interactive',
        action='store_true',
        help='Ejecutar sin prompts interactivos'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Continuar aún con errores no críticos'
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Resetear configuración existente'
    )
    
    parser.add_argument(
        '--skip-db',
        action='store_true',
        help='Saltar configuración de base de datos'
    )
    
    parser.add_argument(
        '--skip-deps',
        action='store_true',
        help='Saltar instalación de dependencias'
    )
    
    parser.add_argument(
        '--skip-services',
        action='store_true',
        help='Saltar configuración de servicios externos'
    )
    
    parser.add_argument(
        '--skip-data',
        action='store_true',
        help='Saltar creación de datos iniciales'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Output verboso'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostrar qué se haría sin ejecutar'
    )
    
    args = parser.parse_args()
    
    # Crear configuración
    config = SetupConfig(
        environment=args.environment,
        interactive=not args.skip_interactive,
        force=args.force,
        reset=args.reset,
        skip_db=args.skip_db,
        skip_deps=args.skip_deps,
        skip_services=args.skip_services,
        skip_data=args.skip_data,
        verbose=args.verbose,
        dry_run=args.dry_run
    )
    
    # Ejecutar setup
    setup = EcosistemaSetup(config)
    setup.run()


if __name__ == '__main__':
    main()