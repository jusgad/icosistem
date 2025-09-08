#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify core dependencies are working
"""

def test_core_imports():
    """Test that core Flask and extensions can be imported."""
    print("🧪 Probando importaciones principales...")
    
    try:
        import flask
        print(f"✅ Flask {flask.__version__}")
    except ImportError as e:
        print(f"❌ Flask: {e}")
        return False
    
    try:
        import sqlalchemy
        print(f"✅ SQLAlchemy {sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ SQLAlchemy: {e}")
        return False
    
    try:
        import flask_sqlalchemy
        print(f"✅ Flask-SQLAlchemy {flask_sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ Flask-SQLAlchemy: {e}")
        return False
    
    try:
        import psycopg2
        print(f"✅ psycopg2 {psycopg2.__version__}")
    except ImportError as e:
        print(f"❌ psycopg2: {e}")
        return False
    
    try:
        import flask_login
        print(f"✅ Flask-Login {flask_login.__version__}")
    except ImportError as e:
        print(f"❌ Flask-Login: {e}")
        return False
    
    try:
        import flask_wtf
        print(f"✅ Flask-WTF {flask_wtf.__version__}")
    except ImportError as e:
        print(f"❌ Flask-WTF: {e}")
        return False
    
    try:
        import redis
        print(f"✅ Redis {redis.__version__}")
    except ImportError as e:
        print(f"❌ Redis: {e}")
        return False
    
    try:
        import celery
        print(f"✅ Celery {celery.__version__}")
    except ImportError as e:
        print(f"❌ Celery: {e}")
        return False
    
    return True

def test_flask_app():
    """Test basic Flask app creation."""
    print("\n🧪 Probando creación de aplicación Flask básica...")
    
    try:
        from flask import Flask
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        
        @app.route('/')
        def hello():
            return {'status': 'OK', 'message': 'Flask app works!'}
        
        @app.route('/health')
        def health():
            return {'status': 'healthy', 'dependencies': 'OK'}
        
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'OK'
            
            response = client.get('/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'healthy'
        
        print("✅ Aplicación Flask básica funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en aplicación Flask: {e}")
        return False

def test_database_connection():
    """Test basic database setup without models."""
    print("\n🧪 Probando configuración básica de base de datos...")
    
    try:
        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy
        
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db = SQLAlchemy(app)
        
        # Test table creation
        class TestModel(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50), nullable=False)
        
        with app.app_context():
            db.create_all()
            
            # Test insert
            test_record = TestModel(name='test')
            db.session.add(test_record)
            db.session.commit()
            
            # Test query
            result = TestModel.query.first()
            assert result.name == 'test'
        
        print("✅ Base de datos SQLite en memoria funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en base de datos: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 PRUEBA DE DEPENDENCIAS - ECOSISTEMA DE EMPRENDIMIENTO")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    if test_core_imports():
        tests_passed += 1
    
    if test_flask_app():
        tests_passed += 1
    
    if test_database_connection():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTADOS: {tests_passed}/{total_tests} pruebas pasaron")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todas las dependencias principales funcionan correctamente!")
        print("✅ El requirements-core.txt está listo para usar")
        print("\n📋 Para usar la aplicación:")
        print("   1. Configura las variables de entorno (DATABASE_URL, SECRET_KEY, etc.)")
        print("   2. Ejecuta las migraciones de base de datos")
        print("   3. Inicia la aplicación")
        return True
    else:
        print("⚠️  Algunas dependencias necesitan corrección")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)