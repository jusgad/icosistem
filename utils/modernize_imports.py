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
    
    # Modernizar datetime.now(timezone.utc) -> datetime.now(timezone.utc)
    pattern = r'\bdatetime\.utcnow\(\)'
    if 'datetime.now(timezone.utc)' in content:
        if 'from datetime import' in content and 'timezone' not in content:
            content = re.sub(
                r'(from datetime import.*?)(\n)',
                r'\1, timezone\2',
                content,
                count=1
            )
        content = re.sub(pattern, 'datetime.now(timezone.utc)', content)
        replacements['datetime.now(timezone.utc)'] = len(re.findall(pattern, original_content))
    
    # Modernizar typing imports para Python 3.9+
    typing_replacements = [
        (r'\bList\[', 'list['),
        (r'\bDict\[', 'dict['),
        (r'\bTuple\[', 'tuple['),
        (r'\bSet\[', 'set['),
    ]
    
    for old_pattern, new_replacement in typing_replacements:
        matches = re.findall(old_pattern, content)
        if matches:
            content = re.sub(old_pattern, new_replacement, content)
            replacements[old_pattern] = len(matches)
    
    # Limpiar imports innecesarios de typing
    if any(replacement in content for _, replacement in typing_replacements):
        # Remover List, Dict, Tuple, Set de imports de typing si ya no se usan
        typing_import_pattern = r'        match = re.search(typing_import_pattern, content)
        if match:
            imports = [imp.strip() for imp in match.group(1).split(',')]
            imports_to_remove = {'List', 'Dict', 'Tuple', 'Set'}
            updated_imports = [imp for imp in imports if imp not in imports_to_remove]
            
            if updated_imports != imports:
                if updated_imports:
                    new_import_line = f"                    content = re.sub(typing_import_pattern, new_import_line, content)
                else:
                    # Remover la línea completa si no quedan imports
                    content = re.sub(r'                replacements['typing_cleanup'] = 1
    
    # Modernizar imports relativos problemáticos
    # Buscar patterns como "from .config import" en archivos de app/
    if 'app/' in str(file_path):
        if re.search(r'from \.config import', content):
            content = re.sub(r'from \.config import', 'from config import', content)
            replacements['relative_config_import'] = 1
    
    # Escribir el archivo solo si hubo cambios
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return replacements
        except Exception as e:
            print(f"❌ Error escribiendo {file_path}: {e}")
            return {}
    
    return {}

def modernize_project_imports(project_root: Path) -> dict[str, dict[str, int]]:
    """
    Moderniza imports en todo el proyecto.
    
    Returns:
        Diccionario con estadísticas por archivo
    """
    results = {}
    
    # Patrones de archivos a incluir
    include_patterns = [
        'app/**/*.py',
        'config/**/*.py',
        'runners/*.py',
        'utils/*.py',
        'scripts/*.py',
        'tests/**/*.py',
    ]
    
    # Archivos y carpetas a excluir
    exclude_patterns = [
        '*/migrations/*',
        '*/__pycache__/*',
        '*/node_modules/*',
        '*/.git/*',
        '*/venv/*',
        '*/env/*',
    ]
    
    python_files = []
    for pattern in include_patterns:
        python_files.extend(project_root.glob(pattern))
    
    # Filtrar archivos excluidos
    filtered_files = []
    for file_path in python_files:
        should_exclude = any(
            any(part == exclude_part for part in file_path.parts)
            for exclude_pattern in exclude_patterns
            for exclude_part in exclude_pattern.split('/')
            if exclude_part and exclude_part != '*'
        )
        if not should_exclude:
            filtered_files.append(file_path)
    
    print(f"🔍 Procesando {len(filtered_files)} archivos Python...")
    
    total_files_modified = 0
    total_replacements = 0
    
    for file_path in filtered_files:
        replacements = modernize_imports_in_file(file_path)
        if replacements:
            results[str(file_path.relative_to(project_root))] = replacements
            total_files_modified += 1
            total_replacements += sum(replacements.values())
            print(f"✅ {file_path.relative_to(project_root)}: {sum(replacements.values())} cambios")
    
    print(f"\n📊 RESUMEN:")
    print(f"   • Archivos modificados: {total_files_modified}")
    print(f"   • Total de reemplazos: {total_replacements}")
    
    return results

def main():
    """Función principal del script."""
    project_root = Path(__file__).parent.parent
    
    print("🚀 Iniciando modernización de imports...")
    print(f"📁 Directorio del proyecto: {project_root}")
    
    # Ejecutar modernización
    results = modernize_project_imports(project_root)
    
    # Mostrar resultados detallados
    if results:
        print(f"\n📋 ARCHIVOS MODIFICADOS ({len(results)}):")
        for file_path, replacements in results.items():
            print(f"   {file_path}:")
            for replacement_type, count in replacements.items():
                print(f"      - {replacement_type}: {count}")
    else:
        print("\n✨ No se encontraron imports para modernizar.")
    
    print(f"\n🎉 Modernización completada!")

if __name__ == '__main__':
    main()