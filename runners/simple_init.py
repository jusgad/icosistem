#!/usr/bin/env python3
"""
Simple database initialization
"""

import sqlite3
import os
from pathlib import Path

def create_simple_database():
    """Create a simple SQLite database"""
    # Ensure instance directory exists
    instance_dir = Path('instance')
    instance_dir.mkdir(exist_ok=True)
    
    db_path = instance_dir / 'entrepreneurship_ecosystem.db'
    
    try:
        # Create database connection
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create system config table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert basic config
        cursor.execute('''
            INSERT OR IGNORE INTO system_config (key, value, description) 
            VALUES ('app_name', 'Ecosistema de Emprendimiento', 'Application name')
        ''')
        
        cursor.execute('''
            INSERT OR IGNORE INTO system_config (key, value, description) 
            VALUES ('app_version', '1.0.0', 'Application version')
        ''')
        
        # Create admin user
        from werkzeug.security import generate_password_hash
        admin_password_hash = generate_password_hash('admin123')
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash, role) 
            VALUES ('admin', 'admin@ecosistema.local', ?, 'admin')
        ''', (admin_password_hash,))
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"✅ Database created successfully at: {db_path}")
        print("✅ Admin user created (admin/admin123)")
        return True
        
    except Exception as e:
        print(f"❌ Database creation failed: {e}")
        return False

if __name__ == '__main__':
    create_simple_database()