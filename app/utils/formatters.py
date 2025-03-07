# app/utils/formatters.py

import locale
from datetime import datetime
import pytz
from babel.numbers import format_currency as babel_format_currency
from flask import current_app, request

def format_currency(amount, currency='USD', locale_str='es_ES'):
    """
    Formatea un valor monetario según la moneda y localización especificada.
    
    Args:
        amount (float): El valor monetario a formatear
        currency (str): El código ISO de la moneda (por defecto 'USD')
        locale_str (str): El código de localización (por defecto 'es_ES')
        
    Returns:
        str: El valor formateado según la moneda y localización
        
    Example:
        >>> format_currency(1234.56, 'EUR')
        '1.234,56 €'
        >>> format_currency(1234.56, 'USD', 'en_US')
        '$1,234.56'
    """
    try:
        return babel_format_currency(amount, currency, locale=locale_str)
    except:
        # Fallback simple si babel falla
        locale.setlocale(locale.LC_ALL, '')
        symbol = {'USD': '$', 'EUR': '€', 'GBP': '£', 'CLP': '$', 'COP': '$', 'MXN': '$'}.get(currency, '')
        return f"{symbol}{locale.format_string('%0.2f', amount, grouping=True)}"

def format_date(date_obj=None, format_str='%d/%m/%Y', from_string=False, string_format='%Y-%m-%d'):
    """
    Formatea una fecha según el formato especificado.
    
    Args:
        date_obj (datetime/str): Objeto datetime o string a formatear
        format_str (str): Formato de salida
        from_string (bool): Indica si date_obj es un string
        string_format (str): Formato del string de entrada si from_string es True
        
    Returns:
        str: La fecha formateada
        
    Example:
        >>> from datetime import datetime
        >>> format_date(datetime(2023, 4, 15))
        '15/04/2023'
        >>> format_date('2023-04-15', from_string=True)
        '15/04/2023'
    """
    if date_obj is None:
        date_obj = datetime.now()
        
    if from_string and isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, string_format)
        
    return date_obj.strftime(format_str)

def format_time(time_obj=None, format_str='%H:%M', from_string=False, string_format='%H:%M:%S'):
    """
    Formatea una hora según el formato especificado.
    
    Args:
        time_obj (datetime/str): Objeto datetime o string a formatear
        format_str (str): Formato de salida
        from_string (bool): Indica si time_obj es un string
        string_format (str): Formato del string de entrada si from_string es True
        
    Returns:
        str: La hora formateada
    """
    if time_obj is None:
        time_obj = datetime.now()
        
    if from_string and isinstance(time_obj, str):
        time_obj = datetime.strptime(time_obj, string_format)
        
    return time_obj.strftime(format_str)

def format_datetime(dt_obj=None, format_str='%d/%m/%Y %H:%M', timezone=None):
    """
    Formatea una fecha y hora según el formato y zona horaria especificados.
    
    Args:
        dt_obj (datetime): Objeto datetime a formatear
        format_str (str): Formato de salida
        timezone (str): Zona horaria (ej. 'America/Santiago')
        
    Returns:
        str: La fecha y hora formateada
    """
    if dt_obj is None:
        dt_obj = datetime.now()
        
    if timezone:
        if dt_obj.tzinfo is None:
            dt_obj = pytz.UTC.localize(dt_obj)
        dt_obj = dt_obj.astimezone(pytz.timezone(timezone))
        
    return dt_obj.strftime(format_str)

def format_decimal(value, decimal_places=2, thousands_sep=True, locale_str='es_ES'):
    """
    Formatea un valor decimal con el número de decimales especificado.
    
    Args:
        value (float): El valor a formatear
        decimal_places (int): Número de decimales
        thousands_sep (bool): Indica si se debe usar separador de miles
        locale_str (str): El código de localización
        
    Returns:
        str: El valor formateado
    """
    try:
        locale.setlocale(locale.LC_ALL, locale_str)
    except:
        locale.setlocale(locale.LC_ALL, '')
        
    format_string = '%0.' + str(decimal_places) + 'f'
    return locale.format_string(format_string, value, grouping=thousands_sep)

def format_percentage(value, decimal_places=2):
    """
    Formatea un valor como porcentaje.
    
    Args:
        value (float): El valor a formatear (0.15 para 15%)
        decimal_places (int): Número de decimales
        
    Returns:
        str: El valor formateado como porcentaje
    """
    format_string = '%0.' + str(decimal_places) + 'f%%'
    return locale.format_string(format_string, value * 100, grouping=True)

