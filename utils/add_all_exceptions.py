#!/usr/bin/env python3

missing_exceptions = [
    "ExternalServiceError", "ConfigurationError", "DatabaseError", 
    "CacheError", "EmailError", "FileError", "APIError", "RateLimitError",
    "SecurityError", "TokenError", "SessionError", "WebhookError"
]

exception_template = '''
class {name}(EcosistemaException):
    \"\"\"Exception raised for {desc} errors.\"\"\"
    
    def __init__(self, message=None):
        message = message or '{desc} error occurred'
        super().__init__(message, error_code='{code}')
'''

with open('app/core/exceptions.py', 'a') as f:
    for exc in missing_exceptions:
        code = exc.upper().replace('ERROR', '_ERROR')
        desc = exc.replace('Error', '').lower()
        f.write(exception_template.format(name=exc, code=code, desc=desc))

print(f"Added {len(missing_exceptions)} missing exceptions")