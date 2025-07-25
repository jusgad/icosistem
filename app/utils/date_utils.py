"""
Utilidades de Fecha y Hora para el Ecosistema de Emprendimiento

Este módulo proporciona funciones helper para manipular, formatear y calcular
fechas y horas, incluyendo manejo de zonas horarias, deltas y períodos.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import logging
from datetime import datetime, timedelta, date, time, timezone as dt_timezone
from typing import Optional, Tuple, Union, List
import pytz
from babel.dates import format_date as babel_format_date, \
                        format_datetime as babel_format_datetime, \
                        format_time as babel_format_time, \
                        format_timedelta as babel_format_timedelta
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
from flask import current_app

logger = logging.getLogger(__name__)

# Constantes de formato
ISO_DATE_FORMAT = "%Y-%m-%d"
ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ" # ISO 8601 con Z para UTC
READABLE_DATE_FORMAT = "%d de %B de %Y"
READABLE_DATETIME_FORMAT = "%d de %B de %Y, %H:%M"

DEFAULT_TIMEZONE = 'America/Bogota' # O la zona horaria por defecto de tu aplicación

def get_current_utc_time() -> datetime:
    """Retorna la fecha y hora actual en UTC."""
    return datetime.now(dt_timezone.utc)

def get_current_local_time(tz_name: Optional[str] = None) -> datetime:
    """
    Retorna la fecha y hora actual en la zona horaria especificada o la por defecto.
    """
    target_tz_name = tz_name or current_app.config.get('BABEL_DEFAULT_TIMEZONE', DEFAULT_TIMEZONE)
    target_tz = pytz.timezone(target_tz_name)
    return datetime.now(target_tz)

def parse_datetime(
    datetime_str: Optional[str],
    default_to_utc: bool = True,
    raise_error: bool = False
) -> Optional[datetime]:
    """
    Parsea una cadena de fecha y hora a un objeto datetime.
    Intenta manejar varios formatos comunes.

    Args:
        datetime_str: Cadena de fecha y hora.
        default_to_utc: Si la fecha no tiene timezone, asumirla como UTC.
        raise_error: Si lanzar un error en caso de fallo de parseo.

    Returns:
        Objeto datetime o None si falla el parseo y raise_error es False.
    """
    if not datetime_str:
        return None
    
    try:
        dt = dateutil_parser.parse(datetime_str)
        if dt.tzinfo is None and default_to_utc:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parseando datetime string '{datetime_str}': {e}")
        if raise_error:
            raise ValueError(f"Formato de fecha y hora inválido: {datetime_str}")
        return None

def parse_date(
    date_str: Optional[str],
    raise_error: bool = False
) -> Optional[date]:
    """
    Parsea una cadena de fecha a un objeto date.
    """
    if not date_str:
        return None
    
    try:
        dt = dateutil_parser.parse(date_str)
        return dt.date()
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parseando date string '{date_str}': {e}")
        if raise_error:
            raise ValueError(f"Formato de fecha inválido: {date_str}")
        return None

def format_datetime_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """Formatea un datetime a ISO 8601 en UTC (YYYY-MM-DDTHH:MM:SS.ffffffZ)."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc) # Asumir UTC si no tiene timezone
    else:
        dt = dt.astimezone(dt_timezone.utc)
    return dt.strftime(ISO_DATETIME_FORMAT)

def format_datetime_local(
    dt: Optional[datetime],
    format_str: str = READABLE_DATETIME_FORMAT,
    tz_name: Optional[str] = None,
    locale: Optional[str] = None
) -> str:
    """
    Formatea un datetime a una cadena legible en la zona horaria local.
    """
    if not dt:
        return ""
    
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    target_tz_name = tz_name or current_app.config.get('BABEL_DEFAULT_TIMEZONE', DEFAULT_TIMEZONE)
    
    try:
        target_tz = pytz.timezone(target_tz_name)
        
        if dt.tzinfo is None:
            # Asumir que es UTC si es naive
            dt_aware = pytz.utc.localize(dt)
        else:
            dt_aware = dt
            
        local_dt = dt_aware.astimezone(target_tz)
        
        # Usar Babel para formateo localizado si está disponible
        if 'babel' in current_app.extensions:
            return babel_format_datetime(local_dt, format=format_str, locale=locale_to_use)
        else:
            return local_dt.strftime(format_str)
            
    except Exception as e:
        logger.error(f"Error formateando datetime local: {e}")
        return dt.strftime(READABLE_DATETIME_FORMAT) # Fallback

def format_date_local(
    d: Optional[Union[date, datetime]],
    format_str: str = READABLE_DATE_FORMAT,
    locale: Optional[str] = None
) -> str:
    """
    Formatea un date o datetime (solo la parte de la fecha) a una cadena legible.
    """
    if not d:
        return ""
        
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    
    try:
        if 'babel' in current_app.extensions:
            return babel_format_date(d, format=format_str, locale=locale_to_use)
        else:
            return d.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formateando date local: {e}")
        return d.strftime(READABLE_DATE_FORMAT) # Fallback

