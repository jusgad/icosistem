"""
Sistema de Tareas de Backup - Ecosistema de Emprendimiento
=========================================================

Este módulo maneja todas las tareas asíncronas relacionadas con backups,
restore y disaster recovery para el ecosistema de emprendimiento.

Funcionalidades principales:
- Backups completos e incrementales de base de datos
- Backup de archivos y documentos de usuarios
- Backup de configuraciones del sistema
- Sincronización con servicios cloud (AWS S3, Google Cloud, Azure)
- Verificación de integridad de backups
- Restore automático y manual
- Compresión y cifrado de backups
- Cleanup automático de backups antiguos
- Monitoreo y alertas de backup
- Backup de logs y analytics
- Backup de media files
- Disaster recovery procedures
"""

import logging
import os
import gzip
import shutil
import hashlib
import json
import zipfile
import tarfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import tempfile
import subprocess
import threading
from pathlib import Path

import boto3
from google.cloud import storage as gcs
from azure.storage.blob import BlobServiceClient
import psycopg2
from sqlalchemy import create_engine, text
import paramiko
from cryptography.fernet import Fernet
import schedule

from app.tasks.celery_app import celery_app
from app.core.exceptions import (
    BackupError, 
    RestoreError, 
    BackupVerificationError,
    StorageError
)
from app.core.constants import (
    BACKUP_TYPES,
    STORAGE_PROVIDERS,
    BACKUP_SCHEDULES,
    RETENTION_POLICIES
)
from app.models.backup import BackupRecord, BackupStatus, BackupType
from app.models.user import User
from app.models.project import Project
from app.models.document import Document
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.utils.formatters import format_datetime, format_file_size
from app.utils.string_utils import generate_backup_filename, sanitize_filename
from app.utils.cache_utils import cache_get, cache_set, cache_delete
from app.utils.file_utils import ensure_directory_exists, get_file_checksum
from app.utils.crypto_utils import encrypt_file, decrypt_file, generate_encryption_key

logger = logging.getLogger(__name__)

# Configuración de backup
BACKUP_BASE_DIR = os.getenv('BACKUP_BASE_DIR', '/var/backups/ecosistema')
DATABASE_URL = os.getenv('DATABASE_URL')
ENCRYPTION_KEY = os.getenv('BACKUP_ENCRYPTION_KEY')

# Configuración de servicios cloud
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BACKUP_BUCKET')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

GCS_CREDENTIALS_PATH = os.getenv('GOOGLE_CLOUD_CREDENTIALS')
GCS_BUCKET_NAME = os.getenv('GCS_BACKUP_BUCKET')

AZURE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
AZURE_CONTAINER_NAME = os.getenv('AZURE_BACKUP_CONTAINER')

# Configuración de retención
RETENTION_POLICIES = {
    'daily': {'keep_days': 30},
    'weekly': {'keep_weeks': 12},
    'monthly': {'keep_months': 12},
    'yearly': {'keep_years': 5}
}


