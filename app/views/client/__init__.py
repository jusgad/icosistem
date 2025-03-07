# app/views/client/__init__.py

from flask import Blueprint

client = Blueprint('client', __name__, url_prefix='/client')

# Importar las vistas del cliente para registrarlas con el blueprint
from app.views.client.dashboard import *
from app.views.client.impact import *
from app.views.client.directory import *