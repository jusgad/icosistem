"""
Módulo de utilidades para la aplicación de gestión de postpenados.

Este módulo contiene diferentes utilidades y funciones auxiliares que
son utilizadas a través de toda la aplicación, incluyendo funciones
para interactuar con la base de datos PostgreSQL.
"""

# Importar funciones y clases existentes
from .decorators import role_required, ajax_required
from .validators import validate_email, validate_phone
from .formatters import format_currency, format_date, format_time
from .notifications import send_notification
from .pdf import generate_pdf
from .excel import generate_excel

# Importar utilidades de base de datos PostgreSQL
from .db_utils import (
    # Funciones de conexión
    get_db_url,
    create_db_engine,
    test_connection,
    
    # Funciones CRUD
    save_to_db,
    delete_from_db,
    get_by_id,
    get_all,
    update_object,
    
    # Consultas y transacciones
    execute_raw_query,
    execute_in_transaction,
    begin_transaction
)

# Definir __all__ para especificar qué se exporta cuando se hace 'from app.utils import *'
__all__ = [
    # Utilidades existentes
    'role_required',
    'ajax_required',
    'validate_email',
    'validate_phone',
    'format_currency',
    'format_date',
    'format_time',
    'send_notification',
    'generate_pdf',
    'generate_excel',
    
    # Utilidades de base de datos PostgreSQL
    'get_db_url',
    'create_db_engine',
    'test_connection',
    'save_to_db',
    'delete_from_db',
    'get_by_id',
    'get_all',
    'update_object',
    'execute_raw_query',
    'execute_in_transaction',
    'begin_transaction'
]