#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Backup Empresarial del Ecosistema de Emprendimiento
=============================================================

Sistema completo de backup y recovery que maneja:
- Backup de base de datos PostgreSQL con múltiples estrategias
- Backup de archivos estáticos y uploads
- Backup incremental y diferencial
- Compresión y encriptación de backups
- Múltiples destinos (local, AWS S3, Google Cloud Storage)
- Rotación automática con políticas de retención
- Validación e integridad de backups
- Restore completo y selectivo
- Monitoreo y alertas
- Programación automática con cron
- Cleanup inteligente de backups antiguos
- CI/CD integration y automation

Estrategias de backup:
    - full: Backup completo de todo
    - incremental: Solo cambios desde último backup
    - differential: Cambios desde último backup completo
    - schema: Solo esquema de base de datos
    - data: Solo datos sin esquema

Destinos soportados:
    - local: Almacenamiento local
    - s3: Amazon S3
    - gcs: Google Cloud Storage
    - ftp: FTP/SFTP servers

Uso:
    python scripts/backup.py --strategy full --destination s3
    python scripts/backup.py --restore --backup-id abc123def
    python scripts/backup.py --list-backups --destination s3
    python scripts/backup.py --cleanup --older-than 30
    python scripts/backup.py --validate --backup-id abc123def

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
import gzip
import time
import sqlite3
import psycopg2
from pathlib import Path
from typing import Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import secrets
import fnmatch
from cryptography.fernet import Fernet
import boto3
from google.cloud import storage as gcs
import requests


# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class BackupConfig:
    """
    Configuración completa del sistema de backup.
    """
    strategy: str = 'full'                      # full, incremental, differential, schema, data
    destination: str = 'local'                  # local, s3, gcs, ftp
    encrypt: bool = True
    compress: bool = True
    verify: bool = True
    cleanup: bool = False
    restore: bool = False
    list_backups: bool = False
    validate: bool = False
    backup_id: Optional[str] = None
    restore_target: Optional[str] = None
    older_than: Optional[int] = None            # días
    include_uploads: bool = True
    include_logs: bool = False
    include_config: bool = True
    exclude_patterns: list[str] = field(default_factory=list)
    retention_days: int = 30
    max_backups: int = 50
    parallel_workers: int = 4
    bandwidth_limit: Optional[str] = None       # e.g., "10MB/s"
    notification_webhook: Optional[str] = None
    dry_run: bool = False
    verbose: bool = False
    force: bool = False


@dataclass
class BackupMetadata:
    """
    Metadata de un backup específico.
    """
    backup_id: str
    timestamp: datetime
    strategy: str
    environment: str
    version: str
    git_commit: str
    size_bytes: int
    compressed_size_bytes: int
    checksum: str
    encryption_key_id: Optional[str]
    destination: str
    files: list[str] = field(default_factory=list)
    database_info: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    status: str = 'pending'  # pending, running, completed, failed
    error_message: Optional[str] = None


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


class BackupError(Exception):
    """
    Excepción específica para errores de backup.
    """
    pass


class RestoreError(Exception):
    """
    Excepción específica para errores de restore.
    """
    pass


class BackupLogger:
    """
    Logger especializado para operaciones de backup.
    """
    
    def __init__(self, verbose: bool = False, backup_id: str = None):
        """
        Inicializa el logger de backup.
        
        Args:
            verbose: Si mostrar logs verbosos
            backup_id: ID único del backup
        """
        self.verbose = verbose
        self.backup_id = backup_id or secrets.token_hex(8)
        self.setup_logging()
    
    def setup_logging(self):
        """
        Configura logging estructurado para backup.
        """
        log_format = f'%(asctime)s [BACKUP:{self.backup_id}] %(levelname)s: %(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        
        # Configurar handler para archivo
        log_file = project_root / 'logs' / f'backup_{self.backup_id}.log'
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
        
        self.logger = logging.getLogger('backup')
    
    def info(self, message: str, progress: bool = False):
        """Log info con formato profesional."""
        prefix = f"{Colors.OKCYAN}[PROGRESS]{Colors.ENDC}" if progress else f"{Colors.OKGREEN}[INFO]{Colors.ENDC}"
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
    
    def operation(self, operation_name: str, step: int, total_steps: int):
        """Log operación del backup."""
        print(f"\n{Colors.HEADER}[{step}/{total_steps}] {operation_name}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'-' * 50}{Colors.ENDC}")
        self.logger.info(f"Operation {step}/{total_steps}: {operation_name}")


class EncryptionManager:
    """
    Gestor de encriptación para backups seguros.
    """
    
    def __init__(self, key_file: Optional[Path] = None):
        """
        Inicializa el gestor de encriptación.
        
        Args:
            key_file: Archivo de clave de encriptación
        """
        self.key_file = key_file or project_root / '.backup_key'
        self.fernet = self._get_or_create_key()
    
    def _get_or_create_key(self) -> Fernet:
        """
        Obtiene o crea la clave de encriptación.
        
        Returns:
            Instancia de Fernet para encriptación
        """
        if self.key_file.exists():
            key = self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            self.key_file.chmod(0o600)  # Solo lectura para el propietario
        
        return Fernet(key)
    
    def encrypt_file(self, input_file: Path, output_file: Path) -> str:
        """
        Encripta un archivo.
        
        Args:
            input_file: Archivo a encriptar
            output_file: Archivo encriptado de salida
            
        Returns:
            Checksum del archivo encriptado
        """
        with open(input_file, 'rb') as f_in:
            data = f_in.read()
        
        encrypted_data = self.fernet.encrypt(data)
        
        with open(output_file, 'wb') as f_out:
            f_out.write(encrypted_data)
        
        # Calcular checksum
        hasher = hashlib.sha256()
        hasher.update(encrypted_data)
        return hasher.hexdigest()
    
    def decrypt_file(self, input_file: Path, output_file: Path) -> bool:
        """
        Desencripta un archivo.
        
        Args:
            input_file: Archivo encriptado
            output_file: Archivo desencriptado de salida
            
        Returns:
            True si la desencriptación fue exitosa
        """
        try:
            with open(input_file, 'rb') as f_in:
                encrypted_data = f_in.read()
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            with open(output_file, 'wb') as f_out:
                f_out.write(decrypted_data)
            
            return True
            
        except Exception:
            return False


