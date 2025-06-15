# 📦 Guía de Instalación - Ecosistema de Emprendimiento

> Guía completa para la instalación y configuración del ecosistema de emprendimiento en diferentes entornos

## 📋 Tabla de Contenidos

- [🎯 Resumen de Instalación](#-resumen-de-instalación)
- [📋 Requisitos del Sistema](#-requisitos-del-sistema)
- [🔧 Métodos de Instalación](#-métodos-de-instalación)
- [🚀 Instalación para Desarrollo](#-instalación-para-desarrollo)
- [🏭 Instalación para Producción](#-instalación-para-producción)
- [🐳 Instalación con Docker](#-instalación-con-docker)
- [☁️ Instalación en la Nube](#️-instalación-en-la-nube)
- [⚙️ Configuración Avanzada](#️-configuración-avanzada)
- [🔍 Verificación de Instalación](#-verificación-de-instalación)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [📊 Monitoreo Post-Instalación](#-monitoreo-post-instalación)

## 🎯 Resumen de Instalación

El ecosistema de emprendimiento puede instalarse en múltiples configuraciones:

| Método | Tiempo | Dificultad | Uso Recomendado |
|--------|--------|------------|-----------------|
| **Docker Compose** | 15 min | 🟢 Fácil | Desarrollo rápido |
| **Instalación Local** | 30 min | 🟡 Medio | Desarrollo personalizado |
| **Producción Manual** | 60 min | 🔴 Avanzado | Servidores dedicados |
| **Cloud Deploy** | 45 min | 🟡 Medio | Escalabilidad |

## 📋 Requisitos del Sistema

### Requisitos Mínimos

| Componente | Desarrollo | Producción |
|------------|------------|------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Almacenamiento** | 10 GB | 50+ GB SSD |
| **Red** | 1 Mbps | 10+ Mbps |

### Software Base Requerido

#### 🐍 Python
```bash
# Verificar versión Python (>=3.9)
python --version
# Debe mostrar: Python 3.9.x o superior

# Si no tienes Python 3.9+, instalar:

# Ubuntu/Debian
sudo apt update
sudo apt install python3.9 python3.9-venv python3.9-dev python3-pip

# CentOS/RHEL/Fedora
sudo dnf install python39 python39-devel python39-pip

# macOS (con Homebrew)
brew install python@3.9

# Windows
# Descargar desde: https://www.python.org/downloads/
```

#### 🗄️ PostgreSQL
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib libpq-dev

# CentOS/RHEL/Fedora
sudo dnf install postgresql-server postgresql-contrib postgresql-devel

# macOS
brew install postgresql

# Windows
# Descargar desde: https://www.postgresql.org/download/windows/

# Inicializar y configurar
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Crear usuario y base de datos
sudo -u postgres psql
CREATE USER ecosistema_user WITH PASSWORD 'tu_password_seguro';
CREATE DATABASE ecosistema_db OWNER ecosistema_user;
GRANT ALL PRIVILEGES ON DATABASE ecosistema_db TO ecosistema_user;
\q
```

#### 🔴 Redis
```bash
# Ubuntu/Debian
sudo apt install redis-server

# CentOS/RHEL/Fedora
sudo dnf install redis

# macOS
brew install redis

# Windows
# Usar WSL o descargar desde: https://github.com/microsoftarchive/redis/releases

# Inicializar Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verificar funcionamiento
redis-cli ping
# Debe responder: PONG
```

#### 📦 Node.js (para assets frontend)
```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# CentOS/RHEL/Fedora
sudo dnf install npm nodejs

# macOS
brew install node

# Windows
# Descargar desde: https://nodejs.org/

# Verificar instalación
node --version
npm --version
```

#### 🔧 Herramientas Adicionales
```bash
# Git (control de versiones)
# Ubuntu/Debian
sudo apt install git

# CentOS/RHEL/Fedora
sudo dnf install git

# macOS
brew install git

# Build tools para compilación
# Ubuntu/Debian
sudo apt install build-essential

# CentOS/RHEL/Fedora
sudo dnf groupinstall "Development Tools"

# macOS
xcode-select --install
```

## 🔧 Métodos de Instalación

### Método 1: Docker Compose (Recomendado para Desarrollo)
- ✅ Setup automático de todos los servicios
- ✅ Aislamiento completo del entorno
- ✅ Configuración reproducible
- ❌ Recursos adicionales requeridos

### Método 2: Instalación Local
- ✅ Control total sobre dependencias
- ✅ Mejor rendimiento para desarrollo
- ✅ Fácil debugging
- ❌ Configuración manual extensa

### Método 3: Producción Manual
- ✅ Máximo control de seguridad
- ✅ Optimización específica del hardware
- ✅ Configuración personalizada
- ❌ Complejidad alta de setup

## 🚀 Instalación para Desarrollo

### Paso 1: Clonar el Repositorio

```bash
# Clonar repositorio
git clone https://github.com/tu-org/ecosistema-emprendimiento.git
cd ecosistema-emprendimiento

# Verificar estructura
ls -la
```

### Paso 2: Crear y Configurar Entorno Virtual

```bash
# Crear entorno virtual
python3.9 -m venv venv

# Activar entorno virtual
# Linux/macOS:
source venv/bin/activate

# Windows (Command Prompt):
venv\Scripts\activate.bat

# Windows (PowerShell):
venv\Scripts\Activate.ps1

# Verificar activación (debe mostrar (venv) al inicio)
which python
# Debe mostrar: /ruta/al/proyecto/venv/bin/python
```

### Paso 3: Instalar Dependencias Python

```bash
# Actualizar pip
pip install --upgrade pip setuptools wheel

# Instalar dependencias base
pip install -r requirements.txt

# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Instalar dependencias de testing
pip install -r requirements-test.txt

# Verificar instalación
pip list | grep -E "(Flask|SQLAlchemy|Celery)"
```

### Paso 4: Configurar Variables de Entorno

```bash
# Copiar archivo de configuración
cp .env.example .env

# Editar configuración
nano .env  # o vim .env, o tu editor preferido
```

#### Configuración Básica para Desarrollo (.env)

```env
# ==============================================
# CONFIGURACIÓN DESARROLLO - ECOSISTEMA EMPRENDIMIENTO
# ==============================================

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production

# Database Configuration
DATABASE_URL=postgresql://ecosistema_user:tu_password_seguro@localhost:5432/ecosistema_db
SQLALCHEMY_ECHO=False
SQLALCHEMY_TRACK_MODIFICATIONS=False

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Security Configuration
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=3600
JWT_SECRET_KEY=jwt-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRES=3600

# Email Configuration (Desarrollo con MailHog o similar)
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=False
MAIL_USE_SSL=False
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@ecosistema-dev.local

# Google OAuth (Opcional para desarrollo)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# File Upload Configuration
UPLOAD_FOLDER=app/static/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
ALLOWED_EXTENSIONS=txt,pdf,png,jpg,jpeg,gif,doc,docx,xls,xlsx

# Logging Configuration
LOG_LEVEL=DEBUG
LOG_FILE=logs/app.log

# Development Features
TESTING=False
DEBUG_TB_ENABLED=True
ASSETS_DEBUG=True

# Pagination
POSTS_PER_PAGE=20
USERS_PER_PAGE=50

# Cache Configuration
CACHE_TYPE=redis
CACHE_DEFAULT_TIMEOUT=300

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://localhost:6379/1

# Analytics
GOOGLE_ANALYTICS_ID=
HOTJAR_ID=

# Feature Flags
FEATURE_MESSAGING=True
FEATURE_CALENDAR_INTEGRATION=True
FEATURE_NOTIFICATIONS=True
FEATURE_ANALYTICS=True
```

### Paso 5: Configurar Base de Datos

```bash
# Verificar conexión a PostgreSQL
psql -h localhost -U ecosistema_user -d ecosistema_db -c "SELECT version();"

# Inicializar migraciones (solo primera vez)
flask db init

# Crear migración inicial
flask db migrate -m "Initial migration"

# Aplicar migraciones
flask db upgrade

# Verificar tablas creadas
psql -h localhost -U ecosistema_user -d ecosistema_db -c "\dt"
```

### Paso 6: Instalar y Configurar Assets Frontend

```bash
# Instalar dependencias Node.js
npm install

# Verificar package.json
cat package.json

# Compilar assets para desarrollo
npm run dev

# O en modo watch para desarrollo continuo
npm run watch

# Verificar assets compilados
ls -la app/static/dist/
```

#### package.json (Ejemplo de configuración)

```json
{
  "name": "ecosistema-emprendimiento-frontend",
  "version": "1.0.0",
  "description": "Frontend assets for Ecosistema de Emprendimiento",
  "scripts": {
    "dev": "webpack --mode development",
    "build": "webpack --mode production",
    "watch": "webpack --mode development --watch",
    "clean": "rm -rf app/static/dist/*"
  },
  "dependencies": {
    "bootstrap": "^5.3.0",
    "chart.js": "^4.2.1",
    "socket.io-client": "^4.6.1",
    "htmx.org": "^1.9.0"
  },
  "devDependencies": {
    "webpack": "^5.82.0",
    "webpack-cli": "^5.1.1",
    "css-loader": "^6.7.3",
    "sass-loader": "^13.2.2",
    "sass": "^1.62.1",
    "mini-css-extract-plugin": "^2.7.5",
    "babel-loader": "^9.1.2",
    "@babel/core": "^7.21.8",
    "@babel/preset-env": "^7.21.5"
  }
}
```

### Paso 7: Crear Usuario Administrador Inicial

```bash
# Crear primer usuario administrador
flask create-admin \
  --email admin@ecosistema.local \
  --password admin123 \
  --first-name "Admin" \
  --last-name "Sistema"

# Verificar creación
flask list-users --role admin
```

### Paso 8: Cargar Datos de Prueba (Opcional)

```bash
# Ejecutar script de datos semilla
python scripts/seed_data.py

# O usar comando Flask personalizado
flask seed-database --environment development

# Verificar datos cargados
flask stats
```

### Paso 9: Configurar Servicios de Desarrollo

#### A. Configurar MailHog (Captura de emails para desarrollo)

```bash
# Instalar MailHog
# macOS
brew install mailhog

# Linux (descargar binario)
wget https://github.com/mailhog/MailHog/releases/download/v1.0.1/MailHog_linux_amd64
chmod +x MailHog_linux_amd64
sudo mv MailHog_linux_amd64 /usr/local/bin/mailhog

# Ejecutar MailHog
mailhog &

# Interfaz web: http://localhost:8025
```

#### B. Configurar Celery para Tareas Asíncronas

```bash
# Terminal 1: Worker de Celery
celery -A app.tasks.celery_app worker --loglevel=info

# Terminal 2: Beat scheduler (tareas periódicas)
celery -A app.tasks.celery_app beat --loglevel=info

# Terminal 3: Monitor Flower (opcional)
celery -A app.tasks.celery_app flower --port=5555

# Interfaz Flower: http://localhost:5555
```

### Paso 10: Iniciar Aplicación de Desarrollo

```bash
# Método 1: Flask development server
flask run --host=0.0.0.0 --port=5000 --debug

# Método 2: Con auto-reload
FLASK_ENV=development python run.py

# Método 3: Con Gunicorn para simular producción
gunicorn --bind 127.0.0.1:5000 --workers 1 --reload wsgi:app
```

### Verificación de Instalación de Desarrollo

```bash
# 1. Verificar aplicación web
curl http://localhost:5000/health
# Debe retornar: {"status": "healthy", "timestamp": "..."}

# 2. Verificar API
curl http://localhost:5000/api/v1/health
# Debe retornar JSON con status OK

# 3. Verificar base de datos
flask db-status

# 4. Verificar Redis
redis-cli ping

# 5. Verificar Celery
celery -A app.tasks.celery_app inspect active

# 6. Ejecutar tests básicos
pytest tests/unit/test_basic.py -v
```

## 🏭 Instalación para Producción

### Preparación del Servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar fail2ban para seguridad
sudo apt install fail2ban

# Configurar firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Crear usuario para la aplicación
sudo adduser ecosistema
sudo usermod -aG sudo ecosistema
```

### Configuración de PostgreSQL para Producción

```bash
# Editar configuración PostgreSQL
sudo nano /etc/postgresql/13/main/postgresql.conf

# Configuraciones recomendadas:
# max_connections = 100
# shared_buffers = 256MB
# effective_cache_size = 1GB
# work_mem = 4MB
# maintenance_work_mem = 64MB

# Configurar autenticación
sudo nano /etc/postgresql/13/main/pg_hba.conf

# Reiniciar PostgreSQL
sudo systemctl restart postgresql

# Crear base de datos de producción
sudo -u postgres psql
CREATE DATABASE ecosistema_prod;
CREATE USER ecosistema_prod_user WITH PASSWORD 'password_super_seguro';
GRANT ALL PRIVILEGES ON DATABASE ecosistema_prod TO ecosistema_prod_user;
```

### Instalación de la Aplicación

```bash
# Cambiar a usuario de aplicación
su - ecosistema

# Clonar repositorio
git clone https://github.com/tu-org/ecosistema-emprendimiento.git
cd ecosistema-emprendimiento

# Checkout a tag de producción
git checkout v1.0.0

# Crear entorno virtual
python3.9 -m venv venv
source venv/bin/activate

# Instalar dependencias de producción únicamente
pip install -r requirements.txt
```

### Configuración de Producción

```bash
# Crear configuración de producción
cp .env.example .env.production
```

#### Variables de Entorno para Producción

```env
# ==============================================
# CONFIGURACIÓN PRODUCCIÓN - ECOSISTEMA EMPRENDIMIENTO
# ==============================================

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=clave-super-secreta-aleatoria-64-caracteres-minimo

# Database Configuration
DATABASE_URL=postgresql://ecosistema_prod_user:password_super_seguro@localhost:5432/ecosistema_prod
SQLALCHEMY_ECHO=False
SQLALCHEMY_TRACK_MODIFICATIONS=False
SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": true, "pool_recycle": 300}

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Security Configuration
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=3600
JWT_SECRET_KEY=jwt-clave-super-secreta-aleatoria-64-caracteres-minimo
JWT_ACCESS_TOKEN_EXPIRES=1800

# Email Configuration (SendGrid/Mailgun)
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=apikey
MAIL_PASSWORD=tu-api-key-sendgrid
MAIL_DEFAULT_SENDER=noreply@tudominio.com

# Google OAuth
GOOGLE_CLIENT_ID=tu-google-client-id-produccion
GOOGLE_CLIENT_SECRET=tu-google-client-secret-produccion

# File Upload Configuration
UPLOAD_FOLDER=/var/www/ecosistema/uploads
MAX_CONTENT_LENGTH=52428800  # 50MB
ALLOWED_EXTENSIONS=txt,pdf,png,jpg,jpeg,gif,doc,docx,xls,xlsx

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/ecosistema/app.log

# Production Features
TESTING=False
DEBUG_TB_ENABLED=False
ASSETS_DEBUG=False

# Cache Configuration
CACHE_TYPE=redis
CACHE_DEFAULT_TIMEOUT=3600

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://localhost:6379/1
RATELIMIT_DEFAULT=1000 per hour

# SSL Configuration
PREFERRED_URL_SCHEME=https
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# Analytics
GOOGLE_ANALYTICS_ID=GA-XXXXXXX-X
HOTJAR_ID=tu-hotjar-id

# Monitoring
SENTRY_DSN=https://tu-sentry-dsn@sentry.io/proyecto

# Backup Configuration
BACKUP_S3_BUCKET=ecosistema-backups
AWS_ACCESS_KEY_ID=tu-aws-access-key
AWS_SECRET_ACCESS_KEY=tu-aws-secret-key
```

### Configurar Servicios del Sistema

#### Crear servicio systemd para la aplicación

```bash
sudo nano /etc/systemd/system/ecosistema.service
```

```ini
[Unit]
Description=Ecosistema de Emprendimiento
After=network.target postgresql.service redis.service

[Service]
User=ecosistema
Group=ecosistema
WorkingDirectory=/home/ecosistema/ecosistema-emprendimiento
Environment=PATH=/home/ecosistema/ecosistema-emprendimiento/venv/bin
ExecStart=/home/ecosistema/ecosistema-emprendimiento/venv/bin/gunicorn \
    --workers 4 \
    --worker-class gevent \
    --worker-connections 1000 \
    --bind unix:/tmp/ecosistema.sock \
    --timeout 120 \
    --keepalive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --log-level info \
    --log-file /var/log/ecosistema/gunicorn.log \
    --access-logfile /var/log/ecosistema/access.log \
    wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Crear servicio para Celery Worker

```bash
sudo nano /etc/systemd/system/ecosistema-worker.service
```

```ini
[Unit]
Description=Ecosistema Celery Worker
After=network.target redis.service

[Service]
User=ecosistema
Group=ecosistema
WorkingDirectory=/home/ecosistema/ecosistema-emprendimiento
Environment=PATH=/home/ecosistema/ecosistema-emprendimiento/venv/bin
ExecStart=/home/ecosistema/ecosistema-emprendimiento/venv/bin/celery \
    -A app.tasks.celery_app worker \
    --loglevel=info \
    --logfile=/var/log/ecosistema/celery-worker.log \
    --pidfile=/var/run/celery/worker.pid \
    --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Crear servicio para Celery Beat

```bash
sudo nano /etc/systemd/system/ecosistema-beat.service
```

```ini
[Unit]
Description=Ecosistema Celery Beat
After=network.target redis.service

[Service]
User=ecosistema
Group=ecosistema
WorkingDirectory=/home/ecosistema/ecosistema-emprendimiento
Environment=PATH=/home/ecosistema/ecosistema-emprendimiento/venv/bin
ExecStart=/home/ecosistema/ecosistema-emprendimiento/venv/bin/celery \
    -A app.tasks.celery_app beat \
    --loglevel=info \
    --logfile=/var/log/ecosistema/celery-beat.log \
    --pidfile=/var/run/celery/beat.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Configurar Nginx

```bash
# Instalar Nginx
sudo apt install nginx

# Crear configuración del sitio
sudo nano /etc/nginx/sites-available/ecosistema
```

```nginx
# Configuración Nginx para Ecosistema de Emprendimiento
upstream ecosistema_app {
    server unix:/tmp/ecosistema.sock;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name tudominio.com www.tudominio.com;
    
    # Cert validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name tudominio.com www.tudominio.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tudominio.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    
    # Modern configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.google-analytics.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net;" always;

    # Logging
    access_log /var/log/nginx/ecosistema_access.log;
    error_log /var/log/nginx/ecosistema_error.log;

    # Client upload size
    client_max_body_size 50M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/json;

    # Static files
    location /static {
        alias /home/ecosistema/ecosistema-emprendimiento/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Specific caching for different file types
        location ~* \.(css|js)$ {
            expires 30d;
        }
        
        location ~* \.(jpg|jpeg|png|gif|ico|svg|webp)$ {
            expires 1y;
        }
    }

    # Uploads
    location /uploads {
        alias /var/www/ecosistema/uploads;
        expires 30d;
        add_header Cache-Control "public";
    }

    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://ecosistema_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Login endpoint with strict rate limiting
    location /auth/login {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://ecosistema_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Socket.IO
    location /socket.io/ {
        proxy_pass http://ecosistema_app;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Main application
    location / {
        proxy_pass http://ecosistema_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        access_log off;
        proxy_pass http://ecosistema_app;
        proxy_set_header Host $host;
    }
}
```

### Configurar SSL con Let's Encrypt

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obtener certificado SSL
sudo certbot --nginx -d tudominio.com -d www.tudominio.com

# Verificar renovación automática
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

### Preparar Directorios y Permisos

```bash
# Crear directorios necesarios
sudo mkdir -p /var/log/ecosistema
sudo mkdir -p /var/www/ecosistema/uploads
sudo mkdir -p /var/run/celery

# Configurar permisos
sudo chown -R ecosistema:ecosistema /var/log/ecosistema
sudo chown -R ecosistema:ecosistema /var/www/ecosistema
sudo chown -R ecosistema:ecosistema /var/run/celery

# Configurar logrotate
sudo nano /etc/logrotate.d/ecosistema
```

```bash
/var/log/ecosistema/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 ecosistema ecosistema
    postrotate
        systemctl reload ecosistema
    endscript
}
```

### Inicializar Base de Datos y Servicios

```bash
# Cambiar a usuario ecosistema
su - ecosistema
cd ecosistema-emprendimiento
source venv/bin/activate

# Aplicar migraciones
flask db upgrade

# Compilar assets para producción
npm run build

# Crear usuario administrador
flask create-admin \
  --email admin@tudominio.com \
  --password password_seguro_admin

# Habilitar y iniciar servicios
sudo systemctl enable ecosistema ecosistema-worker ecosistema-beat nginx
sudo systemctl start ecosistema ecosistema-worker ecosistema-beat

# Verificar status
sudo systemctl status ecosistema
sudo systemctl status ecosistema-worker
sudo systemctl status ecosistema-beat
sudo systemctl status nginx
```

## 🐳 Instalación con Docker

### Prerequisitos Docker

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.17.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER
newgrp docker

# Verificar instalación
docker --version
docker-compose --version
```

### Configuración Docker para Desarrollo

```bash
# Clonar repositorio
git clone https://github.com/tu-org/ecosistema-emprendimiento.git
cd ecosistema-emprendimiento

# Copiar configuración de entorno
cp .env.example .env.docker

# Editar configuración Docker
nano .env.docker
```

#### docker-compose.yml para Desarrollo

```yaml
version: '3.8'

services:
  # Base de datos PostgreSQL
  db:
    image: postgres:15-alpine
    container_name: ecosistema_db
    environment:
      POSTGRES_DB: ecosistema_dev
      POSTGRES_USER: ecosistema_user
      POSTGRES_PASSWORD: ecosistema_pass
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ecosistema_user -d ecosistema_dev"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis para cache y Celery
  redis:
    image: redis:7-alpine
    container_name: ecosistema_redis
    command: redis-server --appendonly yes --requirepass ecosistema_redis_pass
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  # Aplicación Flask
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
      target: development
    container_name: ecosistema_web
    env_file:
      - .env.docker
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=postgresql://ecosistema_user:ecosistema_pass@db:5432/ecosistema_dev
      - REDIS_URL=redis://:ecosistema_redis_pass@redis:6379/0
    volumes:
      - .:/app
      - /app/node_modules
      - uploads_data:/app/uploads
    ports:
      - "5000:5000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      sh -c "
        flask db upgrade &&
        npm run dev &&
        flask run --host=0.0.0.0 --port=5000
      "
    restart: unless-stopped

  # Celery Worker
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
      target: development
    container_name: ecosistema_worker
    env_file:
      - .env.docker
    environment:
      - DATABASE_URL=postgresql://ecosistema_user:ecosistema_pass@db:5432/ecosistema_dev
      - REDIS_URL=redis://:ecosistema_redis_pass@redis:6379/0
    volumes:
      - .:/app
      - uploads_data:/app/uploads
    depends_on:
      - db
      - redis
    command: celery -A app.tasks.celery_app worker --loglevel=info
    restart: unless-stopped

  # Celery Beat
  beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
      target: development
    container_name: ecosistema_beat
    env_file:
      - .env.docker
    environment:
      - DATABASE_URL=postgresql://ecosistema_user:ecosistema_pass@db:5432/ecosistema_dev
      - REDIS_URL=redis://:ecosistema_redis_pass@redis:6379/0
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    command: celery -A app.tasks.celery_app beat --loglevel=info
    restart: unless-stopped

  # Monitor Celery (Flower)
  flower:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
      target: development
    container_name: ecosistema_flower
    env_file:
      - .env.docker
    environment:
      - CELERY_BROKER_URL=redis://:ecosistema_redis_pass@redis:6379/0
    ports:
      - "5555:5555"
    depends_on:
      - redis
    command: celery -A app.tasks.celery_app flower --port=5555
    restart: unless-stopped

  # MailHog para testing emails
  mailhog:
    image: mailhog/mailhog:latest
    container_name: ecosistema_mailhog
    ports:
      - "1025:1025"  # SMTP
      - "8025:8025"  # Web UI
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  uploads_data:

networks:
  default:
    name: ecosistema_network
```

#### Dockerfile.dev

```dockerfile
# ==============================================
# DOCKERFILE DESARROLLO - ECOSISTEMA EMPRENDIMIENTO
# ==============================================

# Stage 1: Base
FROM python:3.9-slim as base

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    postgresql-client \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Configurar directorio de trabajo
WORKDIR /app

# Stage 2: Dependencies
FROM base as dependencies

# Copiar archivos de dependencias
COPY requirements*.txt ./
COPY package*.json ./

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Instalar dependencias Node.js
RUN npm install

# Stage 3: Development
FROM dependencies as development

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Copiar código fuente
COPY --chown=app:app . .

# Exponer puerto
EXPOSE 5000

# Comando por defecto
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
```

### Ejecutar con Docker Compose

```bash
# Construir e iniciar servicios
docker-compose up --build

# Ejecutar en segundo plano
docker-compose up -d

# Ver logs
docker-compose logs -f web

# Crear usuario administrador
docker-compose exec web flask create-admin \
  --email admin@ecosistema.local \
  --password admin123

# Cargar datos de prueba
docker-compose exec web python scripts/seed_data.py

# Parar servicios
docker-compose down

# Limpiar volúmenes (CUIDADO: borra datos)
docker-compose down -v
```

### Docker para Producción

#### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  # Nginx como proxy reverso
  nginx:
    image: nginx:alpine
    container_name: ecosistema_nginx
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./app/static:/app/static:ro
      - ./uploads:/uploads:ro
      - ./ssl:/etc/nginx/ssl:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - web
    restart: unless-stopped

  # Aplicación Flask (producción)
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
      target: production
    container_name: ecosistema_web_prod
    env_file:
      - .env.production
    volumes:
      - uploads_data:/app/uploads
    expose:
      - "8000"
    depends_on:
      - db
      - redis
    command: >
      sh -c "
        flask db upgrade &&
        gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class gevent wsgi:app
      "
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Base de datos PostgreSQL (producción)
  db:
    image: postgres:15-alpine
    container_name: ecosistema_db_prod
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
      - ./backups:/backups
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis (producción)
  redis:
    image: redis:7-alpine
    container_name: ecosistema_redis_prod
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_prod_data:/data
    restart: unless-stopped

  # Celery Worker (producción)
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
      target: production
    container_name: ecosistema_worker_prod
    env_file:
      - .env.production
    volumes:
      - uploads_data:/app/uploads
    depends_on:
      - db
      - redis
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
    restart: unless-stopped

  # Celery Beat (producción)
  beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
      target: production
    container_name: ecosistema_beat_prod
    env_file:
      - .env.production
    depends_on:
      - db
      - redis
    command: celery -A app.tasks.celery_app beat --loglevel=info
    restart: unless-stopped

volumes:
  postgres_prod_data:
  redis_prod_data:
  uploads_data:

networks:
  default:
    name: ecosistema_prod_network
```

## ☁️ Instalación en la Nube

### AWS EC2

#### 1. Crear instancia EC2

```bash
# Configuración recomendada:
# - Tipo: t3.medium o superior
# - AMI: Ubuntu 20.04 LTS
# - Storage: 20GB SSD mínimo
# - Security Group: HTTP(80), HTTPS(443), SSH(22)
```

#### 2. Configurar instancia

```bash
# Conectar a instancia
ssh -i tu-key.pem ubuntu@tu-ip-publica

# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Reiniciar sesión para aplicar cambios
exit
ssh -i tu-key.pem ubuntu@tu-ip-publica
```

#### 3. Desplegar aplicación

```bash
# Clonar repositorio
git clone https://github.com/tu-org/ecosistema-emprendimiento.git
cd ecosistema-emprendimiento

# Configurar variables de entorno
cp .env.example .env.production
# Editar .env.production con configuración de producción

# Desplegar con Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Configurar SSL con Let's Encrypt
sudo apt install certbot
sudo certbot --standalone -d tu-dominio.com
```

### Google Cloud Platform

#### 1. Configurar Google Cloud

```bash
# Instalar gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Crear proyecto
gcloud projects create ecosistema-emprendimiento-prod

# Habilitar APIs necesarias
gcloud services enable compute.googleapis.com
gcloud services enable sql.googleapis.com
gcloud services enable redis.googleapis.com
```

#### 2. Crear infraestructura

```bash
# Crear instancia de VM
gcloud compute instances create ecosistema-app \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --machine-type=e2-standard-2 \
    --boot-disk-size=20GB \
    --tags=http-server,https-server

# Crear base de datos Cloud SQL
gcloud sql instances create ecosistema-db \
    --database-version=POSTGRES_13 \
    --tier=db-f1-micro \
    --region=us-central1

# Crear instancia Redis
gcloud redis instances create ecosistema-cache \
    --size=1 \
    --region=us-central1
```

### Digital Ocean

#### 1. Crear Droplet

```bash
# Usar Digital Ocean CLI
doctl compute droplet create ecosistema-app \
    --image ubuntu-20-04-x64 \
    --size s-2vcpu-4gb \
    --region nyc1 \
    --ssh-keys tu-ssh-key-id

# Crear base de datos managed
doctl databases create ecosistema-db \
    --engine postgres \
    --version 13 \
    --size db-s-1vcpu-1gb \
    --region nyc1
```

## ⚙️ Configuración Avanzada

### Configuración de Base de Datos

#### Optimización PostgreSQL

```sql
-- Configuraciones recomendadas para producción
-- En postgresql.conf

-- Memoria
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

-- Checkpoints
checkpoint_completion_target = 0.9
wal_buffers = 16MB
checkpoint_segments = 32

-- Logging
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

-- Autovacuum
autovacuum = on
log_autovacuum_min_duration = 0
autovacuum_max_workers = 3
autovacuum_naptime = 1min
```

#### Índices para Performance

```sql
-- Índices recomendados para mejorar performance
CREATE INDEX CONCURRENTLY idx_users_email_active ON users(email) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_projects_entrepreneur_status ON projects(entrepreneur_id, status);
CREATE INDEX CONCURRENTLY idx_meetings_date_status ON meetings(date, status);
CREATE INDEX CONCURRENTLY idx_messages_conversation_created ON messages(conversation_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_notifications_user_read ON notifications(user_id, is_read, created_at DESC);

-- Índices parciales para queries frecuentes
CREATE INDEX CONCURRENTLY idx_active_entrepreneurs ON users(id) WHERE role = 'entrepreneur' AND is_active = true;
CREATE INDEX CONCURRENTLY idx_pending_meetings ON meetings(id) WHERE status = 'pending';
```

### Configuración de Cache

#### Redis Configuration

```redis
# redis.conf para producción

# Memoria
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistencia
save 900 1
save 300 10
save 60 10000

# Red
timeout 0
tcp-keepalive 300

# Seguridad
requirepass tu_password_redis_seguro
```

#### Cache Strategy en Flask

```python
# app/utils/cache_utils.py
from flask import current_app
from functools import wraps
import redis
import json
import hashlib

def cache_key(*args, **kwargs):
    """Generar clave de cache única"""
    key_data = f"{args}_{kwargs}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(timeout=300, key_prefix=""):
    """Decorador para cachear resultados de funciones"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache = current_app.extensions.get('redis')
            if not cache:
                return f(*args, **kwargs)
            
            key = f"{key_prefix}:{cache_key(*args, **kwargs)}"
            
            # Intentar obtener del cache
            cached_result = cache.get(key)
            if cached_result:
                return json.loads(cached_result)
            
            # Calcular resultado y guardarlo en cache
            result = f(*args, **kwargs)
            cache.setex(key, timeout, json.dumps(result, default=str))
            
            return result
        return decorated_function
    return decorator
```

### Configuración de Logs

#### Configuración avanzada de logging

```python
# config/logging.py
import logging
import logging.handlers
import os
from pythonjsonlogger import jsonlogger

def setup_logging(app):
    """Configurar logging para la aplicación"""
    
    # Crear directorio de logs si no existe
    log_dir = app.config.get('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configurar formato JSON para logs estructurados
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    # Handler para archivo principal
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Handler para errores
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=10485760,
        backupCount=10
    )
    error_handler.setFormatter(json_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Handler para console en desarrollo
    if app.config.get('FLASK_ENV') == 'development':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(name)s %(levelname)s: %(message)s'
        ))
        console_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(console_handler)
    
    # Agregar handlers
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.INFO)
    
    # Configurar loggers específicos
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
```

### Configuración de Monitoreo

#### Prometheus metrics

```python
# app/utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from flask import request, g
import time

# Métricas definidas
REQUEST_COUNT = Counter(
    'flask_requests_total',
    'Total Flask requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'flask_request_duration_seconds',
    'Flask request duration',
    ['method', 'endpoint']
)

ACTIVE_USERS = Gauge(
    'ecosistema_active_users',
    'Currently active users'
)

def init_metrics(app):
    """Inicializar métricas de Prometheus"""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown',
            status=response.status_code
        ).inc()
        
        if hasattr(g, 'start_time'):
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.endpoint or 'unknown'
            ).observe(time.time() - g.start_time)
        
        return response
    
    @app.route('/metrics')
    def metrics():
        return generate_latest(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
```

## 🔍 Verificación de Instalación

### Health Check Completo

```bash
#!/bin/bash
# scripts/health_check.py

echo "🔍 Verificando instalación del Ecosistema de Emprendimiento..."

# Verificar aplicación web
echo "📱 Verificando aplicación web..."
curl -f http://localhost:5000/health || echo "❌ Aplicación web no responde"

# Verificar API
echo "🔌 Verificando API..."
curl -f http://localhost:5000/api/v1/health || echo "❌ API no responde"

# Verificar base de datos
echo "🗄️ Verificando base de datos..."
flask db-status || echo "❌ Base de datos no conecta"

# Verificar Redis
echo "🔴 Verificando Redis..."
redis-cli ping || echo "❌ Redis no responde"

# Verificar Celery
echo "⚡ Verificando Celery..."
celery -A app.tasks.celery_app inspect active || echo "❌ Celery no responde"

# Verificar archivos estáticos
echo "📁 Verificando assets compilados..."
ls -la app/static/dist/ || echo "❌ Assets no compilados"

# Verificar permisos
echo "🔐 Verificando permisos..."
ls -la uploads/ || echo "❌ Directorio uploads no accesible"

echo "✅ Verificación completa"
```

### Tests de Integración

```python
# tests/integration/test_installation.py
import pytest
import requests
from app import create_app, db
from app.models import User

class TestInstallation:
    """Tests para verificar instalación correcta"""
    
    def test_app_starts(self):
        """Verificar que la aplicación inicia correctamente"""
        app = create_app('testing')
        assert app is not None
        assert app.config['TESTING'] is True
    
    def test_database_connection(self):
        """Verificar conexión a base de datos"""
        app = create_app('testing')
        with app.app_context():
            assert db.engine.execute('SELECT 1').scalar() == 1
    
    def test_api_endpoints(self):
        """Verificar endpoints principales de API"""
        app = create_app('testing')
        client = app.test_client()
        
        # Health check
        response = client.get('/health')
        assert response.status_code == 200
        
        # API health
        response = client.get('/api/v1/health')
        assert response.status_code == 200
    
    def test_user_creation(self):
        """Verificar creación de usuarios"""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            user = User(
                email='test@example.com',
                first_name='Test',
                last_name='User',
                role='entrepreneur'
            )
            user.set_password('password123')
            
            db.session.add(user)
            db.session.commit()
            
            assert user.id is not None
            assert user.check_password('password123')
```

## 🛠️ Troubleshooting

### Problemas Comunes y Soluciones

#### 1. Error de Conexión a Base de Datos

```bash
# Problema: FATAL: password authentication failed
# Solución: Verificar credenciales y configuración pg_hba.conf

# Verificar conexión manual
psql -h localhost -U ecosistema_user -d ecosistema_db

# Verificar configuración en .env
echo $DATABASE_URL

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

#### 2. Redis No Conecta

```bash
# Problema: ConnectionError: Error connecting to Redis
# Solución: Verificar que Redis esté ejecutándose

# Verificar status Redis
sudo systemctl status redis

# Iniciar Redis si no está ejecutándose
sudo systemctl start redis

# Verificar conexión
redis-cli ping
```

#### 3. Celery Workers No Inician

```bash
# Problema: Workers no procesan tareas
# Solución: Verificar configuración y logs

# Verificar workers activos
celery -A app.tasks.celery_app inspect active

# Ver logs detallados
celery -A app.tasks.celery_app worker --loglevel=debug

# Limpiar tareas pendientes
celery -A app.tasks.celery_app purge
```

#### 4. Assets No Compilan

```bash
# Problema: npm run build falla
# Solución: Verificar dependencias Node.js

# Limpiar cache npm
npm cache clean --force

# Reinstalar dependencias
rm -rf node_modules package-lock.json
npm install

# Compilar en modo verbose
npm run build --verbose
```

#### 5. Permisos de Archivos

```bash
# Problema: Permission denied en uploads
# Solución: Configurar permisos correctos

# Verificar propietario
ls -la uploads/

# Cambiar propietario si es necesario
sudo chown -R ecosistema:ecosistema uploads/
sudo chmod -R 755 uploads/
```

#### 6. SSL/HTTPS Issues

```bash
# Problema: Certificado SSL no válido
# Solución: Renovar certificado Let's Encrypt

# Verificar estado certificado
sudo certbot certificates

# Renovar certificado
sudo certbot renew

# Verificar configuración Nginx
sudo nginx -t
sudo systemctl reload nginx
```

### Logs de Debugging

#### Ubicaciones importantes de logs

```bash
# Logs de aplicación
tail -f /var/log/ecosistema/app.log

# Logs de Nginx
tail -f /var/log/nginx/ecosistema_error.log
tail -f /var/log/nginx/ecosistema_access.log

# Logs del sistema
journalctl -u ecosistema -f
journalctl -u ecosistema-worker -f

# Logs de PostgreSQL
tail -f /var/log/postgresql/postgresql-13-main.log

# Logs de Redis
tail -f /var/log/redis/redis-server.log
```

#### Herramientas de debugging

```bash
# Verificar procesos activos
ps aux | grep -E "(python|nginx|postgres|redis)"

# Verificar puertos abiertos
netstat -tlnp | grep -E "(5000|80|443|5432|6379)"

# Verificar uso de memoria
free -h
df -h

# Verificar carga del sistema
htop
iotop
```

## 📊 Monitoreo Post-Instalación

### Configurar Prometheus y Grafana

```bash
# Instalar Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-2.40.0.linux-amd64.tar.gz
sudo mv prometheus-2.40.0.linux-amd64 /opt/prometheus

# Configurar como servicio
sudo nano /etc/systemd/system/prometheus.service
```

```ini
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/opt/prometheus/prometheus \
    --config.file /opt/prometheus/prometheus.yml \
    --storage.tsdb.path /opt/prometheus/data \
    --web.console.templates=/opt/prometheus/consoles \
    --web.console.libraries=/opt/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090 \
    --web.enable-lifecycle

[Install]
WantedBy=multi-user.target
```

### Dashboard de Monitoreo

```python
# app/admin/monitoring.py
from flask import Blueprint, render_template, jsonify
from app.models import User, Project, Meeting
from app.utils.metrics import get_system_metrics
import psutil
import redis

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/admin/monitoring')

@monitoring_bp.route('/dashboard')
def dashboard():
    """Dashboard de monitoreo del sistema"""
    return render_template('admin/monitoring/dashboard.html')

@monitoring_bp.route('/api/metrics')
def api_metrics():
    """API de métricas del sistema"""
    return jsonify({
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(is_active=True).count(),
            'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
            'allies': User.query.filter_by(role='ally').count()
        },
        'projects': {
            'total': Project.query.count(),
            'active': Project.query.filter_by(status='active').count(),
            'completed': Project.query.filter_by(status='completed').count()
        },
        'meetings': {
            'today': Meeting.query.filter(
                Meeting.date >= datetime.utcnow().date()
            ).count()
        },
        'system': {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent
        }
    })
```

---

## 🎉 ¡Instalación Completada!

Si has seguido esta guía, deberías tener el **Ecosistema de Emprendimiento** funcionando correctamente. 

### Próximos Pasos

1. **Configurar integraciones externas** (Google Calendar, SendGrid, etc.)
2. **Personalizar la aplicación** según tus necesidades
3. **Configurar backups automáticos**
4. **Implementar monitoreo avanzado**
5. **Revisar la documentación de usuario**

### Soporte

Si encuentras problemas durante la instalación:

- 📧 **Email**: soporte-tecnico@ecosistema-emprendimiento.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/tu-org/ecosistema-emprendimiento/issues)
- 💬 **Discord**: [Comunidad de Desarrolladores](https://discord.gg/ecosistema-dev)

¡Bienvenido al ecosistema! 🚀