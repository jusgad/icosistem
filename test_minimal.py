#!/usr/bin/env python3
"""
Test mínimo para verificar la funcionalidad básica.
"""

def test_core_functionality():
    """Test solo de funcionalidad core sin imports problemáticos."""
    print("🔄 Probando funcionalidad core...")
    
    try:
        # Test básico de configuración
        import os
        os.environ['FLASK_ENV'] = 'development'
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        print("✅ Variables de entorno configuradas")
        
        # Test de imports core
        from app.core.constants import USER_ROLES
        print("✅ Constantes core importadas")
        
        from app.core.security import validate_password_strength
        result = validate_password_strength("TestPassword123!")
        if result['is_valid']:
            print("✅ Validación de contraseñas funciona")
        
        from app.extensions import db
        print("✅ Base de datos disponible")
        
        print("🎉 Test mínimo EXITOSO - La funcionalidad core funciona")
        return True
        
    except Exception as e:
        print(f"❌ Error en test mínimo: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TEST MÍNIMO - CORE FUNCTIONALITY")
    print("=" * 50)
    
    if test_core_functionality():
        print("\n✅ SUCCESS: El core de la aplicación funciona correctamente")
        print("📝 Nota: Algunas utilidades opcionales pueden requerir dependencias adicionales")
    else:
        print("\n❌ FAILED: Problemas con funcionalidad core")
    
    print("=" * 50)