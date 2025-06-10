"""
File Storage Service - Ecosistema de Emprendimiento
Servicio completo de almacenamiento con múltiples proveedores y funcionalidades empresariales

Author: Senior Developer
Version: 1.0.0
"""

import logging
import os
import hashlib
import mimetypes
import magic
import uuid
import shutil
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple, BinaryIO
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import json
import base64

# Image processing
from PIL import Image, ImageOps, ImageDraw, ImageFont
import pillow_heif

# Cloud storage
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from google.cloud import storage as gcs
from azure.storage.blob import BlobServiceClient

# Security and validation
import clamd
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

# Compression
import gzip
import brotli

from flask import current_app, request, url_for
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, cache, redis_client
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    ExternalServiceError,
    SecurityError
)
from app.core.constants import (
    USER_ROLES,
    FILE_CATEGORIES,
    STORAGE_PROVIDERS,
    MAX_FILE_SIZES
)
from app.models.user import User
from app.models.file_upload import FileUpload
from app.models.file_version import FileVersion
from app.models.file_share import FileShare
from app.models.storage_quota import StorageQuota
from app.models.file_scan_result import FileScanResult
from app.services.base import BaseService
from app.services.notification_service import NotificationService
from app.services.analytics_service import AnalyticsService
from app.utils.decorators import log_activity, retry_on_failure, rate_limit
from app.utils.validators import validate_filename, validate_file_type
from app.utils.formatters import format_file_size, format_datetime
from app.utils.crypto_utils import encrypt_file, decrypt_file, generate_hash
from app.utils.image_utils import optimize_image, generate_thumbnail, add_watermark


logger = logging.getLogger(__name__)


class StorageProvider(Enum):
    """Proveedores de almacenamiento"""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"
    CLOUDFLARE_R2 = "cloudflare_r2"


class FileCategory(Enum):
    """Categorías de archivos"""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PRESENTATION = "presentation"
    SPREADSHEET = "spreadsheet"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


