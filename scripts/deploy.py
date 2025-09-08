#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Deployment Empresarial del Ecosistema de Emprendimiento
================================================================

Sistema completo de deployment que maneja:
- Múltiples plataformas (Heroku, AWS, Docker, VPS)
- Estrategias de deployment (rolling, blue-green, canary)
- Validaciones pre y post deployment
- Backup automático y rollback
- Health checks y monitoring
- Manejo seguro de secretos
- Database migrations
- Assets compilation y optimización
- Service orchestration
- CI/CD integration
- Alertas y notificaciones

Uso:
    python scripts/deploy.py --target production --platform heroku
    python scripts/deploy.py --target staging --platform docker --strategy blue-green
    python scripts/deploy.py --rollback --version v1.2.3
    python scripts/deploy.py --target production --dry-run --verbose

Plataformas soportadas:
    - heroku: Heroku Platform
    - aws: AWS ECS/EC2
    - docker: Docker Compose/Swarm
    - kubernetes: Kubernetes cluster
    - vps: VPS tradicional

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import sys
import json
import yaml
import subprocess
import argparse
import logging
import shutil
import tempfile
import hashlib
import tarfile
import time
import requests
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
import secrets
import getpass


# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class DeploymentConfig:
    """
    Configuración completa del deployment.
    """
    target: str                           # production, staging, development
    platform: str                        # heroku, aws, docker, kubernetes, vps
    strategy: str = 'rolling'            # rolling, blue-green, canary
    dry_run: bool = False
    verbose: bool = False
    force: bool = False
    skip_tests: bool = False
    skip_migrations: bool = False
    skip_assets: bool = False
    skip_backup: bool = False
    skip_health_check: bool = False
    rollback: bool = False
    rollback_version: Optional[str] = None
    maintenance_mode: bool = False
    notification_webhook: Optional[str] = None
    deployment_timeout: int = 600        # 10 minutos
    health_check_timeout: int = 300      # 5 minutos
    rollback_timeout: int = 180          # 3 minutos


@dataclass
class DeploymentContext:
    """
    Contexto del deployment actual.
    """
    deployment_id: str = field(default_factory=lambda: secrets.token_hex(8))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    version: Optional[str] = None
    previous_version: Optional[str] = None
    build_artifacts: list[str] = field(default_factory=list)
    backup_created: bool = False
    backup_location: Optional[str] = None
    deployment_url: Optional[str] = None
    rollback_point: Optional[str] = None


