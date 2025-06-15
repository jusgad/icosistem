"""
Utilidades de Archivos para el Ecosistema de Emprendimiento

Este módulo proporciona funciones helper para trabajar con archivos,
nombres de archivo, extensiones, tipos MIME y rutas seguras.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import os
import uuid
import mimetypes
import hashlib
from pathlib import Path
from typing import Optional, Set, Generator, Union, Dict, List

from werkzeug.utils import secure_filename as werkzeug_secure_filename
from flask import current_app

# Configuración de extensiones permitidas (ejemplo, podría estar en config.py)
# Se puede pasar como argumento a las funciones para mayor flexibilidad.
DEFAULT_ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
DEFAULT_ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv'}
DEFAULT_ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_IMAGE_EXTENSIONS.union(DEFAULT_ALLOWED_DOCUMENT_EXTENSIONS)

# Mapeo de extensiones a categorías (ejemplo)
FILE_CATEGORIES: Dict[str, List[str]] = {
    'image': ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff'],
    'document': ['pdf', 'doc', 'docx', 'odt', 'rtf', 'txt'],
    'spreadsheet': ['xls', 'xlsx', 'ods', 'csv'],
    'presentation': ['ppt', 'pptx', 'odp'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
    'audio': ['mp3', 'wav', 'ogg', 'aac'],
    'code': ['py', 'js', 'html', 'css', 'java', 'c', 'cpp', 'json', 'xml'],
}

def get_file_extension(filename: str) -> str:
    """
    Obtiene la extensión de un archivo.

    Args:
        filename: Nombre del archivo.

    Returns:
        Extensión del archivo en minúsculas (sin el punto).
        Retorna una cadena vacía si no hay extensión.
    """
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()

def is_allowed_extension(filename: str, allowed_extensions: Optional[Set[str]] = None) -> bool:
    """
    Verifica si la extensión de un archivo está permitida.

    Args:
        filename: Nombre del archivo.
        allowed_extensions: Conjunto de extensiones permitidas (ej. {'txt', 'pdf'}).
                            Si es None, usa DEFAULT_ALLOWED_EXTENSIONS.

    Returns:
        True si la extensión está permitida, False en caso contrario.
    """
    if allowed_extensions is None:
        allowed_extensions = DEFAULT_ALLOWED_EXTENSIONS
        
    extension = get_file_extension(filename)
    return extension in allowed_extensions

def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """
    Genera un nombre de archivo único para evitar colisiones.
    Formato: [prefijo_]uuid_timestamp.extension

    Args:
        original_filename: Nombre original del archivo.
        prefix: Prefijo opcional para el nombre del archivo.

    Returns:
        Nombre de archivo único.
    """
    extension = get_file_extension(original_filename)
    timestamp = int(datetime.utcnow().timestamp())
    unique_id = uuid.uuid4().hex[:8] # UUID corto para legibilidad
    
    base_name = f"{unique_id}_{timestamp}"
    if prefix:
        base_name = f"{prefix.strip('_')}_{base_name}"
        
    return f"{base_name}.{extension}" if extension else base_name

def secure_filename_custom(filename: str) -> str:
    """
    Genera un nombre de archivo seguro usando werkzeug.utils.secure_filename
    y aplicando sanitización adicional si es necesario.

    Args:
        filename: Nombre de archivo original.

    Returns:
        Nombre de archivo seguro.
    """
    if not filename:
        return ''
        
    # Usar la función de Werkzeug como base
    safe_name = werkzeug_secure_filename(filename)
    
    # Lógica adicional de sanitización (ejemplo)
    # Reemplazar múltiples guiones bajos o puntos con uno solo
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = re.sub(r'\.+', '.', safe_name)
    
    # Limitar longitud del nombre base (sin extensión)
    name_part, dot, ext_part = safe_name.rpartition('.')
    if len(name_part) > 100: # Límite arbitrario
        name_part = name_part[:100]
    
    return f"{name_part}{dot}{ext_part}" if dot else name_part

def get_mime_type(file_path_or_name: str) -> Optional[str]:
    """
    Adivina el tipo MIME de un archivo.

    Args:
        file_path_or_name: Ruta al archivo o nombre del archivo.

    Returns:
        Tipo MIME como string, o None si no se puede determinar.
    """
    mime_type, _ = mimetypes.guess_type(file_path_or_name)
    
    # Fallback si mimetypes no lo detecta, intentar con la librería magic
    if not mime_type and os.path.exists(file_path_or_name):
        try:
            import magic
            mime_type = magic.from_file(file_path_or_name, mime=True)
        except ImportError:
            current_app.logger.warning("Librería 'python-magic' no instalada. Detección de MIME limitada.")
        except Exception as e:
            current_app.logger.error(f"Error detectando MIME con python-magic: {e}")
            
    return mime_type

def sanitize_path_component(component: str) -> str:
    """
    Sanitiza un componente de ruta para evitar caracteres peligrosos.
    Útil para crear nombres de directorios o archivos de forma segura.

    Args:
        component: Componente de ruta a sanitizar.

    Returns:
        Componente sanitizado.
    """
    if not component:
        return ''
    
    # Reemplazar caracteres no alfanuméricos (excepto guiones y underscores) con un guion bajo
    sanitized = re.sub(r'[^\w\.-]', '_', component)
    # Evitar múltiples guiones bajos seguidos
    sanitized = re.sub(r'_+', '_', sanitized)
    # Eliminar guiones bajos al inicio o final
    sanitized = sanitized.strip('_')
    
    return sanitized

def construct_safe_path(base_path: Union[str, Path], *components: str) -> Path:
    """
    Construye una ruta de forma segura, sanitizando cada componente.
    Previene ataques de path traversal.

    Args:
        base_path: Ruta base.
        *components: Componentes adicionales de la ruta.

    Returns:
        Objeto Path de la ruta construida.
        
    Raises:
        ValueError: Si la ruta resultante no está contenida en la base_path.
    """
    base = Path(base_path).resolve()
    
    # Sanitizar cada componente
    sanitized_components = [sanitize_path_component(comp) for comp in components if comp]
    
    # Construir la ruta
    final_path = base.joinpath(*sanitized_components).resolve()
    
    # Verificar que la ruta final esté contenida en la ruta base
    if base not in final_path.parents and base != final_path:
        raise ValueError("Intento de Path Traversal detectado.")
        
    return final_path

def read_file_chunks(file_path: str, chunk_size: int = 8192) -> Generator[bytes, None, None]:
    """
    Lee un archivo en chunks. Útil para procesar archivos grandes.

    Args:
        file_path: Ruta al archivo.
        chunk_size: Tamaño del chunk en bytes.

    Yields:
        Chunks del archivo como bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except FileNotFoundError:
        current_app.logger.error(f"Archivo no encontrado en read_file_chunks: {file_path}")
        raise
    except Exception as e:
        current_app.logger.error(f"Error leyendo archivo en chunks {file_path}: {e}")
        raise

