"""
Utilidades de Base de Datos - Ecosistema de Emprendimiento
=========================================================

Este módulo proporciona un conjunto completo de utilidades para manejo de base de datos,
incluyendo operaciones CRUD avanzadas, paginación, filtrado, transacciones, backup
y herramientas de migración específicas para el ecosistema de emprendimiento.

Características principales:
- Operaciones CRUD seguras y optimizadas
- Sistema de paginación eficiente
- Filtrado y búsqueda avanzada
- Manejo de transacciones con rollback automático
- Utilidades de backup y restore
- Query builder dinámico
- Soft delete y auditoría
- Bulk operations optimizadas
- Pool de conexiones inteligente

Uso básico:
-----------
    from app.utils.db_utils import get_or_create, paginate_query, DatabaseManager
    
    # Obtener o crear registro
    user, created = get_or_create(User, email='user@example.com', defaults={'name': 'Usuario'})
    
    # Paginación
    result = paginate_query(User.query, page=1, per_page=20)
    
    # Manager de BD
    db_manager = DatabaseManager()
    backup_file = db_manager.backup_table('users')
"""

import logging
import json
import csv
import gzip
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Type
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import threading
import time

# Imports de SQLAlchemy
try:
    from sqlalchemy import (
        create_engine, text, inspect, MetaData, Table, Column, 
        Integer, String, DateTime, Boolean, and_, or_, not_,
        func, distinct, case, desc, asc, nullslast, nullsfirst
    )
    from sqlalchemy.orm import sessionmaker, Session, Query, joinedload, selectinload
    from sqlalchemy.exc import (
        SQLAlchemyError, IntegrityError, InvalidRequestError,
        DisconnectionError, TimeoutError as SQLTimeoutError
    )
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.sql import ClauseElement
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logging.warning("SQLAlchemy no disponible. Algunas funcionalidades estarán limitadas.")

# Imports de Flask-SQLAlchemy si está disponible
try:
    from flask_sqlalchemy import SQLAlchemy
    from flask import current_app
    FLASK_SQLALCHEMY_AVAILABLE = True
except ImportError:
    FLASK_SQLALCHEMY_AVAILABLE = False

# Configurar logger
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================

# Configuración por defecto
DB_CONFIG = {
    'default_page_size': 20,
    'max_page_size': 100,
    'query_timeout': 30,
    'connection_pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'backup_dir': 'backups',
    'enable_query_logging': False,
    'soft_delete_column': 'deleted_at',
    'audit_columns': ['created_at', 'updated_at', 'created_by', 'updated_by'],
    'batch_size': 1000,
}

# Tipos de operación para auditoría
AUDIT_OPERATIONS = {
    'CREATE': 'create',
    'UPDATE': 'update',
    'DELETE': 'delete',
    'RESTORE': 'restore',
    'BULK_CREATE': 'bulk_create',
    'BULK_UPDATE': 'bulk_update',
    'BULK_DELETE': 'bulk_delete',
}

# ==============================================================================
# EXCEPCIONES PERSONALIZADAS
# ==============================================================================

class DatabaseError(Exception):
    """Excepción base para errores de base de datos."""
    pass

class ConnectionError(DatabaseError):
    """Error de conexión a la base de datos."""
    pass

class QueryError(DatabaseError):
    """Error en ejecución de consulta."""
    pass

class TransactionError(DatabaseError):
    """Error en transacción."""
    pass

class ValidationError(DatabaseError):
    """Error de validación de datos."""
    pass

class BackupError(DatabaseError):
    """Error en operaciones de backup."""
    pass

# ==============================================================================
# DECORADORES DE UTILIDAD
# ==============================================================================

def with_db_session(func: Callable) -> Callable:
    """
    Decorador que proporciona una sesión de BD y maneja errores.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada con manejo de sesión
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not SQLALCHEMY_AVAILABLE:
            raise DatabaseError("SQLAlchemy no está disponible")
        
        session = None
        try:
            # Intentar obtener sesión existente
            if hasattr(current_app, 'db') and FLASK_SQLALCHEMY_AVAILABLE:
                session = current_app.db.session
            else:
                # Crear nueva sesión
                engine = kwargs.get('engine') or get_default_engine()
                Session = sessionmaker(bind=engine)
                session = Session()
                kwargs['session'] = session
            
            result = func(*args, **kwargs)
            
            # Commit si no es una sesión de Flask-SQLAlchemy
            if 'session' in kwargs:
                session.commit()
            
            return result
            
        except Exception as e:
            if session and 'session' in kwargs:
                session.rollback()
            logger.error(f"Error en operación de BD: {e}")
            raise DatabaseError(f"Error en base de datos: {str(e)}")
        finally:
            if session and 'session' in kwargs:
                session.close()
    
    return wrapper

def measure_query_time(func: Callable) -> Callable:
    """
    Decorador que mide el tiempo de ejecución de consultas.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada con medición de tiempo
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            if DB_CONFIG['enable_query_logging']:
                logger.info(f"Consulta '{func.__name__}' ejecutada en {execution_time:.3f}s")
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error en consulta '{func.__name__}' después de {execution_time:.3f}s: {e}")
            raise
    
    return wrapper