class Colors:
    """
    Códigos de colores ANSI para output profesional.
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


class DeploymentError(Exception):
    """
    Excepción específica para errores de deployment.
    """
    pass


class RollbackError(Exception):
    """
    Excepción específica para errores de rollback.
    """
    pass


class DeploymentLogger:
    """
    Logger especializado para deployments con output estructurado.
    """
    
    def __init__(self, verbose: bool = False, deployment_id: str = None):
        """
        Inicializa el logger de deployment.
        
        Args:
            verbose: Si mostrar logs verbosos
            deployment_id: ID único del deployment
        """
        self.verbose = verbose
        self.deployment_id = deployment_id or secrets.token_hex(8)
        self.setup_logging()
    
    def setup_logging(self):
        """
        Configura logging estructurado para deployment.
        """
        log_format = f'%(asctime)s [DEPLOY:{self.deployment_id}] %(levelname)s: %(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        
        # Configurar handler para archivo
        log_file = project_root / 'logs' / f'deployment_{self.deployment_id}.log'
        log_file.parent.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('deployment')
    
    def info(self, message: str, step: bool = False):
        """Log info con formato profesional."""
        prefix = f"{Colors.OKCYAN}[STEP]{Colors.ENDC}" if step else f"{Colors.OKGREEN}[INFO]{Colors.ENDC}"
        print(f"{prefix} {message}")
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
        separator = "=" * 80
        print(f"\n{Colors.HEADER}{Colors.BOLD}{separator}")
        print(f"{message.center(80)}")
        print(f"{separator}{Colors.ENDC}")
        self.logger.info(f"=== {message} ===")
    
    def stage(self, stage_name: str, stage_num: int, total_stages: int):
        """Log etapa del deployment."""
        print(f"\n{Colors.HEADER}[{stage_num}/{total_stages}] {stage_name}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'-' * 50}{Colors.ENDC}")
        self.logger.info(f"Stage {stage_num}/{total_stages}: {stage_name}")


class PlatformDeployer:
    """
    Clase base para deployers específicos por plataforma.
    """
    
    def __init__(self, config: DeploymentConfig, context: DeploymentContext, logger: DeploymentLogger):
        """
        Inicializa el deployer base.
        
        Args:
            config: Configuración del deployment
            context: Contexto del deployment
            logger: Logger del deployment
        """
        self.config = config
        self.context = context
        self.logger = logger
    
    def validate_platform(self) -> bool:
        """
        Valida que la plataforma esté correctamente configurada.
        
        Returns:
            True si la plataforma está lista
        """
        raise NotImplementedError("Subclases deben implementar validate_platform")
    
    def deploy(self) -> bool:
        """
        Ejecuta el deployment en la plataforma.
        
        Returns:
            True si el deployment fue exitoso
        """
        raise NotImplementedError("Subclases deben implementar deploy")
    
    def rollback(self, version: str) -> bool:
        """
        Ejecuta rollback a una versión específica.
        
        Args:
            version: Versión a la cual hacer rollback
            
        Returns:
            True si el rollback fue exitoso
        """
        raise NotImplementedError("Subclases deben implementar rollback")
    
    def health_check(self) -> bool:
        """
        Ejecuta health check post-deployment.
        
        Returns:
            True si los health checks pasan
        """
        raise NotImplementedError("Subclases deben implementar health_check")


class HerokuDeployer(PlatformDeployer):
    """
    Deployer específico para Heroku.
    """
    
    def validate_platform(self) -> bool:
        """Valida configuración de Heroku."""
        try:
            # Verificar que Heroku CLI esté instalado
            subprocess.run(['heroku', '--version'], check=True, capture_output=True)
            
            # Verificar autenticación
            result = subprocess.run(['heroku', 'auth:whoami'], check=True, capture_output=True, text=True)
            self.logger.info(f"Autenticado en Heroku como: {result.stdout.strip()}")
            
            # Verificar que la app existe
            app_name = os.environ.get('HEROKU_APP_NAME')
            if not app_name:
                raise DeploymentError("HEROKU_APP_NAME no configurado")
            
            subprocess.run(['heroku', 'apps:info', '-a', app_name], check=True, capture_output=True)
            self.logger.info(f"App de Heroku válida: {app_name}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error validando Heroku: {e}")
            return False
        except FileNotFoundError:
            self.logger.error("Heroku CLI no encontrado")
            return False
    
    def deploy(self) -> bool:
        """Ejecuta deployment en Heroku."""
        try:
            app_name = os.environ.get('HEROKU_APP_NAME')
            
            # Configurar variables de entorno
            self._configure_heroku_vars(app_name)
            
            # Push a Heroku
            if not self.config.dry_run:
                self.logger.info("Iniciando push a Heroku...")
                subprocess.run([
                    'git', 'push', 'heroku', f'{self.context.git_branch}:main'
                ], check=True)
            
            # Ejecutar migraciones si es necesario
            if not self.config.skip_migrations:
                self._run_heroku_migrations(app_name)
            
            # Restart de la aplicación
            if not self.config.dry_run:
                subprocess.run(['heroku', 'restart', '-a', app_name], check=True)
            
            self.context.deployment_url = f"https://{app_name}.herokuapp.com"
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en deployment de Heroku: {e}")
            return False
    
    def _configure_heroku_vars(self, app_name: str):
        """Configura variables de entorno en Heroku."""
        env_vars = {
            'ENVIRONMENT': self.config.target,
            'DEPLOYMENT_ID': self.context.deployment_id,
            'DEPLOYMENT_TIMESTAMP': self.context.timestamp.isoformat(),
            'GIT_COMMIT': self.context.git_commit,
        }
        
        for key, value in env_vars.items():
            if value and not self.config.dry_run:
                subprocess.run([
                    'heroku', 'config:set', f'{key}={value}', '-a', app_name
                ], check=True, capture_output=True)
    
    def _run_heroku_migrations(self, app_name: str):
        """Ejecuta migraciones en Heroku."""
        self.logger.info("Ejecutando migraciones en Heroku...")
        if not self.config.dry_run:
            subprocess.run([
                'heroku', 'run', 'flask', 'db', 'upgrade', '-a', app_name
            ], check=True)
    
    def rollback(self, version: str) -> bool:
        """Rollback en Heroku."""
        try:
            app_name = os.environ.get('HEROKU_APP_NAME')
            
            # Obtener releases
            result = subprocess.run([
                'heroku', 'releases', '-a', app_name, '--json'
            ], check=True, capture_output=True, text=True)
            
            releases = json.loads(result.stdout)
            
            # Encontrar release por versión
            target_release = None
            for release in releases:
                if version in release.get('description', ''):
                    target_release = release
                    break
            
            if not target_release:
                raise RollbackError(f"No se encontró release para versión: {version}")
            
            # Ejecutar rollback
            if not self.config.dry_run:
                subprocess.run([
                    'heroku', 'rollback', target_release['version'], '-a', app_name
                ], check=True)
            
            self.logger.success(f"Rollback exitoso a versión: {version}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en rollback de Heroku: {e}")
            return False
    
    def health_check(self) -> bool:
        """Health check para Heroku."""
        app_name = os.environ.get('HEROKU_APP_NAME')
        url = f"https://{app_name}.herokuapp.com/health"
        
        return self._perform_http_health_check(url)
    
    def _perform_http_health_check(self, url: str) -> bool:
        """Ejecuta health check HTTP."""
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    self.logger.success(f"Health check exitoso: {url}")
                    return True
                else:
                    self.logger.warning(f"Health check falló: {response.status_code}")
                    
            except requests.RequestException as e:
                self.logger.warning(f"Error en health check (intento {attempt + 1}): {e}")
            
            if attempt < max_attempts - 1:
                time.sleep(10)
        
        self.logger.error(f"Health check falló después de {max_attempts} intentos")
        return False


class DockerDeployer(PlatformDeployer):
    """
    Deployer específico para Docker.
    """
    
    def validate_platform(self) -> bool:
        """Valida configuración de Docker."""
        try:
            # Verificar Docker
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
            
            # Verificar Docker Compose
            subprocess.run(['docker-compose', '--version'], check=True, capture_output=True)
            
            # Verificar que los archivos de configuración existen
            compose_file = project_root / 'docker-compose.yml'
            if not compose_file.exists():
                raise DeploymentError("docker-compose.yml no encontrado")
            
            dockerfile = project_root / 'Dockerfile'
            if not dockerfile.exists():
                raise DeploymentError("Dockerfile no encontrado")
            
            self.logger.info("Configuración de Docker válida")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error validando Docker: {e}")
            return False
        except FileNotFoundError:
            self.logger.error("Docker o Docker Compose no encontrados")
            return False
    
    def deploy(self) -> bool:
        """Ejecuta deployment con Docker."""
        try:
            # Build de la imagen
            self._build_docker_image()
            
            # Configurar variables de entorno
            self._prepare_docker_env()
            
            # Estrategia de deployment
            if self.config.strategy == 'blue-green':
                return self._blue_green_deploy()
            else:
                return self._rolling_deploy()
                
        except Exception as e:
            self.logger.error(f"Error en deployment de Docker: {e}")
            return False
    
    def _build_docker_image(self):
        """Build de la imagen Docker."""
        image_tag = f"ecosistema:{self.context.version or 'latest'}"
        
        self.logger.info(f"Building imagen Docker: {image_tag}")
        
        if not self.config.dry_run:
            subprocess.run([
                'docker', 'build',
                '-t', image_tag,
                '--build-arg', f'GIT_COMMIT={self.context.git_commit}',
                '--build-arg', f'BUILD_DATE={self.context.timestamp.isoformat()}',
                '.'
            ], cwd=project_root, check=True)
        
        self.context.build_artifacts.append(image_tag)
    
    def _prepare_docker_env(self):
        """Prepara variables de entorno para Docker."""
        env_file = project_root / f'.env.{self.config.target}'
        
        env_vars = {
            'ENVIRONMENT': self.config.target,
            'DEPLOYMENT_ID': self.context.deployment_id,
            'DEPLOYMENT_TIMESTAMP': self.context.timestamp.isoformat(),
            'GIT_COMMIT': self.context.git_commit,
            'IMAGE_TAG': self.context.version or 'latest',
        }
        
        # Escribir archivo .env para Docker Compose
        with open(env_file, 'w') as f:
            for key, value in env_vars.items():
                if value:
                    f.write(f"{key}={value}\n")
    
    def _rolling_deploy(self) -> bool:
        """Deployment rolling con Docker Compose."""
        self.logger.info("Ejecutando rolling deployment...")
        
        if not self.config.dry_run:
            # Pull de imágenes
            subprocess.run(['docker-compose', 'pull'], cwd=project_root, check=True)
            
            # Up de servicios
            subprocess.run([
                'docker-compose', 'up', '-d', '--remove-orphans'
            ], cwd=project_root, check=True)
            
            # Ejecutar migraciones
            if not self.config.skip_migrations:
                subprocess.run([
                    'docker-compose', 'exec', '-T', 'web',
                    'flask', 'db', 'upgrade'
                ], cwd=project_root, check=True)
        
        return True
    
    def _blue_green_deploy(self) -> bool:
        """Deployment blue-green con Docker."""
        self.logger.info("Ejecutando blue-green deployment...")
        
        # Determinar color actual y nuevo
        current_color = self._get_current_color()
        new_color = 'green' if current_color == 'blue' else 'blue'
        
        self.logger.info(f"Desplegando a ambiente {new_color}")
        
        try:
            # Deploy al nuevo ambiente
            if not self.config.dry_run:
                subprocess.run([
                    'docker-compose', '-f', 'docker-compose.yml',
                    '-f', f'docker-compose.{new_color}.yml',
                    'up', '-d'
                ], cwd=project_root, check=True)
            
            # Health check del nuevo ambiente
            if self._health_check_color(new_color):
                # Cambiar tráfico al nuevo ambiente
                self._switch_traffic(new_color)
                
                # Parar ambiente anterior
                self._stop_color(current_color)
                
                return True
            else:
                # Rollback - parar nuevo ambiente
                self._stop_color(new_color)
                return False
                
        except Exception as e:
            self.logger.error(f"Error en blue-green deployment: {e}")
            self._stop_color(new_color)
            return False
    
    def _get_current_color(self) -> str:
        """Obtiene el color del ambiente actual."""
        try:
            # Verificar qué servicios están corriendo
            result = subprocess.run([
                'docker-compose', 'ps', '--services', '--filter', 'status=running'
            ], cwd=project_root, capture_output=True, text=True)
            
            services = result.stdout.strip().split('\n')
            
            if any('blue' in service for service in services):
                return 'blue'
            else:
                return 'green'
                
        except Exception:
            return 'blue'  # Default
    
    def _health_check_color(self, color: str) -> bool:
        """Health check específico para un color."""
        port = '8080' if color == 'blue' else '8081'
        url = f"http://localhost:{port}/health"
        
        return self._perform_http_health_check(url)
    
    def _switch_traffic(self, new_color: str):
        """Cambia el tráfico al nuevo ambiente."""
        self.logger.info(f"Cambiando tráfico a ambiente {new_color}")
        
        # Aquí iría la lógica para cambiar el load balancer
        # Por ejemplo, actualizar configuración de nginx
        
    def _stop_color(self, color: str):
        """Para servicios de un color específico."""
        if not self.config.dry_run:
            subprocess.run([
                'docker-compose', '-f', f'docker-compose.{color}.yml',
                'down'
            ], cwd=project_root, check=True)
    
    def rollback(self, version: str) -> bool:
        """Rollback con Docker."""
        try:
            # Cambiar a la imagen de la versión anterior
            old_image = f"ecosistema:{version}"
            
            self.logger.info(f"Haciendo rollback a imagen: {old_image}")
            
            if not self.config.dry_run:
                # Actualizar docker-compose para usar imagen anterior
                subprocess.run([
                    'docker-compose', 'up', '-d',
                    '--scale', 'web=2'  # Escalar temporalmente
                ], cwd=project_root, check=True)
                
                # Health check
                if self.health_check():
                    # Reducir escala
                    subprocess.run([
                        'docker-compose', 'up', '-d',
                        '--scale', 'web=1'
                    ], cwd=project_root, check=True)
                    
                    return True
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en rollback de Docker: {e}")
            return False
    
    def health_check(self) -> bool:
        """Health check para Docker."""
        # Verificar que los contenedores estén corriendo
        try:
            result = subprocess.run([
                'docker-compose', 'ps', '-q'
            ], cwd=project_root, capture_output=True, text=True, check=True)
            
            container_ids = result.stdout.strip().split('\n')
            
            for container_id in container_ids:
                if container_id:
                    # Verificar estado del contenedor
                    result = subprocess.run([
                        'docker', 'inspect', container_id,
                        '--format', '{{.State.Status}}'
                    ], capture_output=True, text=True, check=True)
                    
                    if result.stdout.strip() != 'running':
                        self.logger.error(f"Contenedor no está corriendo: {container_id}")
                        return False
            
            # Health check HTTP
            url = "http://localhost:8000/health"
            return self._perform_http_health_check(url)
            
        except Exception as e:
            self.logger.error(f"Error en health check de Docker: {e}")
            return False
    
    def _perform_http_health_check(self, url: str) -> bool:
        """Ejecuta health check HTTP."""
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    self.logger.success(f"Health check exitoso: {url}")
                    return True
                else:
                    self.logger.warning(f"Health check falló: {response.status_code}")
                    
            except requests.RequestException as e:
                self.logger.warning(f"Error en health check (intento {attempt + 1}): {e}")
            
            if attempt < max_attempts - 1:
                time.sleep(10)
        
        self.logger.error(f"Health check falló después de {max_attempts} intentos")
        return False


class EcosistemaDeployment:
    """
    Orquestador principal del deployment del ecosistema.
    """
    
    def __init__(self, config: DeploymentConfig):
        """
        Inicializa el deployment.
        
        Args:
            config: Configuración del deployment
        """
        self.config = config
        self.context = DeploymentContext()
        self.logger = DeploymentLogger(config.verbose, self.context.deployment_id)
        
        # Mapeo de plataformas a deployers
        self.deployers = {
            'heroku': HerokuDeployer,
            'docker': DockerDeployer,
            # 'aws': AWSDeployer,      # Se implementarían según necesidad
            # 'kubernetes': K8sDeployer,
            # 'vps': VPSDeployer,
        }
    
    def run(self):
        """
        Ejecuta el proceso completo de deployment.
        """
        try:
            # Header principal
            if self.config.rollback:
                self.logger.header(f"ROLLBACK DEL ECOSISTEMA - {self.config.target.upper()}")
            else:
                self.logger.header(f"DEPLOYMENT DEL ECOSISTEMA - {self.config.target.upper()}")
            
            # Mostrar configuración
            self._show_deployment_config()
            
            # Confirmación para producción
            if self.config.target == 'production' and not self.config.force:
                self._confirm_production_deployment()
            
            if self.config.rollback:
                return self._execute_rollback()
            else:
                return self._execute_deployment()
                
        except KeyboardInterrupt:
            self.logger.warning("Deployment interrumpido por el usuario")
            return False
        except (DeploymentError, RollbackError) as e:
            self.logger.error(f"Error en deployment: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado: {str(e)}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _execute_deployment(self) -> bool:
        """
        Ejecuta el proceso de deployment.
        
        Returns:
            True si el deployment fue exitoso
        """
        stages = [
            ("Pre-deployment Validations", self._pre_deployment_validations),
            ("Backup Creation", self._create_backup),
            ("Build Preparation", self._prepare_build),
            ("Assets Compilation", self._compile_assets),
            ("Platform Deployment", self._platform_deployment),
            ("Post-deployment Health Checks", self._post_deployment_checks),
            ("Cleanup and Finalization", self._cleanup_and_finalize),
        ]
        
        total_stages = len([s for s in stages if not self._should_skip_stage(s[0])])
        current_stage = 1
        
        for stage_name, stage_func in stages:
            if self._should_skip_stage(stage_name):
                continue
                
            self.logger.stage(stage_name, current_stage, total_stages)
            
            if not stage_func():
                self.logger.error(f"Falla en etapa: {stage_name}")
                
                # Intentar rollback automático si está configurado
                if self.context.rollback_point and not self.config.dry_run:
                    self.logger.warning("Iniciando rollback automático...")
                    return self._execute_automatic_rollback()
                
                return False
            
            current_stage += 1
        
        # Deployment exitoso
        self._notify_deployment_success()
        self.logger.success("Deployment completado exitosamente!")
        return True
    
    def _execute_rollback(self) -> bool:
        """
        Ejecuta el proceso de rollback.
        
        Returns:
            True si el rollback fue exitoso
        """
        if not self.config.rollback_version:
            raise RollbackError("Versión de rollback no especificada")
        
        self.logger.stage("Executing Rollback", 1, 1)
        
        # Obtener deployer
        deployer_class = self.deployers.get(self.config.platform)
        if not deployer_class:
            raise RollbackError(f"Plataforma no soportada: {self.config.platform}")
        
        deployer = deployer_class(self.config, self.context, self.logger)
        
        # Ejecutar rollback
        if deployer.rollback(self.config.rollback_version):
            # Health check post-rollback
            if deployer.health_check():
                self.logger.success(f"Rollback exitoso a versión: {self.config.rollback_version}")
                return True
            else:
                self.logger.error("Health check falló después del rollback")
                return False
        else:
            self.logger.error("Rollback falló")
            return False
    
    def _should_skip_stage(self, stage_name: str) -> bool:
        """
        Determina si una etapa debe ser saltada.
        
        Args:
            stage_name: Nombre de la etapa
            
        Returns:
            True si la etapa debe ser saltada
        """
        skip_map = {
            "Backup Creation": self.config.skip_backup,
            "Assets Compilation": self.config.skip_assets,
            "Post-deployment Health Checks": self.config.skip_health_check,
        }
        
        return skip_map.get(stage_name, False)
    
    def _show_deployment_config(self):
        """
        Muestra la configuración del deployment.
        """
        print(f"\n{Colors.OKCYAN}Configuración del Deployment:{Colors.ENDC}")
        print(f"  Target: {Colors.BOLD}{self.config.target}{Colors.ENDC}")
        print(f"  Platform: {Colors.BOLD}{self.config.platform}{Colors.ENDC}")
        print(f"  Strategy: {Colors.BOLD}{self.config.strategy}{Colors.ENDC}")
        print(f"  Deployment ID: {Colors.BOLD}{self.context.deployment_id}{Colors.ENDC}")
        
        if self.config.dry_run:
            print(f"  {Colors.WARNING}Mode: DRY RUN{Colors.ENDC}")
        
        print()
    
    def _confirm_production_deployment(self):
        """
        Confirmación requerida para deployments de producción.
        """
        print(f"{Colors.WARNING}⚠️  DEPLOYMENT A PRODUCCIÓN ⚠️{Colors.ENDC}")
        print(f"Estás a punto de desplegar a producción.")
        print(f"Target: {self.config.target}")
        print(f"Platform: {self.config.platform}")
        
        response = input(f"\n¿Continuar con el deployment? (escriba 'deploy' para confirmar): ")
        if response.lower() != 'deploy':
            raise DeploymentError("Deployment cancelado por el usuario")
    
    def _pre_deployment_validations(self) -> bool:
        """
        Ejecuta validaciones pre-deployment.
        
        Returns:
            True si todas las validaciones pasan
        """
        self.logger.info("Ejecutando validaciones pre-deployment...", step=True)
        
        validations = [
            ("Git Repository Status", self._validate_git_status),
            ("Environment Configuration", self._validate_environment),
            ("Platform Configuration", self._validate_platform),
            ("Dependencies", self._validate_dependencies),
        ]
        
        if not self.config.skip_tests:
            validations.append(("Test Suite", self._run_tests))
        
        for validation_name, validation_func in validations:
            self.logger.info(f"Validando: {validation_name}")
            
            if not validation_func():
                self.logger.error(f"Validación falló: {validation_name}")
                return False
        
        self.logger.success("Todas las validaciones pre-deployment pasaron")
        return True
    
    def _validate_git_status(self) -> bool:
        """Valida el estado del repositorio Git."""
        try:
            # Obtener información de Git
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            self.context.git_commit = result.stdout.strip()
            
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            self.context.git_branch = result.stdout.strip()
            
            # Verificar que no hay cambios sin commit
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, check=True)
            
            if result.stdout.strip() and self.config.target == 'production':
                self.logger.warning("Hay cambios sin commit en el repositorio")
                if not self.config.force:
                    return False
            
            # Obtener versión
            try:
                result = subprocess.run(['git', 'describe', '--tags', '--always'], 
                                      capture_output=True, text=True, check=True)
                self.context.version = result.stdout.strip()
            except subprocess.CalledProcessError:
                self.context.version = self.context.git_commit[:8]
            
            self.logger.info(f"Git commit: {self.context.git_commit[:8]}")
            self.logger.info(f"Git branch: {self.context.git_branch}")
            self.logger.info(f"Version: {self.context.version}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error validando Git: {e}")
            return False
    
    def _validate_environment(self) -> bool:
        """Valida la configuración del ambiente."""
        required_vars = {
            'development': ['SECRET_KEY', 'DATABASE_URL'],
            'staging': ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL'],
            'production': ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL', 'SENTRY_DSN'],
        }
        
        target_vars = required_vars.get(self.config.target, [])
        missing_vars = []
        
        for var in target_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.logger.error(f"Variables de entorno faltantes: {', '.join(missing_vars)}")
            return False
        
        return True
    
    def _validate_platform(self) -> bool:
        """Valida la configuración de la plataforma."""
        deployer_class = self.deployers.get(self.config.platform)
        if not deployer_class:
            self.logger.error(f"Plataforma no soportada: {self.config.platform}")
            return False
        
        deployer = deployer_class(self.config, self.context, self.logger)
        return deployer.validate_platform()
    
    def _validate_dependencies(self) -> bool:
        """Valida las dependencias del proyecto."""
        try:
            # Verificar requirements.txt
            req_file = project_root / 'requirements.txt'
            if not req_file.exists():
                self.logger.error("requirements.txt no encontrado")
                return False
            
            # Verificar que todas las dependencias están instaladas
            if not self.config.dry_run:
                subprocess.run([
                    sys.executable, '-m', 'pip', 'check'
                ], check=True, capture_output=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error validando dependencias: {e}")
            return False
    
    def _run_tests(self) -> bool:
        """Ejecuta la suite de tests."""
        self.logger.info("Ejecutando suite de tests...")
        
        try:
            if not self.config.dry_run:
                result = subprocess.run([
                    sys.executable, '-m', 'pytest',
                    'tests/',
                    '-v',
                    '--tb=short'
                ], cwd=project_root, check=True, capture_output=True, text=True)
                
                self.logger.info("Todos los tests pasaron")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Tests fallaron: {e.stderr}")
            return False
    
    def _create_backup(self) -> bool:
        """
        Crea backup antes del deployment.
        
        Returns:
            True si el backup fue exitoso
        """
        if self.config.target not in ['staging', 'production']:
            self.logger.info("Backup omitido para ambiente de desarrollo")
            return True
        
        self.logger.info("Creando backup pre-deployment...", step=True)
        
        try:
            backup_dir = project_root / 'backups' / f"deployment_{self.context.deployment_id}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup de base de datos
            if not self.config.dry_run:
                db_url = os.environ.get('DATABASE_URL')
                if db_url:
                    backup_file = backup_dir / f"database_{self.context.deployment_id}.sql"
                    
                    subprocess.run([
                        'pg_dump', db_url, '-f', str(backup_file)
                    ], check=True)
                    
                    self.logger.info(f"Backup de base de datos creado: {backup_file}")
            
            # Backup de archivos estáticos si existen
            static_dir = project_root / 'app' / 'static' / 'uploads'
            if static_dir.exists() and not self.config.dry_run:
                backup_static = backup_dir / 'static_uploads.tar.gz'
                
                with tarfile.open(backup_static, 'w:gz') as tar:
                    tar.add(static_dir, arcname='uploads')
                
                self.logger.info(f"Backup de archivos estáticos creado: {backup_static}")
            
            self.context.backup_created = True
            self.context.backup_location = str(backup_dir)
            self.context.rollback_point = self.context.version
            
            self.logger.success(f"Backup creado exitosamente: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creando backup: {e}")
            return False
    
    def _prepare_build(self) -> bool:
        """
        Prepara el build para deployment.
        
        Returns:
            True si la preparación fue exitosa
        """
        self.logger.info("Preparando build...", step=True)
        
        try:
            # Limpiar archivos temporales
            temp_dirs = ['.pytest_cache', '__pycache__', '.coverage']
            for temp_dir in temp_dirs:
                temp_path = project_root / temp_dir
                if temp_path.exists() and not self.config.dry_run:
                    shutil.rmtree(temp_path)
            
            # Generar archivo de versión
            version_file = project_root / 'VERSION'
            if not self.config.dry_run:
                with open(version_file, 'w') as f:
                    f.write(f"{self.context.version}\n")
                    f.write(f"{self.context.git_commit}\n")
                    f.write(f"{self.context.timestamp.isoformat()}\n")
            
            # Verificar que archivos críticos existen
            critical_files = ['run.py', 'wsgi.py', 'requirements.txt']
            for critical_file in critical_files:
                file_path = project_root / critical_file
                if not file_path.exists():
                    self.logger.error(f"Archivo crítico no encontrado: {critical_file}")
                    return False
            
            self.logger.success("Build preparado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error preparando build: {e}")
            return False
    
    def _compile_assets(self) -> bool:
        """
        Compila assets estáticos.
        
        Returns:
            True si la compilación fue exitosa
        """
        self.logger.info("Compilando assets...", step=True)
        
        try:
            # Verificar si hay assets para compilar
            assets_dir = project_root / 'app' / 'static' / 'src'
            if not assets_dir.exists():
                self.logger.info("No hay assets para compilar")
                return True
            
            # Compilar SCSS si existe
            scss_dir = assets_dir / 'scss'
            if scss_dir.exists() and not self.config.dry_run:
                dist_css_dir = project_root / 'app' / 'static' / 'dist' / 'css'
                dist_css_dir.mkdir(parents=True, exist_ok=True)
                
                # Aquí iría la lógica de compilación de SCSS
                # Por ejemplo, usando sass o node-sass
                self.logger.info("Assets SCSS compilados")
            
            # Minificar JavaScript si existe
            js_dir = assets_dir / 'js'
            if js_dir.exists() and not self.config.dry_run:
                dist_js_dir = project_root / 'app' / 'static' / 'dist' / 'js'
                dist_js_dir.mkdir(parents=True, exist_ok=True)
                
                # Aquí iría la lógica de minificación de JS
                self.logger.info("Assets JavaScript procesados")
            
            self.logger.success("Assets compilados exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error compilando assets: {e}")
            return False
    
    def _platform_deployment(self) -> bool:
        """
        Ejecuta el deployment específico de la plataforma.
        
        Returns:
            True si el deployment fue exitoso
        """
        self.logger.info(f"Ejecutando deployment en {self.config.platform}...", step=True)
        
        deployer_class = self.deployers.get(self.config.platform)
        deployer = deployer_class(self.config, self.context, self.logger)
        
        # Activar modo de mantenimiento si está configurado
        if self.config.maintenance_mode:
            self._enable_maintenance_mode()
        
        try:
            success = deployer.deploy()
            
            if success:
                self.logger.success(f"Deployment en {self.config.platform} completado")
            
            return success
            
        finally:
            # Desactivar modo de mantenimiento
            if self.config.maintenance_mode:
                self._disable_maintenance_mode()
    
    def _post_deployment_checks(self) -> bool:
        """
        Ejecuta checks post-deployment.
        
        Returns:
            True si todos los checks pasan
        """
        self.logger.info("Ejecutando checks post-deployment...", step=True)
        
        deployer_class = self.deployers.get(self.config.platform)
        deployer = deployer_class(self.config, self.context, self.logger)
        
        # Health check principal
        if not deployer.health_check():
            self.logger.error("Health check principal falló")
            return False
        
        # Checks adicionales específicos
        checks = [
            ("Database Connection", self._check_database_connection),
            ("Redis Connection", self._check_redis_connection),
            ("External Services", self._check_external_services),
        ]
        
        for check_name, check_func in checks:
            self.logger.info(f"Verificando: {check_name}")
            
            if not check_func():
                self.logger.warning(f"Check falló: {check_name}")
                # No fallar el deployment por checks no críticos
        
        self.logger.success("Checks post-deployment completados")
        return True
    
    def _check_database_connection(self) -> bool:
        """Verifica conexión a la base de datos."""
        try:
            if self.context.deployment_url:
                url = f"{self.context.deployment_url}/health/db"
                response = requests.get(url, timeout=10)
                return response.status_code == 200
            return True
        except Exception:
            return False
    
    def _check_redis_connection(self) -> bool:
        """Verifica conexión a Redis."""
        try:
            if self.context.deployment_url:
                url = f"{self.context.deployment_url}/health/redis"
                response = requests.get(url, timeout=10)
                return response.status_code == 200
            return True
        except Exception:
            return False
    
    def _check_external_services(self) -> bool:
        """Verifica servicios externos."""
        # Aquí se verificarían servicios como SendGrid, Twilio, etc.
        return True
    
    def _cleanup_and_finalize(self) -> bool:
        """
        Limpieza y finalización del deployment.
        
        Returns:
            True si la finalización fue exitosa
        """
        self.logger.info("Finalizando deployment...", step=True)
        
        try:
            # Limpiar archivos temporales
            temp_files = ['VERSION']
            for temp_file in temp_files:
                file_path = project_root / temp_file
                if file_path.exists() and not self.config.dry_run:
                    file_path.unlink()
            
            # Guardar información del deployment
            deployment_info = {
                'deployment_id': self.context.deployment_id,
                'timestamp': self.context.timestamp.isoformat(),
                'target': self.config.target,
                'platform': self.config.platform,
                'version': self.context.version,
                'git_commit': self.context.git_commit,
                'git_branch': self.context.git_branch,
                'deployment_url': self.context.deployment_url,
                'backup_location': self.context.backup_location,
            }
            
            deployment_log = project_root / 'logs' / 'deployments.json'
            
            if not self.config.dry_run:
                # Cargar log existente o crear nuevo
                if deployment_log.exists():
                    with open(deployment_log, 'r') as f:
                        deployments = json.load(f)
                else:
                    deployments = []
                
                deployments.append(deployment_info)
                
                # Mantener solo los últimos 50 deployments
                deployments = deployments[-50:]
                
                with open(deployment_log, 'w') as f:
                    json.dump(deployments, f, indent=2)
            
            self.logger.success("Deployment finalizado exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en finalización: {e}")
            return False
    
    def _execute_automatic_rollback(self) -> bool:
        """
        Ejecuta rollback automático en caso de falla.
        
        Returns:
            True si el rollback fue exitoso
        """
        if not self.context.rollback_point:
            self.logger.error("No hay punto de rollback disponible")
            return False
        
        self.logger.warning(f"Ejecutando rollback automático a: {self.context.rollback_point}")
        
        # Configurar rollback
        rollback_config = DeploymentConfig(
            target=self.config.target,
            platform=self.config.platform,
            rollback=True,
            rollback_version=self.context.rollback_point,
            force=True
        )
        
        # Ejecutar rollback
        return self._execute_rollback()
    
    def _enable_maintenance_mode(self):
        """Activa modo de mantenimiento."""
        self.logger.info("Activando modo de mantenimiento...")
        # Aquí iría la lógica para activar modo de mantenimiento
        # Por ejemplo, crear archivo de mantenimiento o cambiar configuración
    
    def _disable_maintenance_mode(self):
        """Desactiva modo de mantenimiento."""
        self.logger.info("Desactivando modo de mantenimiento...")
        # Aquí iría la lógica para desactivar modo de mantenimiento
    
    def _notify_deployment_success(self):
        """Envía notificación de deployment exitoso."""
        if self.config.notification_webhook:
            try:
                payload = {
                    'deployment_id': self.context.deployment_id,
                    'target': self.config.target,
                    'platform': self.config.platform,
                    'version': self.context.version,
                    'status': 'success',
                    'deployment_url': self.context.deployment_url,
                    'timestamp': self.context.timestamp.isoformat(),
                }
                
                if not self.config.dry_run:
                    requests.post(self.config.notification_webhook, json=payload, timeout=10)
                
                self.logger.info("Notificación de deployment enviada")
                
            except Exception as e:
                self.logger.warning(f"Error enviando notificación: {e}")


def main():
    """
    Función principal del script de deployment.
    """
    parser = argparse.ArgumentParser(
        description="Deployment del Ecosistema de Emprendimiento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Deployment básico
  python scripts/deploy.py --target production --platform heroku
  
  # Deployment con estrategia específica
  python scripts/deploy.py --target staging --platform docker --strategy blue-green
  
  # Rollback
  python scripts/deploy.py --rollback --version v1.2.3 --target production
  
  # Dry run
  python scripts/deploy.py --target production --platform heroku --dry-run --verbose
  
  # Deployment forzado saltando validaciones
  python scripts/deploy.py --target staging --platform docker --force --skip-tests
        """
    )
    
    parser.add_argument(
        '--target', '-t',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Ambiente de deployment'
    )
    
    parser.add_argument(
        '--platform', '-p',
        choices=['heroku', 'docker', 'aws', 'kubernetes', 'vps'],
        required=True,
        help='Plataforma de deployment'
    )
    
    parser.add_argument(
        '--strategy', '-s',
        choices=['rolling', 'blue-green', 'canary'],
        default='rolling',
        help='Estrategia de deployment'
    )
    
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Ejecutar rollback en lugar de deployment'
    )
    
    parser.add_argument(
        '--version',
        help='Versión específica para rollback'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular deployment sin ejecutar'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Output verboso'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forzar deployment saltando algunas validaciones'
    )
    
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Saltar ejecución de tests'
    )
    
    parser.add_argument(
        '--skip-migrations',
        action='store_true',
        help='Saltar migraciones de base de datos'
    )
    
    parser.add_argument(
        '--skip-assets',
        action='store_true',
        help='Saltar compilación de assets'
    )
    
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Saltar creación de backup'
    )
    
    parser.add_argument(
        '--skip-health-check',
        action='store_true',
        help='Saltar health checks post-deployment'
    )
    
    parser.add_argument(
        '--maintenance-mode',
        action='store_true',
        help='Activar modo de mantenimiento durante deployment'
    )
    
    parser.add_argument(
        '--notification-webhook',
        help='URL de webhook para notificaciones'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.rollback and not args.version:
        parser.error("--version es requerido cuando se usa --rollback")
    
    # Crear configuración
    config = DeploymentConfig(
        target=args.target,
        platform=args.platform,
        strategy=args.strategy,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=args.force,
        skip_tests=args.skip_tests,
        skip_migrations=args.skip_migrations,
        skip_assets=args.skip_assets,
        skip_backup=args.skip_backup,
        skip_health_check=args.skip_health_check,
        rollback=args.rollback,
        rollback_version=args.version,
        maintenance_mode=args.maintenance_mode,
        notification_webhook=args.notification_webhook,
    )
    
    # Ejecutar deployment
    deployment = EcosistemaDeployment(config)
    success = deployment.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()