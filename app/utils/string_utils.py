"""
Utilidades de String - Ecosistema de Emprendimiento
==================================================

Este módulo proporciona un conjunto completo de utilidades para manipulación,
limpieza, formateo y procesamiento de strings, optimizado para el idioma español
y el contexto empresarial colombiano.

Características principales:
- Limpieza y normalización de texto
- Conversiones de caso (snake_case, camelCase, PascalCase, kebab-case)
- Truncado inteligente y resumen de texto
- Búsqueda y reemplazo avanzado
- Generación de strings seguros y únicos
- Procesamiento de acentos y caracteres especiales
- Generación de slugs y URLs amigables
- Extracción de menciones y hashtags
- Validación y limpieza de nombres empresariales
- Utilidades específicas para emprendimiento

Uso básico:
-----------
    from app.utils.string_utils import clean_string, slugify, truncate
    
    # Limpiar string
    clean_text = clean_string("  Hola Mundo!  ")
    
    # Crear slug
    slug = slugify("Mi Empresa de Tecnología")  # "mi-empresa-de-tecnologia"
    
    # Truncar texto
    short_text = truncate("Texto muy largo...", max_length=50)
"""

import re
import unicodedata
import string
import secrets
import hashlib
import logging
from typing import List, Dict, Optional, Union, Tuple, Any, Pattern
from datetime import datetime
import html
import json
import base64
from urllib.parse import quote, unquote

# Configurar logger
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================

# Configuración por defecto
STRING_CONFIG = {
    'default_encoding': 'utf-8',
    'max_slug_length': 100,
    'truncate_suffix': '...',
    'random_string_chars': string.ascii_letters + string.digits,
    'safe_filename_chars': string.ascii_letters + string.digits + '-_.',
    'password_chars': string.ascii_letters + string.digits + '!@#$%^&*',
    'remove_accents_default': False,
    'default_locale': 'es_CO',
}

# Mapeo de caracteres con acentos a sin acentos
ACCENT_MAP = {
    'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ā': 'a', 'ã': 'a',
    'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'ē': 'e',
    'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ī': 'i',
    'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'ō': 'o', 'õ': 'o',
    'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ū': 'u',
    'ñ': 'n', 'ç': 'c',
    'Á': 'A', 'À': 'A', 'Ä': 'A', 'Â': 'A', 'Ā': 'A', 'Ã': 'A',
    'É': 'E', 'È': 'E', 'Ë': 'E', 'Ê': 'E', 'Ē': 'E',
    'Í': 'I', 'Ì': 'I', 'Ï': 'I', 'Î': 'I', 'Ī': 'I',
    'Ó': 'O', 'Ò': 'O', 'Ö': 'O', 'Ô': 'O', 'Ō': 'O', 'Õ': 'O',
    'Ú': 'U', 'Ù': 'U', 'Ü': 'U', 'Û': 'U', 'Ū': 'U',
    'Ñ': 'N', 'Ç': 'C'
}

# Palabras de parada en español para truncado inteligente
SPANISH_STOP_WORDS = {
    'a', 'ante', 'bajo', 'cabe', 'con', 'contra', 'de', 'desde', 'durante',
    'en', 'entre', 'hacia', 'hasta', 'mediante', 'para', 'por', 'según',
    'sin', 'so', 'sobre', 'tras', 'versus', 'vía', 'el', 'la', 'los', 'las',
    'un', 'una', 'unos', 'unas', 'y', 'e', 'o', 'u', 'pero', 'mas', 'sino',
    'que', 'como', 'cuando', 'donde', 'quien', 'cual', 'cuyo', 'este', 'esta',
    'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella',
    'aquellos', 'aquellas', 'mi', 'tu', 'su', 'nuestro', 'vuestro', 'suyo'
}

# Sectores empresariales comunes para normalización
BUSINESS_SECTORS = {
    'tech': ['tecnología', 'tecnologia', 'tech', 'tic', 'software', 'apps'],
    'agricultura': ['agricultura', 'agricola', 'agro', 'ganadería', 'ganaderia'],
    'manufactura': ['manufactura', 'industria', 'industrial', 'fabricación', 'fabricacion'],
    'servicios': ['servicios', 'consultoria', 'consultoría', 'asesoría', 'asesoria'],
    'comercio': ['comercio', 'retail', 'ventas', 'tienda', 'marketplace'],
    'turismo': ['turismo', 'hospitalidad', 'hotelería', 'hoteleria', 'viajes'],
    'educacion': ['educación', 'educacion', 'capacitación', 'capacitacion', 'formación'],
    'salud': ['salud', 'medicina', 'healthcare', 'bienestar', 'fitness'],
    'finanzas': ['finanzas', 'fintech', 'bancario', 'seguros', 'inversiones']
}