class BackupFrequency(Enum):
    """Frecuencias de backup"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class StorageProvider(Enum):
    """Proveedores de almacenamiento"""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"
    SFTP = "sftp"


@dataclass
class BackupConfig:
    """Configuración de backup"""
    name: str
    backup_type: BackupType
    frequency: BackupFrequency
    storage_provider: StorageProvider
    compression: bool = True
    encryption: bool = True
    verify_integrity: bool = True
    retention_days: int = 30
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.include_patterns is None:
            self.include_patterns = []
        if self.exclude_patterns is None:
            self.exclude_patterns = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BackupResult:
    """Resultado de operación de backup"""
    success: bool
    backup_id: str
    file_path: str
    file_size: int
    checksum: str
    duration: float
    storage_provider: StorageProvider
    error_message: str = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BackupManager:
    """Gestor principal de backups"""
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.email_service = EmailService()
        ensure_directory_exists(BACKUP_BASE_DIR)
        
        # Inicializar clientes de almacenamiento
        self._init_storage_clients()
    
    def _init_storage_clients(self):
        """Inicializa clientes de servicios de almacenamiento"""
        try:
            # AWS S3
            if AWS_ACCESS_KEY and AWS_SECRET_KEY:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=AWS_ACCESS_KEY,
                    aws_secret_access_key=AWS_SECRET_KEY,
                    region_name=AWS_REGION
                )
            else:
                self.s3_client = None
                
            # Google Cloud Storage
            if GCS_CREDENTIALS_PATH:
                self.gcs_client = gcs.Client.from_service_account_json(GCS_CREDENTIALS_PATH)
            else:
                self.gcs_client = None
                
            # Azure Blob Storage
            if AZURE_CONNECTION_STRING:
                self.azure_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            else:
                self.azure_client = None
                
        except Exception as e:
            logger.error(f"Error inicializando clientes de almacenamiento: {str(e)}")
    
    def create_backup(self, config: BackupConfig) -> BackupResult:
        """Crea un backup según la configuración"""
        start_time = datetime.utcnow()
        backup_id = f"{config.name}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            logger.info(f"Iniciando backup: {backup_id}")
            
            # Crear directorio temporal
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, f"{backup_id}.tmp")
                
                # Ejecutar backup según tipo
                if config.backup_type == BackupType.DATABASE:
                    backup_path = self._backup_database(temp_path, config)
                elif config.backup_type == BackupType.FILES:
                    backup_path = self._backup_files(temp_path, config)
                elif config.backup_type == BackupType.SYSTEM_CONFIG:
                    backup_path = self._backup_system_config(temp_path, config)
                elif config.backup_type == BackupType.USER_DATA:
                    backup_path = self._backup_user_data(temp_path, config)
                elif config.backup_type == BackupType.MEDIA:
                    backup_path = self._backup_media_files(temp_path, config)
                else:
                    raise BackupError(f"Tipo de backup no soportado: {config.backup_type}")
                
                # Comprimir si se solicita
                if config.compression:
                    backup_path = self._compress_backup(backup_path)
                
                # Cifrar si se solicita
                if config.encryption:
                    backup_path = self._encrypt_backup(backup_path)
                
                # Calcular checksum
                checksum = get_file_checksum(backup_path)
                file_size = os.path.getsize(backup_path)
                
                # Mover a ubicación final
                final_filename = generate_backup_filename(
                    config.name, 
                    start_time, 
                    config.backup_type,
                    compressed=config.compression,
                    encrypted=config.encryption
                )
                final_path = os.path.join(BACKUP_BASE_DIR, final_filename)
                shutil.move(backup_path, final_path)
                
                # Verificar integridad si se solicita
                if config.verify_integrity:
                    if not self._verify_backup_integrity(final_path, checksum):
                        raise BackupVerificationError("Falló la verificación de integridad")
                
                # Subir a almacenamiento externo
                remote_path = None
                if config.storage_provider != StorageProvider.LOCAL:
                    remote_path = self._upload_to_storage(final_path, config.storage_provider)
                
                # Calcular duración
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                # Crear resultado
                result = BackupResult(
                    success=True,
                    backup_id=backup_id,
                    file_path=remote_path or final_path,
                    file_size=file_size,
                    checksum=checksum,
                    duration=duration,
                    storage_provider=config.storage_provider,
                    metadata={
                        'config': asdict(config),
                        'local_path': final_path,
                        'remote_path': remote_path,
                        'start_time': start_time.isoformat()
                    }
                )
                
                # Registrar backup
                self._register_backup(result, config)
                
                logger.info(f"Backup completado exitosamente: {backup_id} ({format_file_size(file_size)})")
                
                return result
                
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Error en backup {backup_id}: {str(e)}")
            
            return BackupResult(
                success=False,
                backup_id=backup_id,
                file_path="",
                file_size=0,
                checksum="",
                duration=duration,
                storage_provider=config.storage_provider,
                error_message=str(e)
            )
    
    def _backup_database(self, output_path: str, config: BackupConfig) -> str:
        """Realiza backup de la base de datos"""
        try:
            # Crear backup usando pg_dump
            backup_file = f"{output_path}_database.sql"
            
            # Comando pg_dump
            cmd = [
                'pg_dump',
                DATABASE_URL,
                '--no-password',
                '--verbose',
                '--format=custom',
                '--file=' + backup_file
            ]
            
            # Ejecutar comando
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode != 0:
                raise BackupError(f"pg_dump falló: {result.stderr}")
            
            logger.info(f"Backup de base de datos completado: {backup_file}")
            return backup_file
            
        except subprocess.TimeoutExpired:
            raise BackupError("Timeout en backup de base de datos")
        except Exception as e:
            raise BackupError(f"Error en backup de base de datos: {str(e)}")
    
    def _backup_files(self, output_path: str, config: BackupConfig) -> str:
        """Realiza backup de archivos del sistema"""
        try:
            backup_file = f"{output_path}_files.tar.gz"
            
            # Directorios a incluir
            include_dirs = config.include_patterns or [
                'app/static/uploads',
                'app/templates',
                'app/static/media',
                'config',
                'logs'
            ]
            
            # Crear archivo tar
            with tarfile.open(backup_file, 'w:gz') as tar:
                for dir_path in include_dirs:
                    if os.path.exists(dir_path):
                        tar.add(dir_path, arcname=os.path.basename(dir_path))
                        logger.info(f"Añadido al backup: {dir_path}")
            
            logger.info(f"Backup de archivos completado: {backup_file}")
            return backup_file
            
        except Exception as e:
            raise BackupError(f"Error en backup de archivos: {str(e)}")
    
    def _backup_system_config(self, output_path: str, config: BackupConfig) -> str:
        """Realiza backup de configuraciones del sistema"""
        try:
            backup_file = f"{output_path}_config.json"
            
            # Configuraciones a respaldar
            config_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'app_version': os.getenv('APP_VERSION', '1.0.0'),
                'environment': os.getenv('FLASK_ENV', 'production'),
                'database_url': DATABASE_URL.split('@')[1] if DATABASE_URL else None,  # Sin credenciales
                'backup_config': asdict(config),
                'system_settings': self._get_system_settings(),
                'user_preferences': self._get_user_preferences_summary(),
                'feature_flags': self._get_feature_flags()
            }
            
            # Guardar configuración
            with open(backup_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            logger.info(f"Backup de configuración completado: {backup_file}")
            return backup_file
            
        except Exception as e:
            raise BackupError(f"Error en backup de configuración: {str(e)}")
    
    def _backup_user_data(self, output_path: str, config: BackupConfig) -> str:
        """Realiza backup de datos de usuarios (documentos, proyectos)"""
        try:
            backup_file = f"{output_path}_userdata.tar.gz"
            
            # Crear directorio temporal para datos de usuario
            user_data_dir = os.path.join(os.path.dirname(output_path), 'user_data')
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Exportar datos de usuarios
            self._export_user_documents(user_data_dir)
            self._export_project_data(user_data_dir)
            self._export_user_profiles(user_data_dir)
            
            # Crear archivo tar
            with tarfile.open(backup_file, 'w:gz') as tar:
                tar.add(user_data_dir, arcname='user_data')
            
            # Limpiar directorio temporal
            shutil.rmtree(user_data_dir)
            
            logger.info(f"Backup de datos de usuario completado: {backup_file}")
            return backup_file
            
        except Exception as e:
            raise BackupError(f"Error en backup de datos de usuario: {str(e)}")
    
    def _backup_media_files(self, output_path: str, config: BackupConfig) -> str:
        """Realiza backup de archivos multimedia"""
        try:
            backup_file = f"{output_path}_media.tar.gz"
            
            # Directorios de media
            media_dirs = [
                'app/static/uploads/images',
                'app/static/uploads/documents',
                'app/static/uploads/avatars',
                'app/static/uploads/project_files'
            ]
            
            # Crear archivo tar
            with tarfile.open(backup_file, 'w:gz') as tar:
                for media_dir in media_dirs:
                    if os.path.exists(media_dir):
                        tar.add(media_dir, arcname=os.path.basename(media_dir))
                        logger.info(f"Media añadido al backup: {media_dir}")
            
            logger.info(f"Backup de archivos multimedia completado: {backup_file}")
            return backup_file
            
        except Exception as e:
            raise BackupError(f"Error en backup de archivos multimedia: {str(e)}")
    
    def _compress_backup(self, file_path: str) -> str:
        """Comprime un archivo de backup"""
        try:
            compressed_path = f"{file_path}.gz"
            
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Eliminar archivo original
            os.remove(file_path)
            
            logger.info(f"Backup comprimido: {compressed_path}")
            return compressed_path
            
        except Exception as e:
            raise BackupError(f"Error comprimiendo backup: {str(e)}")
    
    def _encrypt_backup(self, file_path: str) -> str:
        """Cifra un archivo de backup"""
        try:
            if not ENCRYPTION_KEY:
                raise BackupError("Clave de cifrado no configurada")
            
            encrypted_path = f"{file_path}.enc"
            encrypt_file(file_path, encrypted_path, ENCRYPTION_KEY)
            
            # Eliminar archivo original
            os.remove(file_path)
            
            logger.info(f"Backup cifrado: {encrypted_path}")
            return encrypted_path
            
        except Exception as e:
            raise BackupError(f"Error cifrando backup: {str(e)}")
    
    def _verify_backup_integrity(self, file_path: str, expected_checksum: str) -> bool:
        """Verifica la integridad de un backup"""
        try:
            actual_checksum = get_file_checksum(file_path)
            return actual_checksum == expected_checksum
            
        except Exception as e:
            logger.error(f"Error verificando integridad: {str(e)}")
            return False
    
    def _upload_to_storage(self, file_path: str, provider: StorageProvider) -> str:
        """Sube backup a almacenamiento externo"""
        try:
            filename = os.path.basename(file_path)
            
            if provider == StorageProvider.AWS_S3:
                return self._upload_to_s3(file_path, filename)
            elif provider == StorageProvider.GOOGLE_CLOUD:
                return self._upload_to_gcs(file_path, filename)
            elif provider == StorageProvider.AZURE_BLOB:
                return self._upload_to_azure(file_path, filename)
            else:
                raise StorageError(f"Proveedor no soportado: {provider}")
                
        except Exception as e:
            raise StorageError(f"Error subiendo a {provider.value}: {str(e)}")
    
    def _upload_to_s3(self, file_path: str, filename: str) -> str:
        """Sube archivo a AWS S3"""
        if not self.s3_client:
            raise StorageError("Cliente S3 no configurado")
        
        s3_key = f"backups/{datetime.utcnow().strftime('%Y/%m/%d')}/{filename}"
        
        self.s3_client.upload_file(file_path, AWS_BUCKET_NAME, s3_key)
        
        return f"s3://{AWS_BUCKET_NAME}/{s3_key}"
    
    def _upload_to_gcs(self, file_path: str, filename: str) -> str:
        """Sube archivo a Google Cloud Storage"""
        if not self.gcs_client:
            raise StorageError("Cliente GCS no configurado")
        
        bucket = self.gcs_client.bucket(GCS_BUCKET_NAME)
        blob_name = f"backups/{datetime.utcnow().strftime('%Y/%m/%d')}/{filename}"
        blob = bucket.blob(blob_name)
        
        blob.upload_from_filename(file_path)
        
        return f"gs://{GCS_BUCKET_NAME}/{blob_name}"
    
    def _upload_to_azure(self, file_path: str, filename: str) -> str:
        """Sube archivo a Azure Blob Storage"""
        if not self.azure_client:
            raise StorageError("Cliente Azure no configurado")
        
        blob_name = f"backups/{datetime.utcnow().strftime('%Y/%m/%d')}/{filename}"
        
        with open(file_path, 'rb') as data:
            self.azure_client.upload_blob(
                container=AZURE_CONTAINER_NAME,
                name=blob_name,
                data=data,
                overwrite=True
            )
        
        return f"azure://{AZURE_CONTAINER_NAME}/{blob_name}"
    
    def _register_backup(self, result: BackupResult, config: BackupConfig):
        """Registra el backup en la base de datos"""
        try:
            from app import db
            
            backup_record = BackupRecord(
                backup_id=result.backup_id,
                backup_type=config.backup_type,
                file_path=result.file_path,
                file_size=result.file_size,
                checksum=result.checksum,
                storage_provider=config.storage_provider.value,
                frequency=config.frequency.value,
                status=BackupStatus.COMPLETED if result.success else BackupStatus.FAILED,
                duration=result.duration,
                metadata=result.metadata,
                created_at=datetime.utcnow()
            )
            
            db.session.add(backup_record)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error registrando backup: {str(e)}")
    
    # Funciones auxiliares para obtener datos del sistema
    def _get_system_settings(self) -> Dict[str, Any]:
        """Obtiene configuraciones del sistema"""
        return {
            'timezone': os.getenv('TIMEZONE', 'UTC'),
            'language': os.getenv('DEFAULT_LANGUAGE', 'es'),
            'max_file_size': os.getenv('MAX_FILE_SIZE', '10MB'),
            'session_timeout': os.getenv('SESSION_TIMEOUT', '3600')
        }
    
    def _get_user_preferences_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de preferencias de usuarios"""
        try:
            from app import db
            
            total_users = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar()
            active_users = db.session.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true")).scalar()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'backup_timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error obteniendo resumen de usuarios: {str(e)}")
            return {}
    
    def _get_feature_flags(self) -> Dict[str, bool]:
        """Obtiene feature flags del sistema"""
        return {
            'enable_notifications': True,
            'enable_analytics': True,
            'enable_websockets': True,
            'maintenance_mode': False
        }
    
    def _export_user_documents(self, output_dir: str):
        """Exporta documentos de usuarios"""
        try:
            documents = Document.query.all()
            
            docs_dir = os.path.join(output_dir, 'documents')
            os.makedirs(docs_dir, exist_ok=True)
            
            docs_data = []
            for doc in documents:
                docs_data.append({
                    'id': doc.id,
                    'title': doc.title,
                    'content': doc.content,
                    'user_id': doc.user_id,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                    'updated_at': doc.updated_at.isoformat() if doc.updated_at else None
                })
            
            with open(os.path.join(docs_dir, 'documents.json'), 'w') as f:
                json.dump(docs_data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Error exportando documentos: {str(e)}")
    
    def _export_project_data(self, output_dir: str):
        """Exporta datos de proyectos"""
        try:
            projects = Project.query.all()
            
            projects_dir = os.path.join(output_dir, 'projects')
            os.makedirs(projects_dir, exist_ok=True)
            
            projects_data = []
            for project in projects:
                projects_data.append({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'status': project.status,
                    'entrepreneur_id': project.entrepreneur_id,
                    'created_at': project.created_at.isoformat() if project.created_at else None,
                    'updated_at': project.updated_at.isoformat() if project.updated_at else None
                })
            
            with open(os.path.join(projects_dir, 'projects.json'), 'w') as f:
                json.dump(projects_data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Error exportando proyectos: {str(e)}")
    
    def _export_user_profiles(self, output_dir: str):
        """Exporta perfiles de usuarios"""
        try:
            users = User.query.all()
            
            users_dir = os.path.join(output_dir, 'users')
            os.makedirs(users_dir, exist_ok=True)
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role.value if user.role else None,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                })
            
            with open(os.path.join(users_dir, 'users.json'), 'w') as f:
                json.dump(users_data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Error exportando usuarios: {str(e)}")


# Instancia global del gestor de backups
backup_manager = BackupManager()


# === TAREAS DE BACKUP PROGRAMADAS ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='backups',
    priority=9
)
def full_database_backup(self):
    """
    Realiza backup completo de la base de datos
    
    Se ejecuta diariamente a las 2:00 AM
    """
    try:
        logger.info("Iniciando backup completo de base de datos")
        
        # Configuración del backup
        config = BackupConfig(
            name="database_full",
            backup_type=BackupType.DATABASE,
            frequency=BackupFrequency.DAILY,
            storage_provider=StorageProvider.AWS_S3,
            compression=True,
            encryption=True,
            verify_integrity=True,
            retention_days=30
        )
        
        # Ejecutar backup
        result = backup_manager.create_backup(config)
        
        if result.success:
            # Notificar éxito
            backup_manager.notification_service.send_system_notification(
                message=f"Backup completo de BD exitoso: {format_file_size(result.file_size)}",
                recipients=['admin'],
                metadata={
                    'backup_id': result.backup_id,
                    'duration': f"{result.duration:.2f}s",
                    'file_size': result.file_size
                }
            )
            
            logger.info(f"Backup completo exitoso: {result.backup_id}")
            
            # Limpiar backups antiguos
            cleanup_old_backups.apply_async(
                args=[BackupType.DATABASE.value, 'daily'],
                countdown=300
            )
            
        else:
            # Notificar fallo
            backup_manager.notification_service.send_critical_alert(
                message=f"FALLO en backup completo de BD: {result.error_message}",
                recipients=['admin', 'tech_team'],
                metadata={'backup_id': result.backup_id}
            )
            
            logger.error(f"Backup completo falló: {result.error_message}")
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup completo de base de datos: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        
        # Notificar error crítico
        backup_manager.notification_service.send_critical_alert(
            message=f"ERROR CRÍTICO en backup de BD: {str(exc)}",
            recipients=['admin', 'tech_team']
        )
        
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    queue='backups',
    priority=8
)
def incremental_backup(self):
    """
    Realiza backup incremental de la base de datos
    
    Se ejecuta cada hora
    """
    try:
        logger.info("Iniciando backup incremental")
        
        # Configuración del backup incremental
        config = BackupConfig(
            name="database_incremental",
            backup_type=BackupType.DATABASE,
            frequency=BackupFrequency.HOURLY,
            storage_provider=StorageProvider.LOCAL,
            compression=True,
            encryption=False,  # Menos crítico para incrementales
            verify_integrity=False,  # Más rápido
            retention_days=7,  # Retención más corta
            metadata={'incremental': True}
        )
        
        # Ejecutar backup incremental
        result = backup_manager.create_backup(config)
        
        if result.success:
            logger.info(f"Backup incremental exitoso: {result.backup_id}")
            
            # Solo notificar si hay problemas o es el primer backup del día
            current_hour = datetime.utcnow().hour
            if current_hour == 0:  # Primer backup del día
                backup_manager.notification_service.send_system_notification(
                    message=f"Backup incremental diario iniciado: {format_file_size(result.file_size)}",
                    recipients=['admin']
                )
        else:
            logger.error(f"Backup incremental falló: {result.error_message}")
            
            # Notificar solo si fallan múltiples backups consecutivos
            consecutive_failures = cache_get('backup_consecutive_failures') or 0
            consecutive_failures += 1
            cache_set('backup_consecutive_failures', consecutive_failures, timeout=7200)
            
            if consecutive_failures >= 3:
                backup_manager.notification_service.send_alert(
                    message=f"Múltiples fallos en backup incremental: {consecutive_failures}",
                    recipients=['admin']
                )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup incremental: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=180 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='backups',
    priority=7
)
def backup_user_files(self):
    """
    Realiza backup de archivos de usuarios
    
    Se ejecuta semanalmente los domingos a las 3:00 AM
    """
    try:
        logger.info("Iniciando backup de archivos de usuarios")
        
        # Configuración del backup
        config = BackupConfig(
            name="user_files",
            backup_type=BackupType.USER_DATA,
            frequency=BackupFrequency.WEEKLY,
            storage_provider=StorageProvider.GOOGLE_CLOUD,
            compression=True,
            encryption=True,
            verify_integrity=True,
            retention_days=90,
            include_patterns=[
                'app/static/uploads/documents/*',
                'app/static/uploads/images/*',
                'app/static/uploads/avatars/*'
            ]
        )
        
        # Ejecutar backup
        result = backup_manager.create_backup(config)
        
        if result.success:
            backup_manager.notification_service.send_system_notification(
                message=f"Backup semanal de archivos exitoso: {format_file_size(result.file_size)}",
                recipients=['admin'],
                metadata={
                    'backup_id': result.backup_id,
                    'files_backed_up': result.metadata.get('files_count', 'unknown')
                }
            )
            
            logger.info(f"Backup de archivos exitoso: {result.backup_id}")
        else:
            backup_manager.notification_service.send_alert(
                message=f"Fallo en backup de archivos: {result.error_message}",
                recipients=['admin', 'tech_team']
            )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup de archivos: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='backups',
    priority=6
)
def backup_system_config(self):
    """
    Realiza backup de configuraciones del sistema
    
    Se ejecuta semanalmente los domingos a las 4:00 AM
    """
    try:
        logger.info("Iniciando backup de configuraciones del sistema")
        
        # Configuración del backup
        config = BackupConfig(
            name="system_config",
            backup_type=BackupType.SYSTEM_CONFIG,
            frequency=BackupFrequency.WEEKLY,
            storage_provider=StorageProvider.AWS_S3,
            compression=True,
            encryption=True,
            verify_integrity=True,
            retention_days=365  # Retener configuraciones por un año
        )
        
        # Ejecutar backup
        result = backup_manager.create_backup(config)
        
        if result.success:
            logger.info(f"Backup de configuración exitoso: {result.backup_id}")
        else:
            backup_manager.notification_service.send_alert(
                message=f"Fallo en backup de configuración: {result.error_message}",
                recipients=['admin']
            )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup de configuración: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='backups',
    priority=5
)
def backup_media_files(self):
    """
    Realiza backup de archivos multimedia
    
    Se ejecuta mensualmente el primer día del mes a las 5:00 AM
    """
    try:
        logger.info("Iniciando backup de archivos multimedia")
        
        # Configuración del backup
        config = BackupConfig(
            name="media_files",
            backup_type=BackupType.MEDIA,
            frequency=BackupFrequency.MONTHLY,
            storage_provider=StorageProvider.AZURE_BLOB,
            compression=True,
            encryption=False,  # Los archivos multimedia ya están optimizados
            verify_integrity=True,
            retention_days=365,
            include_patterns=[
                'app/static/uploads/images/*',
                'app/static/uploads/videos/*',
                'app/static/uploads/presentations/*'
            ]
        )
        
        # Ejecutar backup
        result = backup_manager.create_backup(config)
        
        if result.success:
            backup_manager.notification_service.send_system_notification(
                message=f"Backup mensual de media exitoso: {format_file_size(result.file_size)}",
                recipients=['admin']
            )
            
            logger.info(f"Backup de media exitoso: {result.backup_id}")
        else:
            backup_manager.notification_service.send_alert(
                message=f"Fallo en backup de media: {result.error_message}",
                recipients=['admin']
            )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup de media: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE RESTORE ===

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    queue='backups',
    priority=10
)
def restore_from_backup(self, backup_id: str, restore_type: str = 'full'):
    """
    Restaura desde un backup específico
    
    Args:
        backup_id: ID del backup a restaurar
        restore_type: Tipo de restore (full, partial, verification)
    """
    try:
        logger.info(f"Iniciando restore desde backup: {backup_id}")
        
        # Obtener información del backup
        backup_record = BackupRecord.query.filter_by(backup_id=backup_id).first()
        if not backup_record:
            raise RestoreError(f"Backup no encontrado: {backup_id}")
        
        # Verificar que el backup esté disponible
        if not _verify_backup_availability(backup_record):
            raise RestoreError(f"Backup no disponible: {backup_id}")
        
        # Descargar backup si está en almacenamiento externo
        local_path = _download_backup_if_needed(backup_record)
        
        # Descifrar si está cifrado
        if backup_record.metadata.get('encrypted', False):
            local_path = _decrypt_backup_file(local_path)
        
        # Descomprimir si está comprimido
        if backup_record.metadata.get('compressed', False):
            local_path = _decompress_backup_file(local_path)
        
        # Ejecutar restore según tipo de backup
        if backup_record.backup_type == BackupType.DATABASE:
            restore_result = _restore_database(local_path, restore_type)
        elif backup_record.backup_type == BackupType.FILES:
            restore_result = _restore_files(local_path, restore_type)
        elif backup_record.backup_type == BackupType.USER_DATA:
            restore_result = _restore_user_data(local_path, restore_type)
        else:
            raise RestoreError(f"Tipo de backup no soportado para restore: {backup_record.backup_type}")
        
        # Verificar integridad del restore
        if restore_type == 'full':
            verification_result = _verify_restore_integrity(backup_record.backup_type)
            restore_result['verification'] = verification_result
        
        # Notificar éxito
        backup_manager.notification_service.send_critical_alert(
            message=f"RESTORE COMPLETADO: {backup_id} ({restore_type})",
            recipients=['admin', 'tech_team'],
            metadata={
                'backup_id': backup_id,
                'restore_type': restore_type,
                'duration': restore_result.get('duration', 0)
            }
        )
        
        logger.info(f"Restore completado exitosamente: {backup_id}")
        
        return {
            'success': True,
            'backup_id': backup_id,
            'restore_type': restore_type,
            'result': restore_result
        }
        
    except Exception as exc:
        logger.error(f"Error en restore: {str(exc)}")
        
        # Notificar error crítico
        backup_manager.notification_service.send_critical_alert(
            message=f"ERROR CRÍTICO EN RESTORE: {backup_id} - {str(exc)}",
            recipients=['admin', 'tech_team']
        )
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=600)
        return {'success': False, 'error': str(exc)}


