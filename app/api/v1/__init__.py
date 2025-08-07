"""
API v1 package.
"""

from flask import Blueprint, jsonify

# Crear el blueprint de API v1
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

@api_v1_bp.route('/status')
def status():
    """Estado de la API."""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0',
        'message': 'API funcionando correctamente'
    })

@api_v1_bp.route('/health')
def health():
    """Health check de la API."""
    return jsonify({
        'status': 'healthy',
        'timestamp': '2023-01-01T00:00:00Z'
    })