def time_ago(
    dt: Optional[datetime],
    locale: Optional[str] = None,
    add_direction: bool = True,
    granularity: str = 'second'
) -> str:
    """
    Retorna una cadena representando el tiempo transcurrido (ej. "hace 5 minutos").
    """
    if not dt:
        return ""
        
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    now = get_current_utc_time()
    
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt) # Asumir UTC si es naive
    
    try:
        if 'babel' in current_app.extensions:
            return babel_format_timedelta(
                dt - now, 
                granularity=granularity, 
                add_direction=add_direction, 
                locale=locale_to_use
            )
        else:
            # Fallback simple si Babel no está disponible
            delta = now - dt
            if delta.days > 0:
                return f"hace {delta.days} día(s)"
            elif delta.seconds // 3600 > 0:
                return f"hace {delta.seconds // 3600} hora(s)"
            elif delta.seconds // 60 > 0:
                return f"hace {delta.seconds // 60} minuto(s)"
            else:
                return "justo ahora"
    except Exception as e:
        logger.error(f"Error en time_ago: {e}")
        return str(dt)

def convert_to_timezone(
    dt: datetime,
    target_tz_name: str,
    source_tz_name: Optional[str] = 'UTC'
) -> datetime:
    """
    Convierte un datetime de una zona horaria a otra.
    """
    if not dt:
        raise ValueError("Datetime no puede ser None para conversión de timezone")
        
    source_tz = pytz.timezone(source_tz_name)
    target_tz = pytz.timezone(target_tz_name)
    
    if dt.tzinfo is None:
        # Asumir que es la zona horaria fuente si es naive
        dt_aware = source_tz.localize(dt)
    else:
        dt_aware = dt
        
    return dt_aware.astimezone(target_tz)

def get_start_of_day(dt: Optional[Union[datetime, date]] = None) -> datetime:
    """Retorna el inicio del día (00:00:00) para una fecha/datetime dada."""
    if dt is None:
        dt = get_current_utc_time()
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, time.min)
    
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def get_end_of_day(dt: Optional[Union[datetime, date]] = None) -> datetime:
    """Retorna el fin del día (23:59:59.999999) para una fecha/datetime dada."""
    if dt is None:
        dt = get_current_utc_time()
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, time.min)
        
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)

def get_start_of_week(dt: Optional[Union[datetime, date]] = None, first_day_is_monday: bool = True) -> date:
    """Retorna el inicio de la semana (Lunes o Domingo)."""
    if dt is None:
        dt = get_current_utc_time().date()
    if isinstance(dt, datetime):
        dt = dt.date()
        
    weekday = dt.weekday() # Lunes es 0, Domingo es 6
    if first_day_is_monday:
        return dt - timedelta(days=weekday)
    else: # Domingo es el primer día
        return dt - timedelta(days=(weekday + 1) % 7)

def get_end_of_week(dt: Optional[Union[datetime, date]] = None, first_day_is_monday: bool = True) -> date:
    """Retorna el fin de la semana."""
    start_of_week = get_start_of_week(dt, first_day_is_monday)
    return start_of_week + timedelta(days=6)

def get_start_of_month(dt: Optional[Union[datetime, date]] = None) -> date:
    """Retorna el inicio del mes."""
    if dt is None:
        dt = get_current_utc_time().date()
    if isinstance(dt, datetime):
        dt = dt.date()
        
    return dt.replace(day=1)

def get_end_of_month(dt: Optional[Union[datetime, date]] = None) -> date:
    """Retorna el fin del mes."""
    start_of_next_month = (get_start_of_month(dt) + relativedelta(months=1))
    return start_of_next_month - timedelta(days=1)