# Patrones regex compilados para performance
REGEX_PATTERNS = {
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'phone': re.compile(r'(\+?57\s?)?[0-9\s\-\(\)]{7,15}'),
    'url': re.compile(r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'),
    'mention': re.compile(r'@(\w+)'),
    'hashtag': re.compile(r'#(\w+)'),
    'whitespace': re.compile(r'\s+'),
    'non_alphanumeric': re.compile(r'[^a-zA-Z0-9\s]'),
    'html_tags': re.compile(r'<[^>]+>'),
    'multiple_spaces': re.compile(r'\s{2,}'),
    'line_breaks': re.compile(r'\n+'),
    'special_chars': re.compile(r'[^\w\s-]'),
    'numbers_only': re.compile(r'^\d+$'),
    'words': re.compile(r'\b\w+\b'),
    'camelcase': re.compile(r'([a-z0-9])([A-Z])'),
    'snake_case': re.compile(r'[^a-zA-Z0-9]+'),
}

# ==============================================================================
# FUNCIONES DE LIMPIEZA Y NORMALIZACIÓN
# ==============================================================================

def clean_string(text: str, 
                 remove_extra_spaces: bool = True,
                 remove_line_breaks: bool = False,
                 remove_special_chars: bool = False,
                 normalize_unicode: bool = True,
                 remove_html: bool = True) -> str:
    """
    Limpia y normaliza un string según parámetros especificados.
    
    Args:
        text: Texto a limpiar
        remove_extra_spaces: Si remover espacios extra
        remove_line_breaks: Si remover saltos de línea
        remove_special_chars: Si remover caracteres especiales
        normalize_unicode: Si normalizar caracteres Unicode
        remove_html: Si remover tags HTML
        
    Returns:
        Texto limpio
        
    Examples:
        >>> clean_string("  Hola   Mundo!  ")
        'Hola Mundo!'
        >>> clean_string("<p>Texto con HTML</p>", remove_html=True)
        'Texto con HTML'
    """
    if not text or not isinstance(text, str):
        return ""
    
    result = text
    
    # Remover HTML tags
    if remove_html:
        result = REGEX_PATTERNS['html_tags'].sub('', result)
        result = html.unescape(result)
    
    # Normalizar Unicode
    if normalize_unicode:
        result = unicodedata.normalize('NFKC', result)
    
    # Remover caracteres especiales
    if remove_special_chars:
        result = REGEX_PATTERNS['special_chars'].sub(' ', result)
    
    # Remover saltos de línea
    if remove_line_breaks:
        result = REGEX_PATTERNS['line_breaks'].sub(' ', result)
    
    # Remover espacios extra
    if remove_extra_spaces:
        result = REGEX_PATTERNS['multiple_spaces'].sub(' ', result)
        result = result.strip()
    
    return result

def normalize_string(text: str, 
                    lowercase: bool = True,
                    remove_accents: bool = False,
                    remove_punctuation: bool = False) -> str:
    """
    Normaliza un string para comparaciones o búsquedas.
    
    Args:
        text: Texto a normalizar
        lowercase: Si convertir a minúsculas
        remove_accents: Si remover acentos
        remove_punctuation: Si remover puntuación
        
    Returns:
        Texto normalizado
        
    Examples:
        >>> normalize_string("Café con Leche")
        'café con leche'
        >>> normalize_string("Café con Leche", remove_accents=True)
        'cafe con leche'
    """
    if not text or not isinstance(text, str):
        return ""
    
    result = text
    
    # Convertir a minúsculas
    if lowercase:
        result = result.lower()
    
    # Remover acentos
    if remove_accents:
        result = remove_accents_string(result)
    
    # Remover puntuación
    if remove_punctuation:
        result = result.translate(str.maketrans('', '', string.punctuation))
    
    # Limpiar espacios extra
    result = clean_string(result, remove_extra_spaces=True)
    
    return result

def remove_accents(text: str) -> str:
    """
    Remueve acentos y caracteres especiales del español.
    
    Args:
        text: Texto con acentos
        
    Returns:
        Texto sin acentos
        
    Examples:
        >>> remove_accents("Café con leche y niña")
        'Cafe con leche y nina'
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Usar mapeo personalizado para mayor control
    result = ""
    for char in text:
        result += ACCENT_MAP.get(char, char)
    
    return result

def remove_accents_string(text: str) -> str:
    """Alias para remove_accents para compatibilidad."""
    return remove_accents(text)

def sanitize_text(text: str, 
                  preserve_html: bool = False,
                  preserve_line_breaks: bool = True) -> str:
    """
    Sanitiza texto para prevenir inyección de código.
    
    Args:
        text: Texto a sanitizar
        preserve_html: Si preservar HTML seguro
        preserve_line_breaks: Si preservar saltos de línea
        
    Returns:
        Texto sanitizado
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Escapar HTML si no se va a preservar
    if not preserve_html:
        text = html.escape(text)
    
    # Remover caracteres de control
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    # Limpiar
    if not preserve_line_breaks:
        text = clean_string(text, remove_line_breaks=True)
    else:
        text = clean_string(text, remove_line_breaks=False)
    
    return text

# ==============================================================================
# CONVERSIONES DE CASO
# ==============================================================================

def to_snake_case(text: str) -> str:
    """
    Convierte texto a snake_case.
    
    Args:
        text: Texto a convertir
        
    Returns:
        Texto en snake_case
        
    Examples:
        >>> to_snake_case("MiEmpresaTecnológica")
        'mi_empresa_tecnologica'
        >>> to_snake_case("Empresa de Tecnología")
        'empresa_de_tecnologia'
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remover acentos
    text = remove_accents(text)
    
    # Insertar guión bajo antes de mayúsculas
    text = REGEX_PATTERNS['camelcase'].sub(r'\1_\2', text)
    
    # Reemplazar espacios y caracteres especiales con guión bajo
    text = REGEX_PATTERNS['snake_case'].sub('_', text)
    
    # Remover guiones bajos múltiples
    text = re.sub(r'_+', '_', text)
    
    # Limpiar inicio y final
    text = text.strip('_').lower()
    
    return text

def to_camel_case(text: str, capitalize_first: bool = False) -> str:
    """
    Convierte texto a camelCase.
    
    Args:
        text: Texto a convertir
        capitalize_first: Si capitalizar primera letra
        
    Returns:
        Texto en camelCase
        
    Examples:
        >>> to_camel_case("mi empresa tecnológica")
        'miEmpresaTecnologica'
        >>> to_camel_case("empresa_de_tecnologia")
        'empresaDeTecnologia'
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remover acentos
    text = remove_accents(text)
    
    # Dividir por espacios, guiones, guiones bajos
    words = re.split(r'[\s\-_]+', text)
    
    if not words:
        return ""
    
    # Primera palabra
    if capitalize_first:
        result = words[0].capitalize()
        start_index = 1
    else:
        result = words[0].lower()
        start_index = 1
    
    # Resto de palabras capitalizadas
    for word in words[start_index:]:
        if word:
            result += word.capitalize()
    
    return result

def to_pascal_case(text: str) -> str:
    """
    Convierte texto a PascalCase.
    
    Args:
        text: Texto a convertir
        
    Returns:
        Texto en PascalCase
        
    Examples:
        >>> to_pascal_case("mi empresa tecnológica")
        'MiEmpresaTecnologica'
    """
    return to_camel_case(text, capitalize_first=True)

def to_kebab_case(text: str) -> str:
    """
    Convierte texto a kebab-case.
    
    Args:
        text: Texto a convertir
        
    Returns:
        Texto en kebab-case
        
    Examples:
        >>> to_kebab_case("Mi Empresa Tecnológica")
        'mi-empresa-tecnologica'
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convertir a snake_case primero
    snake = to_snake_case(text)
    
    # Reemplazar guiones bajos con guiones
    return snake.replace('_', '-')

def to_title_case(text: str, preserve_articles: bool = True) -> str:
    """
    Convierte texto a Title Case respetando reglas del español.
    
    Args:
        text: Texto a convertir
        preserve_articles: Si preservar artículos en minúscula
        
    Returns:
        Texto en Title Case
        
    Examples:
        >>> to_title_case("empresa de tecnología y desarrollo")
        'Empresa de Tecnología y Desarrollo'
    """
    if not text or not isinstance(text, str):
        return ""
    
    words = text.lower().split()
    
    if not words:
        return ""
    
    # Primera palabra siempre se capitaliza
    result = [words[0].capitalize()]
    
    # Artículos y preposiciones que no se capitalizan (excepto al inicio)
    lowercase_words = {'de', 'del', 'la', 'el', 'las', 'los', 'y', 'e', 'o', 'u', 
                      'para', 'por', 'con', 'sin', 'en', 'a', 'ante'}
    
    for word in words[1:]:
        if preserve_articles and word in lowercase_words:
            result.append(word)
        else:
            result.append(word.capitalize())
    
    return ' '.join(result)

# ==============================================================================
# TRUNCADO Y RESUMEN
# ==============================================================================

def truncate(text: str, 
             max_length: int = 100,
             suffix: str = "...",
             preserve_words: bool = True,
             preserve_sentences: bool = False) -> str:
    """
    Trunca texto de forma inteligente.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo a añadir
        preserve_words: Si preservar palabras completas
        preserve_sentences: Si preservar oraciones completas
        
    Returns:
        Texto truncado
        
    Examples:
        >>> truncate("Esta es una descripción muy larga de mi empresa", 20)
        'Esta es una...'
        >>> truncate("Texto corto", 100)
        'Texto corto'
    """
    if not text or not isinstance(text, str):
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Ajustar longitud considerando el sufijo
    effective_length = max_length - len(suffix)
    
    if effective_length <= 0:
        return suffix[:max_length]
    
    if preserve_sentences:
        # Buscar el último punto antes del límite
        truncated = text[:effective_length]
        last_period = truncated.rfind('. ')
        if last_period > effective_length * 0.5:  # Al menos 50% del texto
            return text[:last_period + 1]
        
    if preserve_words:
        # Buscar el último espacio antes del límite
        truncated = text[:effective_length]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return truncated[:last_space] + suffix
    
    # Truncado simple
    return text[:effective_length] + suffix

def truncate_words(text: str, max_words: int = 50, suffix: str = "...") -> str:
    """
    Trunca texto por número de palabras.
    
    Args:
        text: Texto a truncar
        max_words: Número máximo de palabras
        suffix: Sufijo a añadir
        
    Returns:
        Texto truncado
        
    Examples:
        >>> truncate_words("Una dos tres cuatro cinco", 3)
        'Una dos tres...'
    """
    if not text or not isinstance(text, str):
        return ""
    
    words = text.split()
    
    if len(words) <= max_words:
        return text
    
    truncated_words = words[:max_words]
    return ' '.join(truncated_words) + suffix

def smart_truncate(text: str, 
                   max_length: int = 200,
                   min_length: int = 50,
                   preserve_paragraphs: bool = True) -> str:
    """
    Truncado inteligente que intenta preservar estructura del texto.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        min_length: Longitud mínima aceptable
        preserve_paragraphs: Si preservar párrafos completos
        
    Returns:
        Texto truncado inteligentemente
    """
    if not text or not isinstance(text, str):
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Intentar truncar por párrafos
    if preserve_paragraphs:
        paragraphs = text.split('\n\n')
        result = ""
        
        for paragraph in paragraphs:
            test_result = result + paragraph
            if len(test_result) <= max_length:
                result = test_result
            else:
                break
        
        if len(result) >= min_length:
            return result.strip()
    
    # Fallback a truncado normal
    return truncate(text, max_length, preserve_words=True)

def summarize_text(text: str, 
                   max_sentences: int = 3,
                   max_length: int = 300) -> str:
    """
    Crea un resumen del texto manteniendo las oraciones más importantes.
    
    Args:
        text: Texto a resumir
        max_sentences: Número máximo de oraciones
        max_length: Longitud máxima del resumen
        
    Returns:
        Resumen del texto
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Dividir en oraciones
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        result = '. '.join(sentences)
        if result and not result.endswith('.'):
            result += '.'
        return result if len(result) <= max_length else truncate(result, max_length)
    
    # Seleccionar las primeras oraciones (lógica simple)
    # En un caso real, se podría implementar un algoritmo más sofisticado
    selected_sentences = sentences[:max_sentences]
    result = '. '.join(selected_sentences)
    
    if not result.endswith('.'):
        result += '.'
    
    return result if len(result) <= max_length else truncate(result, max_length)

# ==============================================================================
# BÚSQUEDA Y REEMPLAZO
# ==============================================================================

def highlight_text(text: str, 
                   search_term: str,
                   highlight_tag: str = "mark",
                   case_sensitive: bool = False) -> str:
    """
    Resalta texto con tags HTML.
    
    Args:
        text: Texto base
        search_term: Término a resaltar
        highlight_tag: Tag HTML para resaltar
        case_sensitive: Si la búsqueda es sensible a mayúsculas
        
    Returns:
        Texto con términos resaltados
        
    Examples:
        >>> highlight_text("Empresa de tecnología", "tecnología")
        'Empresa de <mark>tecnología</mark>'
    """
    if not text or not search_term:
        return text
    
    flags = 0 if case_sensitive else re.IGNORECASE
    
    # Escapar caracteres especiales en el término de búsqueda
    escaped_term = re.escape(search_term)
    
    # Crear patrón para palabras completas
    pattern = rf'\b{escaped_term}\b'
    
    # Reemplazar con tags de resaltado
    highlighted = re.sub(
        pattern,
        f'<{highlight_tag}>\\g<0></{highlight_tag}>',
        text,
        flags=flags
    )
    
    return highlighted

def replace_variables(template: str, 
                     variables: Dict[str, str],
                     bracket_style: str = "curly") -> str:
    """
    Reemplaza variables en un template.
    
    Args:
        template: Template con variables
        variables: Diccionario de variables
        bracket_style: Estilo de brackets (curly, square, angle)
        
    Returns:
        Template con variables reemplazadas
        
    Examples:
        >>> template = "Hola {nombre}, bienvenido a {empresa}"
        >>> variables = {"nombre": "Juan", "empresa": "TechStart"}
        >>> replace_variables(template, variables)
        'Hola Juan, bienvenido a TechStart'
    """
    if not template or not isinstance(template, str):
        return ""
    
    if not variables:
        return template
    
    result = template
    
    # Definir patrones según el estilo
    if bracket_style == "curly":
        pattern = r'\{(\w+)\}'
    elif bracket_style == "square":
        pattern = r'\[(\w+)\]'
    elif bracket_style == "angle":
        pattern = r'<(\w+)>'
    else:
        pattern = r'\{(\w+)\}'
    
    # Función de reemplazo
    def replace_match(match):
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))
    
    # Aplicar reemplazos
    result = re.sub(pattern, replace_match, result)
    
    return result

