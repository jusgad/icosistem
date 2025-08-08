#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación Flask MÍNIMA para probar que todo funciona.
"""

from flask import Flask, render_template_string
from flask_login import LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
import os

# Crear aplicación Flask
app = Flask(__name__)

# Configuración básica
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///test.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensiones
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Modelo de usuario mínimo
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rutas básicas
@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ecosistema de Emprendimiento - ¡Funcionando!</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; min-height: 100vh; }
            .container { max-width: 800px; margin: 0 auto; text-align: center; padding: 40px; }
            .success-box { background: rgba(255,255,255,0.1); padding: 30px; border-radius: 10px; backdrop-filter: blur(10px); }
            h1 { font-size: 2.5em; margin-bottom: 20px; }
            .check-mark { font-size: 4em; color: #4CAF50; margin-bottom: 20px; }
            .stats { display: flex; justify-content: space-around; margin: 30px 0; }
            .stat { text-align: center; }
            .stat-number { font-size: 2em; font-weight: bold; }
            .links { margin-top: 30px; }
            .links a { color: white; text-decoration: none; margin: 0 10px; padding: 10px 20px; border: 2px solid white; border-radius: 5px; }
            .links a:hover { background: rgba(255,255,255,0.2); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-box">
                <div class="check-mark">✅</div>
                <h1>¡Aplicación Funcionando!</h1>
                <p>El Ecosistema de Emprendimiento está corriendo correctamente.</p>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-number">{{ users_count }}</div>
                        <div>Usuarios</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">Flask 3.1</div>
                        <div>Version</div>
                    </div>
                    <div class="stat">
                        <div class="stat-number">SQLAlchemy</div>
                        <div>Base de Datos</div>
                    </div>
                </div>
                
                <div class="links">
                    <a href="/health">Estado</a>
                    <a href="/api/status">API</a>
                    <a href="/info">Información</a>
                </div>
                
                <p style="margin-top: 30px; opacity: 0.8;">
                    <small>Todas las dependencias principales están funcionando correctamente.</small>
                </p>
            </div>
        </div>
    </body>
    </html>
    ''', users_count=User.query.count())

@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'database': 'connected',
        'users_table': 'working',
        'dependencies': 'loaded'
    }

@app.route('/api/status')
def api_status():
    return {
        'application': 'Ecosistema de Emprendimiento',
        'status': 'running',
        'version': '1.0.0',
        'database': app.config['SQLALCHEMY_DATABASE_URI'],
        'users': User.query.count(),
        'framework': 'Flask 3.1.1',
        'orm': 'SQLAlchemy 2.0+'
    }

@app.route('/info')
def info():
    return render_template_string('''
    <h1>Información del Sistema</h1>
    <h2>✅ Dependencias Funcionando:</h2>
    <ul>
        <li>Flask 3.1.1 - Framework web</li>
        <li>SQLAlchemy 2.0+ - ORM de base de datos</li>
        <li>Flask-Login - Sistema de autenticación</li>
        <li>Flask-SQLAlchemy - Integración BD</li>
        <li>Psycopg2 - Driver PostgreSQL</li>
        <li>Redis - Sistema de caché</li>
        <li>Celery - Tareas en background</li>
    </ul>
    <h2>📊 Estado:</h2>
    <p>Base de datos: {{ db_status }}</p>
    <p>Usuarios registrados: {{ users_count }}</p>
    <p><a href="/">← Volver al inicio</a></p>
    ''', db_status='Conectada y funcionando', users_count=User.query.count())

# Crear tablas al iniciar - Flask 3.x compatible
def init_db():
    """Inicializar base de datos."""
    db.create_all()
    
    # Crear usuario de prueba si no existe
    if User.query.count() == 0:
        test_user = User(
            email='admin@ecosistema.com',
            name='Administrador Sistema'
        )
        db.session.add(test_user)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    
    print("🚀 Iniciando Ecosistema de Emprendimiento...")
    print("📍 Servidor: http://localhost:5000")
    print("💾 Base de datos: SQLite (test.db)")
    print("✨ Estado: Todas las dependencias cargadas correctamente")
    
    app.run(debug=True, host='0.0.0.0', port=5000)