"""
Utilidades para interactuar con la base de datos PostgreSQL.
Este módulo proporciona funciones para crear conexiones, realizar operaciones CRUD
y ejecutar consultas directas en la base de datos.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import inspect
from flask import current_app
from app import db

logger = logging.getLogger(__name__)

# Funciones de conexión y sesión
def get_db_url():
    """Obtiene la URL de conexión a la base de datos desde la configuración"""
    return current_app.config['SQLALCHEMY_DATABASE_URI']

def create_db_engine(db_url=None):
    """
    Crea un motor de SQLAlchemy para la conexión a la base de datos.
    
    Args:
        db_url (str, optional): URL de la base de datos. Si no se proporciona,
                               se obtiene de la configuración.
    
    Returns:
        Engine: Motor de SQLAlchemy para interactuar con la base de datos.
    """
    if db_url is None:
        db_url = get_db_url()
    
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        return engine
    except Exception as e:
        logger.error(f"Error al crear el motor de base de datos: {e}")
        raise

def test_connection(engine=None):
    """
    Prueba la conexión a la base de datos.
    
    Args:
        engine (Engine, optional): Motor de SQLAlchemy. Si no se proporciona,
                                  se crea uno nuevo.
    
    Returns:
        bool: True si la conexión es exitosa, False en caso contrario.
    """
    if engine is None:
        engine = create_db_engine()
    
    try:
        # Ejecuta una consulta simple para verificar la conexión
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error de conexión a la base de datos: {e}")
        return False

# Funciones CRUD genéricas
def save_to_db(item):
    """
    Guarda un objeto en la base de datos.
    
    Args:
        item: Instancia de un modelo SQLAlchemy a guardar
        
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario
    """
    try:
        db.session.add(item)
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error al guardar en la base de datos: {e}")
        return False

def delete_from_db(item):
    """
    Elimina un objeto de la base de datos.
    
    Args:
        item: Instancia de un modelo SQLAlchemy a eliminar
        
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario
    """
    try:
        db.session.delete(item)
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error al eliminar de la base de datos: {e}")
        return False

def get_by_id(model, item_id):
    """
    Obtiene un objeto de la base de datos por su ID.
    
    Args:
        model: Clase del modelo SQLAlchemy
        item_id: ID del objeto a recuperar
        
    Returns:
        object: Instancia del modelo o None si no existe
    """
    try:
        return model.query.get(item_id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener objeto con ID {item_id}: {e}")
        return None

def get_all(model, **filters):
    """
    Obtiene todos los objetos de un modelo con filtros opcionales.
    
    Args:
        model: Clase del modelo SQLAlchemy
        **filters: Filtros a aplicar (ej: estado='activo')
        
    Returns:
        list: Lista de instancias del modelo
    """
    try:
        query = model.query
        for attr, value in filters.items():
            if hasattr(model, attr):
                query = query.filter(getattr(model, attr) == value)
        return query.all()
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener objetos del modelo {model.__name__}: {e}")
        return []

def update_object(item, **kwargs):
    """
    Actualiza los atributos de un objeto y lo guarda en la base de datos.
    
    Args:
        item: Instancia de un modelo SQLAlchemy a actualizar
        **kwargs: Atributos a actualizar (ej: nombre='Nuevo nombre')
        
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario
    """
    try:
        # Actualizar solo los atributos que existen en el modelo
        mapper = inspect(item).mapper
        for key, value in kwargs.items():
            if key in mapper.column_attrs:
                setattr(item, key, value)
        
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error al actualizar objeto: {e}")
        return False

# Funciones para consultas directas
def execute_raw_query(query, params=None):
    """
    Ejecuta una consulta SQL directa.
    
    Args:
        query (str): Consulta SQL a ejecutar
        params (dict, optional): Parámetros para la consulta
        
    Returns:
        list: Resultado de la consulta o None en caso de error
    """
    try:
        result = db.session.execute(text(query), params or {})
        db.session.commit()
        return result
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error al ejecutar consulta SQL: {e}")
        return None

# Funciones de transacción
def execute_in_transaction(operations):
    """
    Ejecuta una serie de operaciones dentro de una transacción.
    
    Args:
        operations (callable): Función que realiza operaciones en la base de datos.
    
    Returns:
        any: El resultado de las operaciones o None en caso de error.
    """
    try:
        result = operations()
        db.session.commit()
        return result
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error en transacción de base de datos: {e}")
        return None

def begin_transaction():
    """Inicia una transacción manual"""
    return db.session.begin(subtransactions=True)