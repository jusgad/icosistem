#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
ECOSISTEMA DE EMPRENDIMIENTO - CORE MODULE (MINIMAL VERSION)
============================================================================
Versión mínima del módulo core para permitir que la aplicación arranque.
============================================================================
"""

# === BASIC CONSTANTS ===
# Minimal constants needed by mixins
CACHE_TIMEOUT_SHORT = 300
CACHE_TIMEOUT_MEDIUM = 1800
CACHE_TIMEOUT_LONG = 3600

# === BASIC PERMISSIONS ===
# Stub implementations
def login_required(f):
    """Stub implementation of login_required."""
    return f

def role_required(role):
    """Stub implementation of role_required."""
    def decorator(f):
        return f
    return decorator

# === BASIC EXCEPTIONS ===
class ApplicationError(Exception):
    """Base application exception."""
    pass

class ValidationError(ApplicationError):
    """Validation error."""
    pass

class BusinessLogicError(ApplicationError):
    """Business logic error."""
    pass

# === EXPORTS ===
__all__ = [
    'CACHE_TIMEOUT_SHORT',
    'CACHE_TIMEOUT_MEDIUM', 
    'CACHE_TIMEOUT_LONG',
    'login_required',
    'role_required',
    'ApplicationError',
    'ValidationError',
    'BusinessLogicError'
]