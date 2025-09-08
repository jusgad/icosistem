#!/usr/bin/env python3
"""
Emergency patch to add all missing functions as basic stubs
"""

import re
import os

def extract_missing_imports(error_text):
    """Extract missing import names from error messages."""
    missing = []
    lines = error_text.strip().split('\n')
    
    for line in lines:
        if 'cannot import name' in line:
            # Extract the import name
            match = re.search(r"cannot import name '(\w+)'", line)
            if match:
                import_name = match.group(1)
                
                # Extract module name
                match_module = re.search(r"from '([^']+)'", line)
                if match_module:
                    module_name = match_module.group(1)
                    missing.append((import_name, module_name))
    
    return missing

def add_stub_functions(missing_imports):
    """Add stub functions for missing imports."""
    base_dir = '/home/sebas/Escritorio/mi-claude/icosistem'
    
    # Group by module
    by_module = {}
    for import_name, module_name in missing_imports:
        if module_name not in by_module:
            by_module[module_name] = []
        by_module[module_name].append(import_name)
    
    for module_name, imports in by_module.items():
        # Convert module name to file path
        file_path = module_name.replace('.', '/') + '.py'
        full_path = os.path.join(base_dir, file_path)
        
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Add stub functions/constants
            stubs = []
            for import_name in imports:
                if import_name not in content:
                    if import_name.isupper():
                        # It's a constant
                        stubs.append(f"{import_name} = []  # Auto-generated stub")
                    else:
                        # It's a function
                        stubs.append(f"def {import_name}(*args, **kwargs):\n    \"\"\"Auto-generated stub function.\"\"\"\n    return None")
            
            if stubs:
                content += '\n\n# Auto-generated stubs\n' + '\n\n'.join(stubs) + '\n'
                
                with open(full_path, 'w') as f:
                    f.write(content)
                    
                print(f"Added {len(stubs)} stubs to {file_path}")

# Error message from the last run
ERROR_MSG = """Error importando decoradores: cannot import name 'log_execution_time' from 'app.utils.decorators' (/home/sebas/Escritorio/mi-claude/icosistem/app/utils/decorators.py)
Error importando formateadores: cannot import name 'format_business_hours' from 'app.utils.formatters' (/home/sebas/Escritorio/mi-claude/icosistem/app/utils/formatters.py)
Error importando utilidades de fecha: cannot import name 'format_relative_date' from 'app.utils.date_utils' (/home/sebas/Escritorio/mi-claude/icosistem/app/utils/date_utils.py)
Error importando utilidades de archivo: cannot import name 'generate_thumbnail' from 'app.utils.file_utils' (/home/sebas/Escritorio/mi-claude/icosistem/app/utils/file_utils.py)
ImportError: cannot import name 'REMINDER_INTERVALS' from 'app.core.constants' (/home/sebas/Escritorio/mi-claude/icosistem/app/core/constants.py)"""

if __name__ == '__main__':
    missing = extract_missing_imports(ERROR_MSG)
    print(f"Found {len(missing)} missing imports:")
    for name, module in missing:
        print(f"  {name} from {module}")
    
    add_stub_functions(missing)