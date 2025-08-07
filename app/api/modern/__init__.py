"""
Modern API module using Flask-RESTX with automatic documentation.
"""

from .v2 import api_v2_bp
from .auth import auth_ns
from .users import users_ns
from .entrepreneurs import entrepreneurs_ns
from .projects import projects_ns
from .health import health_ns

__all__ = [
    'api_v2_bp',
    'auth_ns',
    'users_ns',
    'entrepreneurs_ns', 
    'projects_ns',
    'health_ns'
]