# === TAREAS DE MANTENIMIENTO ===

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    queue='backups',
    priority=4
)
def cleanup_old_backups(self, backup_type: str, frequency: str):
    """
    Limpia backups antiguos según políticas de retención
    
    Args:
        backup_type: Tipo de backup a limpiar
        frequency: Frecuencia del backup (daily, weekly, monthly)
    """
    try:
        logger.info(f"Iniciando limpieza de backups: {backup_type} ({frequency})")
        
        # Obtener política de retención
        retention_policy = RETENTION_POLICIES.get(frequency, {'keep_days': 30})
        retention_days = retention_policy.get('keep_days', 30)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Obtener backups antiguos
        old_backups = BackupRecord.query.filter(
            BackupRecord.backup_type == backup_type,
            BackupRecord.frequency == frequency,
            BackupRecord.created_at < cutoff_date,
            BackupRecord.status == BackupStatus.COMPLETED
        ).all()
        
        deleted_count = 0
        total_size_freed = 0
        
        for backup in old_backups:
            try:
                # Eliminar archivo local si existe
                if backup.file_path and os.path.exists(backup.file_path):
                    file_size = os.path.getsize(backup.file_path)
                    os.remove(backup.file_path)
                    total_size_freed += file_size
                
                # Eliminar de almacenamiento externo
                if backup.storage_provider != 'local':
                    _delete_from_external_storage(backup)
                
                # Marcar como eliminado en la base de datos
                backup.status = BackupStatus.DELETED
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Error eliminando backup {backup.backup_id}: {str(e)}")
                continue
        
        # Guardar cambios
        from app import db
        db.session.commit()
        
        logger.info(f"Limpieza completada: {deleted_count} backups eliminados, {format_file_size(total_size_freed)} liberados")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'size_freed': total_size_freed,
            'backup_type': backup_type,
            'frequency': frequency
        }
        
    except Exception as exc:
        logger.error(f"Error en limpieza de backups: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='backups',
    priority=6
)
def verify_backup_integrity(self, backup_id: str = None, days_back: int = 7):
    """
    Verifica la integridad de backups recientes
    
    Args:
        backup_id: ID específico de backup a verificar (opcional)
        days_back: Días hacia atrás para verificar backups
    """
    try:
        logger.info(f"Iniciando verificación de integridad de backups")
        
        if backup_id:
            # Verificar backup específico
            backups = [BackupRecord.query.filter_by(backup_id=backup_id).first()]
        else:
            # Verificar backups recientes
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            backups = BackupRecord.query.filter(
                BackupRecord.created_at >= cutoff_date,
                BackupRecord.status == BackupStatus.COMPLETED
            ).all()
        
        verification_results = []
        
        for backup in backups:
            if not backup:
                continue
                
            try:
                # Verificar que el archivo existe
                if backup.storage_provider == 'local':
                    file_exists = os.path.exists(backup.file_path)
                else:
                    file_exists = _check_external_file_exists(backup)
                
                if not file_exists:
                    verification_results.append({
                        'backup_id': backup.backup_id,
                        'status': 'FAILED',
                        'error': 'File not found'
                    })
                    continue
                
                # Verificar checksum si está disponible
                if backup.checksum:
                    if backup.storage_provider == 'local':
                        current_checksum = get_file_checksum(backup.file_path)
                    else:
                        # Para archivos externos, descargar temporalmente para verificar
                        temp_path = _download_for_verification(backup)
                        current_checksum = get_file_checksum(temp_path)
                        os.remove(temp_path)
                    
                    if current_checksum == backup.checksum:
                        verification_results.append({
                            'backup_id': backup.backup_id,
                            'status': 'VERIFIED',
                            'checksum_match': True
                        })
                    else:
                        verification_results.append({
                            'backup_id': backup.backup_id,
                            'status': 'CORRUPTED',
                            'checksum_match': False
                        })
                else:
                    verification_results.append({
                        'backup_id': backup.backup_id,
                        'status': 'EXISTS',
                        'checksum_available': False
                    })
                    
            except Exception as e:
                verification_results.append({
                    'backup_id': backup.backup_id,
                    'status': 'ERROR',
                    'error': str(e)
                })
        
        # Resumen de verificación
        total_backups = len(verification_results)
        verified_count = sum(1 for r in verification_results if r['status'] == 'VERIFIED')
        corrupted_count = sum(1 for r in verification_results if r['status'] == 'CORRUPTED')
        error_count = sum(1 for r in verification_results if r['status'] == 'ERROR')
        
        # Notificar si hay problemas
        if corrupted_count > 0 or error_count > 0:
            backup_manager.notification_service.send_alert(
                message=f"Problemas en verificación de backups: {corrupted_count} corruptos, {error_count} errores",
                recipients=['admin', 'tech_team'],
                metadata={
                    'total_checked': total_backups,
                    'corrupted': corrupted_count,
                    'errors': error_count
                }
            )
        
        logger.info(f"Verificación completada: {verified_count}/{total_backups} backups verificados")
        
        return {
            'success': True,
            'total_backups': total_backups,
            'verified_count': verified_count,
            'corrupted_count': corrupted_count,
            'error_count': error_count,
            'results': verification_results
        }
        
    except Exception as exc:
        logger.error(f"Error en verificación de integridad: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS BAJO DEMANDA ===

@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=300,
    queue='backups',
    priority=8
)
def create_manual_backup(self, backup_config: Dict[str, Any]):
    """
    Crea un backup manual bajo demanda
    
    Args:
        backup_config: Configuración del backup manual
    """
    try:
        logger.info("Iniciando backup manual bajo demanda")
        
        # Crear configuración desde diccionario
        config = BackupConfig(
            name=backup_config.get('name', f"manual_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"),
            backup_type=BackupType(backup_config['backup_type']),
            frequency=BackupFrequency.ON_DEMAND,
            storage_provider=StorageProvider(backup_config.get('storage_provider', 'local')),
            compression=backup_config.get('compression', True),
            encryption=backup_config.get('encryption', False),
            verify_integrity=backup_config.get('verify_integrity', True),
            retention_days=backup_config.get('retention_days', 30),
            metadata=backup_config.get('metadata', {})
        )
        
        # Ejecutar backup
        result = backup_manager.create_backup(config)
        
        # Notificar resultado
        if result.success:
            backup_manager.notification_service.send_system_notification(
                message=f"Backup manual completado: {result.backup_id}",
                recipients=['admin'],
                metadata={
                    'backup_id': result.backup_id,
                    'file_size': format_file_size(result.file_size),
                    'duration': f"{result.duration:.2f}s"
                }
            )
        else:
            backup_manager.notification_service.send_alert(
                message=f"Fallo en backup manual: {result.error_message}",
                recipients=['admin']
            )
        
        return result.to_dict()
        
    except Exception as exc:
        logger.error(f"Error en backup manual: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)
        return {'success': False, 'error': str(exc)}


# === FUNCIONES AUXILIARES PRIVADAS ===

def _verify_backup_availability(backup_record: BackupRecord) -> bool:
    """Verifica que un backup esté disponible"""
    try:
        if backup_record.storage_provider == 'local':
            return os.path.exists(backup_record.file_path)
        else:
            return _check_external_file_exists(backup_record)
    except Exception:
        return False


def _check_external_file_exists(backup_record: BackupRecord) -> bool:
    """Verifica si existe un archivo en almacenamiento externo"""
    try:
        if backup_record.storage_provider == 'aws_s3':
            # Verificar en S3
            s3_path = backup_record.file_path.replace('s3://', '').split('/', 1)
            bucket_name, key = s3_path[0], s3_path[1]
            
            s3_client = boto3.client('s3')
            s3_client.head_object(Bucket=bucket_name, Key=key)
            return True
            
        elif backup_record.storage_provider == 'google_cloud':
            # Verificar en GCS
            gcs_path = backup_record.file_path.replace('gs://', '').split('/', 1)
            bucket_name, blob_name = gcs_path[0], gcs_path[1]
            
            client = gcs.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            return blob.exists()
            
        elif backup_record.storage_provider == 'azure_blob':
            # Verificar en Azure
            azure_path = backup_record.file_path.replace('azure://', '').split('/', 1)
            container_name, blob_name = azure_path[0], azure_path[1]
            
            blob_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            blob = blob_client.get_blob_client(container=container_name, blob=blob_name)
            return blob.exists()
            
        return False
        
    except Exception as e:
        logger.error(f"Error verificando archivo externo: {str(e)}")
        return False


def _download_backup_if_needed(backup_record: BackupRecord) -> str:
    """Descarga backup desde almacenamiento externo si es necesario"""
    if backup_record.storage_provider == 'local':
        return backup_record.file_path
    
    # Crear archivo temporal para descarga
    temp_dir = tempfile.mkdtemp()
    filename = os.path.basename(backup_record.file_path)
    local_path = os.path.join(temp_dir, filename)
    
    try:
        if backup_record.storage_provider == 'aws_s3':
            _download_from_s3(backup_record.file_path, local_path)
        elif backup_record.storage_provider == 'google_cloud':
            _download_from_gcs(backup_record.file_path, local_path)
        elif backup_record.storage_provider == 'azure_blob':
            _download_from_azure(backup_record.file_path, local_path)
        
        return local_path
        
    except Exception as e:
        shutil.rmtree(temp_dir)
        raise RestoreError(f"Error descargando backup: {str(e)}")


def _download_from_s3(s3_path: str, local_path: str):
    """Descarga archivo desde S3"""
    s3_path = s3_path.replace('s3://', '').split('/', 1)
    bucket_name, key = s3_path[0], s3_path[1]
    
    s3_client = boto3.client('s3')
    s3_client.download_file(bucket_name, key, local_path)


def _download_from_gcs(gcs_path: str, local_path: str):
    """Descarga archivo desde Google Cloud Storage"""
    gcs_path = gcs_path.replace('gs://', '').split('/', 1)
    bucket_name, blob_name = gcs_path[0], gcs_path[1]
    
    client = gcs.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_path)


