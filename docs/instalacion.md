# 🚀 Guía de Instalación - Ecosistema de Emprendimiento

## 📋 Requisitos del Sistema

### Requisitos Mínimos
- **Python**: 3.11 o superior
- **RAM**: 2GB mínimo (4GB recomendado)
- **Almacenamiento**: 5GB disponibles
- **OS**: Linux, macOS, Windows 10/11

### Requisitos Recomendados
- **Python**: 3.11 o 3.12
- **RAM**: 8GB o superior
- **Almacenamiento**: 20GB disponibles (SSD recomendado)
- **CPU**: 4+ cores
- **OS**: Ubuntu 20.04+, macOS 12+, Windows 11

## 🛠️ Instalación de Dependencias del Sistema

### Ubuntu/Debian
```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python y herramientas de desarrollo
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y build-essential git curl wget

# Instalar PostgreSQL (opcional)
sudo apt install -y postgresql postgresql-contrib libpq-dev

# Instalar Redis (opcional)
sudo apt install -y redis-server

# Instalar Node.js (para herramientas de desarrollo)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### macOS
```bash
# Instalar Homebrew si no está instalado
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar Python
brew install python@3.11

# Instalar PostgreSQL (opcional)
brew install postgresql@15
brew services start postgresql

# Instalar Redis (opcional)
brew install redis
brew services start redis

# Instalar Node.js
brew install node@18
```

### Windows
```powershell
# Instalar Python 3.11 desde https://python.org
# O usar winget
winget install Python.Python.3.11

# Instalar Git
winget install Git.Git

# Instalar PostgreSQL (opcional)
winget install PostgreSQL.PostgreSQL

# Instalar Redis usando WSL o Docker
# Ver sección de Docker más abajo
```

## 📦 Instalación del Proyecto

### 1. Clonar el Repositorio
```bash
git clone https://github.com/your-org/icosistem.git
cd icosistem
```

### 2. Crear y Activar Entorno Virtual
```bash
# Crear entorno virtual
python3.11 -m venv venv

# Activar entorno virtual
# En Linux/macOS:
source venv/bin/activate

# En Windows:
venv\Scripts\activate

# Verificar Python
python --version  # Debe mostrar Python 3.11.x
```

### 3. Actualizar pip y herramientas base
```bash
pip install --upgrade pip setuptools wheel
```

### 4. Instalar Dependencias
```bash
# ✅ Instalar todas las dependencias (archivo unificado)
pip install -r requirements.txt

# Verificar instalación
pip list | grep Flask  # Debe mostrar Flask 3.0+
pip list | grep SQLAlchemy  # Debe mostrar SQLAlchemy 2.0+
pip list | grep pydantic  # Debe mostrar Pydantic 2.0+
```

### 5. Configurar Variables de Entorno
```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar archivo .env
nano .env  # o el editor de tu preferencia
```

#### Variables de Entorno Principales
```bash
# Configuración básica
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta-super-segura-aqui
JWT_SECRET_KEY=tu-jwt-clave-secreta-diferente

# Base de datos (SQLite para desarrollo)
DATABASE_URL=sqlite:///app.db

# Base de datos (PostgreSQL para producción)
# DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/icosistem

# Redis (opcional)
REDIS_URL=redis://localhost:6379/0

# Email (opcional para desarrollo)
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USE_SSL=false

# Servicios externos (opcional)
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret
SENDGRID_API_KEY=tu-sendgrid-api-key
TWILIO_ACCOUNT_SID=tu-twilio-account-sid
TWILIO_AUTH_TOKEN=tu-twilio-auth-token
```

### 6. Inicializar Base de Datos
```bash
# Crear migraciones iniciales
flask db init

# Generar primera migración
flask db migrate -m "Initial migration"

# Aplicar migraciones
flask db upgrade

# Verificar que las tablas se crearon correctamente
python -c "
from app import create_app
from app.extensions import db
app = create_app('development')
with app.app_context():
    print('✅ Base de datos inicializada correctamente')
"
```

### 7. Cargar Datos de Prueba (Opcional)
```bash
# Ejecutar script de seed
python scripts/seed_data.py

