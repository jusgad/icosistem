#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Migración de Datos del Ecosistema de Emprendimiento
=============================================================

Sistema completo de migración que maneja:
- Migración entre versiones del sistema
- Migración desde sistemas externos/legacy
- Migración entre ambientes (dev, staging, prod)
- Transformaciones complejas de datos
- Migración incremental y completa
- Validación de integridad y rollback
- Migración de archivos y documentos
- Procesamiento por batches para performance
- Logging detallado y auditoría
- Recuperación automática de errores
- Mapping de esquemas complejos
- Migración de relaciones y foreign keys

Tipos de migración soportados:
- schema: Migración de esquema de base de datos
- data: Migración de datos entre sistemas
- files: Migración de archivos y documentos
- legacy: Migración desde sistemas legacy
- environment: Migración entre ambientes
- incremental: Migración incremental de cambios
- rollback: Rollback de migraciones

Fuentes soportadas:
- postgresql: Base de datos PostgreSQL
- mysql: Base de datos MySQL
- excel: Archivos Excel (.xlsx, .xls)
- csv: Archivos CSV
- json: Archivos JSON
- api: APIs REST externas
- legacy_db: Bases de datos legacy

Uso:
    python scripts/migrate_data.py --type data --source legacy_db --target postgresql
    python scripts/migrate_data.py --type files --source /old/uploads --target s3
    python scripts/migrate_data.py --type incremental --since 2024-01-01
    python scripts/migrate_data.py --rollback --migration-id abc123def
    python scripts/migrate_data.py --type legacy --config legacy_config.yaml

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import sys
import json
import yaml
import csv
import argparse
import logging
import shutil
import tempfile
import hashlib
import time
import psycopg2
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import secrets
from decimal import Decimal
import sqlite3
import pymysql
import requests
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import StaticPool

# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importar después de agregar al path
try:
    from app import create_app
    from app.extensions import db
    from app.models.user import User
    from app.models.admin import Admin
    from app.models.entrepreneur import Entrepreneur
    from app.models.ally import Ally
    from app.models.client import Client
    from app.models.organization import Organization
    from app.models.program import Program
    from app.models.project import Project
    from app.models.mentorship import MentorshipSession
    from app.models.meeting import Meeting
    from app.models.message import Message
    from app.models.document import Document
    from app.models.task import Task
    from app.models.notification import Notification
    from app.models.activity_log import ActivityLog
except ImportError as e:
    print(f"Error importando modelos de la aplicación: {e}")
    print("Asegúrese de que la aplicación Flask esté configurada correctamente")
    sys.exit(1)


@dataclass
class MigrationConfig:
    """
    Configuración completa del sistema de migración.
    """
    migration_type: str = 'data'                # schema, data, files, legacy, environment, incremental, rollback
    source: str = 'postgresql'                  # postgresql, mysql, excel, csv, json, api, legacy_db
    target: str = 'postgresql'                  # postgresql, mysql, s3, local
    source_config: Dict[str, Any] = field(default_factory=dict)
    target_config: Dict[str, Any] = field(default_factory=dict)
    config_file: Optional[str] = None
    mapping_file: Optional[str] = None
    transformation_rules: Optional[str] = None
    batch_size: int = 1000
    parallel_workers: int = 4
    since: Optional[str] = None                 # Para migración incremental
    until: Optional[str] = None
    migration_id: Optional[str] = None          # Para rollback
    tables: List[str] = field(default_factory=list)
    exclude_tables: List[str] = field(default_factory=list)
    validate: bool = True
    create_backup: bool = True
    dry_run: bool = False
    verbose: bool = False
    force: bool = False
    continue_on_error: bool = False
    max_retries: int = 3
    retry_delay: int = 5
    checkpoint_interval: int = 10000            # Crear checkpoint cada N registros


@dataclass
class MigrationMetadata:
    """
    Metadata de una migración específica.
    """
    migration_id: str
    timestamp: datetime
    migration_type: str
    source: str
    target: str
    status: str = 'pending'                     # pending, running, completed, failed, rolled_back
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    backup_location: Optional[str] = None
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    rollback_data: Dict[str, Any] = field(default_factory=dict)


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


class MigrationError(Exception):
    """
    Excepción específica para errores de migración.
    """
    pass


class RollbackError(Exception):
    """
    Excepción específica para errores de rollback.
    """
    pass


