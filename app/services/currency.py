"""
Servicio de conversión de moneda para la aplicación de emprendimiento.
Proporciona funcionalidades para convertir valores entre diferentes divisas.
"""

import requests
import json
from datetime import datetime, timedelta
from flask import current_app
import os
from functools import lru_cache

class CurrencyService:
    """
    Servicio para la conversión de monedas utilizando APIs externas.
    Soporta almacenamiento en caché de tasas para reducir llamadas a la API.
    """
    
    CACHE_DURATION = 86400  # Duración del caché en segundos (24 horas)
    
    def __init__(self):
        self.api_key = os.environ.get('CURRENCY_API_KEY') or current_app.config.get('CURRENCY_API_KEY')
        self.base_url = current_app.config.get('CURRENCY_API_URL', 'https://api.exchangerate-api.com/v4/latest/')
        self.cache_file = os.path.join(current_app.instance_path, 'currency_cache.json')
        
    def _get_exchange_rates(self, base_currency='USD'):
        """
        Obtiene las tasas de cambio actuales desde la API externa.
        
        Args:
            base_currency: Moneda base para las conversiones
            
        Returns:
            dict: Diccionario con tasas de cambio
        """
        # Intentar cargar desde caché primero
        cached_rates = self._load_from_cache(base_currency)
        if cached_rates:
            return cached_rates
            
        # Si no hay caché válido, consultar la API
        try:
            response = requests.get(f"{self.base_url}{base_currency}", 
                                   headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})
            
            if response.status_code == 200:
                data = response.json()
                # Guardar en caché para futuras consultas
                self._save_to_cache(base_currency, data['rates'])
                return data['rates']
            else:
                current_app.logger.error(f"Error al obtener tasas de cambio: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Excepción al obtener tasas de cambio: {str(e)}")
            return None
    
    def _load_from_cache(self, base_currency):
        """
        Carga tasas de cambio desde el archivo de caché si es válido.
        
        Args:
            base_currency: Moneda base
            
        Returns:
            dict: Tasas de cambio o None si no hay caché válido
        """
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'r') as file:
                cache = json.load(file)
                
            # Verificar si la caché es válida
            if (base_currency in cache and 
                cache[base_currency]['timestamp'] + self.CACHE_DURATION > datetime.now().timestamp()):
                return cache[base_currency]['rates']
                
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error al cargar caché de monedas: {str(e)}")
            return None
    
    def _save_to_cache(self, base_currency, rates):
        """
        Guarda tasas de cambio en caché.
        
        Args:
            base_currency: Moneda base
            rates: Diccionario de tasas de cambio
        """
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            # Cargar caché existente o crear una nueva
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as file:
                    cache = json.load(file)
            else:
                cache = {}
            
            # Actualizar la entrada para la moneda base
            cache[base_currency] = {
                'timestamp': datetime.now().timestamp(),
                'rates': rates
            }
            
            # Guardar el caché actualizado
            with open(self.cache_file, 'w') as file:
                json.dump(cache, file)
                
        except Exception as e:
            current_app.logger.error(f"Error al guardar caché de monedas: {str(e)}")
    
    def convert(self, amount, from_currency, to_currency):
        """
        Convierte una cantidad de una moneda a otra.
        
        Args:
            amount: Cantidad a convertir
            from_currency: Código de moneda origen
            to_currency: Código de moneda destino
            
        Returns:
            float: Cantidad convertida o None si hay error
        """
        try:
            # Si las monedas son iguales, no hay conversión
            if from_currency == to_currency:
                return amount
                
            # Normalizar códigos de moneda
            from_currency = from_currency.upper()
            to_currency = to_currency.upper()
            
            # Obtener tasas de cambio
            rates = self._get_exchange_rates(from_currency)
            
            if rates and to_currency in rates:
                return round(amount * rates[to_currency], 2)
            
            # Si no tenemos tasas directas, usar USD como intermediario
            if from_currency != 'USD':
                usd_rates = self._get_exchange_rates('USD')
                if usd_rates and from_currency in usd_rates and to_currency in usd_rates:
                    # Convertir de moneda origen a USD, luego de USD a moneda destino
                    usd_amount = amount / usd_rates[from_currency]
                    return round(usd_amount * usd_rates[to_currency], 2)
            
            # Si todo lo demás falla, registrar error
            current_app.logger.error(f"No se pudo convertir {amount} de {from_currency} a {to_currency}")
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error en conversión de moneda: {str(e)}")
            return None
    
    @lru_cache(maxsize=100)
    def get_supported_currencies(self):
        """
        Obtiene la lista de monedas soportadas.
        
        Returns:
            dict: Diccionario con códigos y nombres de monedas
        """
        try:
            # A menudo, las APIs proporcionan un endpoint para esto
            # Si no está disponible, podemos usar una lista predefinida
            currencies = {
                "USD": "Dólar estadounidense",
                "EUR": "Euro",
                "GBP": "Libra esterlina",
                "JPY": "Yen japonés",
                "CAD": "Dólar canadiense",
                "AUD": "Dólar australiano",
                "CHF": "Franco suizo",
                "CNY": "Yuan chino",
                "HKD": "Dólar de Hong Kong",
                "NZD": "Dólar neozelandés",
                "MXN": "Peso mexicano",
                "COP": "Peso colombiano",
                "BRL": "Real brasileño",
                "ARS": "Peso argentino",
                "CLP": "Peso chileno",
                "PEN": "Sol peruano",
                "UYU": "Peso uruguayo",
                "BOB": "Boliviano",
                "VES": "Bolívar venezolano",
            }
            
            return currencies
            
        except Exception as e:
            current_app.logger.error(f"Error al obtener monedas soportadas: {str(e)}")
            return {}
    
    def format_currency(self, amount, currency_code):
        """
        Formatea una cantidad monetaria según su moneda.
        
        Args:
            amount: Cantidad a formatear
            currency_code: Código de moneda
            
        Returns:
            str: Cantidad formateada con símbolo de moneda
        """
        # Diccionario de símbolos de moneda
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "CAD": "C$",
            "AUD": "A$",
            "CHF": "CHF",
            "CNY": "¥",
            "HKD": "HK$",
            "NZD": "NZ$",
            "MXN": "MX$",
            "COP": "COL$",
            "BRL": "R$",
            "ARS": "AR$",
            "CLP": "CL$",
            "PEN": "S/",
            "UYU": "$U",
            "BOB": "Bs.",
            "VES": "Bs.S",
        }
        
        symbol = currency_symbols.get(currency_code.upper(), currency_code)
        
        # Formateo básico para diferentes monedas
        if currency_code.upper() in ["JPY", "CLP", "VES"]:
            # Monedas sin decimales
            return f"{symbol} {int(amount):,}"
        else:
            # Monedas con dos decimales
            return f"{symbol} {amount:,.2f}"

# Crear una instancia global del servicio
currency_service = CurrencyService()