def get_date_range(period_name: str, base_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Retorna un rango de fechas (inicio, fin) para un período común.
    
    Args:
        period_name: 'today', 'yesterday', 'this_week', 'last_week', 
                     'this_month', 'last_month', 'this_year', 'last_year'.
        base_date: Fecha base para calcular el período (default: hoy).
    """
    if base_date is None:
        base_date = date.today()

    if period_name == 'today':
        return base_date, base_date
    elif period_name == 'yesterday':
        yesterday = base_date - timedelta(days=1)
        return yesterday, yesterday
    elif period_name == 'this_week':
        start = get_start_of_week(base_date)
        end = get_end_of_week(base_date)
        return start, end
    elif period_name == 'last_week':
        start_last_week = get_start_of_week(base_date - timedelta(weeks=1))
        end_last_week = get_end_of_week(base_date - timedelta(weeks=1))
        return start_last_week, end_last_week
    elif period_name == 'this_month':
        return get_start_of_month(base_date), get_end_of_month(base_date)
    elif period_name == 'last_month':
        start_last_month = get_start_of_month(base_date - relativedelta(months=1))
        end_last_month = get_end_of_month(start_last_month)
        return start_last_month, end_last_month
    elif period_name == 'this_year':
        start_year = date(base_date.year, 1, 1)
        end_year = date(base_date.year, 12, 31)
        return start_year, end_year
    elif period_name == 'last_year':
        start_last_year = date(base_date.year - 1, 1, 1)
        end_last_year = date(base_date.year - 1, 12, 31)
        return start_last_year, end_last_year
    else:
        raise ValueError(f"Período no reconocido: {period_name}")

def is_business_day(d: Union[date, datetime], holidays: Optional[List[date]] = None) -> bool:
    """
    Verifica si una fecha es un día hábil (Lunes a Viernes, no feriado).
    """
    if isinstance(d, datetime):
        d = d.date()
        
    if d.weekday() >= 5: # Sábado o Domingo
        return False
    
    if holidays and d in holidays:
        return False
        
    return True

def add_business_days(start_date: date, num_days: int, holidays: Optional[List[date]] = None) -> date:
    """
    Añade un número de días hábiles a una fecha.
    """
    current_date = start_date
    days_added = 0
    
    while days_added < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date, holidays):
            days_added += 1
            
    return current_date

def get_user_timezone(user=None) -> str:
    """
    Obtiene la zona horaria del usuario o la por defecto.
    """
    from flask_login import current_user
    
    user_to_check = user or (current_user if current_user.is_authenticated else None)
    
    if user_to_check and hasattr(user_to_check, 'timezone') and user_to_check.timezone:
        return user_to_check.timezone
    
    return current_app.config.get('BABEL_DEFAULT_TIMEZONE', DEFAULT_TIMEZONE)

def get_month_name(month_number: int, locale: Optional[str] = None) -> str:
    """Retorna el nombre del mes para un número dado."""
    if not 1 <= month_number <= 12:
        raise ValueError("Número de mes inválido")
        
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    
    # Crear un objeto date para ese mes
    d = date(2000, month_number, 1) # Año y día son irrelevantes
    
    if 'babel' in current_app.extensions:
        return babel_format_date(d, format='MMMM', locale=locale_to_use)
    else:
        # Fallback si Babel no está
        month_names_es = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        month_names_en = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        if locale_to_use.startswith('es'):
            return month_names_es[month_number]
        else:
            return month_names_en[month_number]

def get_quarter_from_date(d: Union[date, datetime]) -> int:
    """Retorna el trimestre (1-4) para una fecha dada."""
    if isinstance(d, datetime):
        d = d.date()
    return (d.month - 1) // 3 + 1

def get_days_in_month(year: int, month: int) -> int:
    """Retorna el número de días en un mes y año específicos."""
    import calendar
    return calendar.monthrange(year, month)[1]

def is_leap_year(year: int) -> bool:
    """Verifica si un año es bisiesto."""
    import calendar
    return calendar.isleap(year)

def format_duration(
    seconds: Optional[Union[int, float, timedelta]], 
    locale: Optional[str] = None,
    granularity: str = 'second',
    format_type: str = 'long' # 'long', 'short', 'narrow'
) -> str:
    """
    Formatea una duración en segundos a una cadena legible (ej. "2 horas, 15 minutos").
    """
    if seconds is None:
        return ""
    
    if isinstance(seconds, timedelta):
        delta = seconds
    else:
        delta = timedelta(seconds=float(seconds))
        
    locale_to_use = locale or current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')
    
    try:
        if 'babel' in current_app.extensions:
            return babel_format_timedelta(
                delta, 
                granularity=granularity, 
                locale=locale_to_use,
                format=format_type,
                threshold=0.85 # Para redondear mejor
            )
        else:
            # Fallback simple
            total_seconds = int(delta.total_seconds())
            days, remainder = divmod(total_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, secs = divmod(remainder, 60)
            
            parts = []
            if days > 0: parts.append(f"{days}d")
            if hours > 0: parts.append(f"{hours}h")
            if minutes > 0: parts.append(f"{minutes}m")
            if secs > 0 or not parts: parts.append(f"{secs}s")
            
            return " ".join(parts)
            
    except Exception as e:
        logger.error(f"Error formateando duración: {e}")
        return f"{int(delta.total_seconds())} segundos"


# Exportaciones principales
__all__ = [
    'get_current_utc_time', 'get_current_local_time',
    'parse_datetime', 'parse_date',
    'format_datetime_utc_iso', 'format_datetime_local', 'format_date_local',
    'time_ago', 'convert_to_timezone',
    'get_start_of_day', 'get_end_of_day',
    'get_start_of_week', 'get_end_of_week',
    'get_start_of_month', 'get_end_of_month',
    'get_date_range', 'is_business_day', 'add_business_days',
    'get_user_timezone', 'get_month_name', 'get_quarter_from_date',
    'get_days_in_month', 'is_leap_year', 'format_duration',
    'ISO_DATE_FORMAT', 'ISO_DATETIME_FORMAT',
    'READABLE_DATE_FORMAT', 'READABLE_DATETIME_FORMAT'
]