def extract_mentions(text: str) -> List[str]:
    """
    Extrae menciones (@usuario) del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de menciones encontradas
        
    Examples:
        >>> extract_mentions("Hola @juan y @maria")
        ['juan', 'maria']
    """
    if not text or not isinstance(text, str):
        return []
    
    matches = REGEX_PATTERNS['mention'].findall(text)
    return list(set(matches))  # Remover duplicados

def extract_hashtags(text: str) -> List[str]:
    """
    Extrae hashtags (#tag) del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de hashtags encontrados
        
    Examples:
        >>> extract_hashtags("Mi #startup de #tecnología")
        ['startup', 'tecnología']
    """
    if not text or not isinstance(text, str):
        return []
    
    matches = REGEX_PATTERNS['hashtag'].findall(text)
    return list(set(matches))  # Remover duplicados

def extract_emails(text: str) -> List[str]:
    """
    Extrae direcciones de email del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de emails encontrados
    """
    if not text or not isinstance(text, str):
        return []
    
    matches = REGEX_PATTERNS['email'].findall(text)
    return list(set(matches))

def extract_urls(text: str) -> List[str]:
    """
    Extrae URLs del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de URLs encontradas
    """
    if not text or not isinstance(text, str):
        return []
    
    matches = REGEX_PATTERNS['url'].findall(text)
    return list(set(matches))