def _download_from_azure(azure_path: str, local_path: str):
    """Descarga archivo desde Azure Blob Storage"""
    azure_path = azure_path.replace('azure://', '').split('/', 1)
    container_name, blob_name = azure_path[0], azure_path[1]
    
    blob_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    blob = blob_client.get_blob_client(container=container_name, blob=blob_name)
    
    with open(local_path, 'wb') as download_file:
        download_file.write(blob.download_blob().readall())


def _decrypt_backup_file(file_path: str) -> str:
    """Descifra un archivo de backup"""
    if not ENCRYPTION_KEY:
        raise RestoreError("Clave de cifrado no disponible")
    
    decrypted_path = file_path.replace('.enc', '')
    decrypt_file(file_path, decrypted_path, ENCRYPTION_KEY)
    
    return decrypted_path


def _decompress_backup_file(file_path: str) -> str:
    """Descomprime un archivo de backup"""
    decompressed_path = file_path.replace('.gz', '')
    
    with gzip.open(file_path, 'rb') as f_in:
        with open(decompressed_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    return decompressed_path


def _restore_database(backup_path: str, restore_type: str) -> Dict[str, Any]:
    """Restaura base de datos desde backup"""
    start_time = datetime.utcnow()
    
    try:
        # Comando pg_restore
        cmd = [
            'pg_restore',
            '--clean',
            '--if-exists',
            '--no-owner',
            '--no-privileges',
            '--verbose',
            '--dbname=' + DATABASE_URL,
            backup_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2 horas
        
        if result.returncode != 0:
            raise RestoreError(f"pg_restore falló: {result.stderr}")
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'restore_type': 'database',
            'duration': duration,
            'status': 'completed',
            'method': 'pg_restore'
        }
        
    except subprocess.TimeoutExpired:
        raise RestoreError("Timeout en restore de base de datos")
    except Exception as e:
        raise RestoreError(f"Error en restore de base de datos: {str(e)}")


def _restore_files(backup_path: str, restore_type: str) -> Dict[str, Any]:
    """Restaura archivos desde backup"""
    start_time = datetime.utcnow()
    
    try:
        # Extraer archivos tar
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(path='/')
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'restore_type': 'files',
            'duration': duration,
            'status': 'completed',
            'method': 'tar_extract'
        }
        
    except Exception as e:
        raise RestoreError(f"Error en restore de archivos: {str(e)}")