def retry_db_operation(max_retries: int = 3, delay: float = 1.0):
    """
    Decorador que reintenta operaciones de BD en caso de fallo temporal.
    
    Args:
        max_retries: Número máximo de reintentos
        delay: Tiempo de espera entre reintentos
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (DisconnectionError, SQLTimeoutError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Intento {attempt + 1} falló, reintentando en {delay}s: {e}")
                        time.sleep(delay * (2 ** attempt))  # Backoff exponencial
                    else:
                        logger.error(f"Operación falló después de {max_retries} reintentos")
                        raise ConnectionError(f"Error de conexión después de {max_retries} reintentos: {e}")
                except Exception as e:
                    # Para otros tipos de error, no reintentar
                    raise e
            
            raise last_exception
        
        return wrapper
    return decorator

# ==============================================================================
# UTILIDADES DE SESIÓN Y CONEXIÓN
# ==============================================================================

def get_default_engine():
    """
    Obtiene el motor de BD por defecto.
    
    Returns:
        Motor de SQLAlchemy
    """
    if FLASK_SQLALCHEMY_AVAILABLE and hasattr(current_app, 'db'):
        return current_app.db.engine
    else:
        # Configuración por defecto para desarrollo
        return create_engine(
            'sqlite:///ecosystem.db',
            pool_size=DB_CONFIG['connection_pool_size'],
            max_overflow=DB_CONFIG['max_overflow'],
            pool_timeout=DB_CONFIG['pool_timeout'],
            echo=DB_CONFIG['enable_query_logging']
        )

@contextmanager
def get_db_session(engine=None):
    """
    Context manager para manejo de sesiones de BD.
    
    Args:
        engine: Motor de BD (opcional)
        
    Yields:
        Sesión de BD
        
    Examples:
        >>> with get_db_session() as session:
        ...     users = session.query(User).all()
    """
    if engine is None:
        engine = get_default_engine()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en sesión de BD: {e}")
        raise
    finally:
        session.close()

def test_connection(engine=None) -> bool:
    """
    Prueba la conexión a la base de datos.
    
    Args:
        engine: Motor de BD (opcional)
        
    Returns:
        True si la conexión es exitosa
    """
    try:
        if engine is None:
            engine = get_default_engine()
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        return False

# ==============================================================================
# OPERACIONES CRUD BÁSICAS
# ==============================================================================

@measure_query_time
@retry_db_operation(max_retries=2)
def get_or_create(model_class: Type, session: Optional[Session] = None, 
                  defaults: Optional[Dict] = None, **kwargs) -> Tuple[Any, bool]:
    """
    Obtiene un registro existente o crea uno nuevo.
    
    Args:
        model_class: Clase del modelo
        session: Sesión de BD (opcional)
        defaults: Valores por defecto para crear
        **kwargs: Filtros para buscar
        
    Returns:
        Tupla (instancia, creado)
        
    Examples:
        >>> user, created = get_or_create(User, email='test@example.com', 
        ...                               defaults={'name': 'Test User'})
    """
    if defaults is None:
        defaults = {}
    
    # Usar sesión proporcionada o crear nueva
    if session is None:
        with get_db_session() as session:
            return get_or_create(model_class, session, defaults, **kwargs)
    
    # Intentar obtener registro existente
    try:
        instance = session.query(model_class).filter_by(**kwargs).first()
        
        if instance:
            return instance, False
        else:
            # Crear nuevo registro
            create_kwargs = dict(kwargs, **defaults)
            instance = model_class(**create_kwargs)
            
            session.add(instance)
            session.flush()  # Para obtener ID sin commit
            
            return instance, True
            
    except IntegrityError as e:
        session.rollback()
        # Podría ser un race condition, intentar obtener de nuevo
        instance = session.query(model_class).filter_by(**kwargs).first()
        if instance:
            return instance, False
        else:
            raise QueryError(f"Error de integridad al crear {model_class.__name__}: {e}")

@measure_query_time
def bulk_create_or_update(model_class: Type, data_list: List[Dict], 
                         unique_fields: List[str], session: Optional[Session] = None,
                         batch_size: Optional[int] = None) -> Dict[str, int]:
    """
    Crea o actualiza múltiples registros de forma eficiente.
    
    Args:
        model_class: Clase del modelo
        data_list: Lista de diccionarios con datos
        unique_fields: Campos únicos para determinar si actualizar
        session: Sesión de BD (opcional)
        batch_size: Tamaño del lote
        
    Returns:
        Diccionario con estadísticas de operación
        
    Examples:
        >>> stats = bulk_create_or_update(User, [
        ...     {'email': 'user1@example.com', 'name': 'User 1'},
        ...     {'email': 'user2@example.com', 'name': 'User 2'}
        ... ], unique_fields=['email'])
    """
    if batch_size is None:
        batch_size = DB_CONFIG['batch_size']
    
    stats = {'created': 0, 'updated': 0, 'errors': 0}
    
    if session is None:
        with get_db_session() as session:
            return bulk_create_or_update(model_class, data_list, unique_fields, session, batch_size)
    
    try:
        # Procesar en lotes
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            
            for data in batch:
                try:
                    # Construir filtros únicos
                    unique_filter = {field: data[field] for field in unique_fields if field in data}
                    
                    if not unique_filter:
                        continue
                    
                    # Buscar registro existente
                    existing = session.query(model_class).filter_by(**unique_filter).first()
                    
                    if existing:
                        # Actualizar
                        for key, value in data.items():
                            if hasattr(existing, key):
                                setattr(existing, key, value)
                        stats['updated'] += 1
                    else:
                        # Crear
                        instance = model_class(**data)
                        session.add(instance)
                        stats['created'] += 1
                        
                except Exception as e:
                    logger.error(f"Error procesando registro {data}: {e}")
                    stats['errors'] += 1
                    continue
            
            # Commit por lotes
            session.commit()
            
        return stats
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error en bulk_create_or_update: {e}")
        raise QueryError(f"Error en operación masiva: {e}")

@measure_query_time
def safe_delete(model_class: Type, instance_id: Any, 
                session: Optional[Session] = None, soft_delete: bool = True) -> bool:
    """
    Elimina un registro de forma segura.
    
    Args:
        model_class: Clase del modelo
        instance_id: ID del registro
        session: Sesión de BD (opcional)
        soft_delete: Si usar borrado lógico
        
    Returns:
        True si se eliminó correctamente
        
    Examples:
        >>> deleted = safe_delete(User, user_id, soft_delete=True)
    """
    if session is None:
        with get_db_session() as session:
            return safe_delete(model_class, instance_id, session, soft_delete)
    
    try:
        instance = session.query(model_class).get(instance_id)
        
        if not instance:
            logger.warning(f"Registro {model_class.__name__}:{instance_id} no encontrado")
            return False
        
        if soft_delete and hasattr(instance, DB_CONFIG['soft_delete_column']):
            # Borrado lógico
            setattr(instance, DB_CONFIG['soft_delete_column'], datetime.utcnow())
            session.commit()
        else:
            # Borrado físico
            session.delete(instance)
            session.commit()
        
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error eliminando {model_class.__name__}:{instance_id}: {e}")
        raise QueryError(f"Error al eliminar registro: {e}")

@measure_query_time
def soft_delete(model_class: Type, instance_id: Any, session: Optional[Session] = None) -> bool:
    """
    Realiza borrado lógico de un registro.
    
    Args:
        model_class: Clase del modelo
        instance_id: ID del registro
        session: Sesión de BD (opcional)
        
    Returns:
        True si se eliminó correctamente
    """
    return safe_delete(model_class, instance_id, session, soft_delete=True)

@measure_query_time
def restore_deleted(model_class: Type, instance_id: Any, 
                   session: Optional[Session] = None) -> bool:
    """
    Restaura un registro eliminado lógicamente.
    
    Args:
        model_class: Clase del modelo
        instance_id: ID del registro
        session: Sesión de BD (opcional)
        
    Returns:
        True si se restauró correctamente
    """
    if session is None:
        with get_db_session() as session:
            return restore_deleted(model_class, instance_id, session)
    
    try:
        instance = session.query(model_class).get(instance_id)
        
        if not instance:
            return False
        
        if hasattr(instance, DB_CONFIG['soft_delete_column']):
            setattr(instance, DB_CONFIG['soft_delete_column'], None)
            session.commit()
            return True
        
        return False
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error restaurando {model_class.__name__}:{instance_id}: {e}")
        raise QueryError(f"Error al restaurar registro: {e}")

# ==============================================================================
# UTILIDADES DE PAGINACIÓN
# ==============================================================================

class PaginationResult:
    """Resultado de paginación con metadata útil."""
    
    def __init__(self, items: List[Any], page: int, per_page: int, 
                 total: int, has_prev: bool = False, has_next: bool = False):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.has_prev = has_prev
        self.has_next = has_next
        self.pages = (total + per_page - 1) // per_page  # Redondeo hacia arriba
        self.prev_num = page - 1 if has_prev else None
        self.next_num = page + 1 if has_next else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el resultado a diccionario."""
        return {
            'items': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in self.items],
            'pagination': {
                'page': self.page,
                'per_page': self.per_page,
                'total': self.total,
                'pages': self.pages,
                'has_prev': self.has_prev,
                'has_next': self.has_next,
                'prev_num': self.prev_num,
                'next_num': self.next_num
            }
        }

