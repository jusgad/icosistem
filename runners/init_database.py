#!/usr/bin/env python3
"""
Database initialization script for the entrepreneurship ecosystem
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///instance/entrepreneurship_ecosystem.db'
os.environ['SECRET_KEY'] = 'dev-secret-key-for-initialization-only'
os.environ['JWT_SECRET_KEY'] = 'dev-jwt-secret-key-for-initialization-only'

def create_app_minimal():
    """Create minimal Flask app for database operations"""
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Initialize extensions
    db = SQLAlchemy()
    migrate = Migrate()
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    return app, db

def create_database_tables():
    """Create basic database structure"""
    print("🗄️ Initializing database...")
    
    try:
        app, db = create_app_minimal()
        
        with app.app_context():
            # Create instance directory
            instance_dir = Path('instance')
            instance_dir.mkdir(exist_ok=True)
            
            # Create all tables
            db.create_all()
            
            print("✅ Database tables created successfully")
            
            # Create basic admin user if needed
            try:
                from werkzeug.security import generate_password_hash
                
                # Basic user table
                result = db.engine.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username VARCHAR(80) UNIQUE NOT NULL,
                        email VARCHAR(120) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(20) DEFAULT 'user',
                        is_active BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Check if admin user exists
                admin_exists = db.engine.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'").scalar()
                
                if admin_exists == 0:
                    # Create admin user
                    admin_password_hash = generate_password_hash('admin123')
                    db.engine.execute("""
                        INSERT INTO users (username, email, password_hash, role) 
                        VALUES ('admin', 'admin@ecosistema.local', ?, 'admin')
                    """, admin_password_hash)
                    
                    print("✅ Admin user created (admin/admin123)")
                else:
                    print("ℹ️ Admin user already exists")
                    
            except Exception as e:
                print(f"⚠️ Could not create admin user: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def initialize_basic_data():
    """Initialize basic data for the system"""
    print("📊 Initializing basic data...")
    
    try:
        app, db = create_app_minimal()
        
        with app.app_context():
            # Create basic configuration table
            db.engine.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert basic configuration
            basic_configs = [
                ('app_name', 'Ecosistema de Emprendimiento', 'Application name'),
                ('app_version', '1.0.0', 'Application version'),
                ('maintenance_mode', 'false', 'Maintenance mode flag'),
                ('max_upload_size', '16777216', 'Maximum file upload size in bytes'),
                ('session_timeout', '3600', 'Session timeout in seconds')
            ]
            
            for key, value, description in basic_configs:
                # Check if config exists
                exists = db.engine.execute("SELECT COUNT(*) FROM system_config WHERE key = ?", key).scalar()
                if exists == 0:
                    db.engine.execute(
                        "INSERT INTO system_config (key, value, description) VALUES (?, ?, ?)",
                        key, value, description
                    )
            
            print("✅ Basic system configuration initialized")
            return True
            
    except Exception as e:
        print(f"⚠️ Could not initialize basic data: {e}")
        return False

def main():
    """Main initialization function"""
    print("🚀 Starting Entrepreneurship Ecosystem Database Initialization")
    print("=" * 60)
    
    # Step 1: Create database tables
    if not create_database_tables():
        print("❌ Database initialization failed")
        return False
    
    # Step 2: Initialize basic data
    if not initialize_basic_data():
        print("⚠️ Basic data initialization had issues, but continuing...")
    
    print("=" * 60)
    print("✅ Database initialization completed successfully!")
    print()
    print("Next steps:")
    print("1. Run: source venv/bin/activate")
    print("2. Run: python run_minimal.py")
    print("3. Access: http://localhost:5000")
    print()
    print("Default admin credentials:")
    print("Username: admin")
    print("Password: admin123")
    
    return True

if __name__ == '__main__':
    main()