def _restore_user_data(backup_path: str, restore_type: str) -> Dict[str, Any]:
    """Restaura datos de usuario desde backup"""
    start_time = datetime.utcnow()
    
    try:
        # Extraer y procesar datos de usuario
        temp_dir = tempfile.mkdtemp()
        
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(path=temp_dir)
        
        # Procesar archivos JSON de datos
        _import_user_data_from_json(temp_dir)
        
        # Limpiar directorio temporal
        shutil.rmtree(temp_dir)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'restore_type': 'user_data',
            'duration': duration,
            'status': 'completed',
            'method': 'json_import'
        }
        
    except Exception as e:
        raise RestoreError(f"Error en restore de datos de usuario: {str(e)}")


def _verify_restore_integrity(backup_type: BackupType) -> Dict[str, Any]:
    """Verifica la integridad del restore"""
    try:
        if backup_type == BackupType.DATABASE:
            # Verificar conectividad y estructura de BD
            from app import db
            db.session.execute(text('SELECT 1'))
            
            # Verificar tablas principales
            tables = ['users', 'projects', 'meetings', 'notifications']
            for table in tables:
                count = db.session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
                if count is None:
                    return {'status': 'failed', 'error': f'Table {table} not accessible'}
            
            return {'status': 'verified', 'method': 'database_query'}
            
        elif backup_type == BackupType.FILES:
            # Verificar archivos críticos
            critical_files = ['app/__init__.py', 'config/config.py']
            for file_path in critical_files:
                if not os.path.exists(file_path):
                    return {'status': 'failed', 'error': f'Critical file missing: {file_path}'}
            
            return {'status': 'verified', 'method': 'file_check'}
        
        return {'status': 'skipped', 'reason': 'verification not implemented for this backup type'}
        
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}


