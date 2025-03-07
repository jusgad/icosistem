# app/utils/validators.py

import re
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename

def validate_email(email):
    """
    Valida que una dirección de correo electrónico tenga un formato adecuado.
    
    Args:
        email (str): La dirección de correo electrónico a validar
        
    Returns:
        bool: True si el formato es válido, False en caso contrario
        
    Example:
        >>> validate_email("usuario@ejemplo.com")
        True
        >>> validate_email("usuario.invalido")
        False
    """
    # Patrón básico de validación de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone_number):
    """
    Valida que un número de teléfono tenga un formato adecuado.
    Acepta formatos internacionales y nacionales con o sin espacios/guiones.
    
    Args:
        phone_number (str): El número de teléfono a validar
        
    Returns:
        bool: True si el formato es válido, False en caso contrario
        
    Example:
        >>> validate_phone("+34 612 345 678")
        True
        >>> validate_phone("612-345-678")
        True
    """
    # Eliminar espacios, guiones y paréntesis para facilitar la validación
    clean_number = re.sub(r'[\s\-\(\)]', '', phone_number)
    
    # Patrón para números nacionales e internacionales
    pattern = r'^(\+\d{1,3})?(\d{9,15})$'
    return bool(re.match(pattern, clean_number))

def validate_date_format(date_str, format='%Y-%m-%d'):
    """
    Valida que una cadena tenga un formato de fecha válido.
    
    Args:
        date_str (str): La fecha en formato string
        format (str): El formato esperado (por defecto YYYY-MM-DD)
        
    Returns:
        bool: True si el formato es válido, False en caso contrario
    """
    try:
        datetime.strptime(date_str, format)
        return True
    except ValueError:
        return False

def validate_rut_chile(rut):
    """
    Valida un RUT chileno.
    
    Args:
        rut (str): El RUT a validar (con o sin puntos y con guión antes del dígito verificador)
        
    Returns:
        bool: True si el RUT es válido, False en caso contrario
    """
    # Eliminar puntos y guión
    rut = rut.replace(".", "").replace("-", "")
    
    # Verificar longitud
    if len(rut) < 2:
        return False
    
    # Separar cuerpo y dígito verificador
    cuerpo = rut[:-1]
    dv = rut[-1].upper()
    
    # Verificar que el cuerpo sea numérico
    if not cuerpo.isdigit():
        return False
    
    # Calcular dígito verificador
    suma = 0
    multiplo = 2
    
    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo += 1
        if multiplo > 7:
            multiplo = 2
    
    resto = suma % 11
    dv_calculado = 11 - resto
    
    if dv_calculado == 11:
        dv_calculado = '0'
    elif dv_calculado == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(dv_calculado)
    
    return dv == dv_calculado

def validate_strong_password(password):
    """
    Valida que una contraseña sea lo suficientemente fuerte.
    Debe tener al menos 8 caracteres, una letra mayúscula, una minúscula,
    un número y un carácter especial.
    
    Args:
        password (str): La contraseña a validar
        
    Returns:
        bool: True si la contraseña es fuerte, False en caso contrario
    """
    # Verificar longitud mínima
    if len(password) < 8:
        return False
    
    # Verificar presencia de al menos una letra mayúscula
    if not re.search(r'[A-Z]', password):
        return False
    
    # Verificar presencia de al menos una letra minúscula
    if not re.search(r'[a-z]', password):
        return False
    
    # Verificar presencia de al menos un número
    if not re.search(r'[0-9]', password):
        return False
    
    # Verificar presencia de al menos un carácter especial
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    
    return True

def validate_file_extension(filename, allowed_extensions=None):
    """
    Valida que la extensión de un archivo sea permitida.
    
    Args:
        filename (str): El nombre del archivo
        allowed_extensions (list): Lista de extensiones permitidas. Si es None,
                                  usa las configuradas en la aplicación.
                                  
    Returns:
        bool: True si la extensión es permitida, False en caso contrario
    """
    if allowed_extensions is None:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', 
                                                   ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])
    
    # Asegurar el nombre del archivo y obtener la extensión
    filename = secure_filename(filename)
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def validate_url(url):
    """
    Valida que una URL tenga un formato adecuado.
    
    Args:
        url (str): La URL a validar
        
    Returns:
        bool: True si el formato es válido, False en caso contrario
    """
    pattern = r'^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    return bool(re.match(pattern, url))

def validate_document_type(doc_type, allowed_types=None):
    """
    Valida que un tipo de documento esté en la lista de tipos permitidos.
    
    Args:
        doc_type (str): El tipo de documento a validar
        allowed_types (list): Lista de tipos permitidos. Si es None,
                             usa los configurados en la aplicación.
                             
    Returns:
        bool: True si el tipo es permitido, False en caso contrario
    """
    if allowed_types is None:
        allowed_types = current_app.config.get('ALLOWED_DOCUMENT_TYPES', 
                                              ['dni', 'pasaporte', 'licencia', 'otro'])
    
    return doc_type in allowed_types

def validate_input_length(text, min_length=0, max_length=None):
    """
    Valida que un texto tenga una longitud dentro de los límites especificados.
    
    Args:
        text (str): El texto a validar
        min_length (int): Longitud mínima permitida
        max_length (int): Longitud máxima permitida. Si es None, no hay límite.
        
    Returns:
        bool: True si la longitud es válida, False en caso contrario
    """
    if len(text) < min_length:
        return False
    
    if max_length is not None and len(text) > max_length:
        return False
    
    return True