@measure_query_time
def paginate_query(query: Query, page: int = 1, per_page: Optional[int] = None,
                  max_per_page: Optional[int] = None) -> PaginationResult:
    """
    Pagina una consulta de SQLAlchemy de forma eficiente.
    
    Args:
        query: Consulta de SQLAlchemy
        page: Número de página (1-based)
        per_page: Registros por página
        max_per_page: Máximo registros por página
        
    Returns:
        PaginationResult con items y metadata
        
    Examples:
        >>> query = session.query(User).filter(User.active == True)
        >>> result = paginate_query(query, page=1, per_page=20)
        >>> print(f"Página {result.page} de {result.pages}")
    """
    if per_page is None:
        per_page = DB_CONFIG['default_page_size']
    
    if max_per_page is None:
        max_per_page = DB_CONFIG['max_page_size']
    
    # Validar parámetros
    page = max(1, page)
    per_page = min(max_per_page, max(1, per_page))
    
    # Contar total de registros (optimizado)
    total = query.count()
    
    # Calcular offset
    offset = (page - 1) * per_page
    
    # Obtener items de la página
    items = query.offset(offset).limit(per_page).all()
    
    # Calcular metadata
    has_prev = page > 1
    has_next = offset + per_page < total
    
    return PaginationResult(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        has_prev=has_prev,
        has_next=has_next
    )