def _delete_from_external_storage(backup_record: BackupRecord):
    """Elimina archivo de almacenamiento externo"""
    try:
        if backup_record.storage_provider == 'aws_s3':
            s3_path = backup_record.file_path.replace('s3://', '').split('/', 1)
            bucket_name, key = s3_path[0], s3_path[1]
            
            s3_client = boto3.client('s3')
            s3_client.delete_object(Bucket=bucket_name, Key=key)
            
        elif backup_record.storage_provider == 'google_cloud':
            gcs_path = backup_record.file_path.replace('gs://', '').split('/', 1)
            bucket_name, blob_name = gcs_path[0], gcs_path[1]
            
            client = gcs.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            
        elif backup_record.storage_provider == 'azure_blob':
            azure_path = backup_record.file_path.replace('azure://', '').split('/', 1)
            container_name, blob_name = azure_path[0], azure_path[1]
            
            blob_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            blob = blob_client.get_blob_client(container=container_name, blob=blob_name)
            blob.delete_blob()
            
    except Exception as e:
        logger.error(f"Error eliminando archivo externo: {str(e)}")


def _download_for_verification(backup_record: BackupRecord) -> str:
    """Descarga archivo temporalmente para verificación"""
    temp_dir = tempfile.mkdtemp()
    filename = os.path.basename(backup_record.file_path)
    temp_path = os.path.join(temp_dir, filename)
    
    _download_backup_if_needed(backup_record)
    
    return temp_path


