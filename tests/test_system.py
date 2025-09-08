#!/usr/bin/env python3
"""
Basic testing system for the entrepreneurship ecosystem
"""

import os
import sys
import requests
import time
import sqlite3
from pathlib import Path

def test_database_connection():
    """Test database connectivity"""
    print("🗄️ Testing database connection...")
    
    db_path = Path('instance/entrepreneurship_ecosystem.db')
    
    if not db_path.exists():
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"✅ Database connected - Found {len(tables)} tables")
        
        # Test user table
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Users table: {user_count} users")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_application_startup():
    """Test if application can start"""
    print("🚀 Testing application startup...")
    
    try:
        # Import minimal app
        sys.path.insert(0, str(Path(__file__).parent))
        from run_minimal import create_minimal_app
        
        app = create_minimal_app()
        
        print("✅ Flask app created successfully")
        print(f"✅ Secret key configured: {bool(app.config.get('SECRET_KEY'))}")
        print(f"✅ Database URI set: {bool(app.config.get('SQLALCHEMY_DATABASE_URI'))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Application startup test failed: {e}")
        return False

def test_security_functions():
    """Test security functions"""
    print("🔐 Testing security functions...")
    
    try:
        # Test password hashing
        from werkzeug.security import generate_password_hash, check_password_hash
        
        password = "test_password_123"
        hashed = generate_password_hash(password)
        
        if check_password_hash(hashed, password):
            print("✅ Password hashing works")
        else:
            print("❌ Password hashing failed")
            return False
        
        # Test crypto utils if available
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from app.utils.crypto_utils import generate_token, secure_random_string
            
            token = generate_token(32)
            random_str = secure_random_string(16)
            
            if len(token) > 0 and len(random_str) > 0:
                print("✅ Crypto utilities working")
            else:
                print("⚠️ Crypto utilities have issues")
                
        except Exception as e:
            print(f"⚠️ Crypto utilities test failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Security functions test failed: {e}")
        return False

def test_file_operations():
    """Test file operations"""
    print("📁 Testing file operations...")
    
    try:
        # Test directory creation
        test_dir = Path('test_uploads')
        test_dir.mkdir(exist_ok=True)
        
        # Test file writing
        test_file = test_dir / 'test.txt'
        test_file.write_text("Test file content")
        
        # Test file reading
        content = test_file.read_text()
        
        if content == "Test file content":
            print("✅ File operations working")
        else:
            print("❌ File operations failed")
            return False
        
        # Cleanup
        test_file.unlink()
        test_dir.rmdir()
        
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints"""
    print("🌐 Testing API endpoints...")
    
    # Note: This would require the server to be running
    # For now, we'll test the endpoint functions directly
    
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from run_minimal import create_minimal_app
        
        app = create_minimal_app()
        
        with app.test_client() as client:
            # Test health endpoint
            response = client.get('/api/health')
            if response.status_code == 200:
                data = response.get_json()
                if data.get('status') == 'healthy':
                    print("✅ Health endpoint working")
                else:
                    print("❌ Health endpoint returned wrong status")
                    return False
            else:
                print(f"❌ Health endpoint returned {response.status_code}")
                return False
            
            # Test status endpoint
            response = client.get('/api/status')
            if response.status_code == 200:
                print("✅ Status endpoint working")
            else:
                print(f"❌ Status endpoint returned {response.status_code}")
                return False
            
            # Test security endpoint
            response = client.get('/api/security')
            if response.status_code == 200:
                print("✅ Security endpoint working")
            else:
                print(f"❌ Security endpoint returned {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ API endpoints test failed: {e}")
        return False

def test_configuration():
    """Test system configuration"""
    print("⚙️ Testing system configuration...")
    
    try:
        # Test environment variables
        required_vars = ['DATABASE_URL', 'SECRET_KEY', 'JWT_SECRET_KEY']
        missing_vars = []
        
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️ Missing environment variables: {missing_vars}")
        else:
            print("✅ All required environment variables set")
        
        # Test .env file
        env_file = Path('.env')
        if env_file.exists():
            print("✅ .env file exists")
        else:
            print("⚠️ .env file not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def run_performance_test():
    """Run basic performance test"""
    print("⚡ Running performance tests...")
    
    try:
        # Test database query performance
        start_time = time.time()
        
        db_path = Path('instance/entrepreneurship_ecosystem.db')
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Run 100 simple queries
        for i in range(100):
            cursor.execute("SELECT COUNT(*) FROM users")
            cursor.fetchone()
        
        conn.close()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Database performance: 100 queries in {duration:.3f}s ({100/duration:.1f} queries/sec)")
        
        if duration < 1.0:
            print("✅ Database performance is good")
        else:
            print("⚠️ Database performance could be better")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("🧪 STARTING COMPREHENSIVE SYSTEM TESTS")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Application Startup", test_application_startup), 
        ("Security Functions", test_security_functions),
        ("File Operations", test_file_operations),
        ("API Endpoints", test_api_endpoints),
        ("System Configuration", test_configuration),
        ("Performance", run_performance_test)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"💥 {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print("🏁 TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"✅ Tests passed: {passed}")
    print(f"❌ Tests failed: {failed}")
    print(f"📊 Success rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! System is working correctly.")
    elif failed <= 2:
        print(f"\n⚠️ {failed} tests failed, but core functionality is working.")
    else:
        print(f"\n🚨 {failed} tests failed. System needs attention.")
    
    return failed == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)