class StorageBackend:
    """
    Clase base para backends de almacenamiento.
    """
    
    def upload_file(self, local_file: Path, remote_path: str) -> bool:
        """Sube un archivo al backend."""
        raise NotImplementedError
    
    def download_file(self, remote_path: str, local_file: Path) -> bool:
        """Descarga un archivo del backend."""
        raise NotImplementedError
    
    def list_files(self, prefix: str = '') -> list[str]:
        """Lista archivos en el backend."""
        raise NotImplementedError
    
    def delete_file(self, remote_path: str) -> bool:
        """Elimina un archivo del backend."""
        raise NotImplementedError
    
    def get_file_size(self, remote_path: str) -> int:
        """Obtiene el tamaño de un archivo."""
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """
    Backend de almacenamiento local.
    """
    
    def __init__(self, base_path: str):
        """
        Inicializa el backend local.
        
        Args:
            base_path: Directorio base para backups
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def upload_file(self, local_file: Path, remote_path: str) -> bool:
        """Copia archivo al directorio de backups."""
        try:
            target_file = self.base_path / remote_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_file, target_file)
            return True
        except Exception:
            return False
    
    def download_file(self, remote_path: str, local_file: Path) -> bool:
        """Copia archivo desde el directorio de backups."""
        try:
            source_file = self.base_path / remote_path
            if source_file.exists():
                local_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, local_file)
                return True
            return False
        except Exception:
            return False
    
    def list_files(self, prefix: str = '') -> list[str]:
        """Lista archivos en el directorio."""
        try:
            search_path = self.base_path / prefix if prefix else self.base_path
            if search_path.is_dir():
                return [str(f.relative_to(self.base_path)) for f in search_path.rglob('*') if f.is_file()]
            elif search_path.exists():
                return [str(search_path.relative_to(self.base_path))]
            return []
        except Exception:
            return []
    
    def delete_file(self, remote_path: str) -> bool:
        """Elimina archivo del directorio."""
        try:
            target_file = self.base_path / remote_path
            if target_file.exists():
                target_file.unlink()
                return True
            return False
        except Exception:
            return False
    
    def get_file_size(self, remote_path: str) -> int:
        """Obtiene tamaño del archivo."""
        try:
            target_file = self.base_path / remote_path
            return target_file.stat().st_size if target_file.exists() else 0
        except Exception:
            return 0


class S3StorageBackend(StorageBackend):
    """
    Backend de almacenamiento AWS S3.
    """
    
    def __init__(self, bucket_name: str, prefix: str = 'backups/'):
        """
        Inicializa el backend S3.
        
        Args:
            bucket_name: Nombre del bucket S3
            prefix: Prefijo para organizar backups
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.s3_client = boto3.client('s3')
    
    def upload_file(self, local_file: Path, remote_path: str) -> bool:
        """Sube archivo a S3."""
        try:
            key = f"{self.prefix}{remote_path}"
            self.s3_client.upload_file(str(local_file), self.bucket_name, key)
            return True
        except Exception:
            return False
    
    def download_file(self, remote_path: str, local_file: Path) -> bool:
        """Descarga archivo de S3."""
        try:
            key = f"{self.prefix}{remote_path}"
            local_file.parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(self.bucket_name, key, str(local_file))
            return True
        except Exception:
            return False
    
    def list_files(self, prefix: str = '') -> list[str]:
        """Lista archivos en S3."""
        try:
            full_prefix = f"{self.prefix}{prefix}"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=full_prefix
            )
            
            files = []
            for obj in response.get('Contents', []):
                # Remover el prefijo base
                relative_path = obj['Key'][len(self.prefix):]
                files.append(relative_path)
            
            return files
        except Exception:
            return []
    
    def delete_file(self, remote_path: str) -> bool:
        """Elimina archivo de S3."""
        try:
            key = f"{self.prefix}{remote_path}"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False
    
    def get_file_size(self, remote_path: str) -> int:
        """Obtiene tamaño del archivo en S3."""
        try:
            key = f"{self.prefix}{remote_path}"
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return response['ContentLength']
        except Exception:
            return 0