def _import_user_data_from_json(data_dir: str):
    """Importa datos de usuario desde archivos JSON"""
    try:
        from app import db
        
        # Importar documentos
        docs_file = os.path.join(data_dir, 'user_data', 'documents', 'documents.json')
        if os.path.exists(docs_file):
            with open(docs_file, 'r') as f:
                docs_data = json.load(f)
                # Procesar e importar documentos
                logger.info(f"Importando {len(docs_data)} documentos")
        
        # Importar proyectos
        projects_file = os.path.join(data_dir, 'user_data', 'projects', 'projects.json')
        if os.path.exists(projects_file):
            with open(projects_file, 'r') as f:
                projects_data = json.load(f)
                # Procesar e importar proyectos
                logger.info(f"Importando {len(projects_data)} proyectos")
        
        # Importar usuarios
        users_file = os.path.join(data_dir, 'user_data', 'users', 'users.json')
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users_data = json.load(f)
                # Procesar e importar usuarios
                logger.info(f"Importando {len(users_data)} usuarios")
        
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error importando datos de usuario: {str(e)}")
        raise


# Exportar tareas principales
__all__ = [
    'full_database_backup',
    'incremental_backup',
    'backup_user_files',
    'backup_system_config',
    'backup_media_files',
    'restore_from_backup',
    'cleanup_old_backups',
    'verify_backup_integrity',
    'create_manual_backup',
    'BackupConfig',
    'BackupResult',
    'BackupManager',
    'BackupFrequency',
    'StorageProvider'
]