# app/services/__init__.py

# Importar los servicios individuales
from .oauth import OAuth
from .google_calendar import GoogleCalendarService
from .google_meet import GoogleMeetService
from .email import EmailService
from .currency import CurrencyService
from .storage import StorageService

# Opcionalmente, exportar los servicios para facilitar la importación
__all__ = [
    'OAuth',
    'GoogleCalendarService',
    'GoogleMeetService',
    'EmailService',
    'CurrencyService',
    'StorageService'
]