"""
Security Utilities Module - Stub for compatibility

Basic security utility functions for CSRF protection and other security measures.
"""

import secrets
import hashlib
from typing import Optional


def validate_csrf_token(token: str, expected: Optional[str] = None) -> bool:
    """
    Validate CSRF token.
    
    Args:
        token: Token to validate
        expected: Expected token value
        
    Returns:
        True if token is valid
    """
    if not token:
        return False
    
    if expected:
        return token == expected
    
    # Basic validation - in production, this would be more sophisticated
    return len(token) >= 32 and token.isalnum()


def generate_csrf_token() -> str:
    """
    Generate a CSRF token.
    
    Returns:
        Generated CSRF token
    """
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """
    Hash a password (basic implementation).
    
    Args:
        password: Password to hash
        
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against hash.
    
    Args:
        password: Plain password
        hashed: Hashed password
        
    Returns:
        True if password matches
    """
    return hash_password(password) == hashed


__all__ = ['validate_csrf_token', 'generate_csrf_token', 'hash_password', 'verify_password']