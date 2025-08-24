"""
Security utilities for the entrepreneurship ecosystem.
"""

import re
from typing import Dict, Any


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength."""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors
    }


def validate_email_format(email: str) -> Dict[str, Any]:
    """Validate email format."""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return {
            'is_valid': False,
            'error': 'Invalid email format'
        }
    
    return {
        'is_valid': True,
        'normalized_email': email.lower().strip()
    }


def log_security_event(event_type: str, details: Dict[str, Any] = None, user_id: int = None):
    """Log security event - stub implementation."""
    import logging
    logger = logging.getLogger('security')
    logger.info(f"Security event: {event_type}, User: {user_id}, Details: {details}")

def generate_secure_token(length: int = 32) -> str:
    """Generate secure random token."""
    import secrets
    return secrets.token_urlsafe(length)

def hash_password(password: str) -> str:
    """Hash password securely."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    from werkzeug.security import check_password_hash
    return check_password_hash(password_hash, password)