def extract_phones(text: str) -> List[str]:
    """
    Extrae números de teléfono del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de teléfonos encontrados
    """
    if not text or not isinstance(text, str):
        return []
    
    matches = REGEX_PATTERNS['phone'].findall(text)
    return list(set(matches))

# ==============================================================================
# GENERACIÓN DE STRINGS
# ==============================================================================

def generate_random_string(length: int = 8, 
                          chars: Optional[str] = None,
                          exclude_ambiguous: bool = True) -> str:
    """
    Genera string aleatorio seguro.
    
    Args:
        length: Longitud del string
        chars: Caracteres a usar (opcional)
        exclude_ambiguous: Si excluir caracteres ambiguos (0, O, l, I)
        
    Returns:
        String aleatorio
        
    Examples:
        >>> len(generate_random_string(10))
        10
        >>> generate_random_string(5, chars="ABC123")
        # Resultado como "A3B1C"
    """
    if chars is None:
        chars = STRING_CONFIG['random_string_chars']
    
    if exclude_ambiguous:
        # Remover caracteres ambiguos
        ambiguous = '0OlI1'
        chars = ''.join(c for c in chars if c not in ambiguous)
    
    if not chars:
        raise ValueError("No hay caracteres disponibles para generar string")
    
    return ''.join(secrets.choice(chars) for _ in range(length))

