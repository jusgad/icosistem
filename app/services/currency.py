"""
Currency Service

Servicio para manejo de conversión de monedas, tasas de cambio y formateo.
Incluye cache, múltiples proveedores de APIs y manejo robusto de errores.

Author: jusga
Date: 2025
"""

import json
import logging
import requests
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from functools import wraps
from flask import current_app
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from app.core.exceptions import CurrencyServiceError, ExternalAPIError
from app.utils.cache_utils import CacheManager
from app.utils.decorators import retry_on_failure


logger = logging.getLogger(__name__)


class CurrencyProvider:
    """Clase base para proveedores de tasas de cambio"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Crea una sesión HTTP con reintentos automáticos"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def get_rates(self, base_currency: str = 'USD') -> Dict[str, float]:
        """Método base para obtener tasas de cambio"""
        raise NotImplementedError
    
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtiene tasa específica entre dos monedas"""
        raise NotImplementedError


class ExchangeRatesAPIProvider(CurrencyProvider):
    """Proveedor usando ExchangeRates API"""
    
    BASE_URL = "https://api.exchangeratesapi.io/v1"
    
    def get_rates(self, base_currency: str = 'EUR') -> Dict[str, float]:
        """Obtiene todas las tasas desde EUR (base de la API gratuita)"""
        try:
            url = f"{self.BASE_URL}/latest"
            params = {
                'access_key': self.api_key,
                'base': base_currency,
                'format': 1
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', False):
                raise ExternalAPIError(f"API Error: {data.get('error', {}).get('info', 'Unknown error')}")
            
            return data.get('rates', {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching rates from ExchangeRates API: {e}")
            raise ExternalAPIError(f"Failed to fetch exchange rates: {str(e)}")
    
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtiene tasa específica usando conversión"""
        if from_currency == to_currency:
            return 1.0
            
        try:
            # Para la API gratuita, necesitamos convertir a través de EUR
            if from_currency != 'EUR':
                # Obtener tasa EUR -> from_currency
                eur_rates = self.get_rates('EUR')
                eur_to_from = eur_rates.get(from_currency)
                if not eur_to_from:
                    raise CurrencyServiceError(f"Currency {from_currency} not supported")
                from_to_eur = 1 / eur_to_from
            else:
                from_to_eur = 1.0
            
            if to_currency != 'EUR':
                # Obtener tasa EUR -> to_currency
                eur_rates = self.get_rates('EUR')
                eur_to_to = eur_rates.get(to_currency)
                if not eur_to_to:
                    raise CurrencyServiceError(f"Currency {to_currency} not supported")
            else:
                eur_to_to = 1.0
            
            # Calcular tasa final: from -> EUR -> to
            final_rate = from_to_eur * eur_to_to
            return final_rate
            
        except Exception as e:
            logger.error(f"Error getting rate {from_currency} to {to_currency}: {e}")
            raise


class CurrencyLayerProvider(CurrencyProvider):
    """Proveedor usando CurrencyLayer API"""
    
    BASE_URL = "https://api.currencylayer.com"
    
    def get_rates(self, base_currency: str = 'USD') -> Dict[str, float]:
        """Obtiene tasas desde USD (base de CurrencyLayer)"""
        try:
            url = f"{self.BASE_URL}/live"
            params = {
                'access_key': self.api_key,
                'source': base_currency,
                'format': 1
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', False):
                raise ExternalAPIError(f"API Error: {data.get('error', {}).get('info', 'Unknown error')}")
            
            # CurrencyLayer devuelve quotes como USDEUR, USDGBP, etc.
            quotes = data.get('quotes', {})
            rates = {}
            source_len = len(base_currency)
            
            for quote_key, rate in quotes.items():
                currency = quote_key[source_len:]  # Remover prefijo USD
                rates[currency] = rate
            
            return rates
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching rates from CurrencyLayer: {e}")
            raise ExternalAPIError(f"Failed to fetch exchange rates: {str(e)}")
    
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtiene tasa específica"""
        if from_currency == to_currency:
            return 1.0
            
        try:
            url = f"{self.BASE_URL}/live"
            params = {
                'access_key': self.api_key,
                'currencies': f"{from_currency},{to_currency}",
                'source': 'USD',
                'format': 1
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', False):
                raise ExternalAPIError(f"API Error: {data.get('error', {}).get('info', 'Unknown error')}")
            
            quotes = data.get('quotes', {})
            usd_to_from = quotes.get(f"USD{from_currency}")
            usd_to_to = quotes.get(f"USD{to_currency}")
            
            if not usd_to_from or not usd_to_to:
                raise CurrencyServiceError(f"Rate not available for {from_currency} to {to_currency}")
            
            # Convertir: from -> USD -> to
            rate = usd_to_to / usd_to_from
            return rate
            
        except Exception as e:
            logger.error(f"Error getting rate {from_currency} to {to_currency}: {e}")
            raise


class FreeCurrencyAPIProvider(CurrencyProvider):
    """Proveedor gratuito como fallback"""
    
    BASE_URL = "https://api.freecurrencyapi.com/v1"
    
    def get_rates(self, base_currency: str = 'USD') -> Dict[str, float]:
        """Obtiene tasas de la API gratuita"""
        try:
            url = f"{self.BASE_URL}/latest"
            params = {
                'apikey': self.api_key,
                'base_currency': base_currency
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching rates from FreeCurrencyAPI: {e}")
            raise ExternalAPIError(f"Failed to fetch exchange rates: {str(e)}")
    
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Obtiene tasa específica"""
        if from_currency == to_currency:
            return 1.0
            
        rates = self.get_rates(from_currency)
        rate = rates.get(to_currency)
        
        if rate is None:
            raise CurrencyServiceError(f"Rate not available for {from_currency} to {to_currency}")
        
        return rate


class CurrencyService:
    """
    Servicio principal para manejo de monedas y conversiones.
    Implementa múltiples proveedores con fallback automático.
    """
    
    # Monedas soportadas con sus símbolos y nombres
    SUPPORTED_CURRENCIES = {
        'USD': {'symbol': '$', 'name': 'US Dollar', 'decimal_places': 2},
        'EUR': {'symbol': '€', 'name': 'Euro', 'decimal_places': 2},
        'GBP': {'symbol': '£', 'name': 'British Pound', 'decimal_places': 2},
        'JPY': {'symbol': '¥', 'name': 'Japanese Yen', 'decimal_places': 0},
        'CAD': {'symbol': 'C$', 'name': 'Canadian Dollar', 'decimal_places': 2},
        'AUD': {'symbol': 'A$', 'name': 'Australian Dollar', 'decimal_places': 2},
        'CHF': {'symbol': 'CHF', 'name': 'Swiss Franc', 'decimal_places': 2},
        'CNY': {'symbol': '¥', 'name': 'Chinese Yuan', 'decimal_places': 2},
        'COP': {'symbol': '$', 'name': 'Colombian Peso', 'decimal_places': 0},
        'MXN': {'symbol': '$', 'name': 'Mexican Peso', 'decimal_places': 2},
        'BRL': {'symbol': 'R$', 'name': 'Brazilian Real', 'decimal_places': 2},
        'ARS': {'symbol': '$', 'name': 'Argentine Peso', 'decimal_places': 2},
        'CLP': {'symbol': '$', 'name': 'Chilean Peso', 'decimal_places': 0},
        'PEN': {'symbol': 'S/', 'name': 'Peruvian Sol', 'decimal_places': 2},
    }
    
    def __init__(self):
        self.cache = CacheManager()
        self.providers = self._initialize_providers()
        self.default_currency = current_app.config.get('DEFAULT_CURRENCY', 'USD')
        self.cache_duration = current_app.config.get('CURRENCY_CACHE_DURATION', 3600)  # 1 hora
    
    def _initialize_providers(self) -> List[CurrencyProvider]:
        """Inicializa los proveedores de tasas de cambio"""
        providers = []
        
        # Provider principal (CurrencyLayer)
        currencylayer_key = current_app.config.get('CURRENCYLAYER_API_KEY')
        if currencylayer_key:
            providers.append(CurrencyLayerProvider(currencylayer_key))
        
        # Provider secundario (ExchangeRates API)
        exchangerates_key = current_app.config.get('EXCHANGERATES_API_KEY')
        if exchangerates_key:
            providers.append(ExchangeRatesAPIProvider(exchangerates_key))
        
        # Provider gratuito como fallback
        freecurrency_key = current_app.config.get('FREECURRENCY_API_KEY')
        if freecurrency_key:
            providers.append(FreeCurrencyAPIProvider(freecurrency_key))
        
        if not providers:
            logger.warning("No currency providers configured, using fallback rates")
            
        return providers
    
    def _get_cache_key(self, key_type: str, **kwargs) -> str:
        """Genera clave de cache"""
        if key_type == 'rate':
            return f"currency_rate_{kwargs['from_currency']}_{kwargs['to_currency']}"
        elif key_type == 'rates':
            return f"currency_rates_{kwargs['base_currency']}"
        return f"currency_{key_type}"
    
    @retry_on_failure(max_retries=2, delay=1)
    def get_exchange_rate(self, from_currency: str, to_currency: str, 
                         force_refresh: bool = False) -> float:
        """
        Obtiene tasa de cambio entre dos monedas.
        
        Args:
            from_currency: Moneda origen (ej: 'USD')
            to_currency: Moneda destino (ej: 'EUR')
            force_refresh: Forzar actualización del cache
            
        Returns:
            float: Tasa de cambio
            
        Raises:
            CurrencyServiceError: Si no se puede obtener la tasa
        """
        # Validar monedas
        self._validate_currency(from_currency)
        self._validate_currency(to_currency)
        
        if from_currency == to_currency:
            return 1.0
        
        # Verificar cache
        cache_key = self._get_cache_key('rate', 
                                       from_currency=from_currency, 
                                       to_currency=to_currency)
        
        if not force_refresh:
            cached_rate = self.cache.get(cache_key)
            if cached_rate is not None:
                logger.debug(f"Using cached rate for {from_currency} to {to_currency}: {cached_rate}")
                return float(cached_rate)
        
        # Intentar obtener tasa de los proveedores
        last_error = None
        for provider in self.providers:
            try:
                rate = provider.get_rate(from_currency, to_currency)
                if rate and rate > 0:
                    # Guardar en cache
                    self.cache.set(cache_key, rate, timeout=self.cache_duration)
                    logger.info(f"Obtained rate {from_currency} to {to_currency}: {rate} from {provider.__class__.__name__}")
                    return float(rate)
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                continue
        
        # Si todos los proveedores fallan, usar tasas de fallback
        fallback_rate = self._get_fallback_rate(from_currency, to_currency)
        if fallback_rate:
            logger.warning(f"Using fallback rate for {from_currency} to {to_currency}: {fallback_rate}")
            return fallback_rate
        
        # Si no hay fallback disponible, lanzar error
        raise CurrencyServiceError(
            f"Failed to get exchange rate from {from_currency} to {to_currency}. "
            f"Last error: {last_error}"
        )
    
    def convert_amount(self, amount: Union[float, Decimal, str], 
                      from_currency: str, to_currency: str,
                      round_result: bool = True) -> Decimal:
        """
        Convierte un monto de una moneda a otra.
        
        Args:
            amount: Monto a convertir
            from_currency: Moneda origen
            to_currency: Moneda destino
            round_result: Si redondear el resultado
            
        Returns:
            Decimal: Monto convertido
        """
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))
        elif not isinstance(amount, Decimal):
            amount = Decimal(amount)
        
        if amount <= 0:
            raise CurrencyServiceError("Amount must be greater than 0")
        
        rate = self.get_exchange_rate(from_currency, to_currency)
        converted_amount = amount * Decimal(str(rate))
        
        if round_result:
            decimal_places = self.SUPPORTED_CURRENCIES[to_currency]['decimal_places']
            converted_amount = converted_amount.quantize(
                Decimal('0.1') ** decimal_places, 
                rounding=ROUND_HALF_UP
            )
        
        return converted_amount
    
    def format_currency(self, amount: Union[float, Decimal, str], 
                       currency: str, include_symbol: bool = True,
                       locale: str = None) -> str:
        """
        Formatea un monto con símbolo de moneda.
        
        Args:
            amount: Monto a formatear
            currency: Código de moneda
            include_symbol: Si incluir símbolo de moneda
            locale: Localización (ej: 'es_CO' para Colombia)
            
        Returns:
            str: Monto formateado
        """
        self._validate_currency(currency)
        
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, float):
            amount = Decimal(str(amount))
        elif not isinstance(amount, Decimal):
            amount = Decimal(amount)
        
        currency_info = self.SUPPORTED_CURRENCIES[currency]
        decimal_places = currency_info['decimal_places']
        
        # Redondear al número correcto de decimales
        amount = amount.quantize(
            Decimal('0.1') ** decimal_places, 
            rounding=ROUND_HALF_UP
        )
        
        # Formatear con separadores de miles
        amount_str = f"{amount:,.{decimal_places}f}"
        
        # Aplicar localización si se especifica
        if locale and locale.startswith('es'):
            # Formato español: usar punto para miles y coma para decimales
            amount_str = amount_str.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
        
        if include_symbol:
            symbol = currency_info['symbol']
            if currency == 'COP' and locale and locale.startswith('es'):
                return f"${amount_str} COP"
            elif currency in ['USD', 'CAD', 'AUD', 'COP', 'MXN', 'CLP', 'ARS']:
                return f"{symbol}{amount_str}"
            else:
                return f"{amount_str} {symbol}"
        
        return amount_str
    
    def get_supported_currencies(self) -> Dict[str, Dict[str, Union[str, int]]]:
        """Retorna las monedas soportadas"""
        return self.SUPPORTED_CURRENCIES.copy()
    
    def is_currency_supported(self, currency: str) -> bool:
        """Verifica si una moneda está soportada"""
        return currency.upper() in self.SUPPORTED_CURRENCIES
    
    def get_all_rates(self, base_currency: str = None, 
                     force_refresh: bool = False) -> Dict[str, float]:
        """
        Obtiene todas las tasas de cambio para una moneda base.
        
        Args:
            base_currency: Moneda base (por defecto USD)
            force_refresh: Forzar actualización del cache
            
        Returns:
            Dict[str, float]: Diccionario con todas las tasas
        """
        if base_currency is None:
            base_currency = self.default_currency
        
        self._validate_currency(base_currency)
        
        # Verificar cache
        cache_key = self._get_cache_key('rates', base_currency=base_currency)
        
        if not force_refresh:
            cached_rates = self.cache.get(cache_key)
            if cached_rates is not None:
                return cached_rates
        
        rates = {}
        for currency in self.SUPPORTED_CURRENCIES:
            if currency != base_currency:
                try:
                    rate = self.get_exchange_rate(base_currency, currency)
                    rates[currency] = rate
                except Exception as e:
                    logger.error(f"Failed to get rate for {currency}: {e}")
                    continue
        
        # Guardar en cache
        self.cache.set(cache_key, rates, timeout=self.cache_duration)
        return rates
    
    def get_historical_rate(self, from_currency: str, to_currency: str, 
                           date: datetime) -> Optional[float]:
        """
        Obtiene tasa histórica (implementación básica).
        En producción, se conectaría a un proveedor de datos históricos.
        """
        # Por ahora, retorna None ya que requiere APIs premium
        logger.warning(f"Historical rates not implemented for {from_currency} to {to_currency} on {date}")
        return None
    
    def _validate_currency(self, currency: str) -> None:
        """Valida que una moneda esté soportada"""
        if not self.is_currency_supported(currency):
            raise CurrencyServiceError(
                f"Currency '{currency}' is not supported. "
                f"Supported currencies: {', '.join(self.SUPPORTED_CURRENCIES.keys())}"
            )
    
    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Retorna tasas de fallback hardcodeadas para casos de emergencia.
        Estas tasas deben actualizarse periódicamente.
        """
        # Tasas aproximadas de diciembre 2024 (solo para emergencias)
        fallback_rates = {
            ('USD', 'EUR'): 0.95,
            ('USD', 'GBP'): 0.79,
            ('USD', 'JPY'): 150.0,
            ('USD', 'CAD'): 1.36,
            ('USD', 'AUD'): 1.48,
            ('USD', 'COP'): 4100.0,
            ('USD', 'MXN'): 20.5,
            ('USD', 'BRL'): 6.0,
            # Agregar más tasas según necesidad
        }
        
        # Buscar tasa directa
        rate = fallback_rates.get((from_currency, to_currency))
        if rate:
            return rate
        
        # Buscar tasa inversa
        inverse_rate = fallback_rates.get((to_currency, from_currency))
        if inverse_rate:
            return 1.0 / inverse_rate
        
        # Conversión a través de USD
        if from_currency != 'USD' and to_currency != 'USD':
            usd_from_rate = fallback_rates.get(('USD', from_currency))
            usd_to_rate = fallback_rates.get(('USD', to_currency))
            
            if usd_from_rate and usd_to_rate:
                return usd_to_rate / usd_from_rate
        
        return None
    
    def clear_cache(self) -> None:
        """Limpia el cache de tasas de cambio"""
        self.cache.clear_pattern("currency_*")
        logger.info("Currency cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Union[int, List[str]]]:
        """Retorna estadísticas del cache"""
        return {
            'cached_rates': len(self.cache.get_keys_pattern("currency_rate_*")),
            'cached_rate_sets': len(self.cache.get_keys_pattern("currency_rates_*")),
            'cache_keys': self.cache.get_keys_pattern("currency_*")
        }


# Instancia global del servicio
currency_service = CurrencyService()


def get_currency_service() -> CurrencyService:
    """Factory function para obtener el servicio de currency"""
    return currency_service


# Decoradores utilitarios

def with_currency_conversion(from_field: str = 'amount', 
                           from_currency_field: str = 'currency',
                           to_currency: str = 'USD'):
    """
    Decorador para agregar conversión automática de moneda a métodos.
    
    Usage:
        @with_currency_conversion('price', 'price_currency', 'USD')
        def process_product(self, product_data):
            # product_data tendrá 'price_usd' agregado automáticamente
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener datos del primer argumento si es un dict
            if args and isinstance(args[0], dict):
                data = args[0]
                if from_field in data and from_currency_field in data:
                    try:
                        converted_amount = currency_service.convert_amount(
                            data[from_field],
                            data[from_currency_field],
                            to_currency
                        )
                        data[f"{from_field}_{to_currency.lower()}"] = float(converted_amount)
                    except Exception as e:
                        logger.error(f"Currency conversion failed: {e}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def format_currency_filter(amount: Union[float, Decimal, str], 
                          currency: str = 'USD') -> str:
    """Filtro Jinja2 para formatear monedas"""
    try:
        return currency_service.format_currency(amount, currency)
    except Exception:
        return str(amount)


# Registrar filtro Jinja2
@current_app.template_filter('currency')
def currency_filter(amount, currency='USD'):
    return format_currency_filter(amount, currency)