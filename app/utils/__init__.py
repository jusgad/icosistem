# app/utils/__init__.py

"""
Módulo de utilidades para la aplicación emprendimiento-app.

Este módulo contiene diferentes utilidades y funciones auxiliares que
son utilizadas a través de toda la aplicación.
"""

# Importar funciones y clases comunes para que sean accesibles
# directamente desde app.utils
from .decorators import role_required, ajax_required
from .validators import validate_email, validate_phone
from .formatters import format_currency, format_date, format_time
from .notifications import send_notification
from .pdf import generate_pdf
from .excel import generate_excel

# Definir __all__ para especificar qué se exporta cuando se hace 'from app.utils import *'
__all__ = [
    'role_required', 
    'ajax_required',
    'validate_email',
    'validate_phone',
    'format_currency',
    'format_date',
    'format_time',
    'send_notification',
    'generate_pdf',
    'generate_excel'
]