def generate_slug(text: str, 
                  max_length: Optional[int] = None,
                  allow_unicode: bool = False) -> str:
    """
    Genera slug URL-amigable desde texto.
    
    Args:
        text: Texto base
        max_length: Longitud máxima del slug
        allow_unicode: Si permitir caracteres Unicode
        
    Returns:
        Slug generado
        
    Examples:
        >>> generate_slug("Mi Empresa de Tecnología")
        'mi-empresa-de-tecnologia'
        >>> generate_slug("Startup & Innovación!")
        'startup-innovacion'
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Limpiar texto
    slug = clean_string(text, remove_html=True)
    
    if not allow_unicode:
        # Remover acentos
        slug = remove_accents(slug)
    
    # Convertir a minúsculas
    slug = slug.lower()
    
    # Reemplazar espacios y caracteres especiales con guiones
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    
    # Remover guiones al inicio y final
    slug = slug.strip('-')
    
    # Aplicar longitud máxima
    if max_length is None:
        max_length = STRING_CONFIG['max_slug_length']
    
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')
    
    return slug

def slugify(text: str, **kwargs) -> str:
    """Alias para generate_slug."""
    return generate_slug(text, **kwargs)

def generate_password(length: int = 12,
                     include_uppercase: bool = True,
                     include_lowercase: bool = True,
                     include_numbers: bool = True,
                     include_symbols: bool = True,
                     exclude_ambiguous: bool = True) -> str:
    """
    Genera contraseña segura.
    
    Args:
        length: Longitud de la contraseña
        include_uppercase: Incluir mayúsculas
        include_lowercase: Incluir minúsculas
        include_numbers: Incluir números
        include_symbols: Incluir símbolos
        exclude_ambiguous: Excluir caracteres ambiguos
        
    Returns:
        Contraseña generada
    """
    chars = ""
    
    if include_lowercase:
        chars += string.ascii_lowercase
    if include_uppercase:
        chars += string.ascii_uppercase
    if include_numbers:
        chars += string.digits
    if include_symbols:
        chars += "!@#$%^&*"
    
    if exclude_ambiguous:
        ambiguous = '0OlI1'
        chars = ''.join(c for c in chars if c not in ambiguous)
    
    if not chars:
        raise ValueError("Debe incluir al menos un tipo de carácter")
    
    # Generar contraseña asegurando que incluya al menos un carácter de cada tipo
    password = []
    
    # Añadir al menos un carácter de cada tipo requerido
    if include_lowercase:
        password.append(secrets.choice(string.ascii_lowercase))
    if include_uppercase:
        password.append(secrets.choice(string.ascii_uppercase))
    if include_numbers:
        password.append(secrets.choice(string.digits))
    if include_symbols:
        password.append(secrets.choice("!@#$%^&*"))
    
    # Completar con caracteres aleatorios
    for _ in range(length - len(password)):
        password.append(secrets.choice(chars))
    
    # Mezclar los caracteres
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

def generate_unique_id(prefix: str = "", 
                      suffix: str = "",
                      include_timestamp: bool = True,
                      include_random: bool = True) -> str:
    """
    Genera ID único.
    
    Args:
        prefix: Prefijo del ID
        suffix: Sufijo del ID
        include_timestamp: Si incluir timestamp
        include_random: Si incluir parte aleatoria
        
    Returns:
        ID único generado
        
    Examples:
        >>> generate_unique_id("emp", include_timestamp=True)
        'emp_20241213_143022_a8b9c'
    """
    parts = []
    
    if prefix:
        parts.append(prefix)
    
    if include_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts.append(timestamp)
    
    if include_random:
        random_part = generate_random_string(5)
        parts.append(random_part)
    
    if suffix:
        parts.append(suffix)
    
    return '_'.join(parts)

# ==============================================================================
# UTILIDADES ESPECÍFICAS PARA EMPRENDIMIENTO
# ==============================================================================

def normalize_business_name(name: str) -> str:
    """
    Normaliza nombre de empresa para búsquedas y comparaciones.
    
    Args:
        name: Nombre de la empresa
        
    Returns:
        Nombre normalizado
        
    Examples:
        >>> normalize_business_name("TECH SOLUTIONS S.A.S.")
        'tech solutions'
        >>> normalize_business_name("Café & Co. Ltda.")
        'cafe co'
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Limpiar y normalizar
    normalized = clean_string(name, remove_html=True)
    normalized = remove_accents(normalized)
    normalized = normalized.lower()
    
    # Remover sufijos empresariales comunes
    business_suffixes = [
        'sas', 's.a.s', 'sa', 's.a', 'ltda', 'limitada', 'ltda.', 
        'eirl', 'e.i.r.l', 'spa', 's.p.a', 'inc', 'llc', 'corp',
        'corporation', 'company', 'co', 'cia', 'cía'
    ]
    
    words = normalized.split()
    filtered_words = []
    
    for word in words:
        # Remover puntuación del final
        clean_word = word.rstrip('.,')
        if clean_word not in business_suffixes:
            filtered_words.append(clean_word)
    
    # Remover conectores comunes
    connectors = ['y', 'e', 'de', 'del', 'la', 'el', '&', 'and']
    final_words = [w for w in filtered_words if w not in connectors]
    
    return ' '.join(final_words)