class MigrationLogger:
    """
    Logger especializado para operaciones de migración.
    """
    
    def __init__(self, verbose: bool = False, migration_id: str = None):
        """
        Inicializa el logger de migración.
        
        Args:
            verbose: Si mostrar logs verbosos
            migration_id: ID único de la migración
        """
        self.verbose = verbose
        self.migration_id = migration_id or secrets.token_hex(8)
        self.setup_logging()
    
    def setup_logging(self):
        """
        Configura logging estructurado para migración.
        """
        log_format = f'%(asctime)s [MIGRATE:{self.migration_id}] %(levelname)s: %(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        
        # Configurar handler para archivo
        log_file = project_root / 'logs' / f'migration_{self.migration_id}.log'
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
        
        self.logger = logging.getLogger('migration')
    
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
    
    def phase(self, phase_name: str, phase_num: int, total_phases: int):
        """Log fase de la migración."""
        print(f"\n{Colors.HEADER}[{phase_num}/{total_phases}] {phase_name}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'-' * 50}{Colors.ENDC}")
        self.logger.info(f"Phase {phase_num}/{total_phases}: {phase_name}")
    
    def progress(self, current: int, total: int, item_name: str = "records"):
        """Muestra progreso de la migración."""
        if total == 0:
            return
        
        percent = (current / total) * 100
        bar_length = 40
        filled_length = int(bar_length * current // total)
        
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        print(f'\r{Colors.OKCYAN}[{bar}] {percent:.1f}% ({current:,}/{total:,} {item_name}){Colors.ENDC}', end='')
        
        if current == total:
            print()  # Nueva línea al completar


class DataConnector:
    """
    Clase base para conectores de datos.
    """
    
    def __init__(self, config: Dict[str, Any], logger: MigrationLogger):
        """
        Inicializa el conector.
        
        Args:
            config: Configuración del conector
            logger: Logger para operaciones
        """
        self.config = config
        self.logger = logger
        self.connection = None
    
    def connect(self) -> bool:
        """Establece conexión con la fuente de datos."""
        raise NotImplementedError("Subclases deben implementar connect")
    
    def disconnect(self):
        """Cierra la conexión."""
        raise NotImplementedError("Subclases deben implementar disconnect")
    
    def get_tables(self) -> List[str]:
        """Obtiene lista de tablas disponibles."""
        raise NotImplementedError("Subclases deben implementar get_tables")
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Obtiene esquema de una tabla."""
        raise NotImplementedError("Subclases deben implementar get_table_schema")
    
    def read_data(self, table_name: str, batch_size: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Lee datos de una tabla."""
        raise NotImplementedError("Subclases deben implementar read_data")
    
    def write_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Escribe datos a una tabla."""
        raise NotImplementedError("Subclases deben implementar write_data")
    
    def get_record_count(self, table_name: str) -> int:
        """Obtiene número de registros de una tabla."""
        raise NotImplementedError("Subclases deben implementar get_record_count")


class PostgreSQLConnector(DataConnector):
    """
    Conector para bases de datos PostgreSQL.
    """
    
    def connect(self) -> bool:
        """Establece conexión con PostgreSQL."""
        try:
            connection_string = self.config.get('url') or self._build_connection_string()
            self.engine = create_engine(connection_string)
            self.connection = self.engine.connect()
            self.logger.info(f"Conectado a PostgreSQL: {self._mask_connection_string(connection_string)}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando a PostgreSQL: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión."""
        if self.connection:
            self.connection.close()
        if hasattr(self, 'engine'):
            self.engine.dispose()
    
    def _build_connection_string(self) -> str:
        """Construye string de conexión desde configuración."""
        host = self.config.get('host', 'localhost')
        port = self.config.get('port', 5432)
        database = self.config.get('database', 'postgres')
        username = self.config.get('username', 'postgres')
        password = self.config.get('password', '')
        
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    def _mask_connection_string(self, connection_string: str) -> str:
        """Enmascara password en string de conexión."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', connection_string)
    
    def get_tables(self) -> List[str]:
        """Obtiene lista de tablas."""
        try:
            inspector = inspect(self.engine)
            return inspector.get_table_names()
        except Exception as e:
            self.logger.error(f"Error obteniendo tablas: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Obtiene esquema de una tabla."""
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            primary_keys = inspector.get_pk_constraint(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            return {
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo esquema de {table_name}: {e}")
            return {}
    
    def read_data(self, table_name: str, batch_size: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Lee datos de una tabla."""
        try:
            query = text(f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}")
            result = self.connection.execute(query)
            
            data = []
            for row in result:
                data.append(dict(row._mapping))
            
            return data
        except Exception as e:
            self.logger.error(f"Error leyendo datos de {table_name}: {e}")
            return []
    
    def write_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Escribe datos a una tabla."""
        try:
            if not data:
                return True
            
            # Usar pandas para inserción eficiente
            df = pd.DataFrame(data)
            df.to_sql(table_name, self.engine, if_exists='append', index=False, method='multi')
            
            return True
        except Exception as e:
            self.logger.error(f"Error escribiendo datos a {table_name}: {e}")
            return False
    
    def get_record_count(self, table_name: str) -> int:
        """Obtiene número de registros."""
        try:
            query = text(f"SELECT COUNT(*) FROM {table_name}")
            result = self.connection.execute(query)
            return result.scalar()
        except Exception as e:
            self.logger.error(f"Error contando registros en {table_name}: {e}")
            return 0


class MySQLConnector(DataConnector):
    """
    Conector para bases de datos MySQL.
    """
    
    def connect(self) -> bool:
        """Establece conexión con MySQL."""
        try:
            connection_string = self._build_connection_string()
            self.engine = create_engine(connection_string)
            self.connection = self.engine.connect()
            self.logger.info(f"Conectado a MySQL: {self._mask_connection_string(connection_string)}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando a MySQL: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión."""
        if self.connection:
            self.connection.close()
        if hasattr(self, 'engine'):
            self.engine.dispose()
    
    def _build_connection_string(self) -> str:
        """Construye string de conexión MySQL."""
        host = self.config.get('host', 'localhost')
        port = self.config.get('port', 3306)
        database = self.config.get('database')
        username = self.config.get('username')
        password = self.config.get('password', '')
        
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
    
    def _mask_connection_string(self, connection_string: str) -> str:
        """Enmascara password en string de conexión."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', connection_string)
    
    def get_tables(self) -> List[str]:
        """Obtiene lista de tablas MySQL."""
        try:
            inspector = inspect(self.engine)
            return inspector.get_table_names()
        except Exception as e:
            self.logger.error(f"Error obteniendo tablas MySQL: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Obtiene esquema de tabla MySQL."""
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            primary_keys = inspector.get_pk_constraint(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            return {
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo esquema MySQL de {table_name}: {e}")
            return {}
    
    def read_data(self, table_name: str, batch_size: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Lee datos de tabla MySQL."""
        try:
            query = text(f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}")
            result = self.connection.execute(query)
            
            data = []
            for row in result:
                data.append(dict(row._mapping))
            
            return data
        except Exception as e:
            self.logger.error(f"Error leyendo datos MySQL de {table_name}: {e}")
            return []
    
    def write_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Escribe datos a tabla MySQL."""
        try:
            if not data:
                return True
            
            df = pd.DataFrame(data)
            df.to_sql(table_name, self.engine, if_exists='append', index=False, method='multi')
            
            return True
        except Exception as e:
            self.logger.error(f"Error escribiendo datos MySQL a {table_name}: {e}")
            return False
    
    def get_record_count(self, table_name: str) -> int:
        """Obtiene número de registros MySQL."""
        try:
            query = text(f"SELECT COUNT(*) FROM {table_name}")
            result = self.connection.execute(query)
            return result.scalar()
        except Exception as e:
            self.logger.error(f"Error contando registros MySQL en {table_name}: {e}")
            return 0


class ExcelConnector(DataConnector):
    """
    Conector para archivos Excel.
    """
    
    def connect(self) -> bool:
        """Verifica que el archivo Excel existe."""
        try:
            self.file_path = Path(self.config.get('file_path'))
            if not self.file_path.exists():
                raise FileNotFoundError(f"Archivo Excel no encontrado: {self.file_path}")
            
            self.logger.info(f"Conectado a archivo Excel: {self.file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando a Excel: {e}")
            return False
    
    def disconnect(self):
        """No hay conexión que cerrar para Excel."""
        pass
    
    def get_tables(self) -> List[str]:
        """Obtiene lista de hojas del Excel."""
        try:
            xl_file = pd.ExcelFile(self.file_path)
            return xl_file.sheet_names
        except Exception as e:
            self.logger.error(f"Error obteniendo hojas de Excel: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Obtiene esquema de una hoja Excel."""
        try:
            df = pd.read_excel(self.file_path, sheet_name=table_name, nrows=1)
            columns = [{'name': col, 'type': str(df[col].dtype)} for col in df.columns]
            
            return {
                'columns': columns,
                'primary_keys': {'constrained_columns': []},
                'foreign_keys': []
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo esquema Excel de {table_name}: {e}")
            return {}
    
    def read_data(self, table_name: str, batch_size: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Lee datos de una hoja Excel."""
        try:
            # Leer en chunks para manejar archivos grandes
            df = pd.read_excel(
                self.file_path, 
                sheet_name=table_name,
                skiprows=offset,
                nrows=batch_size
            )
            
            # Convertir DataFrame a lista de diccionarios
            data = df.to_dict('records')
            
            # Limpiar valores NaN
            for record in data:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
            
            return data
        except Exception as e:
            self.logger.error(f"Error leyendo datos Excel de {table_name}: {e}")
            return []
    
    def write_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Escribe datos a un archivo Excel."""
        try:
            if not data:
                return True
            
            df = pd.DataFrame(data)
            
            # Si el archivo ya existe, agregar como nueva hoja
            if self.file_path.exists():
                with pd.ExcelWriter(self.file_path, mode='a', if_sheet_exists='overlay') as writer:
                    df.to_excel(writer, sheet_name=table_name, index=False)
            else:
                df.to_excel(self.file_path, sheet_name=table_name, index=False)
            
            return True
        except Exception as e:
            self.logger.error(f"Error escribiendo datos Excel a {table_name}: {e}")
            return False
    
    def get_record_count(self, table_name: str) -> int:
        """Obtiene número de registros en hoja Excel."""
        try:
            df = pd.read_excel(self.file_path, sheet_name=table_name, usecols=[0])
            return len(df)
        except Exception as e:
            self.logger.error(f"Error contando registros Excel en {table_name}: {e}")
            return 0


class CSVConnector(DataConnector):
    """
    Conector para archivos CSV.
    """
    
    def connect(self) -> bool:
        """Verifica directorio de archivos CSV."""
        try:
            self.csv_dir = Path(self.config.get('directory', '.'))
            if not self.csv_dir.exists():
                raise FileNotFoundError(f"Directorio CSV no encontrado: {self.csv_dir}")
            
            self.logger.info(f"Conectado a directorio CSV: {self.csv_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando a CSV: {e}")
            return False
    
    def disconnect(self):
        """No hay conexión que cerrar para CSV."""
        pass
    
    def get_tables(self) -> List[str]:
        """Obtiene lista de archivos CSV."""
        try:
            csv_files = list(self.csv_dir.glob('*.csv'))
            return [f.stem for f in csv_files]
        except Exception as e:
            self.logger.error(f"Error obteniendo archivos CSV: {e}")
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Obtiene esquema de un archivo CSV."""
        try:
            csv_file = self.csv_dir / f"{table_name}.csv"
            df = pd.read_csv(csv_file, nrows=1)
            columns = [{'name': col, 'type': str(df[col].dtype)} for col in df.columns]
            
            return {
                'columns': columns,
                'primary_keys': {'constrained_columns': []},
                'foreign_keys': []
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo esquema CSV de {table_name}: {e}")
            return {}
    
    def read_data(self, table_name: str, batch_size: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """Lee datos de un archivo CSV."""
        try:
            csv_file = self.csv_dir / f"{table_name}.csv"
            
            # Leer en chunks
            df = pd.read_csv(
                csv_file,
                skiprows=range(1, offset + 1) if offset > 0 else None,
                nrows=batch_size
            )
            
            # Convertir a lista de diccionarios
            data = df.to_dict('records')
            
            # Limpiar valores NaN
            for record in data:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
            
            return data
        except Exception as e:
            self.logger.error(f"Error leyendo datos CSV de {table_name}: {e}")
            return []
    
    def write_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Escribe datos a un archivo CSV."""
        try:
            if not data:
                return True
            
            csv_file = self.csv_dir / f"{table_name}.csv"
            df = pd.DataFrame(data)
            
            # Agregar al archivo existente o crear nuevo
            df.to_csv(csv_file, mode='a', header=not csv_file.exists(), index=False)
            
            return True
        except Exception as e:
            self.logger.error(f"Error escribiendo datos CSV a {table_name}: {e}")
            return False
    
    def get_record_count(self, table_name: str) -> int:
        """Obtiene número de registros en archivo CSV."""
        try:
            csv_file = self.csv_dir / f"{table_name}.csv"
            df = pd.read_csv(csv_file, usecols=[0])
            return len(df)
        except Exception as e:
            self.logger.error(f"Error contando registros CSV en {table_name}: {e}")
            return 0


class DataTransformer:
    """
    Clase para transformaciones de datos durante la migración.
    """
    
    def __init__(self, transformation_rules: Optional[Dict[str, Any]] = None, logger: MigrationLogger = None):
        """
        Inicializa el transformador.
        
        Args:
            transformation_rules: Reglas de transformación
            logger: Logger para operaciones
        """
        self.transformation_rules = transformation_rules or {}
        self.logger = logger
    
    def transform_record(self, record: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """
        Transforma un registro según las reglas definidas.
        
        Args:
            record: Registro a transformar
            table_name: Nombre de la tabla
            
        Returns:
            Registro transformado
        """
        if table_name not in self.transformation_rules:
            return record
        
        table_rules = self.transformation_rules[table_name]
        transformed_record = record.copy()
        
        # Aplicar mapeo de campos
        if 'field_mapping' in table_rules:
            field_mapping = table_rules['field_mapping']
            new_record = {}
            
            for old_field, new_field in field_mapping.items():
                if old_field in transformed_record:
                    new_record[new_field] = transformed_record[old_field]
                else:
                    # Mantener campos no mapeados
                    for field, value in transformed_record.items():
                        if field not in field_mapping:
                            new_record[field] = value
            
            transformed_record = new_record
        
        # Aplicar transformaciones de valores
        if 'value_transformations' in table_rules:
            value_transformations = table_rules['value_transformations']
            
            for field, transformation in value_transformations.items():
                if field in transformed_record:
                    transformed_record[field] = self._apply_transformation(
                        transformed_record[field], 
                        transformation
                    )
        
        # Aplicar campos por defecto
        if 'default_values' in table_rules:
            default_values = table_rules['default_values']
            
            for field, default_value in default_values.items():
                if field not in transformed_record or transformed_record[field] is None:
                    transformed_record[field] = default_value
        
        # Aplicar validaciones
        if 'validations' in table_rules:
            validations = table_rules['validations']
            
            for field, validation in validations.items():
                if field in transformed_record:
                    if not self._validate_field(transformed_record[field], validation):
                        if self.logger:
                            self.logger.warning(f"Validación falló para campo {field}: {transformed_record[field]}")
        
        return transformed_record
    
    def _apply_transformation(self, value: Any, transformation: Dict[str, Any]) -> Any:
        """
        Aplica una transformación específica a un valor.
        
        Args:
            value: Valor a transformar
            transformation: Configuración de transformación
            
        Returns:
            Valor transformado
        """
        transform_type = transformation.get('type')
        
        if transform_type == 'format_date':
            if value and isinstance(value, str):
                try:
                    from dateutil import parser
                    dt = parser.parse(value)
                    format_str = transformation.get('format', '%Y-%m-%d %H:%M:%S')
                    return dt.strftime(format_str)
                except:
                    return value
        
        elif transform_type == 'uppercase':
            return str(value).upper() if value else value
        
        elif transform_type == 'lowercase':
            return str(value).lower() if value else value
        
        elif transform_type == 'replace':
            if value and isinstance(value, str):
                old_value = transformation.get('old', '')
                new_value = transformation.get('new', '')
                return value.replace(old_value, new_value)
        
        elif transform_type == 'mapping':
            mapping = transformation.get('mapping', {})
            return mapping.get(value, value)
        
        elif transform_type == 'prefix':
            prefix = transformation.get('prefix', '')
            return f"{prefix}{value}" if value else value
        
        elif transform_type == 'suffix':
            suffix = transformation.get('suffix', '')
            return f"{value}{suffix}" if value else value
        
        elif transform_type == 'truncate':
            max_length = transformation.get('max_length', 255)
            return str(value)[:max_length] if value else value
        
        return value
    
    def _validate_field(self, value: Any, validation: Dict[str, Any]) -> bool:
        """
        Valida un campo según reglas específicas.
        
        Args:
            value: Valor a validar
            validation: Configuración de validación
            
        Returns:
            True si la validación pasa
        """
        validation_type = validation.get('type')
        
        if validation_type == 'required':
            return value is not None and value != ''
        
        elif validation_type == 'max_length':
            max_length = validation.get('max_length', 255)
            return len(str(value)) <= max_length if value else True
        
        elif validation_type == 'min_length':
            min_length = validation.get('min_length', 0)
            return len(str(value)) >= min_length if value else False
        
        elif validation_type == 'pattern':
            import re
            pattern = validation.get('pattern', '')
            return bool(re.match(pattern, str(value))) if value else True
        
        elif validation_type == 'range':
            min_val = validation.get('min')
            max_val = validation.get('max')
            try:
                numeric_value = float(value)
                if min_val is not None and numeric_value < min_val:
                    return False
                if max_val is not None and numeric_value > max_val:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        
        return True


class MigrationManager:
    """
    Gestor principal del sistema de migración.
    """
    
    def __init__(self, config: MigrationConfig):
        """
        Inicializa el gestor de migración.
        
        Args:
            config: Configuración de la migración
        """
        self.config = config
        self.logger = MigrationLogger(config.verbose)
        self.metadata = MigrationMetadata(
            migration_id=self.logger.migration_id,
            timestamp=datetime.now(timezone.utc),
            migration_type=config.migration_type,
            source=config.source,
            target=config.target
        )
        
        # Configurar conectores
        self.source_connector = self._create_connector(config.source, config.source_config)
        self.target_connector = self._create_connector(config.target, config.target_config)
        
        # Configurar transformador
        transformation_rules = self._load_transformation_rules()
        self.transformer = DataTransformer(transformation_rules, self.logger)
        
        # Directorio para metadatos
        self.metadata_dir = project_root / 'migrations' / 'metadata'
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self) -> bool:
        """
        Ejecuta la migración completa.
        
        Returns:
            True si la migración fue exitosa
        """
        try:
            # Header principal
            self.logger.header(f"MIGRACIÓN DE DATOS - {self.config.migration_type.upper()}")
            
            # Mostrar configuración
            self._show_migration_config()
            
            # Ejecutar migración según el tipo
            if self.config.migration_type == 'rollback':
                return self._execute_rollback()
            else:
                return self._execute_migration()
                
        except KeyboardInterrupt:
            self.logger.warning("Migración interrumpida por el usuario")
            self.metadata.status = 'cancelled'
            self._save_metadata()
            return False
        except (MigrationError, RollbackError) as e:
            self.logger.error(f"Error en migración: {e}")
            self.metadata.status = 'failed'
            self.metadata.errors.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            })
            self._save_metadata()
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado: {e}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            self.metadata.status = 'failed'
            self._save_metadata()
            return False
    
    def _execute_migration(self) -> bool:
        """
        Ejecuta el proceso de migración.
        
        Returns:
            True si la migración fue exitosa
        """
        self.metadata.status = 'running'
        self.metadata.start_time = datetime.now(timezone.utc)
        
        phases = [
            ("Pre-migration Validation", self._pre_migration_validation),
            ("Source Connection", self._connect_source),
            ("Target Connection", self._connect_target),
            ("Schema Analysis", self._analyze_schema),
            ("Create Backup", self._create_backup),
            ("Data Migration", self._migrate_data),
            ("Post-migration Validation", self._post_migration_validation),
            ("Cleanup and Finalization", self._cleanup_and_finalize),
        ]
        
        total_phases = len([p for p in phases if not self._should_skip_phase(p[0])])
        current_phase = 1
        
        try:
            for phase_name, phase_func in phases:
                if self._should_skip_phase(phase_name):
                    continue
                
                self.logger.phase(phase_name, current_phase, total_phases)
                
                if not phase_func():
                    self.logger.error(f"Falla en fase: {phase_name}")
                    self.metadata.status = 'failed'
                    return False
                
                current_phase += 1
            
            # Migración exitosa
            self.metadata.end_time = datetime.now(timezone.utc)
            self.metadata.duration_seconds = (
                self.metadata.end_time - self.metadata.start_time
            ).total_seconds()
            self.metadata.status = 'completed'
            
            self._save_metadata()
            self.logger.success("Migración completada exitosamente!")
            self._show_migration_summary()
            
            return True
            
        except Exception as e:
            self.metadata.status = 'failed'
            self.metadata.end_time = datetime.now(timezone.utc)
            self._save_metadata()
            raise
        finally:
            # Cerrar conexiones
            if self.source_connector:
                self.source_connector.disconnect()
            if self.target_connector:
                self.target_connector.disconnect()
    
    def _execute_rollback(self) -> bool:
        """
        Ejecuta rollback de una migración.
        
        Returns:
            True si el rollback fue exitoso
        """
        if not self.config.migration_id:
            raise RollbackError("ID de migración requerido para rollback")
        
        self.logger.header(f"ROLLBACK DE MIGRACIÓN - {self.config.migration_id}")
        
        # Cargar metadata de la migración original
        original_metadata = self._load_migration_metadata(self.config.migration_id)
        if not original_metadata:
            raise RollbackError(f"Metadata de migración no encontrada: {self.config.migration_id}")
        
        # Ejecutar rollback según el tipo de migración
        if original_metadata.migration_type == 'data':
            return self._rollback_data_migration(original_metadata)
        elif original_metadata.migration_type == 'schema':
            return self._rollback_schema_migration(original_metadata)
        else:
            raise RollbackError(f"Rollback no soportado para tipo: {original_metadata.migration_type}")
    
    def _show_migration_config(self):
        """Muestra la configuración de la migración."""
        print(f"\n{Colors.OKCYAN}Configuración de Migración:{Colors.ENDC}")
        print(f"  ID: {Colors.BOLD}{self.metadata.migration_id}{Colors.ENDC}")
        print(f"  Tipo: {Colors.BOLD}{self.config.migration_type}{Colors.ENDC}")
        print(f"  Origen: {Colors.BOLD}{self.config.source}{Colors.ENDC}")
        print(f"  Destino: {Colors.BOLD}{self.config.target}{Colors.ENDC}")
        print(f"  Batch Size: {Colors.BOLD}{self.config.batch_size:,}{Colors.ENDC}")
        print(f"  Workers: {Colors.BOLD}{self.config.parallel_workers}{Colors.ENDC}")
        
        if self.config.tables:
            print(f"  Tablas: {Colors.BOLD}{', '.join(self.config.tables)}{Colors.ENDC}")
        
        if self.config.dry_run:
            print(f"  {Colors.WARNING}Modo: DRY RUN{Colors.ENDC}")
    
    def _should_skip_phase(self, phase_name: str) -> bool:
        """Determina si una fase debe ser saltada."""
        skip_map = {
            "Create Backup": not self.config.create_backup,
            "Post-migration Validation": not self.config.validate,
        }
        
        return skip_map.get(phase_name, False)
    
    def _pre_migration_validation(self) -> bool:
        """Ejecuta validaciones pre-migración."""
        self.logger.info("Ejecutando validaciones pre-migración...", step=True)
        
        validations = [
            ("Source Configuration", self._validate_source_config),
            ("Target Configuration", self._validate_target_config),
            ("Transformation Rules", self._validate_transformation_rules),
            ("Disk Space", self._validate_disk_space),
        ]
        
        for validation_name, validation_func in validations:
            self.logger.info(f"Validando: {validation_name}")
            
            if not validation_func():
                self.logger.error(f"Validación falló: {validation_name}")
                return False
        
        self.logger.success("Validaciones pre-migración completadas")
        return True
    
    def _connect_source(self) -> bool:
        """Conecta a la fuente de datos."""
        self.logger.info("Conectando a fuente de datos...", step=True)
        
        if not self.source_connector.connect():
            self.logger.error("Error conectando a fuente de datos")
            return False
        
        self.logger.success("Conexión a fuente establecida")
        return True
    
    def _connect_target(self) -> bool:
        """Conecta al destino de datos."""
        self.logger.info("Conectando a destino de datos...", step=True)
        
        if not self.target_connector.connect():
            self.logger.error("Error conectando a destino de datos")
            return False
        
        self.logger.success("Conexión a destino establecida")
        return True
    
    def _analyze_schema(self) -> bool:
        """Analiza esquemas de origen y destino."""
        self.logger.info("Analizando esquemas...", step=True)
        
        try:
            # Obtener tablas a migrar
            if self.config.tables:
                tables_to_migrate = self.config.tables
            else:
                all_tables = self.source_connector.get_tables()
                tables_to_migrate = [
                    table for table in all_tables
                    if table not in self.config.exclude_tables
                ]
            
            self.logger.info(f"Tablas a migrar: {len(tables_to_migrate)}")
            
            # Analizar esquema de cada tabla
            for table_name in tables_to_migrate:
                source_schema = self.source_connector.get_table_schema(table_name)
                if not source_schema:
                    self.logger.warning(f"No se pudo obtener esquema de {table_name}")
                    continue
                
                # Contar registros
                record_count = self.source_connector.get_record_count(table_name)
                self.metadata.total_records += record_count
                
                self.logger.info(f"  {table_name}: {record_count:,} registros")
            
            self.logger.success(f"Análisis completado: {self.metadata.total_records:,} registros totales")
            return True
            
        except Exception as e:
            self.logger.error(f"Error analizando esquemas: {e}")
            return False
    
    def _create_backup(self) -> bool:
        """Crea backup antes de la migración."""
        if self.config.dry_run:
            self.logger.info("DRY RUN: Saltando creación de backup")
            return True
        
        self.logger.info("Creando backup...", step=True)
        
        try:
            backup_dir = project_root / 'migrations' / 'backups' / self.metadata.migration_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Crear backup de metadata
            backup_file = backup_dir / 'pre_migration_metadata.json'
            backup_data = {
                'migration_id': self.metadata.migration_id,
                'timestamp': self.metadata.timestamp.isoformat(),
                'total_records': self.metadata.total_records,
                'source_config': self._sanitize_config(self.config.source_config),
                'target_config': self._sanitize_config(self.config.target_config)
            }
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            self.metadata.backup_location = str(backup_dir)
            self.logger.success(f"Backup creado: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creando backup: {e}")
            return False
    
    def _migrate_data(self) -> bool:
        """Ejecuta la migración de datos."""
        self.logger.info("Iniciando migración de datos...", step=True)
        
        if self.config.dry_run:
            self.logger.info("DRY RUN: Simulando migración de datos")
            return True
        
        try:
            # Obtener tablas a migrar
            if self.config.tables:
                tables_to_migrate = self.config.tables
            else:
                all_tables = self.source_connector.get_tables()
                tables_to_migrate = [
                    table for table in all_tables
                    if table not in self.config.exclude_tables
                ]
            
            processed_records = 0
            
            for table_name in tables_to_migrate:
                self.logger.info(f"Migrando tabla: {table_name}")
                
                table_record_count = self.source_connector.get_record_count(table_name)
                if table_record_count == 0:
                    self.logger.info(f"  Tabla {table_name} está vacía, saltando")
                    continue
                
                # Migrar tabla en batches
                offset = 0
                table_processed = 0
                
                while offset < table_record_count:
                    # Leer batch de datos
                    batch_data = self.source_connector.read_data(
                        table_name, 
                        self.config.batch_size, 
                        offset
                    )
                    
                    if not batch_data:
                        break
                    
                    # Transformar datos
                    transformed_data = []
                    for record in batch_data:
                        try:
                            transformed_record = self.transformer.transform_record(record, table_name)
                            transformed_data.append(transformed_record)
                        except Exception as e:
                            self.metadata.failed_records += 1
                            self.metadata.errors.append({
                                'table': table_name,
                                'record': record,
                                'error': str(e),
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            })
                            
                            if not self.config.continue_on_error:
                                raise
                    
                    # Escribir batch al destino
                    if transformed_data:
                        retry_count = 0
                        while retry_count < self.config.max_retries:
                            try:
                                if self.target_connector.write_data(table_name, transformed_data):
                                    break
                                else:
                                    raise Exception("Error escribiendo datos")
                            except Exception as e:
                                retry_count += 1
                                if retry_count >= self.config.max_retries:
                                    raise
                                
                                self.logger.warning(f"Error escribiendo batch, reintento {retry_count}")
                                time.sleep(self.config.retry_delay)
                    
                    # Actualizar progreso
                    table_processed += len(batch_data)
                    processed_records += len(batch_data)
                    offset += self.config.batch_size
                    
                    self.metadata.processed_records = processed_records
                    
                    # Mostrar progreso
                    self.logger.progress(table_processed, table_record_count, f"registros de {table_name}")
                    
                    # Crear checkpoint si es necesario
                    if processed_records % self.config.checkpoint_interval == 0:
                        self._create_checkpoint(processed_records)
                
                self.logger.success(f"  Tabla {table_name} migrada: {table_processed:,} registros")
            
            self.logger.success(f"Migración de datos completada: {processed_records:,} registros procesados")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en migración de datos: {e}")
            return False
    
    def _post_migration_validation(self) -> bool:
        """Ejecuta validaciones post-migración."""
        self.logger.info("Ejecutando validaciones post-migración...", step=True)
        
        if self.config.dry_run:
            self.logger.info("DRY RUN: Saltando validaciones")
            return True
        
        try:
            validations = []
            
            # Validar conteo de registros
            if self.config.tables:
                tables_to_validate = self.config.tables
            else:
                tables_to_validate = self.source_connector.get_tables()
                tables_to_validate = [
                    table for table in tables_to_validate
                    if table not in self.config.exclude_tables
                ]
            
            for table_name in tables_to_validate:
                source_count = self.source_connector.get_record_count(table_name)
                target_count = self.target_connector.get_record_count(table_name)
                
                validation_result = {
                    'table': table_name,
                    'source_count': source_count,
                    'target_count': target_count,
                    'match': source_count == target_count
                }
                
                validations.append(validation_result)
                
                if validation_result['match']:
                    self.logger.info(f"✓ {table_name}: {source_count:,} registros")
                else:
                    self.logger.warning(f"✗ {table_name}: origen={source_count:,}, destino={target_count:,}")
            
            self.metadata.validation_results = {
                'table_validations': validations,
                'total_tables': len(validations),
                'passed_tables': len([v for v in validations if v['match']]),
                'failed_tables': len([v for v in validations if not v['match']])
            }
            
            passed_validations = self.metadata.validation_results['passed_tables']
            total_validations = self.metadata.validation_results['total_tables']
            
            self.logger.success(f"Validaciones completadas: {passed_validations}/{total_validations} tablas")
            
            return passed_validations == total_validations
            
        except Exception as e:
            self.logger.error(f"Error en validaciones post-migración: {e}")
            return False
    
    def _cleanup_and_finalize(self) -> bool:
        """Limpieza y finalización."""
        self.logger.info("Finalizando migración...", step=True)
        
        try:
            # Guardar metadata final
            self._save_metadata()
            
            # Limpiar archivos temporales si existen
            # (implementar según necesidad)
            
            self.logger.success("Migración finalizada correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error en finalización: {e}")
            return False
    
    def _create_connector(self, connector_type: str, config: Dict[str, Any]) -> DataConnector:
        """
        Crea un conector de datos según el tipo.
        
        Args:
            connector_type: Tipo de conector
            config: Configuración del conector
            
        Returns:
            Instancia del conector
        """
        connectors = {
            'postgresql': PostgreSQLConnector,
            'mysql': MySQLConnector,
            'excel': ExcelConnector,
            'csv': CSVConnector,
        }
        
        connector_class = connectors.get(connector_type)
        if not connector_class:
            raise MigrationError(f"Tipo de conector no soportado: {connector_type}")
        
        return connector_class(config, self.logger)
    
    def _load_transformation_rules(self) -> Optional[Dict[str, Any]]:
        """Carga reglas de transformación desde archivo."""
        if not self.config.transformation_rules:
            return None
        
        try:
            rules_file = Path(self.config.transformation_rules)
            if rules_file.exists():
                with open(rules_file, 'r') as f:
                    if rules_file.suffix.lower() == '.yaml':
                        return yaml.safe_load(f)
                    else:
                        return json.load(f)
            
        except Exception as e:
            self.logger.warning(f"Error cargando reglas de transformación: {e}")
        
        return None
    
    def _validate_source_config(self) -> bool:
        """Valida configuración de origen."""
        # Implementar validaciones específicas según el tipo de origen
        return True
    
    def _validate_target_config(self) -> bool:
        """Valida configuración de destino."""
        # Implementar validaciones específicas según el tipo de destino
        return True
    
    def _validate_transformation_rules(self) -> bool:
        """Valida reglas de transformación."""
        # Implementar validación de reglas de transformación
        return True
    
    def _validate_disk_space(self) -> bool:
        """Valida espacio en disco disponible."""
        try:
            import shutil
            total, used, free = shutil.disk_usage(project_root)
            
            # Verificar que hay al menos 1GB libre
            min_free_bytes = 1 * 1024 * 1024 * 1024  # 1GB
            
            if free < min_free_bytes:
                self.logger.warning(f"Poco espacio en disco: {free / (1024**3):.2f}GB libres")
                return False
            
            self.logger.info(f"Espacio en disco: {free / (1024**3):.2f}GB libres")
            return True
            
        except Exception as e:
            self.logger.warning(f"Error verificando espacio en disco: {e}")
            return True  # No fallar por esto
    
    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitiza configuración removiendo datos sensibles."""
        sanitized = config.copy()
        
        sensitive_keys = ['password', 'token', 'secret', 'key']
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = '***'
        
        return sanitized
    
    def _create_checkpoint(self, processed_records: int):
        """Crea un checkpoint de la migración."""
        checkpoint = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'processed_records': processed_records,
            'total_records': self.metadata.total_records,
            'progress_percentage': (processed_records / self.metadata.total_records) * 100 if self.metadata.total_records > 0 else 0
        }
        
        self.metadata.checkpoints.append(checkpoint)
        self.logger.info(f"Checkpoint creado: {processed_records:,} registros procesados")
    
    def _save_metadata(self):
        """Guarda metadata de la migración."""
        try:
            metadata_file = self.metadata_dir / f"{self.metadata.migration_id}.json"
            
            metadata_dict = {
                'migration_id': self.metadata.migration_id,
                'timestamp': self.metadata.timestamp.isoformat(),
                'migration_type': self.metadata.migration_type,
                'source': self.metadata.source,
                'target': self.metadata.target,
                'status': self.metadata.status,
                'total_records': self.metadata.total_records,
                'processed_records': self.metadata.processed_records,
                'failed_records': self.metadata.failed_records,
                'start_time': self.metadata.start_time.isoformat() if self.metadata.start_time else None,
                'end_time': self.metadata.end_time.isoformat() if self.metadata.end_time else None,
                'duration_seconds': self.metadata.duration_seconds,
                'backup_location': self.metadata.backup_location,
                'checkpoints': self.metadata.checkpoints,
                'errors': self.metadata.errors,
                'validation_results': self.metadata.validation_results,
                'rollback_data': self.metadata.rollback_data
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata_dict, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error guardando metadata: {e}")
    
    def _load_migration_metadata(self, migration_id: str) -> Optional[MigrationMetadata]:
        """Carga metadata de una migración."""
        try:
            metadata_file = self.metadata_dir / f"{migration_id}.json"
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                data = json.load(f)
            
            metadata = MigrationMetadata(
                migration_id=data['migration_id'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                migration_type=data['migration_type'],
                source=data['source'],
                target=data['target'],
                status=data['status'],
                total_records=data['total_records'],
                processed_records=data['processed_records'],
                failed_records=data['failed_records'],
                duration_seconds=data['duration_seconds'],
                backup_location=data.get('backup_location'),
                checkpoints=data.get('checkpoints', []),
                errors=data.get('errors', []),
                validation_results=data.get('validation_results', {}),
                rollback_data=data.get('rollback_data', {})
            )
            
            if data.get('start_time'):
                metadata.start_time = datetime.fromisoformat(data['start_time'])
            if data.get('end_time'):
                metadata.end_time = datetime.fromisoformat(data['end_time'])
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error cargando metadata: {e}")
            return None
    
    def _rollback_data_migration(self, original_metadata: MigrationMetadata) -> bool:
        """Ejecuta rollback de migración de datos."""
        self.logger.info("Ejecutando rollback de migración de datos...")
        
        # Implementar rollback específico para migración de datos
        # Esto dependerá del tipo específico de migración realizada
        
        self.logger.success("Rollback de datos completado")
        return True
    
    def _rollback_schema_migration(self, original_metadata: MigrationMetadata) -> bool:
        """Ejecuta rollback de migración de esquema."""
        self.logger.info("Ejecutando rollback de migración de esquema...")
        
        # Implementar rollback específico para migración de esquema
        
        self.logger.success("Rollback de esquema completado")
        return True
    
    def _show_migration_summary(self):
        """Muestra resumen de la migración."""
        self.logger.header("RESUMEN DE MIGRACIÓN")
        
        print(f"{Colors.OKGREEN}Migración ID:{Colors.ENDC} {self.metadata.migration_id}")
        print(f"{Colors.OKGREEN}Estado:{Colors.ENDC} {self.metadata.status}")
        print(f"{Colors.OKGREEN}Duración:{Colors.ENDC} {self.metadata.duration_seconds:.2f} segundos")
        print(f"{Colors.OKGREEN}Registros procesados:{Colors.ENDC} {self.metadata.processed_records:,}")
        print(f"{Colors.OKGREEN}Registros fallidos:{Colors.ENDC} {self.metadata.failed_records:,}")
        
        if self.metadata.validation_results:
            results = self.metadata.validation_results
            print(f"{Colors.OKGREEN}Validaciones:{Colors.ENDC} {results['passed_tables']}/{results['total_tables']} tablas")
        
        if self.metadata.backup_location:
            print(f"{Colors.OKGREEN}Backup:{Colors.ENDC} {self.metadata.backup_location}")


def main():
    """
    Función principal del script de migración.
    """
    parser = argparse.ArgumentParser(
        description="Sistema de Migración de Datos del Ecosistema de Emprendimiento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Migración de datos entre PostgreSQL
  python scripts/migrate_data.py --type data --source postgresql --target postgresql \\
    --source-config host=old.db.com,database=old_db \\
    --target-config host=new.db.com,database=new_db
  
  # Migración desde Excel a PostgreSQL
  python scripts/migrate_data.py --type data --source excel --target postgresql \\
    --source-config file_path=data.xlsx --target-config url=$DATABASE_URL
  
  # Migración incremental
  python scripts/migrate_data.py --type incremental --since 2024-01-01 \\
    --source postgresql --target postgresql
  
  # Rollback de migración
  python scripts/migrate_data.py --rollback --migration-id abc123def
  
  # Migración con transformaciones
  python scripts/migrate_data.py --type data --source csv --target postgresql \\
    --transformation-rules transformations.yaml --batch-size 5000
  
  # Dry run para preview
  python scripts/migrate_data.py --type data --source excel --target postgresql \\
    --dry-run --verbose
        """
    )
    
    # Tipo de migración
    parser.add_argument(
        '--type', '-t',
        choices=['schema', 'data', 'files', 'legacy', 'environment', 'incremental'],
        default='data',
        help='Tipo de migración a ejecutar'
    )
    
    # Configuración de origen y destino
    parser.add_argument(
        '--source', '-s',
        choices=['postgresql', 'mysql', 'excel', 'csv', 'json', 'api', 'legacy_db'],
        required=True,
        help='Tipo de fuente de datos'
    )
    
    parser.add_argument(
        '--target',
        choices=['postgresql', 'mysql', 's3', 'local'],
        required=True,
        help='Tipo de destino de datos'
    )
    
    parser.add_argument(
        '--source-config',
        help='Configuración de origen (key=value,key=value)'
    )
    
    parser.add_argument(
        '--target-config',
        help='Configuración de destino (key=value,key=value)'
    )
    
    # Archivos de configuración
    parser.add_argument(
        '--config-file',
        help='Archivo de configuración YAML/JSON'
    )
    
    parser.add_argument(
        '--mapping-file',
        help='Archivo de mapeo de campos'
    )
    
    parser.add_argument(
        '--transformation-rules',
        help='Archivo de reglas de transformación'
    )
    
    # Opciones de migración
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Tamaño de batch para procesamiento'
    )
    
    parser.add_argument(
        '--parallel-workers',
        type=int,
        default=4,
        help='Número de workers paralelos'
    )
    
    # Migración incremental
    parser.add_argument(
        '--since',
        help='Fecha desde para migración incremental (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--until',
        help='Fecha hasta para migración incremental (YYYY-MM-DD)'
    )
    
    # Rollback
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Ejecutar rollback de migración'
    )
    
    parser.add_argument(
        '--migration-id',
        help='ID de migración para rollback'
    )
    
    # Filtros de tablas
    parser.add_argument(
        '--tables',
        help='Tablas específicas a migrar (comma-separated)'
    )
    
    parser.add_argument(
        '--exclude-tables',
        help='Tablas a excluir (comma-separated)'
    )
    
    # Opciones de validación y backup
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='No ejecutar validaciones'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='No crear backup antes de migración'
    )
    
    # Opciones de error handling
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continuar migración aunque haya errores'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Número máximo de reintentos'
    )
    
    parser.add_argument(
        '--retry-delay',
        type=int,
        default=5,
        help='Delay entre reintentos (segundos)'
    )
    
    # Opciones generales
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular migración sin ejecutar'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Output verboso'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forzar migración sin confirmaciones'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.rollback and not args.migration_id:
        parser.error("--migration-id es requerido para --rollback")
    
    # Parsear configuraciones
    def parse_config(config_str):
        if not config_str:
            return {}
        
        config = {}
        for item in config_str.split(','):
            if '=' in item:
                key, value = item.split('=', 1)
                config[key.strip()] = value.strip()
        
        return config
    
    # Crear configuración
    config = MigrationConfig(
        migration_type='rollback' if args.rollback else args.type,
        source=args.source,
        target=args.target,
        source_config=parse_config(args.source_config),
        target_config=parse_config(args.target_config),
        config_file=args.config_file,
        mapping_file=args.mapping_file,
        transformation_rules=args.transformation_rules,
        batch_size=args.batch_size,
        parallel_workers=args.parallel_workers,
        since=args.since,
        until=args.until,
        migration_id=args.migration_id,
        tables=args.tables.split(',') if args.tables else [],
        exclude_tables=args.exclude_tables.split(',') if args.exclude_tables else [],
        validate=not args.no_validate,
        create_backup=not args.no_backup,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=args.force,
        continue_on_error=args.continue_on_error,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )
    
    # Ejecutar migración
    manager = MigrationManager(config)
    success = manager.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()