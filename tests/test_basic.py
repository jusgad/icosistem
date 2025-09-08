#!/usr/bin/env python3
"""
Test básico para verificar que la aplicación arranca correctamente.
"""

import sys
import os

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Probar imports básicos."""
    print("🔄 Probando imports básicos...")
    
    try:
        from app.extensions import db, login_manager, mail
        print("✅ Extensions importadas correctamente")
    except Exception as e:
        print(f"❌ Error importando extensions: {e}")
        return False
    
    try:
        from app.core.constants import USER_ROLES, VALID_ROLES
        print("✅ Constants importadas correctamente")
    except Exception as e:
        print(f"❌ Error importando constants: {e}")
        return False
    
    try:
        from app.models import User, UserType
        print("✅ Models importados correctamente")
    except Exception as e:
        print(f"❌ Error importando models: {e}")
        return False
    
    return True

def test_app_creation():
    """Probar creación de aplicación."""
    print("\n🔄 Probando creación de aplicación...")
    
    try:
        from app import create_app
        app = create_app('development')
        print("✅ Aplicación creada correctamente")
        
        # Probar context
        with app.app_context():
            print("✅ Context de aplicación funciona")
            
        return True
    except Exception as e:
        print(f"❌ Error creando aplicación: {e}")
        return False

def main():
    """Función principal de tests."""
    print("=" * 60)
    print("🧪 TESTS BÁSICOS - ECOSISTEMA DE EMPRENDIMIENTO")
    print("=" * 60)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test app creation  
    if not test_app_creation():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 TODOS LOS TESTS BÁSICOS PASARON")
        print("✅ La aplicación está lista para usar")
    else:
        print("💥 ALGUNOS TESTS FALLARON") 
        print("❌ Revisa los errores anteriores")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())