def extract_business_sector(text: str) -> Optional[str]:
    """
    Extrae el sector empresarial de un texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Sector identificado o None
        
    Examples:
        >>> extract_business_sector("Desarrollo de software y aplicaciones")
        'tech'
        >>> extract_business_sector("Producción agrícola orgánica")
        'agricultura'
    """
    if not text or not isinstance(text, str):
        return None
    
    # Normalizar texto
    normalized = normalize_string(text, remove_accents=True)
    
    # Buscar en sectores empresariales
    for sector, keywords in BUSINESS_SECTORS.items():
        for keyword in keywords:
            if keyword in normalized:
                return sector
    
    return None

def format_business_description(description: str, 
                               max_length: int = 500,
                               capitalize_sentences: bool = True) -> str:
    """
    Formatea descripción empresarial.
    
    Args:
        description: Descripción original
        max_length: Longitud máxima
        capitalize_sentences: Si capitalizar inicio de oraciones
        
    Returns:
        Descripción formateada
    """
    if not description or not isinstance(description, str):
        return ""
    
    # Limpiar texto
    formatted = clean_string(description, 
                           remove_html=True,
                           remove_extra_spaces=True)
    
    if capitalize_sentences:
        # Capitalizar inicio de oraciones
        sentences = re.split(r'([.!?]+)', formatted)
        capitalized = []
        
        for i, part in enumerate(sentences):
            if i % 2 == 0:  # Texto (no puntuación)
                if part.strip():
                    part = part.strip()
                    if part:
                        part = part[0].upper() + part[1:]
                    capitalized.append(part)
            else:  # Puntuación
                capitalized.append(part)
        
        formatted = ''.join(capitalized)
    
    # Truncar si es necesario
    if len(formatted) > max_length:
        formatted = smart_truncate(formatted, max_length)
    
    return formatted.strip()

