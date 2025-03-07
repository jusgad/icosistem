# tests/__init__.py
"""
Paquete de pruebas para la aplicación de emprendimiento.
Este paquete contiene todas las pruebas unitarias e integración.
"""

# Este archivo puede estar vacío y simplemente marca el directorio como un paquete Python
# Sin embargo, también podría contener configuración común para todas las pruebas

import os
import sys

# Asegurar que el directorio raíz del proyecto esté en el path de Python
# para que las importaciones funcionen correctamente durante las pruebas
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))