def get_page_info(total_items: int, page: int, per_page: int) -> Dict[str, Any]:
    """
    Calcula información de paginación sin ejecutar consulta.
    
    Args:
        total_items: Total de registros
        page: Número de página
        per_page: Registros por página
        
    Returns:
        Diccionario con información de paginación
    """
    pages = (total_items + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < pages
    
    return {
        'page': page,
        'per_page': per_page,
        'total': total_items,
        'pages': pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None,
        'offset': (page - 1) * per_page
    }

# ==============================================================================
# UTILIDADES DE FILTRADO Y BÚSQUEDA
# ==============================================================================

class FilterBuilder:
    """Constructor dinámico de filtros para consultas."""
    
    def __init__(self, model_class: Type):
        self.model_class = model_class
        self.filters = []
        self.joins = []
        self.order_by = []
    
    def add_filter(self, field: str, value: Any, operator: str = 'eq') -> 'FilterBuilder':
        """
        Añade un filtro a la consulta.
        
        Args:
            field: Campo a filtrar
            value: Valor del filtro
            operator: Operador (eq, ne, lt, gt, le, ge, like, ilike, in, not_in)
            
        Returns:
            Self para encadenamiento
        """
        if not hasattr(self.model_class, field):
            logger.warning(f"Campo {field} no existe en {self.model_class.__name__}")
            return self
        
        column = getattr(self.model_class, field)
        
        if operator == 'eq':
            self.filters.append(column == value)
        elif operator == 'ne':
            self.filters.append(column != value)
        elif operator == 'lt':
            self.filters.append(column < value)
        elif operator == 'gt':
            self.filters.append(column > value)
        elif operator == 'le':
            self.filters.append(column <= value)
        elif operator == 'ge':
            self.filters.append(column >= value)
        elif operator == 'like':
            self.filters.append(column.like(f'%{value}%'))
        elif operator == 'ilike':
            self.filters.append(column.ilike(f'%{value}%'))
        elif operator == 'in':
            if isinstance(value, (list, tuple)):
                self.filters.append(column.in_(value))
        elif operator == 'not_in':
            if isinstance(value, (list, tuple)):
                self.filters.append(~column.in_(value))
        elif operator == 'is_null':
            self.filters.append(column.is_(None))
        elif operator == 'is_not_null':
            self.filters.append(column.isnot(None))
        
        return self
    
    def add_date_range(self, field: str, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None) -> 'FilterBuilder':
        """
        Añade filtro de rango de fechas.
        
        Args:
            field: Campo de fecha
            start_date: Fecha inicio (opcional)
            end_date: Fecha fin (opcional)
            
        Returns:
            Self para encadenamiento
        """
        if not hasattr(self.model_class, field):
            return self
        
        column = getattr(self.model_class, field)
        
        if start_date:
            self.filters.append(column >= start_date)
        if end_date:
            self.filters.append(column <= end_date)
        
        return self
    
    def add_search(self, search_term: str, fields: List[str]) -> 'FilterBuilder':
        """
        Añade búsqueda de texto en múltiples campos.
        
        Args:
            search_term: Término de búsqueda
            fields: Lista de campos donde buscar
            
        Returns:
            Self para encadenamiento
        """
        if not search_term or not fields:
            return self
        
        search_filters = []
        for field in fields:
            if hasattr(self.model_class, field):
                column = getattr(self.model_class, field)
                search_filters.append(column.ilike(f'%{search_term}%'))
        
        if search_filters:
            self.filters.append(or_(*search_filters))
        
        return self
    
    def add_order(self, field: str, direction: str = 'asc') -> 'FilterBuilder':
        """
        Añade ordenamiento.
        
        Args:
            field: Campo para ordenar
            direction: Dirección (asc, desc)
            
        Returns:
            Self para encadenamiento
        """
        if not hasattr(self.model_class, field):
            return self
        
        column = getattr(self.model_class, field)
        
        if direction.lower() == 'desc':
            self.order_by.append(desc(column))
        else:
            self.order_by.append(asc(column))
        
        return self
    
    def build_query(self, session: Session) -> Query:
        """
        Construye la consulta final.
        
        Args:
            session: Sesión de BD
            
        Returns:
            Query configurada
        """
        query = session.query(self.model_class)
        
        # Aplicar joins
        for join in self.joins:
            query = query.join(join)
        
        # Aplicar filtros
        if self.filters:
            query = query.filter(and_(*self.filters))
        
        # Aplicar ordenamiento
        if self.order_by:
            query = query.order_by(*self.order_by)
        
        return query

@measure_query_time
def apply_filters(query: Query, filters: Dict[str, Any]) -> Query:
    """
    Aplica filtros dinámicos a una consulta.
    
    Args:
        query: Consulta base
        filters: Diccionario de filtros
        
    Returns:
        Query con filtros aplicados
        
    Examples:
        >>> filters = {
        ...     'name__ilike': 'juan',
        ...     'age__gte': 18,
        ...     'city__in': ['bogota', 'medellin']
        ... }
        >>> filtered_query = apply_filters(User.query, filters)
    """
    model_class = query.column_descriptions[0]['type']
    
    for filter_key, filter_value in filters.items():
        if '__' in filter_key:
            field, operator = filter_key.split('__', 1)
        else:
            field, operator = filter_key, 'eq'
        
        if not hasattr(model_class, field):
            continue
        
        column = getattr(model_class, field)
        
        # Aplicar operador
        if operator == 'eq':
            query = query.filter(column == filter_value)
        elif operator == 'ne':
            query = query.filter(column != filter_value)
        elif operator == 'lt':
            query = query.filter(column < filter_value)
        elif operator == 'lte' or operator == 'le':
            query = query.filter(column <= filter_value)
        elif operator == 'gt':
            query = query.filter(column > filter_value)
        elif operator == 'gte' or operator == 'ge':
            query = query.filter(column >= filter_value)
        elif operator == 'like':
            query = query.filter(column.like(f'%{filter_value}%'))
        elif operator == 'ilike':
            query = query.filter(column.ilike(f'%{filter_value}%'))
        elif operator == 'in':
            if isinstance(filter_value, (list, tuple)):
                query = query.filter(column.in_(filter_value))
        elif operator == 'not_in':
            if isinstance(filter_value, (list, tuple)):
                query = query.filter(~column.in_(filter_value))
        elif operator == 'is_null':
            query = query.filter(column.is_(None))
        elif operator == 'is_not_null':
            query = query.filter(column.isnot(None))
    
    return query

@measure_query_time
def build_search_query(model_class: Type, search_term: str, 
                      search_fields: List[str], session: Session) -> Query:
    """
    Construye consulta de búsqueda de texto completo.
    
    Args:
        model_class: Clase del modelo
        search_term: Término de búsqueda
        search_fields: Campos donde buscar
        session: Sesión de BD
        
    Returns:
        Query de búsqueda
        
    Examples:
        >>> query = build_search_query(User, 'juan perez', ['name', 'email'], session)
    """
    query = session.query(model_class)
    
    if not search_term or not search_fields:
        return query
    
    # Dividir término en palabras
    words = search_term.strip().split()
    search_conditions = []
    
    for word in words:
        word_conditions = []
        for field in search_fields:
            if hasattr(model_class, field):
                column = getattr(model_class, field)
                word_conditions.append(column.ilike(f'%{word}%'))
        
        if word_conditions:
            search_conditions.append(or_(*word_conditions))
    
    # Todas las palabras deben encontrarse (AND)
    if search_conditions:
        query = query.filter(and_(*search_conditions))
    
    return query

# ==============================================================================
# UTILIDADES DE TRANSACCIONES
# ==============================================================================

@contextmanager
def atomic_transaction(session: Optional[Session] = None, rollback_on_error: bool = True):
    """
    Context manager para transacciones atómicas.
    
    Args:
        session: Sesión de BD (opcional)
        rollback_on_error: Si hacer rollback automático en error
        
    Yields:
        Sesión de BD
        
    Examples:
        >>> with atomic_transaction() as session:
        ...     user = User(name='Test')
        ...     session.add(user)
        ...     # Commit automático al salir del contexto
    """
    if session is None:
        with get_db_session() as session:
            yield session
        return
    
    savepoint = None
    try:
        # Crear savepoint si ya estamos en una transacción
        if session.in_transaction():
            savepoint = session.begin_nested()
        
        yield session
        
        if savepoint:
            savepoint.commit()
        else:
            session.commit()
            
    except Exception as e:
        if rollback_on_error:
            if savepoint:
                savepoint.rollback()
            else:
                session.rollback()
        
        logger.error(f"Error en transacción: {e}")
        raise TransactionError(f"Error en transacción: {e}")

def rollback_on_error(func: Callable) -> Callable:
    """
    Decorador que hace rollback automático en caso de error.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada con rollback automático
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get('session')
        
        if session:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                session.rollback()
                logger.error(f"Rollback ejecutado en {func.__name__}: {e}")
                raise
        else:
            return func(*args, **kwargs)
    
    return wrapper

# ==============================================================================
# UTILIDADES DE BACKUP Y RESTORE
# ==============================================================================

class BackupManager:
    """Manager para operaciones de backup y restore."""
    
    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = Path(backup_dir or DB_CONFIG['backup_dir'])
        self.backup_dir.mkdir(exist_ok=True)
    
    def backup_table(self, model_class: Type, session: Optional[Session] = None,
                    compress: bool = True) -> str:
        """
        Hace backup de una tabla completa.
        
        Args:
            model_class: Clase del modelo
            session: Sesión de BD (opcional)
            compress: Si comprimir el archivo
            
        Returns:
            Ruta del archivo de backup
        """
        if session is None:
            with get_db_session() as session:
                return self.backup_table(model_class, session, compress)
        
        table_name = model_class.__tablename__
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Determinar formato y extensión
        if compress:
            filename = f"{table_name}_backup_{timestamp}.json.gz"
            file_path = self.backup_dir / filename
        else:
            filename = f"{table_name}_backup_{timestamp}.json"
            file_path = self.backup_dir / filename
        
        try:
            # Obtener todos los registros
            records = session.query(model_class).all()
            
            # Convertir a diccionarios
            data = []
            for record in records:
                if hasattr(record, 'to_dict'):
                    data.append(record.to_dict())
                else:
                    # Conversión básica usando inspect
                    record_dict = {}
                    for column in model_class.__table__.columns:
                        value = getattr(record, column.name)
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        record_dict[column.name] = value
                    data.append(record_dict)
            
            # Metadata del backup
            backup_data = {
                'metadata': {
                    'table': table_name,
                    'timestamp': timestamp,
                    'record_count': len(data),
                    'created_by': 'BackupManager'
                },
                'data': data
            }
            
            # Guardar archivo
            if compress:
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Backup de {table_name} creado: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error creando backup de {table_name}: {e}")
            raise BackupError(f"Error en backup: {e}")
    
    def restore_table(self, backup_file: str, model_class: Type,
                     session: Optional[Session] = None, 
                     truncate_first: bool = False) -> int:
        """
        Restaura una tabla desde un archivo de backup.
        
        Args:
            backup_file: Ruta del archivo de backup
            model_class: Clase del modelo
            session: Sesión de BD (opcional)
            truncate_first: Si truncar la tabla antes de restaurar
            
        Returns:
            Número de registros restaurados
        """
        if session is None:
            with get_db_session() as session:
                return self.restore_table(backup_file, model_class, session, truncate_first)
        
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise BackupError(f"Archivo de backup no encontrado: {backup_file}")
        
        try:
            # Leer archivo de backup
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rt', encoding='utf-8') as f:
                    backup_data = json.load(f)
            else:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
            
            data = backup_data.get('data', [])
            
            if truncate_first:
                # Truncar tabla
                session.query(model_class).delete()
                session.commit()
            
            # Restaurar registros
            restored_count = 0
            for record_data in data:
                try:
                    # Convertir fechas ISO de vuelta a datetime
                    for key, value in record_data.items():
                        if isinstance(value, str) and 'T' in value:
                            try:
                                record_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            except ValueError:
                                pass  # No es una fecha
                    
                    instance = model_class(**record_data)
                    session.add(instance)
                    restored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error restaurando registro: {e}")
                    continue
            
            session.commit()
            logger.info(f"Restaurados {restored_count} registros en {model_class.__tablename__}")
            return restored_count
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error restaurando desde {backup_file}: {e}")
            raise BackupError(f"Error en restore: {e}")
    
    def list_backups(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista los archivos de backup disponibles.
        
        Args:
            table_name: Filtrar por nombre de tabla (opcional)
            
        Returns:
            Lista de información de backups
        """
        backups = []
        pattern = f"{table_name}_backup_*" if table_name else "*_backup_*"
        
        for backup_file in self.backup_dir.glob(pattern):
            try:
                # Extraer información del nombre
                parts = backup_file.stem.split('_backup_')
                if len(parts) == 2:
                    table = parts[0]
                    timestamp_part = parts[1].replace('.json', '')
                    
                    backup_info = {
                        'file': str(backup_file),
                        'table': table,
                        'timestamp': timestamp_part,
                        'size': backup_file.stat().st_size,
                        'compressed': backup_file.suffix == '.gz'
                    }
                    backups.append(backup_info)
                    
            except Exception as e:
                logger.warning(f"Error procesando archivo de backup {backup_file}: {e}")
        
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)