def generate_entrepreneur_username(name: str, 
                                  company: str = "",
                                  min_length: int = 3,
                                  max_length: int = 20) -> str:
    """
    Genera nombre de usuario para emprendedor.
    
    Args:
        name: Nombre del emprendedor
        company: Nombre de la empresa (opcional)
        min_length: Longitud mínima
        max_length: Longitud máxima
        
    Returns:
        Username generado
        
    Examples:
        >>> generate_entrepreneur_username("Juan Pérez", "TechStart")
        'juan_perez_techstart'
    """
    if not name:
        return generate_random_string(8)
    
    # Normalizar nombre
    normalized_name = normalize_string(name, remove_accents=True)
    username_parts = []
    
    # Añadir partes del nombre
    name_parts = normalized_name.split()
    for part in name_parts[:2]:  # Máximo 2 partes del nombre
        if part:
            username_parts.append(part)
    
    # Añadir empresa si se proporciona
    if company:
        normalized_company = normalize_business_name(company)
        company_parts = normalized_company.split()
        if company_parts:
            username_parts.append(company_parts[0])  # Primera palabra
    
    # Unir con guiones bajos
    username = '_'.join(username_parts)
    
    # Asegurar que esté en el rango de longitud
    if len(username) < min_length:
        username += '_' + generate_random_string(min_length - len(username) - 1)
    elif len(username) > max_length:
        username = username[:max_length]
    
    return username

# ==============================================================================
# UTILIDADES DE VALIDACIÓN Y ANÁLISIS
# ==============================================================================

def count_words(text: str, exclude_stop_words: bool = False) -> int:
    """
    Cuenta palabras en un texto.
    
    Args:
        text: Texto a analizar
        exclude_stop_words: Si excluir palabras de parada
        
    Returns:
        Número de palabras
    """
    if not text or not isinstance(text, str):
        return 0
    
    words = REGEX_PATTERNS['words'].findall(text.lower())
    
    if exclude_stop_words:
        words = [w for w in words if w not in SPANISH_STOP_WORDS]
    
    return len(words)

def count_sentences(text: str) -> int:
    """
    Cuenta oraciones en un texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Número de oraciones
    """
    if not text or not isinstance(text, str):
        return 0
    
    sentences = re.split(r'[.!?]+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return len(sentences)

def count_characters(text: str, include_spaces: bool = True) -> int:
    """
    Cuenta caracteres en un texto.
    
    Args:
        text: Texto a analizar
        include_spaces: Si incluir espacios
        
    Returns:
        Número de caracteres
    """
    if not text or not isinstance(text, str):
        return 0
    
    if include_spaces:
        return len(text)
    else:
        return len(text.replace(' ', ''))

def analyze_text(text: str) -> Dict[str, Any]:
    """
    Analiza texto y retorna estadísticas completas.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Diccionario con estadísticas
        
    Examples:
        >>> stats = analyze_text("Mi empresa de tecnología. Desarrollamos apps.")
        >>> stats['word_count']
        7
    """
    if not text or not isinstance(text, str):
        return {
            'character_count': 0,
            'character_count_no_spaces': 0,
            'word_count': 0,
            'sentence_count': 0,
            'paragraph_count': 0,
            'emails': [],
            'urls': [],
            'mentions': [],
            'hashtags': [],
            'phones': []
        }
    
    return {
        'character_count': count_characters(text, include_spaces=True),
        'character_count_no_spaces': count_characters(text, include_spaces=False),
        'word_count': count_words(text),
        'word_count_no_stop_words': count_words(text, exclude_stop_words=True),
        'sentence_count': count_sentences(text),
        'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
        'emails': extract_emails(text),
        'urls': extract_urls(text),
        'mentions': extract_mentions(text),
        'hashtags': extract_hashtags(text),
        'phones': extract_phones(text),
        'average_word_length': sum(len(word) for word in text.split()) / max(len(text.split()), 1),
        'reading_time_minutes': max(1, count_words(text) // 200)  # ~200 palabras por minuto
    }

def is_valid_slug(slug: str) -> bool:
    """
    Valida si un string es un slug válido.
    
    Args:
        slug: String a validar
        
    Returns:
        True si es slug válido
    """
    if not slug or not isinstance(slug, str):
        return False
    
    # Slug válido: solo letras, números y guiones, no empieza/termina con guión
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, slug))