def format_filesize(size_bytes):
    """
    Formatea un tamaño en bytes a una representación legible.
    
    Args:
        size_bytes (int): Tamaño en bytes
        
    Returns:
        str: Tamaño formateado (ej. '2.5 MB')
    """
    # Definir unidades
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    
    # Inicializar variables
    i = 0
    size = float(size_bytes)
    
    # Convertir a la unidad apropiada
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
        
    # Formatear resultado
    if i == 0:  # En bytes, sin decimales
        return f"{int(size)} {units[i]}"
    else:
        return f"{size:.2f} {units[i]}"

def format_phone(phone_number, country_code=None):
    """
    Formatea un número de teléfono según el país.
    
    Args:
        phone_number (str): Número de teléfono a formatear
        country_code (str): Código de país (ej. 'CL' para Chile)
        
    Returns:
        str: Número de teléfono formateado
    """
    # Limpiar el número
    clean_number = ''.join(filter(str.isdigit, phone_number))
    
    # Si no hay código de país especificado, usar el de la configuración
    if not country_code:
        country_code = current_app.config.get('DEFAULT_COUNTRY_CODE', 'CL')
    
    # Formateo según país
    if country_code == 'CL':  # Chile
        if len(clean_number) == 9:
            return f"+56 {clean_number[0]} {clean_number[1:5]} {clean_number[5:]}"
        elif len(clean_number) == 8:
            return f"+56 9 {clean_number[:4]} {clean_number[4:]}"
    elif country_code == 'CO':  # Colombia
        if len(clean_number) == 10:
            return f"+57 {clean_number[:3]} {clean_number[3:6]} {clean_number[6:]}"
    
    # Formato genérico si no hay un formato específico para el país
    if clean_number.startswith('00'):
        clean_number = '+' + clean_number[2:]
    elif not clean_number.startswith('+'):
        # Agregar código de país por defecto
        country_to_code = {'CL': '+56', 'CO': '+57', 'MX': '+52', 'ES': '+34'}
        clean_number = country_to_code.get(country_code, '+') + clean_number
    
    return clean_number

def format_rut_chile(rut):
    """
    Formatea un RUT chileno en el formato estándar.
    
    Args:
        rut (str): RUT a formatear (con o sin formato)
        
    Returns:
        str: RUT formateado (ej. '12.345.678-9')
    """
    # Eliminar formato actual
    rut = rut.replace(".", "").replace("-", "")
    
    # Separar cuerpo y dígito verificador
    if len(rut) > 1:
        cuerpo, dv = rut[:-1], rut[-1]
        
        # Formatear cuerpo con puntos
        reversed_cuerpo = cuerpo[::-1]
        formatted_cuerpo = ""
        for i, char in enumerate(reversed_cuerpo):
            if i > 0 and i % 3 == 0:
                formatted_cuerpo = "." + formatted_cuerpo
            formatted_cuerpo = char + formatted_cuerpo
            
        return f"{formatted_cuerpo}-{dv}"
    
    return rut

def format_list_to_string(items, separator=', ', last_separator=' y '):
    """
    Convierte una lista de elementos a un string con formato.
    
    Args:
        items (list): Lista de elementos
        separator (str): Separador para los elementos (excepto el último)
        last_separator (str): Separador para el último elemento
        
    Returns:
        str: String formateado
        
    Example:
        >>> format_list_to_string(['manzanas', 'peras', 'uvas'])
        'manzanas, peras y uvas'
    """
    if not items:
        return ""
    
    if len(items) == 1:
        return str(items[0])
    
    return separator.join(str(item) for item in items[:-1]) + last_separator + str(items[-1])

def format_address(street, number, city, state=None, country=None, postal_code=None):
    """
    Formatea una dirección postal.
    
    Args:
        street (str): Nombre de la calle
        number (str): Número
        city (str): Ciudad
        state (str): Estado/Provincia/Región
        country (str): País
        postal_code (str): Código postal
        
    Returns:
        str: Dirección formateada
    """
    address_parts = []
    
    # Calle y número
    if street and number:
        address_parts.append(f"{street} {number}")
    elif street:
        address_parts.append(street)
    
    # Ciudad y estado/provincia/región
    if city and state:
        address_parts.append(f"{city}, {state}")
    elif city:
        address_parts.append(city)
    elif state:
        address_parts.append(state)
    
    # Código postal
    if postal_code:
        address_parts.append(postal_code)
    
    # País
    if country:
        address_parts.append(country)
    
    return ", ".join(address_parts)