# Instancia global del backup manager
backup_manager = BackupManager()

def backup_table(model_class: Type, **kwargs) -> str:
    """Función de conveniencia para backup de tabla."""
    return backup_manager.backup_table(model_class, **kwargs)

def restore_table(backup_file: str, model_class: Type, **kwargs) -> int:
    """Función de conveniencia para restore de tabla."""
    return backup_manager.restore_table(backup_file, model_class, **kwargs)

# ==============================================================================
# QUERY BUILDER AVANZADO
# ==============================================================================

class QueryBuilder:
    """Constructor avanzado de consultas con fluent interface."""
    
    def __init__(self, model_class: Type, session: Session):
        self.model_class = model_class
        self.session = session
        self.query = session.query(model_class)
        self._joins = []
        self._filters = []
        self._order_by = []
        self._group_by = []
        self._having = []
        self._limit = None
        self._offset = None
    
    def join(self, *args, **kwargs) -> 'QueryBuilder':
        """Añade JOIN a la consulta."""
        self.query = self.query.join(*args, **kwargs)
        return self
    
    def outerjoin(self, *args, **kwargs) -> 'QueryBuilder':
        """Añade OUTER JOIN a la consulta."""
        self.query = self.query.outerjoin(*args, **kwargs)
        return self
    
    def filter(self, *criterion) -> 'QueryBuilder':
        """Añade filtros WHERE."""
        self.query = self.query.filter(*criterion)
        return self
    
    def filter_by(self, **kwargs) -> 'QueryBuilder':
        """Añade filtros WHERE por igualdad."""
        self.query = self.query.filter_by(**kwargs)
        return self
    
    def order_by(self, *criterion) -> 'QueryBuilder':
        """Añade ordenamiento."""
        self.query = self.query.order_by(*criterion)
        return self
    
    def group_by(self, *criterion) -> 'QueryBuilder':
        """Añade GROUP BY."""
        self.query = self.query.group_by(*criterion)
        return self
    
    def having(self, *criterion) -> 'QueryBuilder':
        """Añade HAVING."""
        self.query = self.query.having(*criterion)
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """Añade LIMIT."""
        self.query = self.query.limit(limit)
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """Añade OFFSET."""
        self.query = self.query.offset(offset)
        return self
    
    def distinct(self, *columns) -> 'QueryBuilder':
        """Añade DISTINCT."""
        if columns:
            self.query = self.query.distinct(*columns)
        else:
            self.query = self.query.distinct()
        return self
    
    def options(self, *args) -> 'QueryBuilder':
        """Añade opciones de carga (eager loading)."""
        self.query = self.query.options(*args)
        return self
    
    def with_entities(self, *entities) -> 'QueryBuilder':
        """Especifica entidades a retornar."""
        self.query = self.query.with_entities(*entities)
        return self
    
    def subquery(self) -> Any:
        """Convierte a subquery."""
        return self.query.subquery()
    
    def count(self) -> int:
        """Cuenta registros."""
        return self.query.count()
    
    def first(self) -> Optional[Any]:
        """Obtiene primer registro."""
        return self.query.first()
    
    def first_or_404(self) -> Any:
        """Obtiene primer registro o lanza 404."""
        result = self.query.first()
        if result is None:
            raise QueryError("Registro no encontrado")
        return result
    
    def one(self) -> Any:
        """Obtiene exactamente un registro."""
        return self.query.one()
    
    def one_or_none(self) -> Optional[Any]:
        """Obtiene un registro o None."""
        return self.query.one_or_none()
    
    def all(self) -> List[Any]:
        """Obtiene todos los registros."""
        return self.query.all()
    
    def paginate(self, page: int = 1, per_page: int = 20) -> PaginationResult:
        """Pagina la consulta."""
        return paginate_query(self.query, page, per_page)
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convierte resultados a lista de diccionarios."""
        results = self.all()
        return [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in results]
    
    def explain(self) -> str:
        """Obtiene plan de ejecución de la consulta."""
        try:
            explained = self.session.execute(
                text(f"EXPLAIN ANALYZE {str(self.query.statement.compile(compile_kwargs={'literal_binds': True}))}")
            )
            return '\n'.join([row[0] for row in explained])
        except Exception as e:
            logger.error(f"Error obteniendo EXPLAIN: {e}")
            return f"Error: {e}"

# ==============================================================================
# DATABASE MANAGER PRINCIPAL
# ==============================================================================

class DatabaseManager:
    """Manager principal para operaciones de base de datos."""
    
    def __init__(self, engine=None):
        self.engine = engine or get_default_engine()
        self.backup_manager = BackupManager()
        self._connection_pool_stats = {}
    
    def get_session(self) -> Session:
        """Obtiene nueva sesión de BD."""
        Session = sessionmaker(bind=self.engine)
        return Session()
    
    def test_connection(self) -> bool:
        """Prueba la conexión a la BD."""
        return test_connection(self.engine)
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Obtiene información de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            Información de la tabla
        """
        try:
            inspector = inspect(self.engine)
            
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            return {
                'name': table_name,
                'columns': columns,
                'indexes': indexes,
                'foreign_keys': foreign_keys,
                'column_count': len(columns),
                'index_count': len(indexes)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo info de tabla {table_name}: {e}")
            return {}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la base de datos.
        
        Returns:
            Estadísticas de BD
        """
        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            
            stats = {
                'table_count': len(table_names),
                'tables': table_names,
                'engine_info': str(self.engine.url),
                'pool_size': getattr(self.engine.pool, 'size', None),
                'checked_out': getattr(self.engine.pool, 'checkedout', None),
                'overflow': getattr(self.engine.pool, 'overflow', None),
            }
            
            # Estadísticas por tabla
            with self.get_session() as session:
                table_stats = {}
                for table_name in table_names:
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        table_stats[table_name] = {'record_count': count}
                    except Exception as e:
                        table_stats[table_name] = {'error': str(e)}
                
                stats['table_stats'] = table_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de BD: {e}")
            return {'error': str(e)}
    
    def optimize_table(self, table_name: str) -> bool:
        """
        Optimiza una tabla (específico del motor de BD).
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            True si se optimizó correctamente
        """
        try:
            # Para PostgreSQL
            if 'postgresql' in str(self.engine.url):
                with self.engine.connect() as conn:
                    conn.execute(text(f"VACUUM ANALYZE {table_name}"))
                    
            # Para MySQL
            elif 'mysql' in str(self.engine.url):
                with self.engine.connect() as conn:
                    conn.execute(text(f"OPTIMIZE TABLE {table_name}"))
            
            logger.info(f"Tabla {table_name} optimizada")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizando tabla {table_name}: {e}")
            return False
    
    def create_index(self, table_name: str, column_names: List[str], 
                    index_name: Optional[str] = None, unique: bool = False) -> bool:
        """
        Crea un índice en la tabla.
        
        Args:
            table_name: Nombre de la tabla
            column_names: Lista de columnas
            index_name: Nombre del índice (opcional)
            unique: Si el índice es único
            
        Returns:
            True si se creó correctamente
        """
        try:
            if not index_name:
                index_name = f"idx_{table_name}_{'_'.join(column_names)}"
            
            columns_str = ', '.join(column_names)
            unique_str = 'UNIQUE' if unique else ''
            
            sql = f"CREATE {unique_str} INDEX {index_name} ON {table_name} ({columns_str})"
            
            with self.engine.connect() as conn:
                conn.execute(text(sql))
            
            logger.info(f"Índice {index_name} creado en {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creando índice: {e}")
            return False
    
    def query_builder(self, model_class: Type) -> QueryBuilder:
        """
        Crea un query builder para el modelo.
        
        Args:
            model_class: Clase del modelo
            
        Returns:
            QueryBuilder configurado
        """
        session = self.get_session()
        return QueryBuilder(model_class, session)

# ==============================================================================
# FUNCIONES DE MIGRACIÓN Y MANTENIMIENTO
# ==============================================================================

class MigrationHelper:
    """Helper para operaciones de migración de datos."""
    
    def __init__(self, engine=None):
        self.engine = engine or get_default_engine()
    
    def add_column(self, table_name: str, column_name: str, 
                  column_type: str, nullable: bool = True, 
                  default_value: Any = None) -> bool:
        """
        Añade una columna a una tabla existente.
        
        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna
            column_type: Tipo de la columna (SQL)
            nullable: Si permite NULL
            default_value: Valor por defecto
            
        Returns:
            True si se añadió correctamente
        """
        try:
            null_str = 'NULL' if nullable else 'NOT NULL'
            default_str = f'DEFAULT {default_value}' if default_value is not None else ''
            
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {null_str} {default_str}"
            
            with self.engine.connect() as conn:
                conn.execute(text(sql))
            
            logger.info(f"Columna {column_name} añadida a {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error añadiendo columna: {e}")
            return False
    
    def drop_column(self, table_name: str, column_name: str) -> bool:
        """
        Elimina una columna de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
            
            with self.engine.connect() as conn:
                conn.execute(text(sql))
            
            logger.info(f"Columna {column_name} eliminada de {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando columna: {e}")
            return False
    
    def rename_column(self, table_name: str, old_name: str, new_name: str) -> bool:
        """
        Renombra una columna.
        
        Args:
            table_name: Nombre de la tabla
            old_name: Nombre actual
            new_name: Nuevo nombre
            
        Returns:
            True si se renombró correctamente
        """
        try:
            # El SQL varía según el motor de BD
            if 'postgresql' in str(self.engine.url):
                sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"
            elif 'mysql' in str(self.engine.url):
                # MySQL requiere especificar el tipo
                sql = f"ALTER TABLE {table_name} CHANGE {old_name} {new_name}"
            else:
                sql = f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"
            
            with self.engine.connect() as conn:
                conn.execute(text(sql))
            
            logger.info(f"Columna {old_name} renombrada a {new_name} en {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error renombrando columna: {e}")
            return False
    
    def migrate_data(self, source_query: str, target_table: str, 
                    field_mapping: Dict[str, str], batch_size: int = 1000) -> int:
        """
        Migra datos entre tablas con mapeo de campos.
        
        Args:
            source_query: Query fuente
            target_table: Tabla destino
            field_mapping: Mapeo de campos {source: target}
            batch_size: Tamaño del lote
            
        Returns:
            Número de registros migrados
        """
        migrated_count = 0
        
        try:
            with self.engine.connect() as conn:
                # Obtener datos fuente
                result = conn.execute(text(source_query))
                batch = []
                
                for row in result:
                    # Mapear campos
                    mapped_row = {}
                    for source_field, target_field in field_mapping.items():
                        if hasattr(row, source_field):
                            mapped_row[target_field] = getattr(row, source_field)
                    
                    batch.append(mapped_row)
                    
                    # Procesar lote
                    if len(batch) >= batch_size:
                        self._insert_batch(conn, target_table, batch)
                        migrated_count += len(batch)
                        batch = []
                
                # Procesar último lote
                if batch:
                    self._insert_batch(conn, target_table, batch)
                    migrated_count += len(batch)
            
            logger.info(f"Migrados {migrated_count} registros a {target_table}")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrando datos: {e}")
            raise QueryError(f"Error en migración: {e}")
    
    def _insert_batch(self, conn, table_name: str, batch: List[Dict]):
        """Inserta un lote de registros."""
        if not batch:
            return
        
        # Construir INSERT
        columns = list(batch[0].keys())
        placeholders = ', '.join([f':{col}' for col in columns])
        columns_str = ', '.join(columns)
        
        sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        conn.execute(text(sql), batch)

# ==============================================================================
# INSTANCIAS GLOBALES Y FUNCIONES DE CONVENIENCIA
# ==============================================================================

# Instancia global del database manager
db_manager = DatabaseManager()

# Instancia global del migration helper
migration_helper = MigrationHelper()

# Funciones de conveniencia que usan las instancias globales
def get_table_info(table_name: str) -> Dict[str, Any]:
    """Función de conveniencia para obtener info de tabla."""
    return db_manager.get_table_info(table_name)

def get_database_stats() -> Dict[str, Any]:
    """Función de conveniencia para obtener estadísticas de BD."""
    return db_manager.get_database_stats()

def optimize_table(table_name: str) -> bool:
    """Función de conveniencia para optimizar tabla."""
    return db_manager.optimize_table(table_name)

# Logging de inicialización
if SQLALCHEMY_AVAILABLE:
    logger.info("Módulo de utilidades de BD inicializado con SQLAlchemy")
else:
    logger.warning("Módulo de utilidades de BD inicializado sin SQLAlchemy")