def similarity_ratio(text1: str, text2: str) -> float:
    """
    Calcula ratio de similitud entre dos textos (Jaro-Winkler simplificado).
    
    Args:
        text1: Primer texto
        text2: Segundo texto
        
    Returns:
        Ratio de similitud (0.0 a 1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalizar textos
    norm1 = normalize_string(text1, remove_accents=True)
    norm2 = normalize_string(text2, remove_accents=True)
    
    if norm1 == norm2:
        return 1.0
    
    # Algoritmo simple de similitud basado en palabras comunes
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return 0.0
    
    common_words = words1.intersection(words2)
    total_words = words1.union(words2)
    
    return len(common_words) / len(total_words)

# ==============================================================================
# CLASE PRINCIPAL StringUtils
# ==============================================================================

class StringUtils:
    """Clase principal que encapsula todas las utilidades de string."""
    
    def __init__(self, default_encoding: str = 'utf-8'):
        self.default_encoding = default_encoding
        self.config = STRING_CONFIG.copy()
    
    def configure(self, **kwargs):
        """Configura parámetros por defecto."""
        self.config.update(kwargs)
    
    # Métodos de limpieza
    def clean(self, text: str, **kwargs) -> str:
        """Limpia string con configuración por defecto."""
        return clean_string(text, **kwargs)
    
    def normalize(self, text: str, **kwargs) -> str:
        """Normaliza string con configuración por defecto."""
        return normalize_string(text, **kwargs)
    
    def sanitize(self, text: str, **kwargs) -> str:
        """Sanitiza string con configuración por defecto."""
        return sanitize_text(text, **kwargs)
    
    # Métodos de conversión
    def to_slug(self, text: str, **kwargs) -> str:
        """Convierte a slug con configuración por defecto."""
        max_length = kwargs.get('max_length', self.config['max_slug_length'])
        return generate_slug(text, max_length=max_length, **kwargs)
    
    def to_snake_case(self, text: str) -> str:
        """Convierte a snake_case."""
        return to_snake_case(text)
    
    def to_camel_case(self, text: str, **kwargs) -> str:
        """Convierte a camelCase."""
        return to_camel_case(text, **kwargs)
    
    def to_pascal_case(self, text: str) -> str:
        """Convierte a PascalCase."""
        return to_pascal_case(text)
    
    def to_kebab_case(self, text: str) -> str:
        """Convierte a kebab-case."""
        return to_kebab_case(text)
    
    # Métodos de truncado
    def truncate(self, text: str, max_length: int, **kwargs) -> str:
        """Trunca texto con configuración por defecto."""
        suffix = kwargs.get('suffix', self.config['truncate_suffix'])
        return truncate(text, max_length, suffix=suffix, **kwargs)
    
    def smart_truncate(self, text: str, **kwargs) -> str:
        """Truncado inteligente."""
        return smart_truncate(text, **kwargs)
    
    # Métodos de generación
    def generate_random(self, length: int = 8, **kwargs) -> str:
        """Genera string aleatorio."""
        chars = kwargs.get('chars', self.config['random_string_chars'])
        return generate_random_string(length, chars=chars, **kwargs)
    
    def generate_password(self, **kwargs) -> str:
        """Genera contraseña segura."""
        return generate_password(**kwargs)
    
    def generate_unique_id(self, **kwargs) -> str:
        """Genera ID único."""
        return generate_unique_id(**kwargs)
    
    # Métodos de análisis
    def analyze(self, text: str) -> Dict[str, Any]:
        """Analiza texto."""
        return analyze_text(text)
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud entre textos."""
        return similarity_ratio(text1, text2)
    
    # Métodos específicos para emprendimiento
    def normalize_business_name(self, name: str) -> str:
        """Normaliza nombre empresarial."""
        return normalize_business_name(name)
    
    def format_business_description(self, description: str, **kwargs) -> str:
        """Formatea descripción empresarial."""
        return format_business_description(description, **kwargs)
    
    def generate_entrepreneur_username(self, name: str, **kwargs) -> str:
        """Genera username para emprendedor."""
        return generate_entrepreneur_username(name, **kwargs)

# ==============================================================================
# INSTANCIA GLOBAL Y FUNCIONES DE CONVENIENCIA
# ==============================================================================

# Instancia global de StringUtils
string_utils = StringUtils()

# Funciones de conveniencia que usan la instancia global
def get_string_config() -> Dict[str, Any]:
    """Obtiene configuración actual de strings."""
    return string_utils.config.copy()

def configure_strings(**kwargs):
    """Configura utilidades de string globalmente."""
    string_utils.configure(**kwargs)

# Missing functions - adding stubs
def generate_secure_token(length=32):
    """Generate a secure random token."""
    import secrets
    return secrets.token_urlsafe(length)

def get_client_ip():
    """Get the client IP address from Flask request."""
    from flask import request
    return request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

# Logging de inicialización
logger.info("Módulo de utilidades de string inicializado correctamente")