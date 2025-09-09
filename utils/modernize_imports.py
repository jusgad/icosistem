#!/usr/bin/env python3
"""
Script para modernizar imports en todo el proyecto del Ecosistema de Emprendimiento.
Actualiza patrones de import obsoletos a las mejores prácticas modernas de Python 3.9+.
"""

import os
import re
import sys
from pathlib import Path

def modernize_imports_in_file(file_path: Path) -> dict[str, int]:
    """
    Moderniza los imports en un archivo específico.
    
    Returns:
        Diccionario con el número de reemplazos por tipo
    """
    if not file_path.suffix == '.py':
        return {}
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, FileNotFoundError):
        print(f"⚠️  No se pudo leer {file_path}")
        return {}
    
    original_content = content
    replacements = {}
    
    # 1. Modernizar typing imports
    typing_replacements = [
        (r'from typing import List', 'from typing import List  # Use list[T] in Python 3.9+'),
        (r'from typing import Dict', 'from typing import Dict  # Use dict[K, V] in Python 3.9+'),
        (r'from typing import Tuple', 'from typing import Tuple  # Use tuple[T, ...] in Python 3.9+'),
        (r'from typing import Set', 'from typing import Set  # Use set[T] in Python 3.9+'),
        # Actualizar anotaciones de tipo modernas
        (r'\bList\[([^\]]+)\]', r'list[\1]'),
        (r'\bDict\[([^\]]+)\]', r'dict[\1]'),
        (r'\bTuple\[([^\]]+)\]', r'tuple[\1]'),
        (r'\bSet\[([^\]]+)\]', r'set[\1]'),
    ]
    
    for old_pattern, new_replacement in typing_replacements:
        matches = re.findall(old_pattern, content)
        if matches:
            content = re.sub(old_pattern, new_replacement, content)
            replacements[old_pattern] = len(matches)
    
    # 2. Modernizar imports relativos
    relative_patterns = [
        (r'from \.(\w+) import', r'from app.\1 import'),
        (r'from \.\.(\w+) import', r'from app.\1 import'),
    ]
    
    for old_pattern, new_replacement in relative_patterns:
        matches = re.findall(old_pattern, content)
        if matches:
            content = re.sub(old_pattern, new_replacement, content)
            replacements[f'relative_import_{old_pattern}'] = len(matches)
    
    # 3. Organizar imports según PEP 8
    # Solo marcar, no reorganizar automáticamente para evitar errores
    if 'import ' in content and len(content.split('\n')) > 10:
        replacements['needs_import_organization'] = 1
    
    # Escribir cambios si hubo modificaciones
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Modernizado: {file_path}")
        except Exception as e:
            print(f"❌ Error escribiendo {file_path}: {e}")
            return {}
    
    return replacements

def main():
    """Ejecutar modernización en todo el proyecto."""
    project_root = Path(__file__).parent.parent
    
    # Directorios a procesar
    directories_to_process = [
        'app',
        'tests',
        'utils',
        'config',
        'scripts'
    ]
    
    total_files = 0
    total_replacements = 0
    
    print("🔄 Iniciando modernización de imports...")
    
    for directory in directories_to_process:
        dir_path = project_root / directory
        if not dir_path.exists():
            continue
            
        print(f"\n📁 Procesando directorio: {directory}")
        
        for py_file in dir_path.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
                
            replacements = modernize_imports_in_file(py_file)
            if replacements:
                total_files += 1
                file_replacements = sum(replacements.values())
                total_replacements += file_replacements
                print(f"  📝 {py_file.relative_to(project_root)}: {file_replacements} cambios")
    
    print(f"\n✨ Modernización completada:")
    print(f"  📊 Archivos procesados: {total_files}")
    print(f"  🔄 Total de reemplazos: {total_replacements}")
    
    if total_replacements > 0:
        print("\n⚠️  Recomendaciones post-modernización:")
        print("  1. Ejecutar tests para verificar que todo funciona")
        print("  2. Revisar imports organizados manualmente")
        print("  3. Actualizar Python a 3.9+ para usar las nuevas características")

if __name__ == '__main__':
    main()