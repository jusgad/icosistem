#!/usr/bin/env python3
"""
Script para auto-reparar imports faltantes
"""

import os
import re

def add_missing_functions():
    """Add all missing functions detected."""
    
    # Add to date_utils.py
    with open('app/utils/date_utils.py', 'a') as f:
        f.write('''
def week_range(start_date, end_date):
    """Generate week range between dates."""
    from datetime import timedelta
    current = start_date - timedelta(days=start_date.weekday())
    while current <= end_date:
        yield current
        current += timedelta(weeks=1)

def year_range(start_date, end_date):
    """Generate year range between dates.""" 
    current = start_date.replace(month=1, day=1)
    while current.year <= end_date.year:
        yield current
        current = current.replace(year=current.year + 1)
''')
    
    # Add to file_utils.py
    with open('app/utils/file_utils.py', 'a') as f:
        f.write('''
def create_zip_archive(files, archive_path):
    """Create ZIP archive from files."""
    import zipfile
    import os
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            if os.path.exists(file_path):
                zipf.write(file_path, os.path.basename(file_path))
    return archive_path

def extract_archive(archive_path, destination):
    """Extract archive to destination."""
    import zipfile
    import os
    
    with zipfile.ZipFile(archive_path, 'r') as zipf:
        zipf.extractall(destination)
    return destination
''')
    
    # Add missing models to models/__init__.py
    with open('app/models/__init__.py', 'a') as f:
        f.write('''
# Additional model stubs
class Admin:
    """Admin model stub."""
    pass

class Organization:
    """Organization model stub."""
    pass

class Program:
    """Program model stub."""
    pass

class Activity:
    """Activity model stub."""  
    pass

# Export additional models
__all__.extend(['Admin', 'Organization', 'Program', 'Activity'])
''')

def add_missing_constants():
    """Add any missing constants."""
    with open('app/core/constants.py', 'a') as f:
        f.write('''
# Additional constants for complete functionality
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp'
LOG_FOLDER = 'logs'

# File type mappings
MIME_TYPES = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'txt': 'text/plain',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif'
}

# Status mappings
STATUS_MAPPINGS = {
    'active': 'Activo',
    'inactive': 'Inactivo',
    'pending': 'Pendiente',
    'suspended': 'Suspendido',
    'banned': 'Prohibido'
}
''')

def main():
    """Main repair function."""
    print("🔧 Auto-reparando imports faltantes...")
    
    try:
        add_missing_functions()
        print("✅ Funciones faltantes agregadas")
        
        add_missing_constants()
        print("✅ Constantes faltantes agregadas")
        
        print("🎉 Auto-reparación completada!")
        return True
    except Exception as e:
        print(f"❌ Error durante auto-reparación: {e}")
        return False

if __name__ == "__main__":
    main()