# O crear datos mínimos
python -c "
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app('development')
with app.app_context():
    admin = User(
        email='admin@example.com',
        username='admin',
        first_name='Admin',
        last_name='Usuario',
        user_type='admin',
        is_active=True,
        email_verified=True
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    print('✅ Usuario admin creado: admin@example.com / admin123')
"
```

## 🚀 Ejecutar la Aplicación

### Modo Desarrollo
```bash
# Ejecutar con servidor de desarrollo
python run.py

# O usando Flask CLI
flask run --host=0.0.0.0 --port=5000 --debug

# La aplicación estará disponible en:
# http://localhost:5000
```

### Verificar Instalación
```bash
# Health check básico
curl http://localhost:5000/health

# Health check detallado
curl http://localhost:5000/health/detailed

# Documentación API
# Abrir en navegador: http://localhost:5000/api/docs
```

## 🐳 Instalación con Docker (Recomendada)

### Prerrequisitos Docker
```bash
# Instalar Docker y Docker Compose
# Ubuntu:
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
# Reiniciar sesión o ejecutar: newgrp docker

# macOS:
brew install --cask docker

# Windows:
# Instalar Docker Desktop desde https://docker.com
```

### Instalación con Docker
```bash
# Clonar repositorio
git clone https://github.com/your-org/icosistem.git
cd icosistem

# Configurar variables de entorno
cp .env.example .env
# Editar .env según necesidades

# Construir y ejecutar servicios
docker-compose up --build

# En modo background
docker-compose up -d --build

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down
```

### Docker para Producción
```bash
# Usar configuración de producción
docker-compose -f docker-compose.prod.yml up --build -d

# Ver estado de servicios
docker-compose -f docker-compose.prod.yml ps

# Ver logs de producción
docker-compose -f docker-compose.prod.yml logs -f app
```

## 🧪 Verificación de la Instalación

### Tests de Verificación
```bash
# Ejecutar tests básicos
python -c "
import sys
print('Python version:', sys.version)

# Test Flask
from flask import Flask
print('✅ Flask importado correctamente')

# Test SQLAlchemy
from sqlalchemy import __version__
print('✅ SQLAlchemy version:', __version__)

# Test app creation
from app import create_app
app = create_app('development')
print('✅ App creada correctamente')

# Test database
with app.app_context():
    from app.extensions import db
    print('✅ Base de datos conectada')
    
# ✅ Test modelos reparados
from app.models.milestone import Milestone, ProjectMilestone
from app.models.application import Application
from app.models.project import ProjectPriority
print('✅ Nuevos modelos funcionando')

print('🎉 Instalación verificada exitosamente!')
"
```

### Health Check Completo
```bash
# Script de verificación completa
python scripts/health_check.py --all

# O verificación manual
python -c "
from app import create_app
from app.extensions import db
from app.core.security import validate_password_strength

app = create_app('development')

with app.app_context():
    # Test database
    try:
        db.engine.execute('SELECT 1')
        print('✅ Base de datos: OK')
    except Exception as e:
        print('❌ Base de datos:', e)
    
    # Test password validation
    result = validate_password_strength('TestPassword123!')
    if result['is_valid']:
        print('✅ Validación de contraseñas: OK')
    else:
        print('❌ Validación de contraseñas: Error')
    
    print('🎉 Sistema listo para usar!')
"
```

## 🔧 Configuraciones Avanzadas

### PostgreSQL Setup Detallado
```bash
# Crear usuario y base de datos
sudo -u postgres psql

CREATE USER icosistem_user WITH PASSWORD 'tu_contraseña_segura';
CREATE DATABASE icosistem_dev OWNER icosistem_user;
CREATE DATABASE icosistem_test OWNER icosistem_user;
GRANT ALL PRIVILEGES ON DATABASE icosistem_dev TO icosistem_user;
GRANT ALL PRIVILEGES ON DATABASE icosistem_test TO icosistem_user;
\q

# Actualizar .env
DATABASE_URL=postgresql://icosistem_user:tu_contraseña_segura@localhost:5432/icosistem_dev
TEST_DATABASE_URL=postgresql://icosistem_user:tu_contraseña_segura@localhost:5432/icosistem_test
```

### Redis Setup Detallado
```bash
# Configurar Redis
sudo nano /etc/redis/redis.conf

# Cambiar configuración recomendada:
# bind 127.0.0.1
# requirepass tu_contraseña_redis
# maxmemory 256mb
# maxmemory-policy allkeys-lru

# Reiniciar Redis
sudo systemctl restart redis-server

# Verificar conexión
redis-cli ping
# Debe responder: PONG

# Actualizar .env
REDIS_URL=redis://:tu_contraseña_redis@localhost:6379/0
```

## 🔍 Solución de Problemas Comunes

### Error: "ModuleNotFoundError"
```bash
# Verificar que el entorno virtual está activo
which python  # Debe apuntar a venv/bin/python

# Reinstalar dependencias
pip install --force-reinstall -r requirements.txt

# Verificar PATH
echo $PYTHONPATH
```

### Error: "Database connection failed"
```bash
# Verificar PostgreSQL está corriendo
sudo systemctl status postgresql

# Verificar conexión manual
psql -U icosistem_user -d icosistem_dev -h localhost

# Resetear base de datos
dropdb icosistem_dev
createdb icosistem_dev -O icosistem_user
flask db upgrade
```

### Error: "Redis connection failed"
```bash
# Verificar Redis está corriendo
sudo systemctl status redis-server

# Test conexión manual
redis-cli ping

# Reiniciar Redis
sudo systemctl restart redis-server
```

### Error: "Permission denied" en Docker
```bash
# Añadir usuario al grupo docker
sudo usermod -aG docker $USER

# Reiniciar sesión o ejecutar:
newgrp docker

# Verificar permisos
docker run hello-world
```

## ✅ Checklist Final de Instalación

- [ ] Python 3.11+ instalado y verificado
- [ ] Entorno virtual creado y activado
- [ ] ✅ Dependencias instaladas desde requirements.txt unificado
- [ ] Variables de entorno configuradas en .env
- [ ] Base de datos inicializada con migraciones
- [ ] ✅ Modelos nuevos funcionando (Milestone, Application)
- [ ] Aplicación ejecutándose en http://localhost:5000
- [ ] Health check responde correctamente
- [ ] Usuario admin creado (opcional)
- [ ] Tests básicos pasan correctamente
- [ ] Docker funciona (si se usa)
- [ ] Servicios externos configurados (opcional)

## 🎉 Mejoras Incluidas en Esta Instalación

### ✅ Código Completamente Reparado
- **Modelos faltantes creados**: Milestone, Application, ProjectPriority
- **Mixins añadidos**: UserTrackingMixin para auditoría
- **Formularios corregidos**: AdminUserForm, validadores
- **Dependencias unificadas**: Un solo requirements.txt con 130+ dependencias

### ✅ Funcionalidades Completas
- **Sistema de Hitos**: Seguimiento completo de milestones
- **Aplicaciones a Programas**: Workflow completo de aplicaciones
- **Gestión de Usuarios**: Tipos múltiples con seguimiento
- **Formularios Admin**: Panel administrativo funcional

### ✅ Stack Tecnológico Moderno
- **Flask 3.0+** con todas las extensiones
- **SQLAlchemy 2.0+** con soporte async
- **Pydantic 2.0+** para validación
- **Redis** para cache y sesiones
- **130+ dependencias** organizadas por categorías

## 🚀 Próximos Pasos

1. **Configurar datos de prueba**: `python scripts/seed_data.py`
2. **Explorar API**: Visitar http://localhost:5000/api/docs
3. **Configurar servicios externos**: Google, SendGrid, etc.
4. **Setup de desarrollo**: Configurar IDE y herramientas
5. **Leer documentación de desarrollo**: [docs/desarrollo.md](desarrollo.md)

---

**¿Necesitas ayuda?** Consulta la [documentación completa](../README.md) o abre un [issue en GitHub](https://github.com/your-org/icosistem/issues).