"""
Formateadores Utilitarios para el Ecosistema de Emprendimiento

Este módulo proporciona funciones para formatear datos comunes como fechas,
monedas, números, texto y más, para ser utilizados en plantillas Jinja2
y otras partes de la aplicación.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import re
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Union
from flask import current_app, Markup
try:
    import bleach
except ImportError:
    bleach = None
try:
    import phonenumbers
except ImportError:
    phonenumbers = None
from babel.dates import format_datetime as babel_format_datetime, \
                        format_date as babel_format_date, \
                        format_time as babel_format_time, \
                        format_timedelta
from babel.numbers import format_currency as babel_format_currency, \
                          format_decimal, format_percent

# Configuración de Bleach para sanitizar HTML
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i',
    'li', 'ol', 'strong', 'ul', 'p', 'br', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'img'
]
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style', 'id', 'title'],
    'a': ['href', 'rel', 'target'],
    'img': ['src', 'alt', 'width', 'height']
}
ALLOWED_STYLES = [
    'color', 'background-color', 'font-weight', 'font-style',
    'text-decoration', 'text-align', 'margin', 'padding',
    'border', 'border-radius', 'width', 'height', 'max-width', 'max-height'
]

def format_datetime(value: Optional[datetime], 
                    format_type: str = 'medium', 
                    locale: Optional[str] = None) -> str:
    """
    Formatea un objeto datetime a una cadena legible.

    Args:
        value: Objeto datetime a formatear.
        format_type: 'short', 'medium', 'long', 'full', o un patrón personalizado.
        locale: Locale a usar (ej. 'es_CO'). Usa el de la app por defecto.

    Returns:
        Cadena de fecha y hora formateada.
    """
    if not isinstance(value, datetime):
        return str(value) if value is not None else ''
    
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    try:
        return babel_format_datetime(value, format_type, locale=locale_to_use)
    except Exception:
        return value.strftime('%Y-%m-%d %H:%M:%S') # Fallback

def format_date(value: Optional[Union[datetime, date]], 
                format_type: str = 'medium', 
                locale: Optional[str] = None) -> str:
    """
    Formatea un objeto date o datetime (solo la parte de la fecha) a una cadena legible.

    Args:
        value: Objeto date o datetime a formatear.
        format_type: 'short', 'medium', 'long', 'full', o un patrón personalizado.
        locale: Locale a usar.

    Returns:
        Cadena de fecha formateada.
    """
    if not isinstance(value, (datetime, date)):
        return str(value) if value is not None else ''
    
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    try:
        return babel_format_date(value, format_type, locale=locale_to_use)
    except Exception:
        return value.strftime('%Y-%m-%d') # Fallback

def format_time(value: Optional[Union[datetime, time]], 
                format_type: str = 'short', 
                locale: Optional[str] = None) -> str:
    """
    Formatea un objeto time o datetime (solo la parte de la hora) a una cadena legible.

    Args:
        value: Objeto time o datetime a formatear.
        format_type: 'short', 'medium', 'long', 'full', o un patrón personalizado.
        locale: Locale a usar.

    Returns:
        Cadena de hora formateada.
    """
    if not isinstance(value, (datetime, time)):
        return str(value) if value is not None else ''
    
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    try:
        return babel_format_time(value, format_type, locale=locale_to_use)
    except Exception:
        return value.strftime('%H:%M:%S') # Fallback

def format_currency(value: Optional[Union[Decimal, float, int]], 
                    currency: str = 'COP', 
                    locale: Optional[str] = None) -> str:
    """
    Formatea un número como moneda.

    Args:
        value: Valor numérico.
        currency: Código de moneda (ej. 'COP', 'USD').
        locale: Locale a usar.

    Returns:
        Cadena de moneda formateada.
    """
    if value is None:
        return ''
    if not isinstance(value, (Decimal, float, int)):
        try:
            value = Decimal(str(value))
        except:
            return str(value) # Fallback

    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    try:
        return babel_format_currency(value, currency, locale=locale_to_use)
    except Exception:
        return f"{currency} {value:,.2f}" # Fallback

def format_decimal_number(value: Optional[Union[Decimal, float, int]], 
                          num_decimals: int = 2, 
                          locale: Optional[str] = None) -> str:
    """
    Formatea un número decimal.

    Args:
        value: Valor numérico.
        num_decimals: Número de decimales a mostrar.
        locale: Locale a usar.

    Returns:
        Cadena de número decimal formateado.
    """
    if value is None:
        return ''
    if not isinstance(value, (Decimal, float, int)):
        try:
            value = Decimal(str(value))
        except:
            return str(value)

    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    format_string = f"#,##0.{'0' * num_decimals}"
    try:
        return format_decimal(value, format=format_string, locale=locale_to_use)
    except Exception:
        return f"{value:,.{num_decimals}f}" # Fallback

def format_percentage(value: Optional[Union[float, int]], 
                      num_decimals: int = 1, 
                      locale: Optional[str] = None) -> str:
    """
    Formatea un número como porcentaje.
    Asume que el valor es una fracción (ej. 0.75 para 75%).

    Args:
        value: Valor numérico (0 a 1).
        num_decimals: Número de decimales.
        locale: Locale a usar.

    Returns:
        Cadena de porcentaje formateado.
    """
    if value is None:
        return ''
    if not isinstance(value, (float, int)):
        try:
            value = float(value)
        except:
            return str(value)

    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    format_string = f"#,##0.{'0' * num_decimals}%"
    try:
        return format_percent(value, format=format_string, locale=locale_to_use)
    except Exception:
        return f"{value * 100:.{num_decimals}f}%" # Fallback

def format_file_size(size_bytes: Optional[int]) -> str:
    """
    Formatea el tamaño de un archivo en una unidad legible.

    Args:
        size_bytes: Tamaño en bytes.

    Returns:
        Cadena de tamaño formateado (ej. "1.5 MB").
    """
    if size_bytes is None or size_bytes < 0:
        return "0 B"
    if size_bytes == 0:
        return "0 B"
    
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    size_bytes_float = float(size_bytes)
    while size_bytes_float >= 1024 and i < len(size_name) - 1:
        size_bytes_float /= 1024.0
        i += 1
    
    # Usar format_decimal_number para consistencia de locale
    return f"{format_decimal_number(size_bytes_float, 1 if i > 0 else 0)} {size_name[i]}"

def truncate_text(text: Optional[str], length: int = 100, suffix: str = '...') -> str:
    """
    Trunca un texto a una longitud máxima, añadiendo un sufijo.

    Args:
        text: Texto a truncar.
        length: Longitud máxima.
        suffix: Sufijo a añadir si se trunca.

    Returns:
        Texto truncado.
    """
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length - len(suffix)].rstrip() + suffix

def nl2br(value: Optional[str]) -> Markup:
    """
    Reemplaza saltos de línea con <br>.
    Usa Markup para que Jinja2 no escape el HTML.
    """
    if not value:
        return Markup('')
    
    # Escapar HTML primero para seguridad, luego reemplazar saltos de línea
    if bleach:
        escaped_value = bleach.clean(value, tags=[], strip=True)
    else:
        # Fallback si bleach no está disponible
        escaped_value = value.replace('<', '&lt;').replace('>', '&gt;')
    return Markup(escaped_value.replace('\n', '<br>\n'))

def markdown_to_html(text: Optional[str]) -> Markup:
    """
    Convierte texto Markdown a HTML de forma segura.
    """
    if not text:
        return Markup('')
    
    try:
        import markdown2
        # Configurar markdown2 para seguridad y extensiones útiles
        html = markdown2.markdown(text, extras=[
            "fenced-code-blocks", 
            "tables", 
            "nofollow", 
            "target-blank-links",
            "code-friendly"
        ])
        # Sanitizar el HTML resultante
        safe_html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, styles=ALLOWED_STYLES)
        return Markup(safe_html)
    except ImportError:
        current_app.logger.warning("Markdown2 no está instalado. El formateo Markdown no funcionará.")
        return nl2br(text) # Fallback a nl2br si markdown2 no está
    except Exception as e:
        current_app.logger.error(f"Error convirtiendo Markdown: {e}")
        return nl2br(text)

def format_phone_number(phone_number_str: Optional[str], 
                        region: str = 'CO', 
                        format_type: phonenumbers.PhoneNumberFormat = phonenumbers.PhoneNumberFormat.INTERNATIONAL) -> str:
    """
    Formatea un número de teléfono usando la librería phonenumbers.

    Args:
        phone_number_str: Número de teléfono como cadena.
        region: Código de región (ej. 'CO' para Colombia).
        format_type: Formato deseado (E164, INTERNATIONAL, NATIONAL, RFC3966).

    Returns:
        Número de teléfono formateado o la cadena original si no es válido.
    """
    if not phone_number_str:
        return ''
    try:
        parsed_number = phonenumbers.parse(phone_number_str, region)
        if phonenumbers.is_valid_number(parsed_number):
            return phonenumbers.format_number(parsed_number, format_type)
        return phone_number_str # Devolver original si no es válido
    except phonenumbers.NumberParseException:
        return phone_number_str # Devolver original si hay error de parseo
    except Exception as e:
        current_app.logger.error(f"Error formateando número de teléfono: {e}")
        return phone_number_str

def time_ago(timestamp: Optional[datetime], 
             locale: Optional[str] = None,
             add_direction: bool = True) -> str:
    """
    Muestra el tiempo transcurrido desde un timestamp (ej. "hace 5 minutos").

    Args:
        timestamp: Objeto datetime.
        locale: Locale a usar.
        add_direction: Si añadir "hace" o "en".

    Returns:
        Cadena de tiempo relativo.
    """
    if not isinstance(timestamp, datetime):
        return str(timestamp) if timestamp is not None else ''

    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    now = datetime.utcnow() # Asumir que el timestamp es UTC
    
    # Si el timestamp tiene timezone, convertir now a ese timezone
    if timestamp.tzinfo:
        now = now.replace(tzinfo=timezone.utc).astimezone(timestamp.tzinfo)
    else: # Si el timestamp es naive, asumir que es UTC
        timestamp = timestamp.replace(tzinfo=timezone.utc)
        now = now.replace(tzinfo=timezone.utc)

    try:
        return format_timedelta(timestamp - now, 
                                granularity='second', 
                                add_direction=add_direction, 
                                locale=locale_to_use)
    except Exception:
        # Fallback si format_timedelta falla (ej. para deltas muy grandes)
        delta = now - timestamp
        if delta.days > 0:
            return f"hace {delta.days} día(s)"
        elif delta.seconds // 3600 > 0:
            return f"hace {delta.seconds // 3600} hora(s)"
        elif delta.seconds // 60 > 0:
            return f"hace {delta.seconds // 60} minuto(s)"
        else:
            return "justo ahora"

def sanitize_html(html_string: Optional[str]) -> str:
    """
    Sanitiza una cadena HTML para prevenir XSS.
    """
    if not html_string:
        return ''
    
    return bleach.clean(html_string, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, styles=ALLOWED_STYLES, strip=True)

def get_gravatar_url(email: str, size: int = 80, default: str = 'identicon') -> str:
    """
    Genera la URL de Gravatar para un email.
    """
    import hashlib
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d={default}"

def format_list_as_string(items: Optional[List[str]], limit: int = 3, separator: str = ', ') -> str:
    """
    Formatea una lista de strings en una cadena, limitando el número de ítems mostrados.
    Ej: ["A", "B", "C", "D"] con limit=2 -> "A, B y 2 más"
    """
    if not items:
        return ""
    
    count = len(items)
    if count == 0:
        return ""
    if count == 1:
        return items[0]
    
    if count <= limit:
        if count == 2:
            return f"{items[0]} y {items[1]}"
        else:
            return separator.join(items[:-1]) + f" y {items[-1]}"
    else:
        displayed_items = separator.join(items[:limit])
        remaining_count = count - limit
        return f"{displayed_items} y {remaining_count} más"

def register_template_filters(app):
    """
    Registra los formateadores como filtros de Jinja2.
    Esta función se llama desde app/__init__.py
    """
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.filters['date'] = format_date
    app.jinja_env.filters['time'] = format_time
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['decimal'] = format_decimal_number
    app.jinja_env.filters['percentage'] = format_percentage
    app.jinja_env.filters['filesize'] = format_file_size
    app.jinja_env.filters['truncate'] = truncate_text
    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['markdown'] = markdown_to_html
    app.jinja_env.filters['phone'] = format_phone_number
    app.jinja_env.filters['timeago'] = time_ago
    app.jinja_env.filters['sanitize_html'] = sanitize_html
    app.jinja_env.filters['gravatar'] = get_gravatar_url
    app.jinja_env.filters['list_to_string'] = format_list_as_string
    
    current_app.logger.info("Template filters registered.")

# Para uso directo si es necesario
__all__ = [
    'format_datetime', 'format_date', 'format_time', 'format_currency',
    'format_decimal_number', 'format_percentage', 'format_file_size',
    'truncate_text', 'nl2br', 'markdown_to_html', 'format_phone_number',
    'time_ago', 'sanitize_html', 'get_gravatar_url', 'format_list_as_string',
    'register_template_filters'
]