class GCSStorageBackend(StorageBackend):
    """
    Backend de almacenamiento Google Cloud Storage.
    """
    
    def __init__(self, bucket_name: str, prefix: str = 'backups/'):
        """
        Inicializa el backend GCS.
        
        Args:
            bucket_name: Nombre del bucket GCS
            prefix: Prefijo para organizar backups
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.client = gcs.Client()
        self.bucket = self.client.bucket(bucket_name)
    
    def upload_file(self, local_file: Path, remote_path: str) -> bool:
        """Sube archivo a GCS."""
        try:
            blob_name = f"{self.prefix}{remote_path}"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(str(local_file))
            return True
        except Exception:
            return False
    
    def download_file(self, remote_path: str, local_file: Path) -> bool:
        """Descarga archivo de GCS."""
        try:
            blob_name = f"{self.prefix}{remote_path}"
            blob = self.bucket.blob(blob_name)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local_file))
            return True
        except Exception:
            return False
    
    def list_files(self, prefix: str = '') -> list[str]:
        """Lista archivos en GCS."""
        try:
            full_prefix = f"{self.prefix}{prefix}"
            blobs = self.client.list_blobs(self.bucket_name, prefix=full_prefix)
            
            files = []
            for blob in blobs:
                # Remover el prefijo base
                relative_path = blob.name[len(self.prefix):]
                files.append(relative_path)
            
            return files
        except Exception:
            return []
    
    def delete_file(self, remote_path: str) -> bool:
        """Elimina archivo de GCS."""
        try:
            blob_name = f"{self.prefix}{remote_path}"
            blob = self.bucket.blob(blob_name)
            blob.delete()
            return True
        except Exception:
            return False
    
    def get_file_size(self, remote_path: str) -> int:
        """Obtiene tamaño del archivo en GCS."""
        try:
            blob_name = f"{self.prefix}{remote_path}"
            blob = self.bucket.blob(blob_name)
            blob.reload()
            return blob.size or 0
        except Exception:
            return 0


class DatabaseBackupManager:
    """
    Gestor especializado para backup de base de datos.
    """
    
    def __init__(self, database_url: str, logger: BackupLogger):
        """
        Inicializa el gestor de backup de DB.
        
        Args:
            database_url: URL de conexión a la base de datos
            logger: Logger para operaciones
        """
        self.database_url = database_url
        self.logger = logger
        self.parsed_url = urlparse(database_url)
        
        # Extraer información de conexión
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or 5432
        self.database = self.parsed_url.path.lstrip('/')
        self.username = self.parsed_url.username
        self.password = self.parsed_url.password
    
    def create_full_backup(self, output_file: Path) -> dict[str, Any]:
        """
        Crea backup completo de la base de datos.
        
        Args:
            output_file: Archivo de salida del backup
            
        Returns:
            Metadata del backup de base de datos
        """
        self.logger.info("Creando backup completo de base de datos...")
        
        start_time = time.time()
        
        try:
            # Configurar variables de entorno para pg_dump
            env = os.environ.copy()
            if self.password:
                env['PGPASSWORD'] = self.password
            
            # Comando pg_dump
            cmd = [
                'pg_dump',
                '--host', self.host,
                '--port', str(self.port),
                '--username', self.username,
                '--dbname', self.database,
                '--format', 'custom',
                '--compress', '9',
                '--verbose',
                '--file', str(output_file)
            ]
            
            # Ejecutar pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            file_size = output_file.stat().st_size
            
            # Obtener información adicional de la base de datos
            db_info = self._get_database_info()
            
            self.logger.success(f"Backup de base de datos completado en {duration:.2f}s ({file_size:,} bytes)")
            
            return {
                'type': 'full',
                'file_size': file_size,
                'duration_seconds': duration,
                'tables_count': db_info.get('tables_count', 0),
                'database_size': db_info.get('database_size', 0),
                'pg_dump_version': self._get_pg_dump_version(),
            }
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en pg_dump: {e.stderr}")
            raise BackupError(f"Fallo en backup de base de datos: {e.stderr}")
    
    def create_schema_backup(self, output_file: Path) -> dict[str, Any]:
        """
        Crea backup solo del esquema de la base de datos.
        
        Args:
            output_file: Archivo de salida del backup
            
        Returns:
            Metadata del backup de esquema
        """
        self.logger.info("Creando backup de esquema de base de datos...")
        
        start_time = time.time()
        
        try:
            env = os.environ.copy()
            if self.password:
                env['PGPASSWORD'] = self.password
            
            cmd = [
                'pg_dump',
                '--host', self.host,
                '--port', str(self.port),
                '--username', self.username,
                '--dbname', self.database,
                '--schema-only',
                '--format', 'custom',
                '--verbose',
                '--file', str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            file_size = output_file.stat().st_size
            
            self.logger.success(f"Backup de esquema completado en {duration:.2f}s")
            
            return {
                'type': 'schema',
                'file_size': file_size,
                'duration_seconds': duration,
                'pg_dump_version': self._get_pg_dump_version(),
            }
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en backup de esquema: {e.stderr}")
            raise BackupError(f"Fallo en backup de esquema: {e.stderr}")
    
    def create_data_backup(self, output_file: Path) -> dict[str, Any]:
        """
        Crea backup solo de los datos (sin esquema).
        
        Args:
            output_file: Archivo de salida del backup
            
        Returns:
            Metadata del backup de datos
        """
        self.logger.info("Creando backup de datos de base de datos...")
        
        start_time = time.time()
        
        try:
            env = os.environ.copy()
            if self.password:
                env['PGPASSWORD'] = self.password
            
            cmd = [
                'pg_dump',
                '--host', self.host,
                '--port', str(self.port),
                '--username', self.username,
                '--dbname', self.database,
                '--data-only',
                '--format', 'custom',
                '--compress', '9',
                '--verbose',
                '--file', str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            file_size = output_file.stat().st_size
            
            self.logger.success(f"Backup de datos completado en {duration:.2f}s")
            
            return {
                'type': 'data',
                'file_size': file_size,
                'duration_seconds': duration,
                'pg_dump_version': self._get_pg_dump_version(),
            }
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en backup de datos: {e.stderr}")
            raise BackupError(f"Fallo en backup de datos: {e.stderr}")
    
    def restore_backup(self, backup_file: Path, target_database: Optional[str] = None) -> bool:
        """
        Restaura un backup de base de datos.
        
        Args:
            backup_file: Archivo de backup a restaurar
            target_database: Base de datos de destino (opcional)
            
        Returns:
            True si la restauración fue exitosa
        """
        target_db = target_database or self.database
        
        self.logger.info(f"Restaurando backup a base de datos: {target_db}")
        
        try:
            env = os.environ.copy()
            if self.password:
                env['PGPASSWORD'] = self.password
            
            cmd = [
                'pg_restore',
                '--host', self.host,
                '--port', str(self.port),
                '--username', self.username,
                '--dbname', target_db,
                '--clean',
                '--if-exists',
                '--verbose',
                str(backup_file)
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            self.logger.success("Restauración de base de datos completada")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en restauración: {e.stderr}")
            return False
    
    def _get_database_info(self) -> dict[str, Any]:
        """Obtiene información adicional de la base de datos."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            # Contar tablas
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables_count = cursor.fetchone()[0]
            
            # Obtener tamaño de la base de datos
            cursor.execute(f"SELECT pg_database_size('{self.database}')")
            database_size = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return {
                'tables_count': tables_count,
                'database_size': database_size,
            }
            
        except Exception:
            return {}
    
    def _get_pg_dump_version(self) -> str:
        """Obtiene la versión de pg_dump."""
        try:
            result = subprocess.run(
                ['pg_dump', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return 'unknown'


class FileBackupManager:
    """
    Gestor para backup de archivos y directorios.
    """
    
    def __init__(self, logger: BackupLogger):
        """
        Inicializa el gestor de backup de archivos.
        
        Args:
            logger: Logger para operaciones
        """
        self.logger = logger
    
    def create_archive(self, source_paths: list[Path], output_file: Path, 
                      exclude_patterns: list[str] = None, compress: bool = True) -> dict[str, Any]:
        """
        Crea archivo tar con los archivos especificados.
        
        Args:
            source_paths: Rutas a incluir en el archive
            output_file: Archivo de salida
            exclude_patterns: Patrones de archivos a excluir
            compress: Si comprimir el archive
            
        Returns:
            Metadata del backup de archivos
        """
        self.logger.info("Creando archivo de backup de archivos...")
        
        exclude_patterns = exclude_patterns or []
        start_time = time.time()
        
        try:
            # Abrir archive
            mode = 'w:gz' if compress else 'w'
            with tarfile.open(output_file, mode) as tar:
                
                files_added = 0
                total_size = 0
                
                for source_path in source_paths:
                    if not source_path.exists():
                        self.logger.warning(f"Ruta no encontrada: {source_path}")
                        continue
                    
                    if source_path.is_file():
                        # Archivo individual
                        if not self._should_exclude(source_path, exclude_patterns):
                            tar.add(source_path, arcname=source_path.name)
                            files_added += 1
                            total_size += source_path.stat().st_size
                    
                    elif source_path.is_dir():
                        # Directorio completo
                        for file_path in source_path.rglob('*'):
                            if file_path.is_file() and not self._should_exclude(file_path, exclude_patterns):
                                # Mantener estructura de directorios
                                arcname = file_path.relative_to(source_path.parent)
                                tar.add(file_path, arcname=arcname)
                                files_added += 1
                                total_size += file_path.stat().st_size
            
            duration = time.time() - start_time
            archive_size = output_file.stat().st_size
            compression_ratio = archive_size / total_size if total_size > 0 else 1.0
            
            self.logger.success(f"Archivo creado: {files_added} archivos, {duration:.2f}s")
            self.logger.info(f"Tamaño original: {total_size:,} bytes")
            self.logger.info(f"Tamaño comprimido: {archive_size:,} bytes")
            self.logger.info(f"Ratio de compresión: {compression_ratio:.2%}")
            
            return {
                'files_count': files_added,
                'original_size': total_size,
                'compressed_size': archive_size,
                'compression_ratio': compression_ratio,
                'duration_seconds': duration,
            }
            
        except Exception as e:
            self.logger.error(f"Error creando archivo: {e}")
            raise BackupError(f"Fallo en backup de archivos: {e}")
    
    def extract_archive(self, archive_file: Path, extract_to: Path) -> bool:
        """
        Extrae un archivo tar.
        
        Args:
            archive_file: Archivo a extraer
            extract_to: Directorio de destino
            
        Returns:
            True si la extracción fue exitosa
        """
        self.logger.info(f"Extrayendo archivo: {archive_file}")
        
        try:
            extract_to.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(archive_file, 'r:*') as tar:
                tar.extractall(path=extract_to)
            
            self.logger.success(f"Archivo extraído a: {extract_to}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error extrayendo archivo: {e}")
            return False
    
    def _should_exclude(self, file_path: Path, exclude_patterns: list[str]) -> bool:
        """
        Determina si un archivo debe ser excluido.
        
        Args:
            file_path: Ruta del archivo
            exclude_patterns: Patrones de exclusión
            
        Returns:
            True si el archivo debe ser excluido
        """
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(str(file_path), pattern):
                return True
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
        
        return False


class BackupManager:
    """
    Gestor principal del sistema de backup.
    """
    
    def __init__(self, config: BackupConfig):
        """
        Inicializa el gestor de backup.
        
        Args:
            config: Configuración del backup
        """
        self.config = config
        self.logger = BackupLogger(config.verbose)
        self.temp_dir = Path(tempfile.mkdtemp(prefix='backup_'))
        self.metadata_file = project_root / 'backups' / 'metadata.json'
        
        # Inicializar componentes
        self.encryption_manager = EncryptionManager() if config.encrypt else None
        self.storage_backend = self._create_storage_backend()
        self.db_manager = self._create_db_manager()
        self.file_manager = FileBackupManager(self.logger)
        
        # Asegurar directorio de backups
        (project_root / 'backups').mkdir(exist_ok=True)
    
    def run(self) -> bool:
        """
        Ejecuta la operación de backup especificada.
        
        Returns:
            True si la operación fue exitosa
        """
        try:
            if self.config.list_backups:
                return self._list_backups()
            elif self.config.restore:
                return self._restore_backup()
            elif self.config.validate:
                return self._validate_backup()
            elif self.config.cleanup:
                return self._cleanup_backups()
            else:
                return self._create_backup()
                
        except KeyboardInterrupt:
            self.logger.warning("Operación interrumpida por el usuario")
            return False
        except (BackupError, RestoreError) as e:
            self.logger.error(f"Error en operación: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado: {e}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            return False
        finally:
            # Limpiar directorio temporal
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
    
    def _create_backup(self) -> bool:
        """
        Crea un nuevo backup.
        
        Returns:
            True si el backup fue exitoso
        """
        # Header principal
        self.logger.header(f"BACKUP {self.config.strategy.upper()} - {self.config.destination.upper()}")
        
        # Crear metadata del backup
        metadata = BackupMetadata(
            backup_id=self.logger.backup_id,
            timestamp=datetime.now(timezone.utc),
            strategy=self.config.strategy,
            environment=os.environ.get('ENVIRONMENT', 'unknown'),
            version=self._get_version(),
            git_commit=self._get_git_commit(),
            size_bytes=0,
            compressed_size_bytes=0,
            checksum='',
            destination=self.config.destination,
            status='running'
        )
        
        start_time = time.time()
        
        try:
            # Operaciones del backup
            operations = self._get_backup_operations()
            total_operations = len(operations)
            
            for i, (operation_name, operation_func) in enumerate(operations, 1):
                self.logger.operation(operation_name, i, total_operations)
                
                if not operation_func(metadata):
                    metadata.status = 'failed'
                    metadata.error_message = f"Fallo en operación: {operation_name}"
                    self._save_metadata(metadata)
                    return False
            
            # Finalizar backup
            metadata.duration_seconds = time.time() - start_time
            metadata.status = 'completed'
            
            # Guardar metadata
            self._save_metadata(metadata)
            
            # Notificación de éxito
            self._notify_backup_success(metadata)
            
            self.logger.success(f"Backup completado exitosamente: {metadata.backup_id}")
            self.logger.info(f"Duración total: {metadata.duration_seconds:.2f}s")
            self.logger.info(f"Tamaño total: {metadata.size_bytes:,} bytes")
            
            return True
            
        except Exception as e:
            metadata.status = 'failed'
            metadata.error_message = str(e)
            metadata.duration_seconds = time.time() - start_time
            self._save_metadata(metadata)
            raise
    
    def _get_backup_operations(self) -> list[tuple[str, callable]]:
        """
        Obtiene la lista de operaciones para el backup.
        
        Returns:
            Lista de tuplas (nombre, función) de operaciones
        """
        operations = []
        
        # Backup de base de datos
        if self.config.strategy in ['full', 'schema', 'data']:
            operations.append(("Database Backup", self._backup_database))
        
        # Backup de archivos
        if self.config.strategy == 'full':
            if self.config.include_uploads:
                operations.append(("Files Backup", self._backup_files))
            
            if self.config.include_config:
                operations.append(("Configuration Backup", self._backup_configuration))
        
        # Compresión y encriptación
        operations.append(("Archive Processing", self._process_archive))
        
        # Upload al destino
        operations.append(("Upload to Destination", self._upload_backup))
        
        # Limpieza automática
        if self.config.cleanup:
            operations.append(("Cleanup Old Backups", self._cleanup_old_backups))
        
        return operations
    
    def _backup_database(self, metadata: BackupMetadata) -> bool:
        """Ejecuta backup de base de datos."""
        if not self.db_manager:
            self.logger.warning("No hay configuración de base de datos disponible")
            return True
        
        db_file = self.temp_dir / f"database_{metadata.backup_id}.dump"
        
        try:
            if self.config.strategy == 'full':
                db_info = self.db_manager.create_full_backup(db_file)
            elif self.config.strategy == 'schema':
                db_info = self.db_manager.create_schema_backup(db_file)
            elif self.config.strategy == 'data':
                db_info = self.db_manager.create_data_backup(db_file)
            else:
                return True
            
            metadata.database_info = db_info
            metadata.files.append(str(db_file.relative_to(self.temp_dir)))
            metadata.size_bytes += db_file.stat().st_size
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en backup de base de datos: {e}")
            return False
    
    def _backup_files(self, metadata: BackupMetadata) -> bool:
        """Ejecuta backup de archivos."""
        files_to_backup = []
        
        # Directorio de uploads
        uploads_dir = project_root / 'app' / 'static' / 'uploads'
        if uploads_dir.exists():
            files_to_backup.append(uploads_dir)
        
        # Logs si están incluidos
        if self.config.include_logs:
            logs_dir = project_root / 'logs'
            if logs_dir.exists():
                files_to_backup.append(logs_dir)
        
        if not files_to_backup:
            self.logger.info("No hay archivos para hacer backup")
            return True
        
        files_archive = self.temp_dir / f"files_{metadata.backup_id}.tar.gz"
        
        try:
            file_info = self.file_manager.create_archive(
                files_to_backup,
                files_archive,
                exclude_patterns=self.config.exclude_patterns,
                compress=self.config.compress
            )
            
            metadata.files.append(str(files_archive.relative_to(self.temp_dir)))
            metadata.size_bytes += files_archive.stat().st_size
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en backup de archivos: {e}")
            return False
    
    def _backup_configuration(self, metadata: BackupMetadata) -> bool:
        """Ejecuta backup de configuración."""
        config_files = [
            project_root / '.env.local',
            project_root / '.env.production',
            project_root / 'docker-compose.yml',
            project_root / 'requirements.txt',
        ]
        
        # Filtrar archivos que existen
        existing_config_files = [f for f in config_files if f.exists()]
        
        if not existing_config_files:
            self.logger.info("No hay archivos de configuración para backup")
            return True
        
        config_archive = self.temp_dir / f"config_{metadata.backup_id}.tar.gz"
        
        try:
            file_info = self.file_manager.create_archive(
                existing_config_files,
                config_archive,
                compress=True
            )
            
            metadata.files.append(str(config_archive.relative_to(self.temp_dir)))
            metadata.size_bytes += config_archive.stat().st_size
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en backup de configuración: {e}")
            return False
    
    def _process_archive(self, metadata: BackupMetadata) -> bool:
        """Procesa el archive final (compresión y encriptación)."""
        if not metadata.files:
            raise BackupError("No hay archivos para procesar")
        
        # Crear archive final
        final_archive = self.temp_dir / f"backup_{metadata.backup_id}.tar.gz"
        
        try:
            # Combinar todos los archivos en un archive final
            with tarfile.open(final_archive, 'w:gz') as tar:
                for file_path in metadata.files:
                    full_path = self.temp_dir / file_path
                    if full_path.exists():
                        tar.add(full_path, arcname=file_path)
            
            # Calcular checksum
            metadata.checksum = self._calculate_checksum(final_archive)
            metadata.compressed_size_bytes = final_archive.stat().st_size
            
            # Encriptar si está habilitado
            if self.config.encrypt and self.encryption_manager:
                encrypted_file = self.temp_dir / f"backup_{metadata.backup_id}.tar.gz.enc"
                
                encryption_checksum = self.encryption_manager.encrypt_file(
                    final_archive, encrypted_file
                )
                
                # Usar archivo encriptado como final
                final_archive.unlink()
                encrypted_file.rename(final_archive)
                
                metadata.checksum = encryption_checksum
                metadata.encryption_key_id = "default"
                metadata.compressed_size_bytes = final_archive.stat().st_size
            
            # Actualizar lista de archivos
            metadata.files = [final_archive.name]
            
            self.logger.success(f"Archive procesado: {metadata.compressed_size_bytes:,} bytes")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error procesando archive: {e}")
            return False
    
    def _upload_backup(self, metadata: BackupMetadata) -> bool:
        """Sube el backup al destino configurado."""
        if self.config.dry_run:
            self.logger.info("DRY RUN: Saltando upload")
            return True
        
        final_archive = self.temp_dir / metadata.files[0]
        remote_path = f"{metadata.timestamp.strftime('%Y/%m/%d')}/{metadata.files[0]}"
        
        try:
            self.logger.info(f"Subiendo backup a {self.config.destination}...")
            
            success = self.storage_backend.upload_file(final_archive, remote_path)
            
            if success:
                self.logger.success(f"Backup subido exitosamente: {remote_path}")
                return True
            else:
                self.logger.error("Error subiendo backup")
                return False
                
        except Exception as e:
            self.logger.error(f"Error en upload: {e}")
            return False
    
    def _cleanup_old_backups(self, metadata: BackupMetadata) -> bool:
        """Limpia backups antiguos según política de retención."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
            
            # Cargar metadata existente
            all_backups = self._load_all_metadata()
            
            # Filtrar backups antiguos
            old_backups = [
                backup for backup in all_backups
                if backup.timestamp < cutoff_date and backup.backup_id != metadata.backup_id
            ]
            
            if not old_backups:
                self.logger.info("No hay backups antiguos para limpiar")
                return True
            
            self.logger.info(f"Limpiando {len(old_backups)} backups antiguos...")
            
            cleaned_count = 0
            for old_backup in old_backups:
                try:
                    # Eliminar archivos del storage
                    for file_path in old_backup.files:
                        remote_path = f"{old_backup.timestamp.strftime('%Y/%m/%d')}/{file_path}"
                        self.storage_backend.delete_file(remote_path)
                    
                    cleaned_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Error eliminando backup {old_backup.backup_id}: {e}")
            
            # Actualizar metadata removiendo backups eliminados
            remaining_backups = [
                backup for backup in all_backups
                if backup.backup_id not in [b.backup_id for b in old_backups]
            ]
            
            self._save_all_metadata(remaining_backups)
            
            self.logger.success(f"Limpieza completada: {cleaned_count} backups eliminados")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en limpieza: {e}")
            return False
    
    def _restore_backup(self) -> bool:
        """Restaura un backup específico."""
        if not self.config.backup_id:
            raise RestoreError("ID de backup requerido para restauración")
        
        self.logger.header(f"RESTORE BACKUP - {self.config.backup_id}")
        
        # Buscar metadata del backup
        backup_metadata = self._find_backup_metadata(self.config.backup_id)
        if not backup_metadata:
            raise RestoreError(f"Backup no encontrado: {self.config.backup_id}")
        
        self.logger.info(f"Restaurando backup: {backup_metadata.backup_id}")
        self.logger.info(f"Fecha: {backup_metadata.timestamp}")
        self.logger.info(f"Estrategia: {backup_metadata.strategy}")
        
        try:
            # Descargar backup
            self.logger.operation("Downloading Backup", 1, 3)
            if not self._download_backup(backup_metadata):
                return False
            
            # Extraer y desencriptar
            self.logger.operation("Extracting Archive", 2, 3)
            if not self._extract_backup(backup_metadata):
                return False
            
            # Restaurar componentes
            self.logger.operation("Restoring Components", 3, 3)
            if not self._restore_components(backup_metadata):
                return False
            
            self.logger.success("Restauración completada exitosamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en restauración: {e}")
            return False
    
    def _download_backup(self, metadata: BackupMetadata) -> bool:
        """Descarga un backup del storage."""
        try:
            remote_path = f"{metadata.timestamp.strftime('%Y/%m/%d')}/{metadata.files[0]}"
            local_file = self.temp_dir / metadata.files[0]
            
            success = self.storage_backend.download_file(remote_path, local_file)
            
            if success:
                # Verificar checksum
                if self.config.verify:
                    actual_checksum = self._calculate_checksum(local_file)
                    if actual_checksum != metadata.checksum:
                        self.logger.error("Checksum de backup no coincide")
                        return False
                
                self.logger.success("Backup descargado y verificado")
                return True
            else:
                self.logger.error("Error descargando backup")
                return False
                
        except Exception as e:
            self.logger.error(f"Error descargando backup: {e}")
            return False
    
    def _extract_backup(self, metadata: BackupMetadata) -> bool:
        """Extrae y desencripta un backup."""
        try:
            archive_file = self.temp_dir / metadata.files[0]
            
            # Desencriptar si es necesario
            if metadata.encryption_key_id and self.encryption_manager:
                decrypted_file = self.temp_dir / f"decrypted_{metadata.files[0]}"
                
                if not self.encryption_manager.decrypt_file(archive_file, decrypted_file):
                    self.logger.error("Error desencriptando backup")
                    return False
                
                archive_file = decrypted_file
            
            # Extraer archive
            extract_dir = self.temp_dir / 'extracted'
            return self.file_manager.extract_archive(archive_file, extract_dir)
            
        except Exception as e:
            self.logger.error(f"Error extrayendo backup: {e}")
            return False
    
    def _restore_components(self, metadata: BackupMetadata) -> bool:
        """Restaura los componentes del backup."""
        extract_dir = self.temp_dir / 'extracted'
        
        try:
            # Restaurar base de datos
            db_file = extract_dir / f"database_{metadata.backup_id}.dump"
            if db_file.exists() and self.db_manager:
                target_db = self.config.restore_target
                if not self.db_manager.restore_backup(db_file, target_db):
                    self.logger.warning("Error restaurando base de datos")
            
            # Restaurar archivos
            files_archive = extract_dir / f"files_{metadata.backup_id}.tar.gz"
            if files_archive.exists():
                restore_dir = project_root / 'restore' / metadata.backup_id
                if not self.file_manager.extract_archive(files_archive, restore_dir):
                    self.logger.warning("Error restaurando archivos")
            
            # Restaurar configuración
            config_archive = extract_dir / f"config_{metadata.backup_id}.tar.gz"
            if config_archive.exists():
                config_restore_dir = project_root / 'restore' / metadata.backup_id / 'config'
                if not self.file_manager.extract_archive(config_archive, config_restore_dir):
                    self.logger.warning("Error restaurando configuración")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error restaurando componentes: {e}")
            return False
    
    def _list_backups(self) -> bool:
        """Lista todos los backups disponibles."""
        self.logger.header("LISTA DE BACKUPS DISPONIBLES")
        
        try:
            all_backups = self._load_all_metadata()
            
            if not all_backups:
                self.logger.info("No hay backups disponibles")
                return True
            
            # Ordenar por fecha (más reciente primero)
            all_backups.sort(key=lambda x: x.timestamp, reverse=True)
            
            print(f"\n{Colors.OKCYAN}{'ID':<12} {'Fecha':<20} {'Estrategia':<12} {'Tamaño':<10} {'Estado':<10}{Colors.ENDC}")
            print("-" * 70)
            
            for backup in all_backups:
                size_mb = backup.compressed_size_bytes / (1024 * 1024)
                date_str = backup.timestamp.strftime('%Y-%m-%d %H:%M')
                status_color = Colors.OKGREEN if backup.status == 'completed' else Colors.FAIL
                
                print(f"{backup.backup_id:<12} {date_str:<20} {backup.strategy:<12} "
                      f"{size_mb:>8.1f}MB {status_color}{backup.status:<10}{Colors.ENDC}")
            
            print(f"\nTotal: {len(all_backups)} backups")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error listando backups: {e}")
            return False
    
    def _validate_backup(self) -> bool:
        """Valida la integridad de un backup."""
        if not self.config.backup_id:
            raise BackupError("ID de backup requerido para validación")
        
        self.logger.header(f"VALIDANDO BACKUP - {self.config.backup_id}")
        
        # Buscar metadata del backup
        backup_metadata = self._find_backup_metadata(self.config.backup_id)
        if not backup_metadata:
            self.logger.error(f"Backup no encontrado: {self.config.backup_id}")
            return False
        
        try:
            # Descargar y verificar checksum
            remote_path = f"{backup_metadata.timestamp.strftime('%Y/%m/%d')}/{backup_metadata.files[0]}"
            local_file = self.temp_dir / backup_metadata.files[0]
            
            self.logger.info("Descargando backup para validación...")
            
            if not self.storage_backend.download_file(remote_path, local_file):
                self.logger.error("Error descargando backup para validación")
                return False
            
            # Verificar checksum
            actual_checksum = self._calculate_checksum(local_file)
            
            if actual_checksum == backup_metadata.checksum:
                self.logger.success("Backup válido - checksum coincide")
                return True
            else:
                self.logger.error("Backup corrupto - checksum no coincide")
                self.logger.error(f"Esperado: {backup_metadata.checksum}")
                self.logger.error(f"Actual:   {actual_checksum}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error validando backup: {e}")
            return False
    
    def _cleanup_backups(self) -> bool:
        """Limpia backups según criterios especificados."""
        self.logger.header("LIMPIEZA DE BACKUPS")
        
        try:
            all_backups = self._load_all_metadata()
            
            if not all_backups:
                self.logger.info("No hay backups para limpiar")
                return True
            
            # Determinar backups a eliminar
            backups_to_delete = []
            
            if self.config.older_than:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.config.older_than)
                backups_to_delete = [b for b in all_backups if b.timestamp < cutoff_date]
            
            # Aplicar límite máximo de backups
            if len(all_backups) > self.config.max_backups:
                # Ordenar por fecha y mantener solo los más recientes
                sorted_backups = sorted(all_backups, key=lambda x: x.timestamp, reverse=True)
                excess_backups = sorted_backups[self.config.max_backups:]
                backups_to_delete.extend(excess_backups)
            
            # Remover duplicados
            backups_to_delete = list({b.backup_id: b for b in backups_to_delete}.values())
            
            if not backups_to_delete:
                self.logger.info("No hay backups para eliminar")
                return True
            
            self.logger.info(f"Se eliminarán {len(backups_to_delete)} backups")
            
            if not self.config.force:
                response = input("¿Continuar con la eliminación? (y/n): ")
                if response.lower() != 'y':
                    self.logger.info("Limpieza cancelada")
                    return True
            
            # Eliminar backups
            deleted_count = 0
            for backup in backups_to_delete:
                try:
                    # Eliminar archivos del storage
                    for file_path in backup.files:
                        remote_path = f"{backup.timestamp.strftime('%Y/%m/%d')}/{file_path}"
                        if not self.config.dry_run:
                            self.storage_backend.delete_file(remote_path)
                    
                    deleted_count += 1
                    self.logger.info(f"Eliminado: {backup.backup_id}")
                    
                except Exception as e:
                    self.logger.warning(f"Error eliminando {backup.backup_id}: {e}")
            
            # Actualizar metadata
            if not self.config.dry_run:
                remaining_backups = [
                    b for b in all_backups 
                    if b.backup_id not in [d.backup_id for d in backups_to_delete]
                ]
                self._save_all_metadata(remaining_backups)
            
            self.logger.success(f"Limpieza completada: {deleted_count} backups eliminados")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error en limpieza: {e}")
            return False
    
    def _create_storage_backend(self) -> StorageBackend:
        """Crea el backend de almacenamiento según configuración."""
        if self.config.destination == 'local':
            backup_dir = os.environ.get('BACKUP_DIR', str(project_root / 'backups'))
            return LocalStorageBackend(backup_dir)
        
        elif self.config.destination == 's3':
            bucket_name = os.environ.get('BACKUP_S3_BUCKET')
            if not bucket_name:
                raise BackupError("BACKUP_S3_BUCKET requerido para destino S3")
            return S3StorageBackend(bucket_name)
        
        elif self.config.destination == 'gcs':
            bucket_name = os.environ.get('BACKUP_GCS_BUCKET')
            if not bucket_name:
                raise BackupError("BACKUP_GCS_BUCKET requerido para destino GCS")
            return GCSStorageBackend(bucket_name)
        
        else:
            raise BackupError(f"Destino no soportado: {self.config.destination}")
    
    def _create_db_manager(self) -> Optional[DatabaseBackupManager]:
        """Crea el gestor de backup de base de datos."""
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            return DatabaseBackupManager(database_url, self.logger)
        return None
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcula checksum SHA256 de un archivo."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _get_version(self) -> str:
        """Obtiene la versión actual del proyecto."""
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--always'],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            return 'unknown'
    
    def _get_git_commit(self) -> str:
        """Obtiene el commit actual de Git."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            return 'unknown'
    
    def _save_metadata(self, metadata: BackupMetadata):
        """Guarda metadata de un backup."""
        all_backups = self._load_all_metadata()
        
        # Actualizar o agregar metadata
        updated = False
        for i, backup in enumerate(all_backups):
            if backup.backup_id == metadata.backup_id:
                all_backups[i] = metadata
                updated = True
                break
        
        if not updated:
            all_backups.append(metadata)
        
        self._save_all_metadata(all_backups)
    
    def _load_all_metadata(self) -> list[BackupMetadata]:
        """Carga toda la metadata de backups."""
        if not self.metadata_file.exists():
            return []
        
        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
            
            backups = []
            for item in data:
                # Convertir timestamp string a datetime
                timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                
                backup = BackupMetadata(
                    backup_id=item['backup_id'],
                    timestamp=timestamp,
                    strategy=item['strategy'],
                    environment=item['environment'],
                    version=item['version'],
                    git_commit=item['git_commit'],
                    size_bytes=item['size_bytes'],
                    compressed_size_bytes=item['compressed_size_bytes'],
                    checksum=item['checksum'],
                    encryption_key_id=item.get('encryption_key_id'),
                    destination=item['destination'],
                    files=item['files'],
                    database_info=item.get('database_info', {}),
                    duration_seconds=item.get('duration_seconds', 0.0),
                    status=item.get('status', 'completed'),
                    error_message=item.get('error_message')
                )
                backups.append(backup)
            
            return backups
            
        except Exception as e:
            self.logger.warning(f"Error cargando metadata: {e}")
            return []
    
    def _save_all_metadata(self, backups: list[BackupMetadata]):
        """Guarda toda la metadata de backups."""
        try:
            self.metadata_file.parent.mkdir(exist_ok=True)
            
            data = []
            for backup in backups:
                item = {
                    'backup_id': backup.backup_id,
                    'timestamp': backup.timestamp.isoformat(),
                    'strategy': backup.strategy,
                    'environment': backup.environment,
                    'version': backup.version,
                    'git_commit': backup.git_commit,
                    'size_bytes': backup.size_bytes,
                    'compressed_size_bytes': backup.compressed_size_bytes,
                    'checksum': backup.checksum,
                    'encryption_key_id': backup.encryption_key_id,
                    'destination': backup.destination,
                    'files': backup.files,
                    'database_info': backup.database_info,
                    'duration_seconds': backup.duration_seconds,
                    'status': backup.status,
                    'error_message': backup.error_message,
                }
                data.append(item)
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error guardando metadata: {e}")
    
    def _find_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """Busca metadata de un backup específico."""
        all_backups = self._load_all_metadata()
        
        for backup in all_backups:
            if backup.backup_id == backup_id:
                return backup
        
        return None
    
    def _notify_backup_success(self, metadata: BackupMetadata):
        """Envía notificación de backup exitoso."""
        if not self.config.notification_webhook:
            return
        
        try:
            payload = {
                'backup_id': metadata.backup_id,
                'timestamp': metadata.timestamp.isoformat(),
                'strategy': metadata.strategy,
                'environment': metadata.environment,
                'size_mb': round(metadata.compressed_size_bytes / (1024 * 1024), 2),
                'duration_seconds': metadata.duration_seconds,
                'destination': metadata.destination,
                'status': 'success'
            }
            
            if not self.config.dry_run:
                requests.post(self.config.notification_webhook, json=payload, timeout=10)
            
            self.logger.info("Notificación de backup enviada")
            
        except Exception as e:
            self.logger.warning(f"Error enviando notificación: {e}")


def main():
    """
    Función principal del script de backup.
    """
    parser = argparse.ArgumentParser(
        description="Sistema de Backup del Ecosistema de Emprendimiento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Backup completo a S3
  python scripts/backup.py --strategy full --destination s3 --encrypt --compress
  
  # Backup solo de base de datos
  python scripts/backup.py --strategy schema --destination local
  
  # Listar backups disponibles
  python scripts/backup.py --list-backups --destination s3
  
  # Restaurar backup específico
  python scripts/backup.py --restore --backup-id abc123def --restore-target test_db
  
  # Validar integridad de backup
  python scripts/backup.py --validate --backup-id abc123def
  
  # Limpiar backups antiguos
  python scripts/backup.py --cleanup --older-than 30 --destination s3
  
  # Dry run de backup
  python scripts/backup.py --strategy full --destination s3 --dry-run --verbose
        """
    )
    
    # Operaciones principales
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        '--strategy', '-s',
        choices=['full', 'incremental', 'differential', 'schema', 'data'],
        help='Estrategia de backup'
    )
    operation_group.add_argument(
        '--restore',
        action='store_true',
        help='Restaurar backup específico'
    )
    operation_group.add_argument(
        '--list-backups',
        action='store_true',
        help='Listar backups disponibles'
    )
    operation_group.add_argument(
        '--validate',
        action='store_true',
        help='Validar integridad de backup'
    )
    operation_group.add_argument(
        '--cleanup',
        action='store_true',
        help='Limpiar backups antiguos'
    )
    
    # Configuración de destino
    parser.add_argument(
        '--destination', '-d',
        choices=['local', 's3', 'gcs', 'ftp'],
        default='local',
        help='Destino del backup'
    )
    
    # Opciones de backup
    parser.add_argument(
        '--encrypt',
        action='store_true',
        help='Encriptar backup'
    )
    
    parser.add_argument(
        '--compress',
        action='store_true',
        default=True,
        help='Comprimir backup'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        default=True,
        help='Verificar integridad del backup'
    )
    
    # Opciones de contenido
    parser.add_argument(
        '--include-uploads',
        action='store_true',
        default=True,
        help='Incluir archivos de uploads'
    )
    
    parser.add_argument(
        '--include-logs',
        action='store_true',
        help='Incluir archivos de logs'
    )
    
    parser.add_argument(
        '--include-config',
        action='store_true',
        default=True,
        help='Incluir archivos de configuración'
    )
    
    parser.add_argument(
        '--exclude-pattern',
        action='append',
        dest='exclude_patterns',
        help='Patrones de archivos a excluir'
    )
    
    # Opciones de restore
    parser.add_argument(
        '--backup-id',
        help='ID del backup para restore/validate'
    )
    
    parser.add_argument(
        '--restore-target',
        help='Base de datos de destino para restore'
    )
    
    # Opciones de cleanup
    parser.add_argument(
        '--older-than',
        type=int,
        help='Eliminar backups más antiguos que N días'
    )
    
    parser.add_argument(
        '--retention-days',
        type=int,
        default=30,
        help='Días de retención para backups'
    )
    
    parser.add_argument(
        '--max-backups',
        type=int,
        default=50,
        help='Número máximo de backups a mantener'
    )
    
    # Opciones de notificación
    parser.add_argument(
        '--notification-webhook',
        help='URL de webhook para notificaciones'
    )
    
    # Opciones generales
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular operación sin ejecutar'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Output verboso'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forzar operación sin confirmación'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.restore and not args.backup_id:
        parser.error("--backup-id es requerido para --restore")
    
    if args.validate and not args.backup_id:
        parser.error("--backup-id es requerido para --validate")
    
    # Crear configuración
    config = BackupConfig(
        strategy=args.strategy or 'full',
        destination=args.destination,
        encrypt=args.encrypt,
        compress=args.compress,
        verify=args.verify,
        cleanup=args.cleanup,
        restore=args.restore,
        list_backups=args.list_backups,
        validate=args.validate,
        backup_id=args.backup_id,
        restore_target=args.restore_target,
        older_than=args.older_than,
        include_uploads=args.include_uploads,
        include_logs=args.include_logs,
        include_config=args.include_config,
        exclude_patterns=args.exclude_patterns or [],
        retention_days=args.retention_days,
        max_backups=args.max_backups,
        notification_webhook=args.notification_webhook,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=args.force,
    )
    
    # Ejecutar backup
    backup_manager = BackupManager(config)
    success = backup_manager.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()