class FileStatus(Enum):
    """Estados de archivo"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    ACTIVE = "active"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"
    DELETED = "deleted"
    CORRUPTED = "corrupted"


class AccessLevel(Enum):
    """Niveles de acceso"""
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"
    ORGANIZATION = "organization"


class ScanStatus(Enum):
    """Estados de escaneo"""
    PENDING = "pending"
    SCANNING = "scanning"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


@dataclass
class FileMetadata:
    """Metadata de archivo"""
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    file_hash: str
    category: str
    dimensions: Optional[Tuple[int, int]] = None
    duration: Optional[float] = None
    encoding: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    exif_data: Optional[Dict[str, Any]] = None
    custom_metadata: Optional[Dict[str, Any]] = None


@dataclass
class UploadConfig:
    """Configuración de upload"""
    max_file_size: int = 100 * 1024 * 1024  # 100MB default
    allowed_extensions: Optional[List[str]] = None
    require_virus_scan: bool = True
    auto_optimize: bool = True
    generate_thumbnails: bool = True
    enable_versioning: bool = True
    encrypt_file: bool = False
    add_watermark: bool = False
    compress_file: bool = False
    storage_provider: str = StorageProvider.LOCAL.value
    storage_class: str = "STANDARD"
    retention_days: Optional[int] = None


@dataclass
class FileUploadResult:
    """Resultado de upload de archivo"""
    success: bool
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_size: int = 0
    file_hash: Optional[str] = None
    scan_result: Optional[str] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None


@dataclass
class StorageStats:
    """Estadísticas de almacenamiento"""
    total_files: int
    total_size_bytes: int
    files_by_category: Dict[str, int]
    size_by_category: Dict[str, int]
    files_by_provider: Dict[str, int]
    monthly_uploads: int
    monthly_downloads: int
    quota_used_percentage: float


class StorageProviderInterface:
    """Interfaz para proveedores de almacenamiento"""
    
    def upload_file(self, file_path: str, key: str, metadata: Dict[str, Any]) -> str:
        """Subir archivo"""
        raise NotImplementedError
    
    def download_file(self, key: str, local_path: str) -> bool:
        """Descargar archivo"""
        raise NotImplementedError
    
    def delete_file(self, key: str) -> bool:
        """Eliminar archivo"""
        raise NotImplementedError
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Obtener URL del archivo"""
        raise NotImplementedError
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copiar archivo"""
        raise NotImplementedError
    
    def file_exists(self, key: str) -> bool:
        """Verificar si el archivo existe"""
        raise NotImplementedError


class LocalStorageProvider(StorageProviderInterface):
    """Proveedor de almacenamiento local"""
    
    def __init__(self):
        self.base_path = Path(current_app.config.get('UPLOAD_FOLDER', '/tmp/uploads'))
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.base_url = current_app.config.get('UPLOAD_URL', '/uploads')
    
    def upload_file(self, file_path: str, key: str, metadata: Dict[str, Any]) -> str:
        """Subir archivo al almacenamiento local"""
        try:
            dest_path = self.base_path / key
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(file_path, dest_path)
            
            # Guardar metadata
            metadata_path = dest_path.with_suffix('.metadata')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
            
            return str(dest_path)
            
        except Exception as e:
            logger.error(f"Error subiendo archivo local: {str(e)}")
            raise ExternalServiceError(f"Error en almacenamiento local: {str(e)}")
    
    def download_file(self, key: str, local_path: str) -> bool:
        """Descargar archivo del almacenamiento local"""
        try:
            source_path = self.base_path / key
            if source_path.exists():
                shutil.copy2(source_path, local_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error descargando archivo local: {str(e)}")
            return False
    
    def delete_file(self, key: str) -> bool:
        """Eliminar archivo del almacenamiento local"""
        try:
            file_path = self.base_path / key
            metadata_path = file_path.with_suffix('.metadata')
            
            if file_path.exists():
                file_path.unlink()
            
            if metadata_path.exists():
                metadata_path.unlink()
            
            return True
        except Exception as e:
            logger.error(f"Error eliminando archivo local: {str(e)}")
            return False
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Obtener URL del archivo local"""
        return f"{self.base_url}/{key}"
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copiar archivo en almacenamiento local"""
        try:
            source_path = self.base_path / source_key
            dest_path = self.base_path / dest_key
            
            if source_path.exists():
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error copiando archivo local: {str(e)}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """Verificar si el archivo existe"""
        return (self.base_path / key).exists()


class S3StorageProvider(StorageProviderInterface):
    """Proveedor de almacenamiento AWS S3"""
    
    def __init__(self):
        self.bucket_name = current_app.config.get('AWS_S3_BUCKET')
        self.region = current_app.config.get('AWS_REGION', 'us-east-1')
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=self.region
            )
        except Exception as e:
            logger.error(f"Error inicializando S3: {str(e)}")
            self.s3_client = None
    
    def upload_file(self, file_path: str, key: str, metadata: Dict[str, Any]) -> str:
        """Subir archivo a S3"""
        try:
            if not self.s3_client:
                raise ExternalServiceError("S3 client not initialized")
            
            extra_args = {
                'Metadata': {k: str(v) for k, v in metadata.items()},
                'ServerSideEncryption': 'AES256'
            }
            
            self.s3_client.upload_file(file_path, self.bucket_name, key, ExtraArgs=extra_args)
            return f"s3://{self.bucket_name}/{key}"
            
        except ClientError as e:
            logger.error(f"Error subiendo a S3: {str(e)}")
            raise ExternalServiceError(f"Error en S3: {str(e)}")
    
    def download_file(self, key: str, local_path: str) -> bool:
        """Descargar archivo de S3"""
        try:
            if not self.s3_client:
                return False
            
            self.s3_client.download_file(self.bucket_name, key, local_path)
            return True
        except ClientError as e:
            logger.error(f"Error descargando de S3: {str(e)}")
            return False
    
    def delete_file(self, key: str) -> bool:
        """Eliminar archivo de S3"""
        try:
            if not self.s3_client:
                return False
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Error eliminando de S3: {str(e)}")
            return False
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Obtener URL presignada de S3"""
        try:
            if not self.s3_client:
                return ""
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Error generando URL de S3: {str(e)}")
            return ""
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copiar archivo en S3"""
        try:
            if not self.s3_client:
                return False
            
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_key
            )
            return True
        except ClientError as e:
            logger.error(f"Error copiando en S3: {str(e)}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """Verificar si el archivo existe en S3"""
        try:
            if not self.s3_client:
                return False
            
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False


class GoogleCloudStorageProvider(StorageProviderInterface):
    """Proveedor de almacenamiento Google Cloud Storage"""
    
    def __init__(self):
        self.bucket_name = current_app.config.get('GCS_BUCKET')
        self.credentials_path = current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        try:
            if self.credentials_path:
                self.client = gcs.Client.from_service_account_json(self.credentials_path)
            else:
                self.client = gcs.Client()
            
            self.bucket = self.client.bucket(self.bucket_name)
        except Exception as e:
            logger.error(f"Error inicializando GCS: {str(e)}")
            self.client = None
            self.bucket = None
    
    def upload_file(self, file_path: str, key: str, metadata: Dict[str, Any]) -> str:
        """Subir archivo a Google Cloud Storage"""
        try:
            if not self.bucket:
                raise ExternalServiceError("GCS bucket not initialized")
            
            blob = self.bucket.blob(key)
            blob.metadata = metadata
            
            with open(file_path, 'rb') as file_obj:
                blob.upload_from_file(file_obj)
            
            return f"gs://{self.bucket_name}/{key}"
            
        except Exception as e:
            logger.error(f"Error subiendo a GCS: {str(e)}")
            raise ExternalServiceError(f"Error en GCS: {str(e)}")
    
    def download_file(self, key: str, local_path: str) -> bool:
        """Descargar archivo de GCS"""
        try:
            if not self.bucket:
                return False
            
            blob = self.bucket.blob(key)
            blob.download_to_filename(local_path)
            return True
        except Exception as e:
            logger.error(f"Error descargando de GCS: {str(e)}")
            return False
    
    def delete_file(self, key: str) -> bool:
        """Eliminar archivo de GCS"""
        try:
            if not self.bucket:
                return False
            
            blob = self.bucket.blob(key)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Error eliminando de GCS: {str(e)}")
            return False
    
    def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Obtener URL firmada de GCS"""
        try:
            if not self.bucket:
                return ""
            
            blob = self.bucket.blob(key)
            url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(seconds=expires_in),
                method='GET'
            )
            return url
        except Exception as e:
            logger.error(f"Error generando URL de GCS: {str(e)}")
            return ""
    
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copiar archivo en GCS"""
        try:
            if not self.bucket:
                return False
            
            source_blob = self.bucket.blob(source_key)
            dest_blob = self.bucket.copy_blob(source_blob, self.bucket, dest_key)
            return True
        except Exception as e:
            logger.error(f"Error copiando en GCS: {str(e)}")
            return False
    
    def file_exists(self, key: str) -> bool:
        """Verificar si el archivo existe en GCS"""
        try:
            if not self.bucket:
                return False
            
            blob = self.bucket.blob(key)
            return blob.exists()
        except Exception as e:
            return False


class FileStorageService(BaseService):
    """
    Servicio completo de almacenamiento de archivos
    
    Funcionalidades:
    - Múltiples proveedores (Local, S3, GCS, Azure)
    - Validación y sanitización de archivos
    - Escaneo antivirus automático
    - Optimización automática de imágenes
    - Generación de thumbnails
    - Versioning de archivos
    - Encriptación en reposo
    - Watermarking automático
    - Compresión inteligente
    - CDN integration
    - Gestión de cuotas
    - Analytics de uso
    - Cleanup automático
    - API completa de gestión
    - Audit trail completo
    """
    
    def __init__(self):
        super().__init__()
        self.notification_service = NotificationService()
        self.analytics_service = AnalyticsService()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.providers = self._initialize_providers()
        self.virus_scanner = self._initialize_virus_scanner()
        self._setup_temp_directory()
    
    def _initialize_providers(self) -> Dict[str, StorageProviderInterface]:
        """Inicializar proveedores de almacenamiento"""
        providers = {}
        
        # Local storage (siempre disponible)
        providers[StorageProvider.LOCAL.value] = LocalStorageProvider()
        
        # AWS S3
        if current_app.config.get('AWS_S3_BUCKET'):
            providers[StorageProvider.AWS_S3.value] = S3StorageProvider()
        
        # Google Cloud Storage
        if current_app.config.get('GCS_BUCKET'):
            providers[StorageProvider.GOOGLE_CLOUD.value] = GoogleCloudStorageProvider()
        
        # Azure Blob Storage
        if current_app.config.get('AZURE_STORAGE_CONNECTION_STRING'):
            # providers[StorageProvider.AZURE_BLOB.value] = AzureStorageProvider()
            pass
        
        return providers
    
    def _initialize_virus_scanner(self):
        """Inicializar escáner de virus"""
        try:
            return clamd.ClamdUnixSocket()
        except Exception as e:
            logger.warning(f"No se pudo inicializar ClamAV: {str(e)}")
            return None
    
    def _setup_temp_directory(self):
        """Configurar directorio temporal"""
        self.temp_dir = Path(tempfile.gettempdir()) / 'file_storage_service'
        self.temp_dir.mkdir(exist_ok=True)
    
    @log_activity("file_uploaded")
    @rate_limit(max_requests=100, window=3600)  # 100 uploads per hour
    def upload_file(
        self,
        file: Union[FileStorage, BinaryIO, str],
        user_id: int,
        filename: Optional[str] = None,
        category: str = FileCategory.OTHER.value,
        config: Optional[UploadConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None
    ) -> FileUploadResult:
        """
        Subir archivo con validación y procesamiento completo
        
        Args:
            file: Archivo a subir (FileStorage, BinaryIO, o path)
            user_id: ID del usuario que sube el archivo
            filename: Nombre personalizado del archivo
            category: Categoría del archivo
            config: Configuración de upload
            metadata: Metadata adicional
            related_entity_type: Tipo de entidad relacionada (project, mentorship, etc.)
            related_entity_id: ID de la entidad relacionada
            
        Returns:
            FileUploadResult: Resultado del upload
        """
        start_time = datetime.utcnow()
        
        try:
            # Configuración por defecto
            if not config:
                config = self._get_default_config(category)
            
            # Verificar cuota del usuario
            self._check_user_quota(user_id, config.max_file_size)
            
            # Procesar archivo según el tipo de input
            temp_file_path = self._process_file_input(file, filename)
            
            # Extraer metadata del archivo
            file_metadata = self._extract_file_metadata(temp_file_path, filename)
            
            # Validaciones de seguridad
            self._validate_file(temp_file_path, file_metadata, config)
            
            # Escaneo antivirus
            scan_result = None
            if config.require_virus_scan:
                scan_result = self._scan_file(temp_file_path)
                if scan_result == ScanStatus.INFECTED.value:
                    raise SecurityError("Archivo infectado detectado")
            
            # Generar ID único para el archivo
            file_id = self._generate_file_id()
            
            # Procesar archivo (optimización, compresión, etc.)
            processed_file_path = self._process_file(
                temp_file_path, file_metadata, config
            )
            
            # Generar clave de almacenamiento
            storage_key = self._generate_storage_key(
                user_id, file_id, file_metadata.filename, category
            )
            
            # Subir a proveedor de almacenamiento
            provider = self.providers[config.storage_provider]
            storage_path = provider.upload_file(
                processed_file_path, 
                storage_key,
                self._prepare_storage_metadata(file_metadata, metadata)
            )
            
            # Generar thumbnail si es imagen
            thumbnail_url = None
            if (config.generate_thumbnails and 
                file_metadata.category == FileCategory.IMAGE.value):
                thumbnail_url = self._generate_thumbnail(
                    processed_file_path, file_id, provider
                )
            
            # Guardar en base de datos
            file_upload = self._save_file_record(
                file_id=file_id,
                user_id=user_id,
                file_metadata=file_metadata,
                storage_key=storage_key,
                storage_provider=config.storage_provider,
                category=category,
                scan_result=scan_result,
                thumbnail_url=thumbnail_url,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                custom_metadata=metadata
            )
            
            # Obtener URL del archivo
            file_url = provider.get_file_url(storage_key)
            
            # Actualizar cuota del usuario
            self._update_user_quota(user_id, file_metadata.file_size)
            
            # Limpiar archivos temporales
            self._cleanup_temp_files([temp_file_path, processed_file_path])
            
            # Registrar analytics
            self.analytics_service.track_event(
                event_type='file_uploaded',
                user_id=user_id,
                properties={
                    'file_id': file_id,
                    'file_size': file_metadata.file_size,
                    'file_category': category,
                    'storage_provider': config.storage_provider,
                    'scan_result': scan_result
                }
            )
            
            # Calcular tiempo de procesamiento
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = FileUploadResult(
                success=True,
                file_id=file_id,
                file_url=file_url,
                thumbnail_url=thumbnail_url,
                file_size=file_metadata.file_size,
                file_hash=file_metadata.file_hash,
                scan_result=scan_result,
                processing_time=processing_time
            )
            
            logger.info(f"Archivo subido exitosamente: {file_id} por usuario {user_id}")
            return result
            
        except Exception as e:
            # Limpiar en caso de error
            if 'temp_file_path' in locals():
                self._cleanup_temp_files([temp_file_path])
            
            logger.error(f"Error subiendo archivo: {str(e)}")
            
            return FileUploadResult(
                success=False,
                error_message=str(e),
                processing_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    @rate_limit(max_requests=1000, window=3600)  # 1000 downloads per hour
    def download_file(
        self,
        file_id: str,
        user_id: int,
        version: Optional[int] = None,
        track_download: bool = True
    ) -> Tuple[str, str]:
        """
        Descargar archivo
        
        Args:
            file_id: ID del archivo
            user_id: ID del usuario que descarga
            version: Versión específica del archivo
            track_download: Trackear la descarga
            
        Returns:
            Tuple[str, str]: (ruta_local, nombre_archivo)
        """
        try:
            # Obtener información del archivo
            file_upload = self._get_file_record(file_id)
            
            if not file_upload:
                raise NotFoundError(f"Archivo {file_id} no encontrado")
            
            # Verificar permisos
            if not self._can_access_file(file_upload, user_id):
                raise PermissionError("No tiene permisos para acceder a este archivo")
            
            # Obtener versión específica si se solicita
            if version:
                file_version = FileVersion.query.filter_by(
                    file_id=file_id,
                    version_number=version
                ).first()
                
                if not file_version:
                    raise NotFoundError(f"Versión {version} no encontrada")
                
                storage_key = file_version.storage_key
                filename = file_version.filename
            else:
                storage_key = file_upload.storage_key
                filename = file_upload.original_filename
            
            # Descargar del proveedor
            provider = self.providers[file_upload.storage_provider]
            
            # Crear archivo temporal para descarga
            temp_file = self.temp_dir / f"download_{file_id}_{uuid.uuid4().hex}"
            
            if provider.download_file(storage_key, str(temp_file)):
                # Trackear descarga
                if track_download:
                    self._track_download(file_upload, user_id)
                
                return str(temp_file), filename
            else:
                raise ExternalServiceError("Error descargando archivo del proveedor")
                
        except Exception as e:
            logger.error(f"Error descargando archivo {file_id}: {str(e)}")
            raise BusinessLogicError(f"Error descargando archivo: {str(e)}")
    
    def get_file_url(
        self,
        file_id: str,
        user_id: int,
        expires_in: int = 3600,
        download: bool = False
    ) -> str:
        """
        Obtener URL del archivo
        
        Args:
            file_id: ID del archivo
            user_id: ID del usuario
            expires_in: Tiempo de expiración en segundos
            download: Si debe forzar descarga
            
        Returns:
            str: URL del archivo
        """
        try:
            file_upload = self._get_file_record(file_id)
            
            if not file_upload:
                raise NotFoundError(f"Archivo {file_id} no encontrado")
            
            # Verificar permisos
            if not self._can_access_file(file_upload, user_id):
                raise PermissionError("No tiene permisos para acceder a este archivo")
            
            # Obtener URL del proveedor
            provider = self.providers[file_upload.storage_provider]
            url = provider.get_file_url(file_upload.storage_key, expires_in)
            
            # Agregar parámetros de descarga si es necesario
            if download:
                url += f"&response-content-disposition=attachment;filename={file_upload.original_filename}"
            
            return url
            
        except Exception as e:
            logger.error(f"Error obteniendo URL de archivo {file_id}: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo URL: {str(e)}")
    
    @log_activity("file_deleted")
    def delete_file(
        self,
        file_id: str,
        user_id: int,
        soft_delete: bool = True
    ) -> bool:
        """
        Eliminar archivo
        
        Args:
            file_id: ID del archivo
            user_id: ID del usuario
            soft_delete: Eliminación lógica (True) o física (False)
            
        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            file_upload = self._get_file_record(file_id)
            
            if not file_upload:
                raise NotFoundError(f"Archivo {file_id} no encontrado")
            
            # Verificar permisos
            if not self._can_delete_file(file_upload, user_id):
                raise PermissionError("No tiene permisos para eliminar este archivo")
            
            if soft_delete:
                # Eliminación lógica
                file_upload.status = FileStatus.DELETED.value
                file_upload.deleted_at = datetime.utcnow()
                file_upload.deleted_by_id = user_id
                db.session.commit()
            else:
                # Eliminación física
                provider = self.providers[file_upload.storage_provider]
                
                # Eliminar del proveedor
                provider.delete_file(file_upload.storage_key)
                
                # Eliminar thumbnail si existe
                if file_upload.thumbnail_url:
                    thumbnail_key = self._extract_key_from_url(file_upload.thumbnail_url)
                    if thumbnail_key:
                        provider.delete_file(thumbnail_key)
                
                # Eliminar versiones
                versions = FileVersion.query.filter_by(file_id=file_id).all()
                for version in versions:
                    provider.delete_file(version.storage_key)
                    db.session.delete(version)
                
                # Eliminar registro de base de datos
                db.session.delete(file_upload)
                db.session.commit()
            
            # Actualizar cuota del usuario
            self._update_user_quota(user_id, -file_upload.file_size)
            
            # Registrar analytics
            self.analytics_service.track_event(
                event_type='file_deleted',
                user_id=user_id,
                properties={
                    'file_id': file_id,
                    'soft_delete': soft_delete
                }
            )
            
            logger.info(f"Archivo {'eliminado' if soft_delete else 'borrado'}: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando archivo {file_id}: {str(e)}")
            raise BusinessLogicError(f"Error eliminando archivo: {str(e)}")
    
    def create_file_version(
        self,
        file_id: str,
        new_file: Union[FileStorage, BinaryIO, str],
        user_id: int,
        version_notes: Optional[str] = None
    ) -> FileUploadResult:
        """
        Crear nueva versión de archivo existente
        
        Args:
            file_id: ID del archivo original
            new_file: Nuevo archivo
            user_id: ID del usuario
            version_notes: Notas de la versión
            
        Returns:
            FileUploadResult: Resultado del upload de la nueva versión
        """
        try:
            # Obtener archivo original
            original_file = self._get_file_record(file_id)
            
            if not original_file:
                raise NotFoundError(f"Archivo original {file_id} no encontrado")
            
            # Verificar permisos
            if not self._can_edit_file(original_file, user_id):
                raise PermissionError("No tiene permisos para crear versiones de este archivo")
            
            # Obtener próximo número de versión
            next_version = self._get_next_version_number(file_id)
            
            # Configuración basada en el archivo original
            config = UploadConfig(
                storage_provider=original_file.storage_provider,
                max_file_size=current_app.config.get('MAX_FILE_SIZE', 100 * 1024 * 1024)
            )
            
            # Procesar nuevo archivo
            temp_file_path = self._process_file_input(new_file, original_file.original_filename)
            file_metadata = self._extract_file_metadata(temp_file_path, original_file.original_filename)
            
            # Validar archivo
            self._validate_file(temp_file_path, file_metadata, config)
            
            # Generar clave de almacenamiento para la versión
            version_key = f"{original_file.storage_key}_v{next_version}"
            
            # Subir nueva versión
            provider = self.providers[original_file.storage_provider]
            storage_path = provider.upload_file(
                temp_file_path,
                version_key,
                self._prepare_storage_metadata(file_metadata, {'version': next_version})
            )
            
            # Crear registro de versión
            file_version = FileVersion(
                file_id=file_id,
                version_number=next_version,
                filename=file_metadata.filename,
                file_size=file_metadata.file_size,
                file_hash=file_metadata.file_hash,
                storage_key=version_key,
                storage_provider=original_file.storage_provider,
                created_by_id=user_id,
                created_at=datetime.utcnow(),
                version_notes=version_notes
            )
            
            db.session.add(file_version)
            
            # Actualizar archivo principal con la nueva versión
            original_file.current_version = next_version
            original_file.file_size = file_metadata.file_size
            original_file.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Limpiar archivo temporal
            self._cleanup_temp_files([temp_file_path])
            
            # Obtener URL de la nueva versión
            file_url = provider.get_file_url(version_key)
            
            result = FileUploadResult(
                success=True,
                file_id=file_id,
                file_url=file_url,
                file_size=file_metadata.file_size,
                file_hash=file_metadata.file_hash
            )
            
            logger.info(f"Nueva versión {next_version} creada para archivo {file_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error creando versión de archivo: {str(e)}")
            raise BusinessLogicError(f"Error creando versión: {str(e)}")
    
    def share_file(
        self,
        file_id: str,
        user_id: int,
        shared_with_user_id: Optional[int] = None,
        shared_with_email: Optional[str] = None,
        access_level: str = AccessLevel.SHARED.value,
        expires_at: Optional[datetime] = None,
        password: Optional[str] = None
    ) -> str:
        """
        Compartir archivo con otro usuario
        
        Args:
            file_id: ID del archivo
            user_id: ID del usuario que comparte
            shared_with_user_id: ID del usuario destinatario
            shared_with_email: Email del destinatario (para usuarios externos)
            access_level: Nivel de acceso
            expires_at: Fecha de expiración
            password: Contraseña para acceso
            
        Returns:
            str: Token de compartición o URL pública
        """
        try:
            file_upload = self._get_file_record(file_id)
            
            if not file_upload:
                raise NotFoundError(f"Archivo {file_id} no encontrado")
            
            # Verificar permisos
            if not self._can_share_file(file_upload, user_id):
                raise PermissionError("No tiene permisos para compartir este archivo")
            
            # Generar token de compartición
            share_token = self._generate_share_token()
            
            # Crear registro de compartición
            file_share = FileShare(
                file_id=file_id,
                shared_by_id=user_id,
                shared_with_user_id=shared_with_user_id,
                shared_with_email=shared_with_email,
                share_token=share_token,
                access_level=access_level,
                expires_at=expires_at,
                password_hash=generate_hash(password) if password else None,
                created_at=datetime.utcnow()
            )
            
            db.session.add(file_share)
            db.session.commit()
            
            # Generar URL de compartición
            share_url = url_for(
                'api.shared_file',
                token=share_token,
                _external=True
            )
            
            # Enviar notificación si es usuario interno
            if shared_with_user_id:
                self.notification_service.send_notification(
                    user_id=shared_with_user_id,
                    type='file_shared',
                    title='Archivo compartido contigo',
                    message=f'El archivo "{file_upload.original_filename}" ha sido compartido contigo',
                    data={
                        'file_id': file_id,
                        'share_url': share_url,
                        'shared_by': user_id
                    }
                )
            
            logger.info(f"Archivo {file_id} compartido con token {share_token}")
            return share_url
            
        except Exception as e:
            logger.error(f"Error compartiendo archivo: {str(e)}")
            raise BusinessLogicError(f"Error compartiendo archivo: {str(e)}")
    
    def get_storage_stats(
        self,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> StorageStats:
        """
        Obtener estadísticas de almacenamiento
        
        Args:
            user_id: ID del usuario (para stats individuales)
            organization_id: ID de organización (para stats organizacionales)
            
        Returns:
            StorageStats: Estadísticas de almacenamiento
        """
        try:
            query = FileUpload.query.filter_by(status=FileStatus.ACTIVE.value)
            
            if user_id:
                query = query.filter_by(uploaded_by_id=user_id)
            elif organization_id:
                # Filtrar por organización (requiere join con tabla de usuarios)
                query = query.join(User).filter(User.organization_id == organization_id)
            
            files = query.all()
            
            # Calcular estadísticas
            total_files = len(files)
            total_size = sum(f.file_size for f in files)
            
            # Agrupar por categoría
            files_by_category = {}
            size_by_category = {}
            
            for file in files:
                category = file.category
                files_by_category[category] = files_by_category.get(category, 0) + 1
                size_by_category[category] = size_by_category.get(category, 0) + file.file_size
            
            # Agrupar por proveedor
            files_by_provider = {}
            for file in files:
                provider = file.storage_provider
                files_by_provider[provider] = files_by_provider.get(provider, 0) + 1
            
            # Estadísticas mensuales
            current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_uploads = query.filter(FileUpload.created_at >= current_month).count()
            
            # Calcular uso de cuota
            quota_used_percentage = 0.0
            if user_id:
                quota = StorageQuota.query.filter_by(user_id=user_id).first()
                if quota and quota.quota_bytes > 0:
                    quota_used_percentage = (quota.used_bytes / quota.quota_bytes) * 100
            
            return StorageStats(
                total_files=total_files,
                total_size_bytes=total_size,
                files_by_category=files_by_category,
                size_by_category=size_by_category,
                files_by_provider=files_by_provider,
                monthly_uploads=monthly_uploads,
                monthly_downloads=0,  # Esto requeriría tabla de tracking de descargas
                quota_used_percentage=quota_used_percentage
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de almacenamiento: {str(e)}")
            raise BusinessLogicError(f"Error obteniendo estadísticas: {str(e)}")
    
    # Métodos privados de utilidad
    def _get_default_config(self, category: str) -> UploadConfig:
        """Obtener configuración por defecto según categoría"""
        configs = {
            FileCategory.IMAGE.value: UploadConfig(
                max_file_size=10 * 1024 * 1024,  # 10MB
                allowed_extensions=['.jpg', '.jpeg', '.png', '.gif', '.webp'],
                auto_optimize=True,
                generate_thumbnails=True,
                compress_file=True
            ),
            FileCategory.DOCUMENT.value: UploadConfig(
                max_file_size=50 * 1024 * 1024,  # 50MB
                allowed_extensions=['.pdf', '.doc', '.docx', '.txt', '.rtf'],
                add_watermark=True,
                encrypt_file=True
            ),
            FileCategory.VIDEO.value: UploadConfig(
                max_file_size=500 * 1024 * 1024,  # 500MB
                allowed_extensions=['.mp4', '.avi', '.mov', '.wmv'],
                compress_file=True,
                storage_provider=StorageProvider.AWS_S3.value
            )
        }
        
        return configs.get(category, UploadConfig())
    
    def _check_user_quota(self, user_id: int, file_size: int):
        """Verificar cuota del usuario"""
        quota = StorageQuota.query.filter_by(user_id=user_id).first()
        
        if not quota:
            # Crear cuota por defecto
            default_quota = current_app.config.get('DEFAULT_USER_QUOTA', 1024 * 1024 * 1024)  # 1GB
            quota = StorageQuota(
                user_id=user_id,
                quota_bytes=default_quota,
                used_bytes=0,
                created_at=datetime.utcnow()
            )
            db.session.add(quota)
            db.session.commit()
        
        if quota.used_bytes + file_size > quota.quota_bytes:
            available = quota.quota_bytes - quota.used_bytes
            raise ValidationError(
                f"Cuota excedida. Disponible: {format_file_size(available)}, "
                f"Requerido: {format_file_size(file_size)}"
            )
    
    def _process_file_input(
        self, 
        file: Union[FileStorage, BinaryIO, str], 
        filename: Optional[str]
    ) -> str:
        """Procesar input de archivo y crear archivo temporal"""
        temp_file = self.temp_dir / f"upload_{uuid.uuid4().hex}"
        
        try:
            if isinstance(file, str):
                # Es una ruta de archivo
                shutil.copy2(file, temp_file)
            elif isinstance(file, FileStorage):
                # Es un FileStorage de Flask
                file.save(str(temp_file))
            else:
                # Es un objeto de archivo binario
                with open(temp_file, 'wb') as f:
                    shutil.copyfileobj(file, f)
            
            return str(temp_file)
            
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise ValidationError(f"Error procesando archivo: {str(e)}")
    
    def _extract_file_metadata(self, file_path: str, filename: Optional[str]) -> FileMetadata:
        """Extraer metadata del archivo"""
        try:
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            
            # Detectar tipo MIME
            mime_type = magic.from_file(file_path, mime=True)
            
            # Generar hash del archivo
            file_hash = self._calculate_file_hash(file_path)
            
            # Nombre del archivo
            if not filename:
                filename = f"file_{uuid.uuid4().hex}"
            
            original_filename = filename
            secure_name = secure_filename(filename)
            
            # Determinar categoría
            category = self._determine_file_category(mime_type, secure_name)
            
            # Extraer dimensiones si es imagen
            dimensions = None
            duration = None
            exif_data = None
            
            if category == FileCategory.IMAGE.value:
                try:
                    with Image.open(file_path) as img:
                        dimensions = img.size
                        exif_data = self._extract_exif_data(img)
                except Exception as e:
                    logger.warning(f"Error extrayendo datos de imagen: {str(e)}")
            
            elif category == FileCategory.VIDEO.value:
                # Aquí se podría usar ffmpeg para extraer duración
                pass
            
            return FileMetadata(
                filename=secure_name,
                original_filename=original_filename,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                category=category,
                dimensions=dimensions,
                duration=duration,
                exif_data=exif_data,
                created_date=datetime.fromtimestamp(file_stat.st_ctime),
                modified_date=datetime.fromtimestamp(file_stat.st_mtime)
            )
            
        except Exception as e:
            logger.error(f"Error extrayendo metadata: {str(e)}")
            raise ValidationError(f"Error procesando archivo: {str(e)}")
    
    def _validate_file(
        self, 
        file_path: str, 
        metadata: FileMetadata, 
        config: UploadConfig
    ):
        """Validar archivo según configuración"""
        # Validar tamaño
        if metadata.file_size > config.max_file_size:
            raise ValidationError(
                f"Archivo muy grande: {format_file_size(metadata.file_size)}. "
                f"Máximo permitido: {format_file_size(config.max_file_size)}"
            )
        
        # Validar extensión
        if config.allowed_extensions:
            file_ext = Path(metadata.filename).suffix.lower()
            if file_ext not in config.allowed_extensions:
                raise ValidationError(
                    f"Extensión no permitida: {file_ext}. "
                    f"Permitidas: {', '.join(config.allowed_extensions)}"
                )
        
        # Validar tipo MIME
        dangerous_mimes = [
            'application/x-executable',
            'application/x-msdownload',
            'application/x-msdos-program'
        ]
        
        if metadata.mime_type in dangerous_mimes:
            raise SecurityError(f"Tipo de archivo no permitido: {metadata.mime_type}")
        
        # Validar contenido del archivo
        self._validate_file_content(file_path, metadata)
    
    def _validate_file_content(self, file_path: str, metadata: FileMetadata):
        """Validar contenido del archivo para detectar archivos maliciosos"""
        try:
            # Leer primeros bytes para detectar magic numbers
            with open(file_path, 'rb') as f:
                header = f.read(1024)
            
            # Detectar ejecutables por magic numbers
            executable_signatures = [
                b'\x4d\x5a',  # PE executable
                b'\x7f\x45\x4c\x46',  # ELF executable
                b'\xfe\xed\xfa\xce',  # Mach-O
                b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit
            ]
            
            for signature in executable_signatures:
                if header.startswith(signature):
                    raise SecurityError("Archivo ejecutable detectado")
            
            # Validar que el tipo MIME coincida con el contenido
            detected_mime = magic.from_buffer(header, mime=True)
            if detected_mime != metadata.mime_type:
                logger.warning(
                    f"Tipo MIME inconsistente: declarado={metadata.mime_type}, "
                    f"detectado={detected_mime}"
                )
            
        except Exception as e:
            logger.error(f"Error validando contenido: {str(e)}")
            raise SecurityError("Error validando archivo")
    
    def _scan_file(self, file_path: str) -> str:
        """Escanear archivo con antivirus"""
        if not self.virus_scanner:
            logger.warning("Escáner de virus no disponible")
            return ScanStatus.ERROR.value
        
        try:
            scan_result = self.virus_scanner.scan(file_path)
            
            if scan_result[0] == 'OK':
                return ScanStatus.CLEAN.value
            elif scan_result[0] == 'FOUND':
                logger.error(f"Virus detectado: {scan_result[1]}")
                return ScanStatus.INFECTED.value
            else:
                logger.error(f"Error en escaneo: {scan_result}")
                return ScanStatus.ERROR.value
                
        except Exception as e:
            logger.error(f"Error escaneando archivo: {str(e)}")
            return ScanStatus.ERROR.value
    
    def _process_file(
        self, 
        file_path: str, 
        metadata: FileMetadata, 
        config: UploadConfig
    ) -> str:
        """Procesar archivo (optimización, compresión, etc.)"""
        processed_path = file_path
        
        try:
            # Optimización de imágenes
            if (config.auto_optimize and 
                metadata.category == FileCategory.IMAGE.value):
                processed_path = self._optimize_image(processed_path, metadata)
            
            # Compresión
            if config.compress_file:
                processed_path = self._compress_file(processed_path, metadata)
            
            # Encriptación
            if config.encrypt_file:
                processed_path = self._encrypt_file(processed_path)
            
            # Watermark
            if (config.add_watermark and 
                metadata.category in [FileCategory.IMAGE.value, FileCategory.DOCUMENT.value]):
                processed_path = self._add_watermark(processed_path, metadata)
            
            return processed_path
            
        except Exception as e:
            logger.error(f"Error procesando archivo: {str(e)}")
            return file_path  # Retornar archivo original si falla el procesamiento
    
    def _generate_file_id(self) -> str:
        """Generar ID único para archivo"""
        return f"file_{uuid.uuid4().hex}"
    
    def _generate_storage_key(
        self, 
        user_id: int, 
        file_id: str, 
        filename: str, 
        category: str
    ) -> str:
        """Generar clave de almacenamiento"""
        # Estructura: año/mes/usuario/categoría/file_id/filename
        now = datetime.utcnow()
        return f"{now.year}/{now.month:02d}/{user_id}/{category}/{file_id}/{filename}"
    
    def _prepare_storage_metadata(
        self, 
        file_metadata: FileMetadata, 
        custom_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Preparar metadata para almacenamiento"""
        metadata = {
            'original_filename': file_metadata.original_filename,
            'file_size': str(file_metadata.file_size),
            'mime_type': file_metadata.mime_type,
            'file_hash': file_metadata.file_hash,
            'category': file_metadata.category,
            'upload_timestamp': datetime.utcnow().isoformat()
        }
        
        if file_metadata.dimensions:
            metadata['width'] = str(file_metadata.dimensions[0])
            metadata['height'] = str(file_metadata.dimensions[1])
        
        if custom_metadata:
            for key, value in custom_metadata.items():
                metadata[f"custom_{key}"] = str(value)
        
        return metadata
    
    def _generate_thumbnail(
        self, 
        image_path: str, 
        file_id: str, 
        provider: StorageProviderInterface
    ) -> Optional[str]:
        """Generar thumbnail para imagen"""
        try:
            thumbnail_path = self.temp_dir / f"thumb_{file_id}.jpg"
            
            # Generar thumbnail
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Redimensionar manteniendo aspecto
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                
                # Guardar como JPEG
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            
            # Subir thumbnail
            thumbnail_key = f"thumbnails/{file_id}_thumb.jpg"
            provider.upload_file(str(thumbnail_path), thumbnail_key, {
                'type': 'thumbnail',
                'parent_file': file_id
            })
            
            # Limpiar archivo temporal
            thumbnail_path.unlink()
            
            # Retornar URL del thumbnail
            return provider.get_file_url(thumbnail_key)
            
        except Exception as e:
            logger.error(f"Error generando thumbnail: {str(e)}")
            return None
    
    def _save_file_record(
        self,
        file_id: str,
        user_id: int,
        file_metadata: FileMetadata,
        storage_key: str,
        storage_provider: str,
        category: str,
        scan_result: Optional[str],
        thumbnail_url: Optional[str],
        related_entity_type: Optional[str],
        related_entity_id: Optional[int],
        custom_metadata: Optional[Dict[str, Any]]
    ) -> FileUpload:
        """Guardar registro de archivo en base de datos"""
        try:
            file_upload = FileUpload(
                id=file_id,
                uploaded_by_id=user_id,
                original_filename=file_metadata.original_filename,
                filename=file_metadata.filename,
                file_size=file_metadata.file_size,
                mime_type=file_metadata.mime_type,
                file_hash=file_metadata.file_hash,
                category=category,
                storage_key=storage_key,
                storage_provider=storage_provider,
                thumbnail_url=thumbnail_url,
                status=FileStatus.ACTIVE.value,
                scan_status=scan_result or ScanStatus.PENDING.value,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                metadata=json.dumps(custom_metadata) if custom_metadata else None,
                dimensions_width=file_metadata.dimensions[0] if file_metadata.dimensions else None,
                dimensions_height=file_metadata.dimensions[1] if file_metadata.dimensions else None,
                created_at=datetime.utcnow(),
                current_version=1
            )
            
            db.session.add(file_upload)
            db.session.commit()
            
            return file_upload
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error guardando archivo en BD: {str(e)}")
            raise BusinessLogicError("Error guardando información del archivo")
    
    def _update_user_quota(self, user_id: int, size_delta: int):
        """Actualizar cuota del usuario"""
        try:
            quota = StorageQuota.query.filter_by(user_id=user_id).first()
            
            if quota:
                quota.used_bytes += size_delta
                quota.updated_at = datetime.utcnow()
                db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error actualizando cuota: {str(e)}")
    
    def _cleanup_temp_files(self, file_paths: List[str]):
        """Limpiar archivos temporales"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Error limpiando archivo temporal {file_path}: {str(e)}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calcular hash SHA-256 del archivo"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _determine_file_category(self, mime_type: str, filename: str) -> str:
        """Determinar categoría del archivo"""
        # Mapeo de tipos MIME a categorías
        category_mapping = {
            'image/': FileCategory.IMAGE.value,
            'video/': FileCategory.VIDEO.value,
            'audio/': FileCategory.AUDIO.value,
            'application/pdf': FileCategory.DOCUMENT.value,
            'application/msword': FileCategory.DOCUMENT.value,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileCategory.DOCUMENT.value,
            'application/vnd.ms-excel': FileCategory.SPREADSHEET.value,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileCategory.SPREADSHEET.value,
            'application/vnd.ms-powerpoint': FileCategory.PRESENTATION.value,
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': FileCategory.PRESENTATION.value,
            'application/zip': FileCategory.ARCHIVE.value,
            'application/x-rar-compressed': FileCategory.ARCHIVE.value,
            'text/': FileCategory.CODE.value if filename.endswith(('.py', '.js', '.html', '.css', '.sql')) else FileCategory.DOCUMENT.value
        }
        
        # Buscar por tipo MIME exacto
        if mime_type in category_mapping:
            return category_mapping[mime_type]
        
        # Buscar por prefijo
        for prefix, category in category_mapping.items():
            if mime_type.startswith(prefix):
                return category
        
        return FileCategory.OTHER.value
    
    def _extract_exif_data(self, img: Image.Image) -> Optional[Dict[str, Any]]:
        """Extraer datos EXIF de imagen"""
        try:
            exif = img._getexif()
            if exif:
                return {str(k): str(v) for k, v in exif.items() if isinstance(v, (str, int, float))}
        except Exception as e:
            logger.warning(f"Error extrayendo EXIF: {str(e)}")
        return None
    
    def _get_file_record(self, file_id: str) -> Optional[FileUpload]:
        """Obtener registro de archivo"""
        return FileUpload.query.filter_by(id=file_id).first()
    
    def _can_access_file(self, file_upload: FileUpload, user_id: int) -> bool:
        """Verificar si el usuario puede acceder al archivo"""
        # El propietario siempre puede acceder
        if file_upload.uploaded_by_id == user_id:
            return True
        
        # Verificar si está compartido con el usuario
        share = FileShare.query.filter_by(
            file_id=file_upload.id,
            shared_with_user_id=user_id
        ).first()
        
        if share and (not share.expires_at or share.expires_at > datetime.utcnow()):
            return True
        
        # Administradores pueden acceder a todo
        user = User.query.get(user_id)
        if user and user.role == USER_ROLES.ADMIN:
            return True
        
        return False
    
    def _can_delete_file(self, file_upload: FileUpload, user_id: int) -> bool:
        """Verificar si el usuario puede eliminar el archivo"""
        # Solo el propietario y administradores pueden eliminar
        if file_upload.uploaded_by_id == user_id:
            return True
        
        user = User.query.get(user_id)
        if user and user.role == USER_ROLES.ADMIN:
            return True
        
        return False
    
    def _can_edit_file(self, file_upload: FileUpload, user_id: int) -> bool:
        """Verificar si el usuario puede editar el archivo"""
        return self._can_delete_file(file_upload, user_id)
    
    def _can_share_file(self, file_upload: FileUpload, user_id: int) -> bool:
        """Verificar si el usuario puede compartir el archivo"""
        return self._can_access_file(file_upload, user_id)
    
    def _track_download(self, file_upload: FileUpload, user_id: int):
        """Trackear descarga de archivo"""
        try:
            # Incrementar contador de descargas
            file_upload.download_count = (file_upload.download_count or 0) + 1
            file_upload.last_downloaded_at = datetime.utcnow()
            
            # Registrar en analytics
            self.analytics_service.track_event(
                event_type='file_downloaded',
                user_id=user_id,
                properties={
                    'file_id': file_upload.id,
                    'file_category': file_upload.category,
                    'file_size': file_upload.file_size
                }
            )
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error trackeando descarga: {str(e)}")
    
    def _extract_key_from_url(self, url: str) -> Optional[str]:
        """Extraer clave de almacenamiento desde URL"""
        try:
            parsed = urlparse(url)
            # Remover el primer slash
            return parsed.path.lstrip('/')
        except Exception:
            return None
    
    def _get_next_version_number(self, file_id: str) -> int:
        """Obtener próximo número de versión"""
        max_version = db.session.query(func.max(FileVersion.version_number)).filter_by(
            file_id=file_id
        ).scalar()
        
        return (max_version or 0) + 1
    
    def _generate_share_token(self) -> str:
        """Generar token de compartición"""
        return f"share_{uuid.uuid4().hex}"
    
    def _optimize_image(self, image_path: str, metadata: FileMetadata) -> str:
        """Optimizar imagen"""
        try:
            optimized_path = self.temp_dir / f"optimized_{uuid.uuid4().hex}.jpg"
            
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Para imágenes con transparencia, usar fondo blanco
                    if img.mode == 'RGBA':
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1])
                        img = background
                    else:
                        img = img.convert('RGB')
                
                # Redimensionar si es muy grande
                max_dimension = 2048
                if max(img.size) > max_dimension:
                    ratio = max_dimension / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Optimizar y guardar
                img.save(
                    optimized_path,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
            
            return str(optimized_path)
            
        except Exception as e:
            logger.error(f"Error optimizando imagen: {str(e)}")
            return image_path
    
    def _compress_file(self, file_path: str, metadata: FileMetadata) -> str:
        """Comprimir archivo"""
        try:
            # Solo comprimir archivos de texto y documentos
            if not metadata.mime_type.startswith(('text/', 'application/json', 'application/xml')):
                return file_path
            
            compressed_path = self.temp_dir / f"compressed_{uuid.uuid4().hex}.gz"
            
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Solo usar compresión si reduce significativamente el tamaño
            original_size = os.path.getsize(file_path)
            compressed_size = os.path.getsize(compressed_path)
            
            if compressed_size < original_size * 0.8:  # 20% de reducción mínima
                return str(compressed_path)
            else:
                compressed_path.unlink()
                return file_path
                
        except Exception as e:
            logger.error(f"Error comprimiendo archivo: {str(e)}")
            return file_path
    
    def _encrypt_file(self, file_path: str) -> str:
        """Encriptar archivo"""
        try:
            encrypted_path = self.temp_dir / f"encrypted_{uuid.uuid4().hex}"
            
            # Generar clave de encriptación
            encryption_key = os.urandom(32)  # 256-bit key
            
            # Encriptar archivo
            encrypt_file(file_path, str(encrypted_path), encryption_key)
            
            # Guardar clave de forma segura (en implementación real, usar KMS)
            key_path = str(encrypted_path) + '.key'
            with open(key_path, 'wb') as f:
                f.write(encryption_key)
            
            return str(encrypted_path)
            
        except Exception as e:
            logger.error(f"Error encriptando archivo: {str(e)}")
            return file_path
    
    def _add_watermark(self, file_path: str, metadata: FileMetadata) -> str:
        """Agregar watermark al archivo"""
        try:
            if metadata.category != FileCategory.IMAGE.value:
                return file_path
            
            watermarked_path = self.temp_dir / f"watermarked_{uuid.uuid4().hex}.jpg"
            
            with Image.open(file_path) as img:
                # Crear watermark
                watermark_text = current_app.config.get('WATERMARK_TEXT', 'Ecosistema Emprendimiento')
                
                # Agregar watermark
                watermarked = add_watermark(img, watermark_text)
                
                # Guardar imagen con watermark
                watermarked.save(watermarked_path, 'JPEG', quality=90)
            
            return str(watermarked_path)
            
        except Exception as e:
            logger.error(f"Error agregando watermark: {str(e)}")
            return file_path
    
    def cleanup_expired_files(self) -> Dict[str, int]:
        """Limpiar archivos expirados y temporales"""
        try:
            stats = {
                'deleted_files': 0,
                'cleaned_temp': 0,
                'freed_bytes': 0
            }
            
            # Limpiar archivos marcados como eliminados hace más de 30 días
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            expired_files = FileUpload.query.filter(
                FileUpload.status == FileStatus.DELETED.value,
                FileUpload.deleted_at < cutoff_date
            ).all()
            
            for file_upload in expired_files:
                try:
                    # Eliminar del proveedor
                    provider = self.providers[file_upload.storage_provider]
                    provider.delete_file(file_upload.storage_key)
                    
                    # Eliminar thumbnail
                    if file_upload.thumbnail_url:
                        thumbnail_key = self._extract_key_from_url(file_upload.thumbnail_url)
                        if thumbnail_key:
                            provider.delete_file(thumbnail_key)
                    
                    # Eliminar versiones
                    versions = FileVersion.query.filter_by(file_id=file_upload.id).all()
                    for version in versions:
                        provider.delete_file(version.storage_key)
                        db.session.delete(version)
                    
                    stats['freed_bytes'] += file_upload.file_size
                    
                    # Eliminar registro
                    db.session.delete(file_upload)
                    stats['deleted_files'] += 1
                    
                except Exception as e:
                    logger.error(f"Error eliminando archivo {file_upload.id}: {str(e)}")
            
            # Limpiar archivos temporales
            temp_files = list(self.temp_dir.glob('*'))
            for temp_file in temp_files:
                try:
                    if temp_file.is_file() and temp_file.stat().st_mtime < (datetime.utcnow() - timedelta(hours=1)).timestamp():
                        temp_file.unlink()
                        stats['cleaned_temp'] += 1
                except Exception as e:
                    logger.error(f"Error limpiando archivo temporal: {str(e)}")
            
            db.session.commit()
            
            logger.info(f"Cleanup completado: {stats}")
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en cleanup: {str(e)}")
            return {'deleted_files': 0, 'cleaned_temp': 0, 'freed_bytes': 0}
    
    def migrate_files_to_provider(
        self,
        from_provider: str,
        to_provider: str,
        file_categories: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Migrar archivos entre proveedores"""
        try:
            if from_provider not in self.providers or to_provider not in self.providers:
                raise ValidationError("Proveedor no válido")
            
            source_provider = self.providers[from_provider]
            dest_provider = self.providers[to_provider]
            
            query = FileUpload.query.filter_by(
                storage_provider=from_provider,
                status=FileStatus.ACTIVE.value
            )
            
            if file_categories:
                query = query.filter(FileUpload.category.in_(file_categories))
            
            files_to_migrate = query.all()
            
            stats = {
                'total_files': len(files_to_migrate),
                'migrated': 0,
                'failed': 0,
                'bytes_migrated': 0
            }
            
            for file_upload in files_to_migrate:
                try:
                    # Descargar del proveedor origen
                    temp_file = self.temp_dir / f"migrate_{file_upload.id}"
                    
                    if source_provider.download_file(file_upload.storage_key, str(temp_file)):
                        # Subir al proveedor destino
                        new_key = file_upload.storage_key.replace(from_provider, to_provider)
                        
                        metadata = {
                            'migrated_from': from_provider,
                            'migration_date': datetime.utcnow().isoformat()
                        }
                        
                        dest_provider.upload_file(str(temp_file), new_key, metadata)
                        
                        # Actualizar registro
                        file_upload.storage_provider = to_provider
                        file_upload.storage_key = new_key
                        file_upload.updated_at = datetime.utcnow()
                        
                        # Limpiar archivo temporal
                        temp_file.unlink()
                        
                        stats['migrated'] += 1
                        stats['bytes_migrated'] += file_upload.file_size
                        
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error migrando archivo {file_upload.id}: {str(e)}")
                    stats['failed'] += 1
            
            db.session.commit()
            
            logger.info(f"Migración completada: {stats}")
            return stats
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en migración: {str(e)}")
            raise BusinessLogicError(f"Error en migración: {str(e)}")


# Instancia del servicio para uso global
file_storage_service = FileStorageService()


# Funciones de conveniencia
def upload_project_document(
    project_id: int,
    file: FileStorage,
    user_id: int,
    document_type: str = "general"
) -> FileUploadResult:
    """Subir documento de proyecto"""
    
    config = UploadConfig(
        max_file_size=50 * 1024 * 1024,  # 50MB
        allowed_extensions=['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.pptx'],
        add_watermark=True,
        encrypt_file=True
    )
    
    return file_storage_service.upload_file(
        file=file,
        user_id=user_id,
        category=FileCategory.DOCUMENT.value,
        config=config,
        related_entity_type='project',
        related_entity_id=project_id,
        metadata={'document_type': document_type}
    )


def upload_profile_image(
    user_id: int,
    image_file: FileStorage
) -> FileUploadResult:
    """Subir imagen de perfil"""
    
    config = UploadConfig(
        max_file_size=5 * 1024 * 1024,  # 5MB
        allowed_extensions=['.jpg', '.jpeg', '.png'],
        auto_optimize=True,
        generate_thumbnails=True,
        compress_file=True
    )
    
    return file_storage_service.upload_file(
        file=image_file,
        user_id=user_id,
        category=FileCategory.IMAGE.value,
        config=config,
        related_entity_type='user_profile',
        related_entity_id=user_id
    )


def get_user_files(
    user_id: int,
    category: Optional[str] = None,
    related_entity_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Obtener archivos del usuario"""
    
    query = FileUpload.query.filter_by(
        uploaded_by_id=user_id,
        status=FileStatus.ACTIVE.value
    )
    
    if category:
        query = query.filter_by(category=category)
    
    if related_entity_type:
        query = query.filter_by(related_entity_type=related_entity_type)
    
    files = query.order_by(FileUpload.created_at.desc()).all()
    
    return [
        {
            'id': f.id,
            'filename': f.original_filename,
            'file_size': f.file_size,
            'category': f.category,
            'created_at': f.created_at,
            'thumbnail_url': f.thumbnail_url,
            'download_url': url_for('api.download_file', file_id=f.id, _external=True)
        }
        for f in files
    ]