def calculate_file_hash(file_path: str, algorithm: str = 'sha256', chunk_size: int = 8192) -> str:
    """
    Calcula el hash de un archivo.

    Args:
        file_path: Ruta al archivo.
        algorithm: Algoritmo de hash a usar (ej. 'md5', 'sha1', 'sha256').
        chunk_size: Tamaño del chunk para leer el archivo.

    Returns:
        Hash hexadecimal del archivo.
    """
    hash_func = hashlib.new(algorithm)
    try:
        for chunk in read_file_chunks(file_path, chunk_size):
            hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        current_app.logger.error(f"Error calculando hash de archivo {file_path}: {e}")
        raise

def get_file_category(filename: str, mime_type: Optional[str] = None) -> str:
    """
    Categoriza un archivo basado en su extensión o tipo MIME.

    Args:
        filename: Nombre del archivo.
        mime_type: Tipo MIME (opcional, se intentará adivinar si no se provee).

    Returns:
        Categoría del archivo (ej. 'image', 'document', 'other').
    """
    extension = get_file_extension(filename)
    
    if not mime_type and extension:
        mime_type = get_mime_type(filename) # Adivinar MIME si no se provee
        
    # Primero intentar por tipo MIME
    if mime_type:
        for category, mimes_or_exts in FILE_CATEGORIES.items():
            # Asumimos que FILE_CATEGORIES podría tener mimes también, aunque el ejemplo solo tiene exts
            if any(mime_type.startswith(m_or_e) for m_or_e in mimes_or_exts if '/' in m_or_e):
                return category
    
    # Luego por extensión
    if extension:
        for category, extensions in FILE_CATEGORIES.items():
            if extension in extensions:
                return category
                
    return 'other'

def create_directory_if_not_exists(directory_path: Union[str, Path]) -> bool:
    """
    Crea un directorio si no existe.

    Args:
        directory_path: Ruta al directorio.

    Returns:
        True si el directorio fue creado o ya existía, False si hubo un error.
    """
    try:
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        current_app.logger.error(f"Error creando directorio {directory_path}: {e}")
        return False

def delete_file_if_exists(file_path: Union[str, Path]) -> bool:
    """
    Elimina un archivo si existe.

    Args:
        file_path: Ruta al archivo.

    Returns:
        True si el archivo fue eliminado o no existía, False si hubo un error.
    """
    try:
        path = Path(file_path)
        if path.is_file():
            path.unlink()
        return True
    except Exception as e:
        current_app.logger.error(f"Error eliminando archivo {file_path}: {e}")
        return False

# Exportaciones principales
__all__ = [
    'get_file_extension',
    'is_allowed_extension',
    'generate_unique_filename',
    'secure_filename_custom',
    'get_mime_type',
    'sanitize_path_component',
    'construct_safe_path',
    'read_file_chunks',
    'calculate_file_hash',
    'get_file_category',
    'create_directory_if_not_exists',
    'delete_file_if_exists',
    'DEFAULT_ALLOWED_EXTENSIONS',
    'DEFAULT_ALLOWED_IMAGE_EXTENSIONS',
    'DEFAULT_ALLOWED_DOCUMENT_EXTENSIONS',
    'FILE_CATEGORIES'
]
