"""
Security utilities for the entrepreneurship ecosystem.
"""

import re
from typing import Any


def validate_password_strength(password: str) -> dict[str, Any]:
    """Validate password strength with enhanced security requirements."""
    errors = []
    
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':".,<>?/~`]', password):
        errors.append("Password must contain at least one special character")
    
    # Check for common weak passwords
    common_passwords = ['password', '123456', 'admin', 'user', 'login']
    if password.lower() in common_passwords:
        errors.append("Password is too common and easily guessable")
    
    # Check for sequential characters
    if re.search(r'123|abc|qwe', password.lower()):
        errors.append("Password should not contain sequential characters")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'strength_score': max(0, 100 - len(errors) * 15)
    }


def validate_email_format(email: str) -> dict[str, Any]:
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


def log_security_event(event_type: str, details: dict[str, Any] = None, user_id: int = None):
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

def encrypt_sensitive_data(data: str, key: str = None) -> str:
    """Encrypt sensitive data using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
        import base64
        import os
        
        if key is None:
            key = os.environ.get('ENCRYPTION_KEY')
            if not key:
                # Generate a key if not provided (should be stored securely)
                key = Fernet.generate_key()
                
        if isinstance(key, str):
            key = key.encode()
            
        f = Fernet(base64.urlsafe_b64encode(key[:32].ljust(32, b'0')))
        encrypted_data = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    except Exception as e:
        log_security_event('encryption_error', {'error': str(e)})
        raise Exception(f"Encryption failed: {str(e)}")

def decrypt_sensitive_data(encrypted_data: str, key: str = None) -> str:
    """Decrypt sensitive data using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
        import base64
        import os
        
        if key is None:
            key = os.environ.get('ENCRYPTION_KEY')
            if not key:
                raise Exception("No encryption key provided")
                
        if isinstance(key, str):
            key = key.encode()
            
        f = Fernet(base64.urlsafe_b64encode(key[:32].ljust(32, b'0')))
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted_data = f.decrypt(encrypted_bytes)
        return decrypted_data.decode()
    except Exception as e:
        log_security_event('decryption_error', {'error': str(e)})
        raise Exception(f"Decryption failed: {str(e)}")

def sanitize_input(input_data: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent injection attacks."""
    import html
    import re
    
    if not input_data:
        return ""
    
    # Truncate if too long
    sanitized = input_data[:max_length]
    
    # Escape HTML entities
    sanitized = html.escape(sanitized)
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>&"\'\\]', '', sanitized)
    
    return sanitized.strip()

def validate_file_upload(filename: str, allowed_extensions: set) -> dict[str, Any]:
    """Validate file upload security."""
    import os
    
    if not filename:
        return {'is_valid': False, 'error': 'No filename provided'}
    
    # Check file extension
    file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if file_ext not in allowed_extensions:
        return {'is_valid': False, 'error': f'File type .{file_ext} not allowed'}
    
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        return {'is_valid': False, 'error': 'Invalid filename characters'}
    
    # Generate safe filename
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    
    return {
        'is_valid': True,
        'safe_filename': safe_filename,
        'original_filename': filename
    }